#!/bin/bash
# daily-news-douyin 定时入口（launchd 每日 8:00 触发）
# 注意：本脚本必须放在 ~/daily-news-douyin/（Documents 受 macOS TCC 保护，launchd 进程读不了）
# 手动补跑：bash ~/daily-news-douyin/run_daily.sh
#
# ── 2026-08-22 两阶段架构 ──
# 事故：8/22 claude -p 发完进度文本即 end_turn 退出，审批门（其后台 Bash 任务）
#       被本脚本兜底清理收割 → 隧道死 → Daniel 点飞书确认打到死 URL。
# 对策：
#   Phase 1  claude -p：跑流水线到「发审批卡片」为止。审批门用 --detach 守护化
#            （独立进程，claude 死活无关），claude 轮询 /tmp/douyin_approval_result.json。
#            claude 若顺利等到结果并完成发布+清理+日报，写 /tmp/daily_gate_done 标记。
#   Gate     shell 层等审批结果文件（claude 死活无关，最长等 timeout+余量）。
#   Phase 2  若 claude 已完成全部收尾（done 标记在）→ 直接跳过；
#            若 claude 中途死了（标记不在）→ 补跑一个 claude 会话消费审批结果：
#            APPROVED → 发布+清理+日报；REJECTED/TIMEOUT → 清理+日报（保草稿）。
#   兜底清理放最后：活门已被 cleanup 豁免（current.json），不会误杀。
PROJECT=/Users/plato/Documents/trae_projects/Trae_Agent_First_Project
RUNDIR=/Users/plato/daily-news-douyin
# launchd 的 PATH 只有 /usr/bin:/bin:/usr/sbin:/sbin，找不到 node（claude wrapper 依赖它）。
# 8/16 实测：不加这行，claude exit=127 "node: not found"，整轮 3 秒报废。
export PATH="$HOME/.local/node-v22.5.0-darwin-x64/bin:$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
LOGDIR="$RUNDIR/logs"
GATE_RESULT=/tmp/douyin_approval_result.json
GATE_CURRENT=/tmp/douyin_approval_current.json
GATE_DONE=/tmp/daily_gate_done
GATE_TIMEOUT=7200        # 审批窗，与 SKILL.md --timeout 7200 一致
mkdir -p "$LOGDIR" "$PROJECT/logs" "$PROJECT/reports" 2>/dev/null
LOG="$LOGDIR/daily-$(date +%F).log"
echo "=== daily-news-douyin start $(date) ===" >> "$LOG"

# 防重入：mkdir 原子锁（pgrep -f 会误匹配脚本自身路径，弃用）
LOCK="$LOGDIR/running.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  # 锁存在：>4h 视为陈锁（审批门 2h + Phase2 + 余量），破锁重跑
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +240 2>/dev/null)" ]; then
    echo "$(date) 发现陈锁(>4h)，破锁重跑" >> "$LOG"; rmdir "$LOCK" 2>/dev/null; mkdir "$LOCK" 2>/dev/null || exit 0
  else
    echo "$(date) 上一次运行尚未结束，跳过本次触发" >> "$LOG"
    exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# 清掉上一轮的审批状态文件（新一轮从干净状态开始）
rm -f "$GATE_RESULT" "$GATE_DONE"

# cd 失败（TCC/Full Disk Access 未授权）时明确记录，别让错误变模糊
if ! cd "$PROJECT" 2>>"$LOG"; then
  echo "$(date) ❌ 无法进入项目目录 $PROJECT —— launchd 进程缺 Documents 读权限。请给 /bin/bash 授 Full Disk Access（系统设置→隐私与安全性→完全磁盘访问权限）。" >> "$LOG"
  exit 1
fi

