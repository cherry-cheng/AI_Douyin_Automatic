---
name: daily-news-douyin
description: 每日头条科技新闻 → 抖音图文全自动流水线。抓热榜选科技新闻→写文章→生成4张视觉笔记→自动发布抖音（飞书审批门，默认保草稿）→生成本地日报。触发词：每日新闻、daily news、自动发布流水线、跑日报。定时任务每日 8:00 自动调用（launchd），也可手动触发。
---

# 每日新闻 → 抖音图文全自动流水线

把今天验证过的完整链路固化成一条龙：**头条热榜抓科技新闻 → 写文章到 `NNnews_content/` → longform-visual-notes 生成 4 张视觉笔记 → douyin-ego-publish 发布（飞书审批门）→ 本地日报**。

## 铁律

1. **内容自动起草、不过目**：标题/描述/话题按 `douyin-ego-publish/templates/desc-template.md` 起草后**直接填**，不停下来问 Daniel（这是与手动调用 douyin-ego-publish 的唯一差异）。
2. **发布必须过飞书审批门**：全流程自动跑完 → 发审批卡片 → **等 Daniel 点「✅确认发布」** → 才点发布。定时模式超时 **7200s（2 小时）**，超时保草稿不发布。
3. **每步失败不静默**：任何一步失败，先重试一次（换措辞/新会话），再失败就跳过该步继续跑完剩余步骤，**日报里如实记录失败点**。
4. **日报必生成**：无论成功失败，最后写 `reports/YYYY-MM-DD-daily-report.md`。
5. **资源必回收（成败都一样）**：流水线开的 task space（visual notes / douyin publish / gemini-health-check）用完即关；`await_approval.py` 等脚本自带 finally 会收 cloudflared/HTTP 服务，但 claude -p 被 kill 时它们会成孤儿。**Step 7 清理是硬要求**——run_daily.sh 退出前还有兜底扫一遍（双保险）。user-owned 的 task space（如 Daniel 手开的 `douyin publish probe`）和 ego lite 浏览器本体**永远不碰**。

## 执行流程

### Step 0 — 环境自检（①~④ 30s 内；⑤ 约 2 分钟，失败直接出失败日报）

```bash
# ① ego-browser 可用
which ego-browser
# ② Clash 代理通（Gemini 生图前提；返回非 000 即通）
curl -s -x http://127.0.0.1:7890 -o /dev/null -w "%{http_code}" --max-time 12 -I https://gemini.google.com/
# ③ 抖音配置在
python3 -c "import json;print(bool(json.load(open('$HOME/.config/douyin-ego-publish/config.json')).get('feishu_webhook')))"
# ④ cloudflared 在
which cloudflared
# ⑤ Gemini 登录态健康（真开页面查模型菜单，非只查代理；2026-08-15 账号退出教训）
#    exit 2 = 账号退出/Pro 全 disabled（自动发飞书告警含修法）；exit 3 = 探测本身失败
python3 .claude/skills/daily-news-douyin/scripts/check_gemini_health.py
```

①~⑤ 任何失败 → 写失败日报（写明缺什么、怎么修），结束。⑤ 失败时飞书告警已由脚本自动发出（含「登录后重跑确认、再补跑 run_daily.sh」指引），日报注明已通知；探测详情在 `/tmp/gemini_health.json`。

**为什么要 ⑤**：账号退出时代理依旧全通、页面照样能开，② 测不出来；等 Step 4 生图才发现就要报废整轮文章。⑤ 用 3 个信号判登录态（页头「登录」按钮 / 「登录即可使用所有模型」文案 / 模型菜单 Pro 条目 disabled），强刷后轮询模式按钮出现（Angular 渲染慢，最长 90s+），退出码 0/2/3。

### Step 1 — 确定输出目录

```bash
# 找当前最大编号的 news_content 目录，+1 作为今天的工作目录
ls -d [0-9][0-9]news_content | sort | tail -1   # 例：04news_content → 今天用 05news_content
```

### Step 2 — 抓取科技新闻（toutiao-news-trends）

```bash
node .claude/skills/toutiao-news-trends/scripts/toutiao.js hot 50
```

选稿规则（按优先级）：
1. `categories` 含 `technology` 的最高热度条目
2. 若无 technology，找科技相关关键词（AI/芯片/手机/机器人/互联网/新能源车/自动驾驶）
3. 都没有 → 选非时政非敏感（跳过 military/international/taiwan/health 类）的最高热度条目

