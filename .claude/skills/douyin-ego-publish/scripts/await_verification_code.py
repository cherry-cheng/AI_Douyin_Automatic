#!/usr/bin/env python3
# await_verification_code.py — 验证码中继：发布后抖音弹验证码时，把 Daniel 的验证码回传给 Claude
#
# ⚠️ 与 await_approval.py 完全独立、不同时触发：
#   - await_approval.py   ：草稿存好 → 飞书卡片「确认发布」→ Claude 点发布。
#   - 本脚本 await_verification_code.py ：Claude 点了发布后抖音弹出短信验证码 →
#     发【另一条】飞书消息 → Daniel 把收到的短信验证码填进表单 → POST 回本地 →
#     Claude 拿到后填进抖音验证码框、点确认、继续发布。
#
# 流程：起本地 HTTP 服务(服务一个验证码输入表单页) → cloudflared 临时隧道拿公网 URL →
#       向飞书机器人发带「📝 输入验证码」按钮的卡片(按钮 open_url 指向表单) →
#       阻塞轮询等 Daniel 提交 → 返回 RESULT=CODE_RECEIVED CODE=xxxx。
# 依赖：仅 Python 标准库 + PATH 上的 cloudflared。复用 await_approval 的隧道/直连 opener/加签函数。
#
# 用法见同目录 ../SKILL.md 的 Step 8「验证码中继」。stdout 最后一行形如 RESULT=CODE_RECEIVED，
# 验证码值在同一块输出的 `CODE=xxxx` 行。

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 复用审批脚本的通用件（隧道、直连 opener、加签、cloudflared 探测、端口分配）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from await_approval import (  # noqa: E402
    _direct_opener, start_tunnel, free_port, feishu_sign, shutil_which,
)

RESULT_FILE_PREFIX = "/tmp/douyin_verify"

