#!/usr/bin/env python3
"""流水线失败飞书告警（2026-08-26 加，8/25 两阶段全挂无感知的教训）。

run_daily.sh 在关键失败点调用：两阶段 claude 全 exit≠0 / 审批门没起来。
与 await_approval.py 同一套 webhook + 加签 + 直连 opener（绕 Clash MITM），
但只发纯通知卡片（红色 header，无按钮），不起服务不开隧道。

用法：
  python3 send_feishu_alert.py --reason "两阶段全挂" \
      [--log ~/daily-news-douyin/logs/daily-2026-08-25.log] [--extra "..."]

永远 exit 0 —— 告警失败不能反过来阻断流水线收尾。
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

CONFIG_PATH = os.path.expanduser("~/.config/douyin-ego-publish/config.json")


def _direct_opener():
    """与 await_approval.py 相同：空 ProxyHandler 强制直连 + 系统 CA。

    坑来自实战：Clash 系统代理会 MITM HTTPS（python 报证书错误），
    python.org 3.9 自带 CA 不全。详见 memory「Python HTTPS 的 SSL 双坑」。
    """
    ctx = ssl.create_default_context()
    ca_candidates = []
    try:
        import certifi
        ca_candidates.append(certifi.where())
    except Exception:
        pass
    ca_candidates += [
        "/etc/ssl/cert.pem",  # macOS 系统 CA（钥匙串导出）
        "/usr/local/etc/openssl@3/cert.pem", "/usr/local/etc/ca-bundle.crt",
        "/opt/homebrew/etc/openssl@3/cert.pem",
    ]
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
    """飞书自定义机器人加签：HMAC-SHA256(timestamp\\nsecret) 的 base64。"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def tail(path, max_lines=12, max_bytes=2000):
    """取日志尾部摘要（丢给卡片，帮一眼定位失败点）。"""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            chunk = f.read().decode("utf-8", "replace")
        lines = [l for l in chunk.splitlines() if l.strip()]
        return "\n".join(lines[-max_lines:])
    except Exception as e:
        return f"（日志读取失败：{e}）"


def send_alert(webhook, secret, reason, log_path, extra):
    md = (
        f"🚨 **{reason}**\n\n"
        f"**日期**：{time.strftime('%Y-%m-%d %H:%M')}\n"
        f"**补跑**：bash ~/daily-news-douyin/run_daily.sh"
    )
    if extra:
        md += f"\n**备注**：{extra}"
    if log_path:
        md += f"\n\n---\n**日志尾部**（`{log_path}`）：\n```\n{tail(log_path)}\n```"

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🚨 每日流水线失败告警"},
            "template": "red",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": md}},
            {"tag": "note", "elements": [
                {"tag": "plain_text",
                 "content": "此卡片为纯通知，无需操作；按需手动补跑或看日志排查。"}
            ]},
        ],
    }
    body = {"msg_type": "interactive", "card": card}
    if secret:
        ts = str(int(time.time()))
        body["timestamp"] = ts
        body["sign"] = feishu_sign(secret, ts)

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(webhook, data=data,
                                headers={"Content-Type": "application/json"})
    try:
        with _direct_opener().open(req, timeout=15) as resp:
            resp_body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8','replace')}"
    except Exception as e:
        return False, repr(e)
    try:
        rj = json.loads(resp_body)
        code = rj.get("StatusCode", rj.get("code"))
        if code in (0, "0"):
            return True, resp_body
        return False, resp_body
    except ValueError:
        return False, resp_body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reason", required=True, help="告警原因（卡片标题行）")
    ap.add_argument("--log", default="", help="日志路径，卡片附尾部摘要")
    ap.add_argument("--extra", default="", help="额外备注")
    args = ap.parse_args()

    try:
        cfg = json.load(open(CONFIG_PATH))
    except Exception as e:
        print(f"❌ 读配置失败 {CONFIG_PATH}: {e}")
        return 0  # 永远 0
    webhook = cfg.get("feishu_webhook")
    if not webhook:
        print("❌ config.json 缺 feishu_webhook，跳过告警")
        return 0

    ok, info = send_alert(webhook, cfg.get("feishu_secret") or "",
                          args.reason, args.log, args.extra)
    print(("✅ 飞书告警已发" if ok else "❌ 飞书告警失败") + f": {info}")
    return 0  # 永远 0，告警失败不阻断流水线


if __name__ == "__main__":
    sys.exit(main())