# ─────────── Phase 1：claude 跑流水线（到发卡为止 + 尽力等到结果收尾）───────────
~/.local/bin/claude -p "运行 daily-news-douyin 技能：完整执行每日新闻到抖音发布流水线。按 SKILL.md 顺序：环境自检→选稿→写文章→4张视觉笔记→抖音发布→资源清理(Step 6)→写日报到 reports/。内容自动起草不需要用户过目。
审批门新规（2026-08-22 起，必须遵守）：
1. await_approval.py 一律加 --detach 参数启动（守护化，命令立即返回，不阻塞不后台等待）。
2. 启动后轮询 /tmp/douyin_approval_result.json（每 30s 一次，最长 2.5h）读到 result 字段。
3. 读到 APPROVED → 发布 → 资源清理 → 写日报；REJECTED/TIMEOUT/KILLED → 保草稿 → 资源清理 → 写日报。
4. 全部收尾完成后：写标记文件 /tmp/daily_gate_done（内容=日期+结果）。
5. 若轮询 10 分钟 /tmp/douyin_approval_current.json 都不出现（门没起来），按发布失败处理，写日报说明。" \
  --permission-mode acceptEdits \
  --allowedTools "Bash(ego-browser:*) Bash(node:*) Bash(python3:*) Bash(curl:*) Bash(mkdir:*) Bash(ls:*) Bash(grep:*) Bash(cat:*) Bash(which:*) Bash(pgrep:*) Bash(file:*) Bash(rm:/tmp/*) Read Write Edit" \
  >> "$LOG" 2>&1

P1=$?
echo "=== Phase1 claude exit=$P1 $(date) ===" >> "$LOG"

# ─────────── Gate：shell 层等审批结果（与 claude 死活无关）───────────
# 门守着（current.json 在）但结果未出 → 等 Daniel 点击，最长 timeout+600s 余量。
if [ ! -f "$GATE_RESULT" ] && [ -f "$GATE_CURRENT" ]; then
  echo "$(date) Phase1 提前退出但审批门还活着，shell 层接管等待…" >> "$LOG"
  WAIT_SEC=$((GATE_TIMEOUT + 600))
  while [ $WAIT_SEC -gt 0 ]; do
    [ -f "$GATE_RESULT" ] && break
    # 门进程消失且没写结果（被 kill -9 / 崩溃）→ 不等了
    GPID=$(python3 -c "import json;print(json.load(open('$GATE_CURRENT')).get('pid',0))" 2>/dev/null)
    if [ -n "$GPID" ] && [ "$GPID" != "0" ] && ! kill -0 "$GPID" 2>/dev/null; then
      echo "$(date) 审批门进程消失且无结果文件，视为 KILLED" >> "$LOG"
      echo '{"result":"KILLED","why":"gate_process_died"}' > "$GATE_RESULT"
      break
    fi
    sleep 20; WAIT_SEC=$((WAIT_SEC - 20))
  done
fi

# ─────────── Phase 2：claude 没收完尾 → 补跑消费结果 ───────────
if [ ! -f "$GATE_DONE" ]; then
  GATE_RES=$(python3 -c "import json;print(json.load(open('$GATE_RESULT')).get('result','NO_RESULT'))" 2>/dev/null || echo NO_RESULT)
  echo "$(date) Phase1 未完成收尾（无 done 标记），审批结果=$GATE_RES，补跑 Phase2" >> "$LOG"
  ~/.local/bin/claude -p "这是每日流水线的 Phase-2 补跑（Phase-1 的 claude 中途退出了，审批门已守护化独立跑完）。审批结果在 /tmp/douyin_approval_result.json（result 字段=APPROVED/REJECTED/TIMEOUT/KILLED）。
你的任务：
1. 读 /tmp/douyin_approval_result.json 的 result。
2. APPROVED → 抖音草稿已在创作者后台（upload 页「继续编辑」可恢复）：用 ego-browser 恢复草稿 → CDP 人类化点击发布（被吞则 React onClick 直调兜底）→ 确认跳转 manage 页。
3. REJECTED/TIMEOUT/KILLED → 保草稿不发布，说明草稿找回路径（upload 页继续编辑）。
4. 无论哪种：跑资源清理 python3 .claude/skills/daily-news-douyin/scripts/cleanup_resources.py → 按日报模板写 reports/$(date +%F)-daily-report.md（如实记录 Phase1 中断+审批结果+发布动作）。
5. 若 result 文件不存在或 NO_RESULT：写失败日报说明审批门未起/结果丢失，草稿按保草稿处理。
6. 脚本一律 Write 落盘 + ego-browser nodejs < file 管道执行（沙箱拦大 heredoc）。" \
    --permission-mode acceptEdits \
    --allowedTools "Bash(ego-browser:*) Bash(node:*) Bash(python3:*) Bash(curl:*) Bash(mkdir:*) Bash(ls:*) Bash(grep:*) Bash(cat:*) Bash(which:*) Bash(pgrep:*) Bash(file:*) Read Write Edit" \
    >> "$LOG" 2>&1
  P2=$?
  echo "=== Phase2 claude exit=$P2 $(date) ===" >> "$LOG"
else
  echo "$(date) Phase1 已完成全部收尾（done 标记在），跳过 Phase2" >> "$LOG"
fi

# ─────────── 兜底资源清理（双保险；活门已被豁免，不会误杀）───────────
echo "--- 兜底清理 $(date) ---" >> "$LOG"
python3 "$PROJECT/.claude/skills/daily-news-douyin/scripts/cleanup_resources.py" >> "$LOG" 2>&1

echo "=== daily-news-douyin end $(date) ===" >> "$LOG"
exit 0