# 验证码输入表单页（移动端友好）。__HINT__/__TOKEN__ 占位
CODE_FORM_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>输入验证码</title>
<style>body{{font-family:-apple-system,sans-serif;display:flex;align-items:center;
justify-content:center;min-height:100vh;margin:0;background:#fff7ed;color:#7c2d12;padding:16px}}
.c{{text-align:center;max-width:360px;width:100%}}h2{{margin:0 0 6px;font-size:22px}}
.sub{{color:#9a3412;margin:0 0 18px;font-size:14px;line-height:1.5}}
input{{font-size:30px;letter-spacing:10px;text-align:center;width:100%;padding:14px;
border:2px solid #fdba74;border-radius:12px;box-sizing:border-box;background:#fff}}
button{{margin-top:14px;width:100%;padding:14px;font-size:18px;border:none;border-radius:12px;
background:#ea580c;color:#fff;font-weight:600}}button:active{{opacity:.85}}</style></head>
<body><div class="c"><h2>🔐 抖音验证码</h2>
<p class="sub">{hint}<br>请输入收到的短信验证码</p>
<form method="POST" action="/submit?token={token}">
<input name="code" type="text" inputmode="numeric" pattern="[0-9]{{4,8}}"
autocomplete="one-time-code" placeholder="验证码" required autofocus>
<button type="submit">提交验证码</button>
</form></div></body></html>"""

# 提交成功页
CODE_OK_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>已提交</title>
<style>body{{font-family:-apple-system,sans-serif;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0;background:#f0fdf4;color:#166534}}
.c{{text-align:center}}h1{{font-size:48px;margin:8px 0}}p{{color:#15803d}}</style></head>
<body><div class="c"><h1>✅</h1><h2>验证码已提交</h2>
<p>Claude 正在把验证码填入抖音，请勿重复提交。可关闭此页面。</p>
</div></body></html>"""

# 格式错误页（让 Daniel 重填）。{token} 复用同一 token
CODE_INVALID_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>重新输入</title>
<style>body{{font-family:-apple-system,sans-serif;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0;background:#fef2f2;color:#991b1b}}
.c{{text-align:center}}h1{{font-size:40px;margin:8px 0}}p{{color:#b91c1c}}
a{{display:inline-block;margin-top:16px;padding:12px 22px;background:#dc2626;color:#fff;
text-decoration:none;border-radius:10px}}</style></head>
<body><div class="c"><h1>⚠️</h1><p>验证码格式不对（应为 4-8 位数字）<br>请重新输入。</p>
<a href="/code?token={token}">返回重填</a></div></body></html>"""


class CodeState:
    def __init__(self, token):
        self.token = token
        self.code = None
        self.result = None  # None | 'CODE_RECEIVED'
        self.lock = threading.Lock()


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass  # 安静

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = self.path.split("?", 1)[0]
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            token_q = dict(p.split("=", 1) for p in qs.split("&") if "=" in p).get("token", "")

            if parsed == "/healthz":
                return self._send(200, b"ok", "text/plain")
            if parsed == "/code" and token_q == state.token:
                hint = getattr(state, "hint", "抖音发布触发了短信验证")
                return self._send(200, CODE_FORM_HTML.format(hint=hint, token=state.token).encode())
            return self._send(404, b"not found", "text/plain")

        def do_POST(self):
            parsed = self.path.split("?", 1)[0]
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            token_q = dict(p.split("=", 1) for p in qs.split("&") if "=" in p).get("token", "")

            if parsed == "/submit" and token_q == state.token:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8", "replace")
                params = dict(p.split("=", 1) for p in body.split("&") if "=" in p)
                raw = urllib.parse.unquote_plus(params.get("code", ""))
                code = re.sub(r"\D", "", raw)[:8]  # 只保留数字，最长 8 位
                if 4 <= len(code) <= 8:
                    with state.lock:
                        state.code = code
                        state.result = "CODE_RECEIVED"
                    return self._send(200, CODE_OK_HTML.encode())
                return self._send(200, CODE_INVALID_HTML.format(token=state.token).encode())
            return self._send(404, b"not found", "text/plain")

    return Handler


def start_server(port, state):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def send_feishu_code_card(webhook, secret, phone_hint, tunnel, token):
    """发验证码中继卡片。按钮 open_url 指向表单页，点击→填码→提交即一次 POST 回本地。"""
    form_url = f"{tunnel}/code?token={token}"
    md = (
        "🔐 **抖音发布需要验证码**\n\n"
        f"发布时触发了短信验证，**验证码已发送到手机 {phone_hint}**。\n\n"
        "请点击下方按钮，把收到的短信验证码填入 👇\n"
        "Claude 收到后会自动填入抖音并继续发布。"
    )
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🔐 抖音发布需要验证码"},
            "template": "red",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": md}},
            {"tag": "hr"},
            {"tag": "note", "elements": [
                {"tag": "plain_text",
                 "content": "短信有时效，请尽快填写；超时则 Claude 会保留草稿并通知你。"}
            ]},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "📝 输入验证码"},
                 "type": "primary", "url": form_url},
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
    opener = _direct_opener()
    try:
        with opener.open(req, timeout=15) as resp:
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
    ap.add_argument("--config", default=os.path.expanduser("~/.config/douyin-ego-publish/config.json"))
    ap.add_argument("--phone-hint", default="",
                    help="验证码发送到的手机提示，如「尾号 1234」。留空用默认文案")
    ap.add_argument("--timeout", type=int, default=None,
                    help="覆盖 config 的 verify_timeout_sec（默认 300s，贴合短信时效）")
    ap.add_argument("--local-only", action="store_true",
                    help="调试用：只起本地服务，不起隧道/不发飞书")
    args = ap.parse_args()

    cfg = {}
    try:
        with open(args.config) as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到配置文件 {args.config}。请先完成 references/feishu-setup.md。")
        print("RESULT=NOCONFIG")
        return
    webhook = cfg.get("feishu_webhook")
    secret = cfg.get("feishu_secret") or ""
    port = int(cfg.get("approval_port", 8848))
    timeout = int(cfg.get("verify_timeout_sec", 300))
    if args.timeout is not None:
        timeout = args.timeout
    if not args.local_only and not webhook:
        print("❌ config.json 缺 feishu_webhook。")
        print("RESULT=NOCONFIG")
        return
    if not args.local_only and not shutil_which("cloudflared"):
        print("❌ 未找到 cloudflared。请先运行: brew install cloudflared")
        print("RESULT=NO_CF")
        return

    import hashlib
    token = hashlib.sha1(os.urandom(24)).hexdigest()[:20]
    state = CodeState(token)
    state.hint = args.phone_hint or "抖音发布触发了短信验证"

    port = free_port(port)
    httpd = start_server(port, state)

    cf_proc = None
    try:
        if args.local_only:
            print(f"🔌 仅本地模式，表单页: http://127.0.0.1:{port}/code?token={token}", flush=True)
        else:
            print(f"⏳ 正在启动 cloudflared 临时隧道 (localhost:{port}) ...", flush=True)
            cf_proc, tunnel = start_tunnel(port)
            print(f"🌐 隧道已就绪: {tunnel}", flush=True)
            ok, info = send_feishu_code_card(webhook, secret, args.phone_hint, tunnel, token)
            if not ok:
                print(f"❌ 飞书卡片发送失败: {info}", flush=True)
                print("RESULT=SEND_FAILED")
                return
            print(f"📨 验证码卡片已发到飞书，等 Daniel 提交（超时 {timeout}s）...", flush=True)

        # 阻塞轮询
        deadline = time.time() + timeout
        while time.time() < deadline:
            with state.lock:
                if state.result:
                    break
            time.sleep(2)

        with state.lock:
            result = state.result or "TIMEOUT"
            code = state.code

        try:
            with open(f"{RESULT_FILE_PREFIX}_{token}.json", "w") as f:
                json.dump({"result": result, "token": token, "code": code},
                          f, ensure_ascii=False)
        except Exception:
            pass

        if result == "CODE_RECEIVED":
            print(f"✅ 收到验证码: {code}", flush=True)
            print("RESULT=CODE_RECEIVED")
            print(f"CODE={code}")
        else:
            print(f"⏰ 等待验证码超时({timeout}s)，保留草稿、转人工。", flush=True)
            print("RESULT=TIMEOUT")
    finally:
        try:
            httpd.shutdown()
        except Exception:
            pass
        if cf_proc:
            try:
                cf_proc.terminate()
                cf_proc.wait(timeout=5)
            except Exception:
                try:
                    cf_proc.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