抓正文：

```bash
node .claude/skills/toutiao-news-trends/scripts/toutiao.js detail <clusterId>
```

正文太薄（<300 字）→ 顺位换下一条候选。

````bash
node .claude/skills/toutiao-news-trends/scripts/toutiao.js hot 50 > /tmp/hot.json && node -e "
const hot = require('/tmp/hot.json');
const TECH = /AI|人工智能|芯片|手机|机器人|互联网|算法|大模型|自动驾驶|新能源|无人机|量子|卫星|6G|5G/i;
const skip = new Set(['military','international','taiwan','health']);
const scored = hot.filter(h => !(h.categories||[]).some(c=>skip.has(c)))
  .map(h => ({ ...h, _tech: (h.categories||[]).includes('technology') ? 2 : (TECH.test(h.title) ? 1 : 0) }))
  .sort((a,b) => b._tech - a._tech || b.popularity - a.popularity);
console.log(JSON.stringify(scored.slice(0,5).map(({rank,title,popularity,clusterId,_tech}) => ({rank,title,popularity,clusterId,_tech})), null, 2));
"
````

### Step 3 — 写文章

存 `NNnews_content/toutiao_<分类>_YYYY-MM-DD_<短标题>.md`，格式沿用 `03news_content/` 现有文章（元信息头 + 核心摘要 + 分节 + 数据表 + 行业影响 + 尾注 clusterId）。**禁止编造**：所有数字/时间/引述必须来自抓取的正文。

### Step 4 — 视觉笔记（longform-visual-notes）

调用 longform-visual-notes 流程（ego-browser 驱动 Gemini），产出 4 张：

| 图 | 内容 | 风格 |
|---|------|------|
| 01-封面 | 标题+核心数据卡 | 科技杂志封面 |
| 02-对比矩阵 | 关键数据对比表 | 手写表格 |
| 03-根因/逻辑链 | 因果链或流程 | **手写笔记风**（白板风格已证实连败，禁用） |
| 03 的内容若文章没有因果结构 → 改为「时间线」 | | |
| 04-总结 | 3 点总结+结论行 | 手写笔记 |

输出 `NNnews_content/素材/visual-note-0X-*.png`（9:16 竖版）+ `素材/prompts/*.md`。

**生图实战坑（已固化，直接照做）**：
- 每张图 = 一个独立 `ego-browser nodejs` heredoc，新开 `https://gemini.google.com/app` 会话
- 轮询上限 **250s**，判据 = stop 态 imgCount>0 即 done
- 填 prompt 用 CDP `Input.insertText` + 填后校验 inputLen
- 状态机判据用 aria-label（发送/停止回答），不用 class
- 引述真实人名可能触发内容策略 → 用中性表述（如「厂商表态」）
- 卡「Creating your image」>6 分钟 → 点停止按钮中止换简化 prompt 重试
- 同一张图重试 3 次失败 → 跳过该图，日报记录，凑不满 2 张则本日不发布

### Step 5 — 发布（douyin-ego-publish 全流程）

**起草规则（自动，不过目）**：
- 标题：≤20 字，从文章钩子提炼，格式参考 `手机全线涨价，苹果也顶不住了`
- 描述：1 句钩子(带1 emoji) + 1-2 句说明 + 1 句 CTA + 无话题（话题单独实体化）
- 话题：4 个 = 1-2 精准 + 2-3 泛（`#主题词` `#数码科技` `#相关事件` `#科技资讯`）
- 配乐：内容主题定关键词（AI/科技→科技感；技术→lofi；商业→大气）
- AIGC：开启「内容由AI生成」

执行序列（细节全按 douyin-ego-publish SKILL.md，此处只列编排顺序）：
1. 开 `creator.douyin.com/creator-micro/content/upload?default-tab=3`，确认登录
2. 上传 4 张图（原生 input 优先，找不到→注入 input；等 editorReady 稳定 10s）
3. 填标题+描述+话题实体化（clearAndFillDouyinBody + addDouyinTopic）
4. 配乐（入口在视口外先 scroll dy=300 再测坐标）
5. **AIGC 最后设**（配乐弹窗会重置它，设完复查）
6. 截图 `/tmp/douyin_draft_preview.png`
7. **飞书审批门**（定时模式 `--timeout 7200`）：

