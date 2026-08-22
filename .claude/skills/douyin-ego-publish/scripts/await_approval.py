#!/usr/bin/env python3
# await_approval.py — 飞书审批门：临时隧道 + 卡片 + 阻塞等待 Daniel 确认
#
# 流程：起本地 HTTP 回调服务 → 起 cloudflared 临时隧道拿公网 URL →
#       向飞书机器人发带「确认发布/取消」按钮的卡片(按钮 open_url 指向隧道) →
#       阻塞轮询等待点击 → 返回 APPROVED/REJECTED/TIMEOUT。
# 依赖：仅 Python 标准库 + PATH 上的 cloudflared。无需 pip、无需账号。
#
# 用法见同目录 ../SKILL.md 的 Step 7。最后一行 stdout 形如 RESULT=APPROVED。

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RESULT_FILE_PREFIX = "/tmp/douyin_approval"
# 守护化状态文件（--detach 模式）：current=活门登记，result=终态（含 KILLED）
CURRENT_FILE = "/tmp/douyin_approval_current.json"
RESULT_FILE = "/tmp/douyin_approval_result.json"

APPROVE_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>已确认</title>
<style>body{font-family:-apple-system,sans-serif;display:flex;align-items:center;
justify-content:center;height:100vh;margin:0;background:#f0fdf4;color:#166534}
.c{text-align:center}h1{font-size:48px;margin:8px 0}p{color:#15803d}</style></head>
<body><div class="c"><h1>✅</h1><h2>已确认发布</h2><p>Claude 正在自动点「发布」，可关闭此页面。</p>
</div></body></html>"""

REJECT_HTML = APPROVE_HTML.replace("f0fdf4", "fef2f2").replace("166534", "991b1b") \
    .replace("15803d", "b91c1c").replace("✅", "🛑").replace("已确认发布", "已取消").replace(
        "Claude 正在自动点「发布」，可关闭此页面。", "已保留草稿，不会发布。可关闭此页面。")


class State:
    def __init__(self, token):
        self.token = token
        self.result = None  # None | 'APPROVED' | 'REJECTED'
        self.screenshot = None
        self.lock = threading.Lock()


def _direct_opener():
    """直连(不走系统代理) + 补 CA 证书包 的 opener。

    python.org 3.9 on mac 默认 cafile=None（缺 CA），且本机 Clash 设了系统代理会做
    HTTPS MITM（自签 CA）。两坑合起来让飞书 webhook POST 报 CERTIFICATE_VERIFY_FAILED。
    这里：①空 ProxyHandler 强制直连绕过系统代理；②加载系统 CA(/etc/ssl/cert.pem)补全证书。
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
            # /approve?token=T  /reject?token=T  /preview/T/<name>  /healthz
            parsed = self.path.split("?", 1)[0]
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            token_q = dict(p.split("=", 1) for p in qs.split("&") if "=" in p).get("token", "")

            if parsed == "/healthz":
                return self._send(200, b"ok", "text/plain")
            if parsed.startswith("/approve") and token_q == state.token:
                with state.lock:
                    state.result = "APPROVED"
                return self._send(200, APPROVE_HTML.encode())
            if parsed.startswith("/reject") and token_q == state.token:
                with state.lock:
                    state.result = "REJECTED"
                return self._send(200, REJECT_HTML.encode())
            if parsed.startswith("/preview/"):
                # /preview/<token>/<filename>
                parts = parsed.split("/")
                if len(parts) >= 4 and parts[2] == state.token:
                    fname = os.path.basename(parts[3])
                    if state.screenshot and os.path.basename(state.screenshot) == fname:
                        try:
                            with open(state.screenshot, "rb") as f:
                                return self._send(200, f.read(), "image/png")
                        except OSError:
                            pass
                return self._send(404, b"not found", "text/plain")
            return self._send(404, b"not found", "text/plain")

    return Handler


def free_port(preferred):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", preferred))
        s.close()
        return preferred
    except OSError:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        return p


def start_server(port, state):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def start_tunnel(port):
    r"""起 cloudflared 临时隧道，返回 (proc, public_url)。

    ⚠️ 2026-08-22 坑：quick tunnel 的随机子域形如 dreams-fork-permit-onion.trycloudflare.com
    （≥3 个词），但输出流里可能先出现 api.trycloudflare.com 等官方域（版本信息/错误提示行）。
    旧正则 [a-z0-9-]+\.trycloudflare\.com 谁先出现匹配谁，曾截胡拿到 api. 域名——
    卡片按钮指到 Cloudflare API 上，Daniel 点了必报错。收紧为：
    ① 优先匹配横幅行 "Visit it at ... https://xxx.trycloudflare.com"（quick tunnel 真实 URL 唯一来源）
    ② 兜底正则要求子域为多词随机形态（\w+-\w+-\w+ 起步），排除 api/www/dashboard 等短官方域
    """
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    # trycloudflare URL 通常在 3~10s 内出现在输出里
    deadline = time.time() + 60
    buf = ""
    url = None
    banner_re = re.compile(r"Visit it at.*?(https://[a-z0-9-]+\.trycloudflare\.com)", re.S)
    # 多词随机子域（dreams-fork-permit-onion 式，≥2 个连字符词段）；api/www 等单词官方域不匹配
    random_re = re.compile(r"https://(?:[a-z0-9]+-){2,}[a-z0-9]+\.trycloudflare\.com")
    while time.time() < deadline:
        line = proc.stdout.readline()
        if line:
            buf += line
            m = banner_re.search(buf) or random_re.search(buf)
            if m:
                url = m.group(1)
                break
        elif proc.poll() is not None:
            break
        else:
            time.sleep(0.3)
    if not url:
        try:
            proc.kill()
        except Exception:
            pass
        raise RuntimeError("cloudflared 隧道未在 60s 内给出公网 URL。输出:\n" + buf[-800:])
    return proc, url


def feishu_sign(secret, timestamp):
    """飞书自定义机器人加签：HMAC-SHA256(timestamp\nsecret) 的 base64。"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def send_feishu_card(webhook, secret, fields, tunnel, token, screenshot_name):
    """发交互卡片。按钮用 open_url 指向隧道回调，点击即一次 GET。"""
    preview_link = ""
    if screenshot_name:
        preview_link = f"\n[📷 查看草稿预览截图]({tunnel}/preview/{token}/{screenshot_name})"
    buttons_url = f"{tunnel}/approve?token={token}"
    cancel_url = f"{tunnel}/reject?token={token}"

    md = (
        "📝 **抖音发布待确认**\n\n"
        f"**类型**：{fields.get('type','')}\n"
        f"**标题**：{fields.get('title','（无）')}\n"
        f"**描述**：{fields.get('desc','（无）')}\n"
        f"**封面**：{fields.get('cover','（无）')}\n"
        f"**AIGC声明**：{fields.get('aigc','已勾选「内容由AI生成」')}\n"
        f"**状态**：已存草稿，等待你确认是否发布"
        f"{preview_link}"
    )

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🎬 抖音发布待审批"},
            "template": "orange",
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": md}},
            {"tag": "hr"},
            {"tag": "note", "elements": [
                {"tag": "plain_text",
                 "content": "点「确认发布」后 Claude 会自动点发布；超时或「取消」则保留草稿不发。"}
            ]},
            {"tag": "action", "actions": [
                {"tag": "button", "text": {"tag": "plain_text", "content": "✅ 确认发布"},
                 "type": "primary", "url": buttons_url},
                {"tag": "button", "text": {"tag": "plain_text", "content": "❌ 取消"},
                 "type": "danger", "url": cancel_url},
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
    # 飞书成功返回 {"StatusCode":0,...} 或 {"code":0,...}；解析 JSON 取状态码最稳
    try:
        rj = json.loads(resp_body)
        code = rj.get("StatusCode", rj.get("code"))
        if code in (0, "0"):
            return True, resp_body
        return False, resp_body
    except ValueError:
        # 非 JSON 响应，保守判失败
        return False, resp_body


def _write_json_atomic(path, obj):
    """原子写 JSON（tmp+rename），防读方读到半截文件。"""
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _write_result(token, result, extra=None):
    """终态落盘到固定路径（RESULT_FILE）+ token 文件（保留旧排查习惯）。"""
    payload = {"result": result, "token": token, "ts": time.strftime("%F %T")}
    if extra:
        payload.update(extra)
    try:
        _write_json_atomic(RESULT_FILE, payload)
        _write_json_atomic(f"{RESULT_FILE_PREFIX}_{token}.json", payload)
    except OSError:
        pass


def _clear_current():
    try:
        os.remove(CURRENT_FILE)
    except OSError:
        pass


def _detach():
    """双 fork + setsid 守护化：脱离 claude/shell 的进程树与 stdout 管道。

    2026-08-22 事故根因：审批门以前作为 claude 的后台 Bash 任务跑，claude -p
    单回合结束（end_turn）即退出 → 审批脚本成孤儿 → 被 run_daily 兜底清理杀掉
    → 隧道死 → Daniel 点飞书「确认发布」打到死 URL 报错。
    守护化后审批门生命周期只由自己的 timeout 决定（默认 7200s），claude 死活无关。
    """
    if os.fork() > 0:
        os._exit(0)          # 原 shell 立即返回，孙进程独立
    os.setsid()
    if os.fork() > 0:
        os._exit(0)          # 二次 fork：彻底断开会话首进程（防重获 tty）
    # 守护进程不持有任何终端/管道；stdout/stderr 丢弃（终态已落盘 RESULT_FILE）
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    if devnull > 2:
        os.close(devnull)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.expanduser("~/.config/douyin-ego-publish/config.json"))
    ap.add_argument("--screenshot", help="草稿预览截图本地路径")
    ap.add_argument("--type", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--desc", default="")
    ap.add_argument("--cover", default="")
    ap.add_argument("--aigc", default="已勾选「内容由AI生成」")
    ap.add_argument("--timeout", type=int, default=None,
                    help="覆盖 config 的 approval_timeout_sec（测试用）")
    ap.add_argument("--detach", action="store_true",
                    help="守护化运行：脱离调用方进程树（claude 死活不影响），"
                         "终态写 " + RESULT_FILE + "（定时流水线用；手动调试不加）")
    args = ap.parse_args()

    # 读配置
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
    timeout = int(cfg.get("approval_timeout_sec", 540))
    if args.timeout is not None:
        timeout = args.timeout
    if not webhook:
        print("❌ config.json 缺 feishu_webhook。")
        print("RESULT=NOCONFIG")
        _write_result("noconfig", "NOCONFIG")
        return
    if not shutil_which("cloudflared"):
        print("❌ 未找到 cloudflared。请先运行: brew install cloudflared")
        print("RESULT=NO_CF")
        _write_result("no_cf", "NO_CF")
        return

    # —— 守护化分叉点：之后本进程已脱离调用方进程树（见 _detach 注释）——
    if args.detach:
        _detach()
    my_pid = os.getpid()

    # 防叠门：若上一扇门还活着（pid 存活且未写终态），先 TERM 它再开门
    # （同轮流水线残留的旧门会占着 8848 端口和一张过期卡片，必须让位）
    try:
        with open(CURRENT_FILE) as f:
            prev = json.load(f)
        prev_pid = int(prev.get("pid", 0))
        if prev_pid and prev_pid != my_pid and _alive(prev_pid):
            try:
                os.kill(prev_pid, signal.SIGTERM)
                for _ in range(20):
                    if not _alive(prev_pid):
                        break
                    time.sleep(0.2)
            except OSError:
                pass
    except (OSError, ValueError):
        pass
    _clear_current()

    # SIGTERM（超期收割/新门替位）也要留终态，否则等待方永远等不到文件
    def _on_term(signum, frame):
        _write_result(token_holder[0], "KILLED",
                      {"why": "SIGTERM", "ts": time.strftime("%F %T")})
        _clear_current()
        os._exit(0)
    signal.signal(signal.SIGTERM, _on_term)
    token_holder = [""]   # token 生成后回填；闭包按引用取

    token = hashlib.sha1(os.urandom(24)).hexdigest()[:20]
    token_holder[0] = token
    state = State(token)
    state.screenshot = args.screenshot
    shot_name = os.path.basename(args.screenshot) if args.screenshot else None
    # 活门登记：cleanup_resources.py 与等待方据此识别「这扇门还活着，别杀/再等」
    _write_json_atomic(CURRENT_FILE, {
        "pid": my_pid, "token": token, "started": time.strftime("%F %T"),
        "timeout": timeout, "title": args.title,
    })

    # 1) 起本地回调服务
    port = free_port(port)
    httpd = start_server(port, state)

    cf_proc = None
    try:
        # 2) 起隧道
        print(f"⏳ 正在启动 cloudflared 临时隧道 (localhost:{port}) ...", flush=True)
        cf_proc, tunnel = start_tunnel(port)
        print(f"🌐 隧道已就绪: {tunnel}", flush=True)

        # 3) 发飞书卡片
        fields = {"type": args.type, "title": args.title, "desc": args.desc,
                  "cover": args.cover, "aigc": args.aigc}
        ok, info = send_feishu_card(webhook, secret, fields, tunnel, token, shot_name)
        if not ok:
            print(f"❌ 飞书卡片发送失败: {info}", flush=True)
            print("RESULT=SEND_FAILED")
            _write_result(token, "SEND_FAILED", {"info": str(info)[:300]})
            return
        print(f"📨 审批卡片已发到飞书，等待 Daniel 点击（超时 {timeout}s）...", flush=True)

        # 4) 阻塞轮询 + 心跳：current 文件每 60s 刷新 ts，
        #    cleanup 判「活门」看 pid 存活即可，ts 心跳供人工排查
        deadline = time.time() + timeout
        last_beat = 0.0
        while time.time() < deadline:
            with state.lock:
                if state.result:
                    break
            if time.time() - last_beat > 60:
                last_beat = time.time()
                _write_json_atomic(CURRENT_FILE, {
                    "pid": my_pid, "token": token,
                    "started": time.strftime("%F %T"),
                    "beat": time.strftime("%F %T"),
                    "timeout": timeout, "title": args.title,
                })
            time.sleep(2)

        with state.lock:
            result = state.result or "TIMEOUT"

        # 5) 终态落盘：固定路径（等待方/清理方读）+ token 文件（排查习惯）
        _write_result(token, result, {"title": args.title})

        if result == "APPROVED":
            print("✅ 已收到确认，开始发布。", flush=True)
        elif result == "REJECTED":
            print("🛑 已取消，保留草稿不发布。", flush=True)
        else:
            print(f"⏰ 等待超时({timeout}s)，保留草稿不发布。", flush=True)
        print(f"RESULT={result}")
    finally:
        _clear_current()
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


def shutil_which(cmd):
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, cmd)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


if __name__ == "__main__":
    main()
