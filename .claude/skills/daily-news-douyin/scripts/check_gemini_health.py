#!/usr/bin/env python3
"""Gemini 登录态健康检查（daily-news-douyin Step 0⑤）.

真开 Gemini 页面查模型菜单，而不是只查代理连通——账号退出后 Clash 代理依旧全通、
页面也能开，但模型菜单里 Pro 全 disabled=true，直到生图才全挂（2026-08-15 实测教训）。

判定信号（任一命中 → FAIL，exit 2）：
  ① 页头 OneGoogleBar 出现「登录 / sign in」
  ② 正文含「登录即可使用所有模型」
  ③ 模型菜单里 Pro 条目存在且全部 disabled

每次运行先 Page.reload(ignoreCache) 强刷：登录恢复后已开标签仍是旧态，不刷会误报。

退出码：0 = 健康（或仅警告）  2 = 登录态异常  3 = 探测本身失败（ego-browser/DOM 问题）
exit 2/3 自动发飞书告警。结果 JSON 落 /tmp/gemini_health.json 供失败日报引用。
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

# scripts/ → daily-news-douyin → skills → .claude → 项目根
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
RESULT_PATH = "/tmp/gemini_health.json"

# ego-browser nodejs 程序：探测登录态 + 模型菜单。
# 选择器/状态机沿用 longform-visual-notes SKILL.md 已实测的写法。
# 末尾无论成败都 completeTaskSpace(keep:false) 自关，不泄漏 task space / tab。
JS = r"""
const task = await useOrCreateTaskSpace('gemini-health-check')
let result = { err: null }
let probe = null, menu = null
try {
await openOrReuseTab('https://gemini.google.com/app', { wait: true, timeout: 30 })
await wait(2)
// 强刷：登录态变化后旧标签仍是旧态（2026-08-15 实测，登录已生效但菜单还 disabled）
await cdp('Page.reload', { ignoreCache: true })
// 等就绪：①代理慢时 reload 后 document.body 可能还是 null；②readyState=complete 后
// Angular 渲染极慢——实测模式选择器按钮要 1 分钟以上才出现（主体按钮先出，它最后出）；
// ③reload 拉满带宽时主线程被阻塞，Runtime.evaluate 会挂到超时——必须 try/catch，别让
// 单次 evaluate 炸掉整个探测。就绪信号 = 模式按钮出现，上限 120s。
let readyAfter = -1
for (let i = 0; i < 60; i++) {
  let rd = null, btn = false
  try { rd = await js('document.readyState + "|" + (document.body ? "body" : "nobody")') } catch (e) { await wait(2); continue }
  if (rd === 'complete|body') {
    try { btn = await js('!!document.querySelector(\'button[aria-label^="打开模式选择器"], [data-test-id="bard-mode-menu-button"]\')') } catch (e) { await wait(2); continue }
    if (btn) { readyAfter = i; break }
  }
  await wait(1)
}
cliLog('mode button ready at: ' + readyAfter + 's (loop sec)')
await wait(1)

probe = await js(String.raw`(() => {
  const bar = document.querySelector('div.boqOnegoogleliteOgbOneGoogleBar');
  const barText = ((bar && bar.innerText) || '').trim();
  const bodyText = ((document.body && document.body.innerText) || '');
  // aria-label 是动态拼接的「打开模式选择器，当前模式为"Pro"」（2026-08-15 实测），必须前缀匹配
  const modeBtn = document.querySelector('button[aria-label^="打开模式选择器"], [data-test-id="bard-mode-menu-button"]');
  return {
    barShowsLogin: bar ? /登录|sign in/i.test(barText) : false,
    loginPromptVisible: /登录即可使用所有模型|sign in to use all models/i.test(bodyText),
    modeLabel: modeBtn ? (modeBtn.getAttribute('aria-label') || '') : '',
    barText: barText.slice(0, 80),
  };
})()`)

menu = { opened: false };
const opened = await js(String.raw`(() => {
  const sels = ['[data-test-id="bard-mode-menu-button"]',
                'button[aria-label^="打开模式选择器"]',
                'button[aria-label*="mode selector" i]',
                'button.mat-mdc-menu-trigger.input-area-switch'];
  let b = null;
  for (const s of sels) { try { b = document.querySelector(s); } catch (e) {} if (b) break; }
  if (!b) return { ok: false };
  b.click(); return { ok: true };
})()`)
menu.opened = !!(opened && opened.ok)
if (menu.opened) {
  await wait(0.8)
  menu.items = await js(String.raw`(() => {
    const els = [...document.querySelectorAll('gem-menu-item, [data-test-id^="bard-mode-option"], [role="menuitem"], [role="menuitemradio"]')]
      .filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
    const seen = new Set(); const out = [];
    for (const el of els) {
      const label = (((el.querySelector('.label') || {}).textContent) || el.textContent || '')
        .trim().replace(/\s+/g, ' ').slice(0, 40);
      if (!label || seen.has(label)) continue;
      seen.add(label);
      const disabled = el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled')
        || /\bdisabled\b/i.test(el.className || '');
      out.push({ label, disabled });
    }
    return out;
  })()`)
  await pressKey('Escape').catch(() => {})
}

} catch (e) {
  result.err = String(e && e.message || e)
}
// 自清理：无论探测成败，用完即关（close 等价于关掉该 space 的全部 tab）
let closed = null
try {
  closed = await completeTaskSpace(task.id, { keep: false })
} catch (e) {
  closed = { done: false, error: String(e && e.message || e) }
}
cliLog('GEMINI_HEALTH_JSON: ' + JSON.stringify({ probe: probe || null, menu: menu || null, err: result.err, closed: closed }))
"""


def find_ego_browser():
    ego = shutil.which("ego-browser")
    if ego:
        return ego
    for p in (os.path.expanduser("~/.local/bin/ego-browser"),
              "/usr/local/bin/ego-browser", "/opt/homebrew/bin/ego-browser"):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def _direct_opener():
    """直连(不走系统代理) + 补 CA 的 opener（沿用 await_approval.py 的双坑修法）."""
    ctx = ssl.create_default_context()
    ca_candidates = []
    try:
        import certifi
        ca_candidates.append(certifi.where())
    except Exception:
        pass
    ca_candidates += ["/etc/ssl/cert.pem", "/usr/local/etc/openssl@3/cert.pem",
                      "/usr/local/etc/ca-bundle.crt", "/opt/homebrew/etc/openssl@3/cert.pem"]
    for ca in ca_candidates:
        if ca and os.path.isfile(ca):
            try:
                ctx.load_verify_locations(cafile=ca)
                break
            except Exception:
                continue
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=ctx))


def feishu_sign(secret, timestamp):
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def send_feishu_text(webhook, secret, text):
    body = {"msg_type": "text", "content": {"text": text}}
    if secret:
        ts = str(int(time.time()))
        body["timestamp"] = ts
        body["sign"] = feishu_sign(secret, ts)
    req = urllib.request.Request(webhook, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with _direct_opener().open(req, timeout=15) as resp:
            resp_body = resp.read().decode("utf-8", "replace")
        try:
            payload = json.loads(resp_body)
        except ValueError:
            payload = {}
        code = payload.get("code", payload.get("StatusCode", -1)) if isinstance(payload, dict) else -1
        return (code in (0, "0")), resp_body
    except Exception as e:
        return False, repr(e)


def judge(res):
    """返回 (fails, warnings)。fails 非空 → exit 2。"""
    fails, warnings = [], []
    probe = res.get("probe") or {}
    menu = res.get("menu") or {}
    if probe.get("barShowsLogin"):
        fails.append("页头显示「登录」按钮（Google 账号已退出）")
    if probe.get("loginPromptVisible"):
        fails.append("页面出现「登录即可使用所有模型」")
    items = menu.get("items") or []
    pro = [i for i in items
           if re.search(r"pro", i.get("label", ""), re.I)
           and not re.search(r"flash|lite|think|扩展", i.get("label", ""), re.I)]
    if menu.get("opened"):
        if pro and all(i.get("disabled") for i in pro):
            fails.append("模型菜单 Pro 条目全部 disabled=true（账号退出典型信号）")
        elif not items:
            fails.append("模型菜单已打开但读不到条目（DOM 可能漂移）")
        elif not pro:
            warnings.append("模型菜单无 Pro 条目，账号可能被限 Flash-Lite（生图会挂）")
    elif probe.get("modeLabel"):
        # 菜单没开成但按钮 aria 自带当前模式：作佐证，不作硬判据
        ml = probe["modeLabel"]
        if re.search(r"flash-?lite", ml, re.I):
            warnings.append(f"当前模式为 Flash-Lite（{ml}），生图会挂，Step 4 需切 Pro")
    else:
        warnings.append("无模型切换器 UI，未判 Pro（Step 4 生图兜底）")
    return fails, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.expanduser(
        "~/.config/douyin-ego-publish/config.json"))
    ap.add_argument("--timeout", type=int, default=240, help="ego-browser 整体超时(s)")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    ego = find_ego_browser()
    if not ego:
        print("❌ 找不到 ego-browser 可执行文件")
        sys.exit(3)

    try:
        p = subprocess.run([ego, "nodejs"], input=JS, capture_output=True,
                           text=True, timeout=args.timeout, cwd=PROJ)
        out = (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        print(f"❌ ego-browser 探测超时（>{args.timeout}s）")
        sys.exit(3)

    m = re.search(r"GEMINI_HEALTH_JSON:\s*(\{.*\})", out)
    if p.returncode != 0 or not m:
        print(f"❌ ego-browser 探测失败 rc={p.returncode}，输出尾部:\n{out[-600:]}")
        sys.exit(3)
    res = json.loads(m.group(1))
    if res.get("err") or not res.get("probe"):
        print(f"❌ 探测异常: {res.get('err') or 'probe 为空'}")
        sys.exit(3)
    closed = res.get("closed")
    if not (closed and closed.get("done")):
        print(f"⚠️ task space 未正常关闭: {json.dumps(closed, ensure_ascii=False)}")

    fails, warnings = judge(res)
    result = {"ts": time.strftime("%F %T"), "fails": fails, "warnings": warnings,
              "probe": res.get("probe"), "menu": res.get("menu")}
    with open(RESULT_PATH, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if fails:
        print("❌ Gemini 登录态异常：")
        for x in fails:
            print(f"   - {x}")
        print(f"   详情: {RESULT_PATH}")
        if not args.no_notify:
            notify(args.config, "登录态异常", fails)
        sys.exit(2)
    for x in warnings:
        print(f"⚠️ {x}")
    print("✅ Gemini 登录态健康（Pro 可用）")
    sys.exit(0)


def notify(config_path, headline, fails):
    try:
        cfg = json.load(open(config_path))
    except Exception as e:
        print(f"⚠️ 飞书通知跳过：读配置失败 {e!r}")
        return
    webhook = cfg.get("feishu_webhook")
    if not webhook:
        print("⚠️ 飞书通知跳过：config.json 缺 feishu_webhook")
        return
    text = ("🚨 daily-news-douyin 前置自检失败：Gemini " + headline + "\n"
            + "\n".join(f"· {x}" for x in fails)
            + "\n今日流水线已中止（未进入生图/发布）。"
            "\n修法：打开 ego lite → 登录 Google 账号 → 重跑 "
            "check_gemini_health.py 确认通过 → 手动补跑 run_daily.sh")
    ok, info = send_feishu_text(webhook, cfg.get("feishu_secret"), text)
    print(("📨 飞书告警已发" if ok else "⚠️ 飞书告警发送失败: ") + f" {info[:120]}")


if __name__ == "__main__":
    main()
