#!/usr/bin/env python3
"""daily-news-douyin 收尾资源清理（无论流水线成败都要跑）.

清理对象（只动流水线自己开的，别的不碰）：
  ① task space：只关本流水线名下的 agent-owned space——'visual notes'、
     'douyin publish'、'gemini-health-check'。user-owned（如 Daniel 手开的
     'douyin publish probe'）和 agentDelegatedToUser（审批门交接出去的）一律跳过。
  ② 孤儿进程（2026-08-22 重写）：await_approval.py 已守护化（--detach 双 fork，
     生命周期独立于 claude，见 await_approval.py _detach 注释）。清理策略：
     - 活门豁免：/tmp/douyin_approval_current.json 登记的 pid 存活且确是 await_approval
       → 不杀（它在等 Daniel 点飞书卡片），其 cloudflared 子进程一并保留
     - 未登记的 await_approval：etime > 3h15m（超审批窗 7200s+余量）判残留 → TERM；
       窗口内的不杀（可能刚 fork 还没登记，或正在正常服务）
     - await_verification_code.py 未守护化，沿用旧逻辑：父进程死 → TERM
     - cloudflared：父是活门 → 留；父死 → TERM；其余留（防误杀 Daniel 手动隧道）
     2026-08-22 事故教训：旧「孤儿即杀」在 claude 提前退出时把活着的审批门连同隧道杀掉，
     Daniel 点飞书「确认发布」打到死 URL 报错。
  ③ /tmp 残留：hot.json、douyin_draft_preview.png、gemini_health.json 等本流水线的临时文件。

结果 JSON 落 /tmp/cleanup_result.json 供日报引用。永远 exit 0（清理失败不阻断日报）。
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

# scripts/ → daily-news-douyin → skills → .claude → 项目根
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
RESULT_PATH = "/tmp/cleanup_result.json"

# 本流水线名下的 task space 名（见 SKILL.md 各 step）
PIPELINE_SPACES = {"visual notes", "douyin publish", "gemini-health-check"}

# 孤儿进程特征：命令行需同时命中 script 名与项目路径（防误杀其他项目的同名脚本）
ORPHAN_PATTERNS = [
    re.compile(r"await_approval\.py"),
    re.compile(r"await_verification_code\.py"),
]
# 守护化活门登记文件（await_approval.py --detach 模式维护）
APPROVAL_CURRENT = "/tmp/douyin_approval_current.json"
# 守护化审批门的最大合法寿命：审批窗 7200s + 15min 余量（超时守护进程应已自然退出）
APPROVAL_MAX_AGE_SEC = 7200 + 900
# cloudflared 只杀「无 controlling tty + 由 python 起的 quick tunnel」——
# 特征 = 命令行含 "tunnel --no-autoupdate --url http://127.0.0.1:PORT"
CF_PATTERN = re.compile(r"cloudflared.*tunnel.*--no-autoupdate\s+--url\s+http://127\.0\.0\.1:\d+")

# 本流水线在 /tmp 的落盘物
TMP_FILES = [
    "/tmp/hot.json",
    "/tmp/douyin_draft_preview.png",
    "/tmp/gemini_health.json",
    "/tmp/douyin_draft_*.png",   # await_verification_code 截图序列
]

# JS：关流水线名下的 agent-owned task space
JS_CLOSE_SPACES = r"""
const closed = [], skipped = [];
let spaces = [];
try { spaces = await listTaskSpaces() } catch (e) { cliLog('SPACES_ERR: ' + String(e)) }
for (const sp of spaces) {
  const target = PIPELINE_SPACES_JSON.find(n => n === sp.name || n === sp.taskId);
  if (!target) { skipped.push({ name: sp.name, why: 'not_pipeline' }); continue }
  if (sp.ownership !== 'agent') { skipped.push({ name: sp.name, why: 'ownership=' + sp.ownership }); continue }
  try {
    const r = await completeTaskSpace(sp.id, { keep: false })
    closed.push({ name: sp.name, done: !!(r && r.done) })
  } catch (e) {
    closed.push({ name: sp.name, done: false, error: String(e && e.message || e) })
  }
}
cliLog('CLEANUP_SPACES_JSON: ' + JSON.stringify({ closed, skipped }))
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


