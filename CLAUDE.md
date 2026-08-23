# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这是什么仓库

AI Agent 技能集合（Claude Code / Trae 可直接调用），核心是一条**每日新闻 → 抖音图文全自动流水线**。仓库语言为中文，owner 是 Daniel。没有传统意义的 build/lint——"代码"就是 `.claude/skills/` 下的技能文档 + 脚本，配套产物（文章/图/日报）按日期落在仓库根目录。

## 常用命令

```bash
# 头条热榜抓取（toutiao-news-trends）
node .claude/skills/toutiao-news-trends/scripts/toutiao.js hot 50        # 热榜前 50
node .claude/skills/toutiao-news-trends/scripts/toutiao.js detail <id>   # 单篇正文

# 流水线环境自检（Gemini 登录态健康检查，exit 2=账号退出，3=探测失败）
python3 .claude/skills/daily-news-douyin/scripts/check_gemini_health.py

# 资源清理（永远 exit 0，不会阻断流程）
python3 .claude/skills/daily-news-douyin/scripts/cleanup_resources.py

# 手动补跑每日流水线（错过 launchd 8:00 触发时）
bash ~/daily-news-douyin/run_daily.sh

# 测试（video-publisher 是仓库里唯一有测试的模块）
node --test .claude/skills/video-publisher/scripts/tests/*.test.mjs

# 浏览器自动化（所有 ego-browser 操作的执行载体）
ego-browser nodejs < /tmp/ego_<步骤>.js    # 脚本先 Write 落盘再管道执行（沙箱拦大 heredoc）
```

## 架构：每日流水线（big picture）

`daily-news-douyin` 是编排层，串起四个技能：

```
launchd (每日 8:00)
  → ~/daily-news-douyin/run_daily.sh          # 部署副本！改源文件后必须 cp 同步
    → Phase 1: claude -p 跑流水线
        ① 环境自检（ego-browser / Clash 7890 / 抖音 config / cloudflared / Gemini 登录态）
        ② toutiao-news-trends 抓热榜选科技新闻
        ③ 写文章 → NNnews_content/toutiao_<分类>_<日期>_<短标题>.md
        ④ longform-visual-notes：ego-browser 驱动 Gemini 官网生 4 张视觉笔记（9:16）
        ⑤ douyin-ego-publish：上传→填内容→配乐→AIGC→存草稿→飞书审批门→发布
        ⑥ cleanup_resources.py 资源回收
        ⑦ 日报 → reports/YYYY-MM-DD-daily-report.md
    → Gate: shell 层等审批结果（与 claude 进程死活无关）
    → Phase 2: claude 中途死了则补跑会话消费审批结果
```

关键机制（改流水线前必须理解）：

- **两阶段 + 审批门守护化（2026-08-22 事故后）**：`await_approval.py --detach` 双 fork 脱离 claude 进程树，结果落 `/tmp/douyin_approval_result.json`；claude 收尾后写 `/tmp/daily_gate_done`，run_daily.sh 据此判断是否需要 Phase-2 补跑。**绝不用 run_in_background 跑长阻塞审批门**——claude end_turn 退出会把门变孤儿被清理杀掉，Daniel 点确认就打到死 URL。
- **NNnews_content 编号**：找当前最大编号目录 +1 作为当天工作目录（如现有 `14news_content` → 明天用 `15news_content`）。
- **日报是硬要求**：无论成败都写 `reports/`，失败点如实记录（不许把失败写成 ✅——8/23 配乐误报事故的教训）。
- **TCC 限制**：Documents 目录 launchd 读不了，所以部署脚本和运行日志在 `~/daily-news-douyin/`（logs 也在那），仓库里的 `scripts/run_daily.sh` 和 plist 只是源码。

## 技能间关系

- **ego-browser** — 所有浏览器自动化的底层原语（CDP + task space 模型）。先读它的 SKILL.md 再写自动化脚本。
- **toutiao-news-trends** — 数据抓取，独立无依赖。
- **longform-visual-notes** — 文章转 4 张视觉笔记图，用 ego-browser 驱动 Gemini 官网（不走 API、不用 gemini MCP）。
- **douyin-ego-publish** — 发布到抖音创作者后台，飞书审批门（cloudflared 临时隧道 + webhook 卡片）。`~/.config/douyin-ego-publish/config.json` 放 webhook 等配置。
- **video-publisher** — 多平台（小红书/B站/视频号）视频发布，douyin-ego-publish 的部分 helper 移植自它的 douyin.mjs。
- **wjz-p-gemini-skill-1.0.1** — Gemini MCP server（`.mcp.json` 里配置的 gemini MCP 就是它）。流水线生图已改走 ego-browser，此技能是备选路径。

## 铁律（改这些流程前先读对应 SKILL.md）

各 SKILL.md 里沉淀了大量实战坑（选择器被吞、配乐五坑、反检测点击法、--detach 等），**都是用真实事故换的，属于 load-bearing 内容**——动流程前先完整读对应技能的 SKILL.md，别凭直觉改写脚本细节。两条全局性的：

1. **发布必须过飞书审批门**：默认只存草稿；只有 Daniel 在飞书点「确认发布」后才点发布。绝不能绕过。
2. **ego lite 浏览器本体和 user-owned task space 永远不碰**：清理脚本只收 agent 自己开的 space 和孤儿进程（进程匹配须 `^python3` 开头，防 `bash -c` 误配）。

## Git

- main 分支直接提交，无 PR 流程；日常产物（news_content、reports、SKILL.md 改动）随做随 commit。
- `.claude/settings.local.json` 和 `.env` 已在 .gitignore（含真实 key，别提交）。
- GitHub 走 SSH（cherry-cheng 账号，专用 key `id_ed25519_github`）。
