#!/bin/bash
# daily-news-douyin 定时入口（launchd 每日 8:00 触发）
# 注意：本脚本必须放在 ~/daily-news-douyin/（Documents 受 macOS TCC 保护，launchd 进程读不了）
# 手动补跑：bash ~/daily-news-douyin/run_daily.sh
PROJECT=/Users/plato/Documents/trae_projects/Trae_Agent_First_Project
RUNDIR=/Users/plato/daily-news-douyin
# launchd 的 PATH 只有 /usr/bin:/bin:/usr/sbin:/sbin，找不到 node（claude wrapper 依赖它）。
# 8/16 实测：不加这行，claude exit=127 "node: not found"，整轮 3 秒报废。
export PATH="$HOME/.local/node-v22.5.0-darwin-x64/bin:$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
LOGDIR="$RUNDIR/logs"
mkdir -p "$LOGDIR" "$PROJECT/logs" "$PROJECT/reports" 2>/dev/null
LOG="$LOGDIR/daily-$(date +%F).log"
echo "=== daily-news-douyin start $(date) ===" >> "$LOG"

# 防重入：mkdir 原子锁（pgrep -f 会误匹配脚本自身路径，弃用）
LOCK="$LOGDIR/running.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  # 锁存在：>3h 视为陈锁（审批门最长 2h + 余量），破锁重跑
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +180 2>/dev/null)" ]; then
    echo "$(date) 发现陈锁(>3h)，破锁重跑" >> "$LOG"; rmdir "$LOCK" 2>/dev/null; mkdir "$LOCK" 2>/dev/null || exit 0
  else
    echo "$(date) 上一次运行尚未结束，跳过本次触发" >> "$LOG"
    exit 0
  fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# cd 失败（TCC/Full Disk Access 未授权）时明确记录，别让错误变模糊
if ! cd "$PROJECT" 2>>"$LOG"; then
  echo "$(date) ❌ 无法进入项目目录 $PROJECT —— launchd 进程缺 Documents 读权限。请给 /bin/bash 授 Full Disk Access（系统设置→隐私与安全性→完全磁盘访问权限）。" >> "$LOG"
  exit 1
fi

~/.local/bin/claude -p "运行 daily-news-douyin 技能：完整执行每日新闻到抖音发布流水线。按 SKILL.md 顺序：环境自检→选稿→写文章→4张视觉笔记→抖音发布(审批门 --timeout 7200)→资源清理(Step 6)→写日报到 reports/。内容自动起草不需要用户过目，发布必须等飞书审批 APPROVED。" \
  --permission-mode acceptEdits \
  --allowedTools "Bash(ego-browser:*) Bash(node:*) Bash(python3:*) Bash(curl:*) Bash(mkdir:*) Bash(ls:*) Bash(grep:*) Bash(cat:*) Bash(which:*) Bash(pgrep:*) Bash(file:*) Read Write Edit" \
  >> "$LOG" 2>&1

EXIT=$?
echo "=== claude exit=$EXIT $(date) ===" >> "$LOG"

# 兜底资源清理（双保险）：无论 claude 成败、甚至被 kill，都扫一遍孤儿进程/残留。
# 脚本自身永远 exit 0，不会影响下面的退出码记录。ego lite 浏览器不受影响。
echo "--- 兜底清理 $(date) ---" >> "$LOG"
python3 "$PROJECT/.claude/skills/daily-news-douyin/scripts/cleanup_resources.py" >> "$LOG" 2>&1

echo "=== daily-news-douyin end $(date) exit=$EXIT ===" >> "$LOG"
exit $EXIT