def run_js(ego, js, timeout):
    """注入常量后跑 ego-browser nodejs；失败返回 (False, tail_of_output)。

    必须 start_new_session（自成进程组）：subprocess.run 超时后只 kill 直接
    子进程，若 ego-browser 派生的孙进程还握着 stdout 管道，communicate() 会
    永远等不到 EOF——8/17 实测卡 23h，吞掉次日 8:00 的 launchd 触发。
    超时后 killpg 整组回收，管道随之关闭。
    """
    script = js.replace("PIPELINE_SPACES_JSON",
                        json.dumps(sorted(PIPELINE_SPACES)))
    p = subprocess.Popen([ego, "nodejs"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, cwd=PROJ, start_new_session=True)
    # 组长 pid 即 pgid。必须启动瞬间记下：组长自己先退出后 getpgid(pid) 会抛
    # ProcessLookupError，而进程组只要还有孙进程就活着（首轮修复实测踩过）。
    pgid = p.pid
    try:
        out, _ = p.communicate(input=script, timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            p.kill()
        p.communicate()   # 回收管道，防僵尸
        return False, "ego-browser 超时(已杀进程组)"
    return p.returncode == 0, out or ""


def close_pipeline_spaces(ego):
    ok, out = run_js(ego, JS_CLOSE_SPACES, timeout=120)
    m = re.search(r"CLEANUP_SPACES_JSON:\s*(\{.*\})", out)
    if not ok or not m:
        return None, out[-300:]
    return json.loads(m.group(1)), None


def ps_lines():
    p = subprocess.run(["ps", "-ax", "-o", "pid=,ppid=,command="],
                       capture_output=True, text=True)
    rows = []
    for line in p.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) == 3:
            rows.append({"pid": int(parts[0]), "ppid": int(parts[1]),
                         "cmd": parts[2]})
    return rows


def _proc_age_sec(cmd_pid, procs_by_pid):
    """ps etime 起步年份不可靠时退化 0；这里用 ps -o etime 解析。找不到返回 None。"""
    try:
        out = subprocess.run(["ps", "-o", "etime=", "-p", str(cmd_pid)],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return None
    if not out:
        return None
    # etime 形如 "MM:SS" / "HH:MM:SS" / "D-HH:MM:SS" / "D-HH:MM"
    days = 0
    parts = out.split("-")
    if len(parts) == 2:
        days = int(parts[0])
        out = parts[1]
    fields = [int(x) for x in out.split(":")]
    if len(fields) == 2:
        h, m, s = 0, fields[0], fields[1]
    else:
        h, m, s = fields[0], fields[1], fields[2]
    return days * 86400 + h * 3600 + m * 60 + s


def kill_orphans():
    """2026-08-22 重写：活门豁免 + etime 判残留。

    await_approval.py（守护化）：
      - current.json 登记的 pid 活着且命令行确是 await_approval → 豁免（活门）
      - 未登记的：etime > APPROVAL_MAX_AGE_SEC → 残留 TERM；否则不杀（窗口内）
    await_verification_code.py（未守护化）：父进程死 → TERM（旧逻辑）
    cloudflared：父活（含活门）→ 留；父死 → TERM
    """
    procs = ps_lines()
    by_pid = {p["pid"]: p for p in procs}
    me = os.getpid()
    killed, kept = [], []

    def alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    # —— 读取活门登记（await_approval --detach 维护）——
    gate_pids = set()
    try:
        with open(APPROVAL_CURRENT) as f:
            cur = json.load(f)
        gp = int(cur.get("pid", 0))
        # 双重校验：pid 活着 + python 直跑 await_approval（防过期文件误配新 pid / bash 包装误认）
        if gp and gp != me and alive(gp):
            cmd = by_pid.get(gp, {}).get("cmd", "")
            if re.search(r"await_approval\.py", cmd) and re.match(r"^(\S+/)?python3?\s", cmd):
                gate_pids.add(gp)
                kept.append({"pid": gp, "why": "active_approval_gate", "cmd": cmd[:120]})
            else:
                kept.append({"pid": gp, "why": "current.json pid 命令行不匹配，忽略", "cmd": cmd[:120]})
    except (OSError, ValueError):
        pass   # 无活门文件 = 没有活门，正常

    await_pids = set()
    for p in procs:
        if p["pid"] == me or p["pid"] == 1:
            continue
        # ⚠️ 只认「python 解释器直接跑脚本」的进程；bash -c / snapshot 包装命令里
        # 出现脚本名（历史命令回显）不算（2026-08-22 实测：shell-snapshot 的
        # bash -c 命令行含 await_approval 字样被当成了审批门）
        if not re.match(r"^(\S+/)?python3?\s", p["cmd"]):
            continue
        if any(rx.search(p["cmd"]) for rx in ORPHAN_PATTERNS):
            await_pids.add(p["pid"])

    cf_pids = set()
    for p in procs:
        if p["pid"] == me or p["pid"] == 1:
            continue
        if CF_PATTERN.search(p["cmd"]):
            cf_pids.add(p["pid"])

    term_awaits = set()
    for pid in await_pids:
        cmd = by_pid[pid]["cmd"]
        if pid in gate_pids:
            continue                      # 活门豁免
        if re.search(r"await_approval\.py", cmd):
            # 守护化审批门：只按寿命判残留
            age = _proc_age_sec(pid, by_pid)
            if age is not None and age > APPROVAL_MAX_AGE_SEC:
                term_awaits.add(pid)
                kept.append({"pid": pid, "why": "stale_gate>3h15m TERM", "cmd": cmd[:120]})
            else:
                kept.append({"pid": pid, "why": "gate_in_window", "cmd": cmd[:120]})
            continue
        # await_verification_code.py 等未守护化脚本：旧孤儿判定（父死即杀）
        ppid = by_pid[pid]["ppid"]
        if not alive(ppid) or ppid == 1:
            term_awaits.add(pid)

    for pid in term_awaits:
        try:
            os.kill(pid, signal.SIGTERM)
            killed.append({"pid": pid, "cmd": by_pid[pid]["cmd"][:120], "sig": "TERM"})
        except OSError as e:
            kept.append({"pid": pid, "why": f"kill_failed:{e}", "cmd": by_pid[pid]["cmd"][:120]})

    # cloudflared：父活 → 留给父的 finally；父死 → TERM（含父是被杀的孤儿脚本）
    for pid in cf_pids:
        ppid = by_pid[pid]["ppid"]
        if alive(ppid) and ppid != 1:
            kept.append({"pid": pid, "why": "parent_alive", "cmd": by_pid[pid]["cmd"][:120]})
        else:
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append({"pid": pid, "cmd": by_pid[pid]["cmd"][:120], "sig": "TERM(cfd)"})
            except OSError:
                pass

    return killed, kept


def clean_tmp():
    removed, kept = [], []
    for pat in TMP_FILES:
        import glob
        for f in glob.glob(pat):
            try:
                os.remove(f)
                removed.append(f)
            except OSError:
                kept.append(f)
    return removed, kept


def _alarm_handler(signum, frame):
    # 兜底硬上限：清理逻辑任何一个环节卡死都不许超过 10 分钟
    # （否则 launchd 下一次日历触发会被吞，见 run_js 注释）。
    print("⚠️ cleanup 整体超时(10min)，强制收尾退出")
    try:
        json.dump({"ts": time.strftime("%F %T"), "error": "overall_timeout_10min"},
                  open(RESULT_PATH, "w"), ensure_ascii=False)
    except OSError:
        pass
    sys.exit(0)   # 清理永远不算失败，不阻断日报


def main():
    signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(600)
    ego = find_ego_browser()
    spaces_result, spaces_err = (None, "ego-browser 未找到")
    if ego:
        spaces_result, spaces_err = close_pipeline_spaces(ego)

    killed, kept_procs = kill_orphans()
    removed_tmp, kept_tmp = clean_tmp()

    result = {
        "ts": time.strftime("%F %T"),
        "spaces": spaces_result or {"error": spaces_err},
        "killed_procs": killed,
        "kept_procs": kept_procs,
        "removed_tmp": removed_tmp,
        "kept_tmp": kept_tmp,
    }
    with open(RESULT_PATH, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 人读版摘要
    if spaces_result:
        closed = [c["name"] for c in spaces_result.get("closed", []) if c.get("done")]
        failed = [c for c in spaces_result.get("closed", []) if not c.get("done")]
        skipped = [s["name"] for s in spaces_result.get("skipped", [])]
        print(f"🧹 task space 关闭 {len(closed)} 个: {', '.join(closed) or '无'}" if closed
              else "🧹 task space: 无流水线名下 space 需关")
        if failed:
            print(f"⚠️ 关闭失败: {json.dumps(failed, ensure_ascii=False)}")
        if skipped:
            print(f"↩️ 跳过: {', '.join(skipped)}")
    else:
        print(f"⚠️ task space 清理未执行: {spaces_err}")
    if killed:
        for k in killed:
            print(f"🧹 杀孤儿进程 pid={k['pid']}: {k['cmd'][:80]}")
    if kept_procs:
        print(f"↩️ 保留进程 {len(kept_procs)} 个（非孤儿/父进程活着）")
    if removed_tmp:
        print(f"🧹 /tmp 清理 {len(removed_tmp)} 个文件")
    print(f"详情: {RESULT_PATH}")
    sys.exit(0)   # 清理永远不算失败，不阻断日报


if __name__ == "__main__":
    main()