```bash
cd <project_root>/.claude/skills/douyin-ego-publish && python3 scripts/await_approval.py \
  --config ~/.config/douyin-ego-publish/config.json \
  --screenshot /tmp/douyin_draft_preview.png \
  --type "图文" --title "<标题>" --desc "<描述+话题>" \
  --cover "默认(不设)" --timeout 7200
```

8. `RESULT=APPROVED` → 发布（CDP 单步点击，被吞则 React onClick 直调兜底）；触发验证码走 8b 中继；`REJECTED/TIMEOUT` → 保草稿
9. 发布成功信号 = URL 跳 `/content/manage`；之后截图收尾

### Step 6 — 资源清理（必跑，成败都一样）

```bash
python3 .claude/skills/daily-news-douyin/scripts/cleanup_resources.py
```

收尾动作（脚本自动做，结果落 `/tmp/cleanup_result.json`）：
- 关流水线名下的 agent-owned task space（`visual notes` / `douyin publish` / `gemini-health-check`）；user-owned（Daniel 手开的）和 agentDelegatedToUser（审批门交接的）跳过
- 杀孤儿 `await_approval.py` / `await_verification_code.py` 及其 cloudflared 隧道（父进程已死的才杀，活的不碰——正常陪伴由脚本自身 finally 收）
- 清 `/tmp/hot.json`、`/tmp/douyin_draft_preview.png`、`/tmp/gemini_health.json` 等临时文件
- **永远 exit 0**，清理失败不阻断日报；ego lite 浏览器本体绝不动

前置配合：Step 4/5 的每个 heredoc 阶段任务完成后应随手 `completeTaskSpace(keep:false)` 或至少关掉草稿 tab，别全堆到最后。

### Step 7 — 日报（必产出）

写 `reports/YYYY-MM-DD-daily-report.md`：

```markdown
# 每日新闻抖音流水线日报 YYYY-MM-DD

## 概览
| 项 | 结果 |
|---|------|
| 选题 | <标题>（热榜 #N，热度 X） |
| 文章 | ✅ NNnews_content/toutiao_….md |
| 视觉笔记 | ✅ 4/4（每张耗时/重试次数） |
| 抖音草稿 | ✅/❌ |
| 审批 | APPROVED / REJECTED / TIMEOUT |
| 发布 | ✅ 已发布，审核中 / 保草稿 / 未发布 |
| 失败点 | 无 / <步骤+原因> |
| 资源清理 | ✅ 关 N space / 杀 N 孤儿 / 临时文件 N 个（详情 /tmp/cleanup_result.json） |

## 详情
（每步的关键细节：选稿理由、生成重试、配乐曲目、审批等待时长、发布是否触发验证码等）

## 产物清单
（文章路径、4 张图路径、截图路径）

## 下一步建议（可选）
```

reports/ 目录不存在则创建。日报写完即流水线结束。

## 定时运行（launchd，每日 8:00）

包装脚本 `.claude/skills/daily-news-douyin/scripts/run_daily.sh`（launchd 触发，claude -p headless 模式跑本 skill；实际部署副本在 `~/daily-news-douyin/run_daily.sh`，改完源文件记得 cp 同步）。要点：

- 防重入 mkdir 原子锁（>3h 陈锁破锁重跑）
- claude -p 退出后**兜底跑 `cleanup_resources.py`**（双保险：claude 即使被 kill 也扫掉孤儿 cloudflared / await_* 进程），清理永远 exit 0 不影响退出码记录
- 日志 `~/daily-news-douyin/logs/daily-YYYY-MM-DD.log`（Documents 受 TCC 保护，launchd bash 读不了，日志放用户根目录）

plist `~/Library/LaunchAgents/com.plato.daily-news-douyin.plist`：StartCalendarHandle Hour=8 Minute=0（源码见 scripts/ 下同名 plist 样例）。

**手动补跑**：错过 8 点（电脑关机等）launchd 错过不补，手动跑 `bash .claude/skills/daily-news-douyin/scripts/run_daily.sh` 即可。

**权限模式说明**：定时跑用 `--permission-mode acceptEdits`——发布流程里的 Bash 命令（ego-browser/node/python3 等）已通过 `--allowedTools` 白名单放行，审批门本身是安全门（Daniel 飞书确认），所以 headless 自动化是安全的。
```
