# 每日新闻抖音流水线日报 2026-08-20

## 概览

| 项 | 结果 |
|---|------|
| 选题 | 宇树科技科创板上市：市值破4400亿，机器人大脑补课（热榜 #10「宇树机器人能学会"拧螺丝"吗」，热度 34,166,540，technology 分类） |
| 文章 | ✅ 11news_content/toutiao_科技_2026-08-20_宇树科技上市4400亿机器人大脑补课.md |
| 视觉笔记 | ✅ 4/4（每张耗时/重试：图1 50s+恢复1次；图2 3次重试；图3 2次重试；图4 一次成功） |
| 抖音草稿 | ✅ 标题/描述/4话题/配乐/AIGC 全填齐，暂存离开成功 |
| 审批 | APPROVED（等待约 6 分钟） |
| 发布 | ✅ 已发布，URL 跳转 /content/manage，未触发验证码/滑块 |
| 失败点 | 无（当日有两处目录/覆盖险情，均已当场纠正，见详情） |
| 资源清理 | ✅ 关 1 space（visual notes）/ 跳过 1（douyin publish probe，user-owned）/ 清 /tmp 临时文件 2 个（详情 /tmp/cleanup_result.json） |

## 详情

### Step 0 环境自检
①ego-browser ✅ ②Clash 代理 200 ✅ ③飞书 webhook 配置 ✅ ④cloudflared ✅ ⑤Gemini 登录态健康（Pro 可用）✅——五项全绿，无告警。

### Step 1+2 选稿
热榜 50 条中 5 条 technology 候选，取热度最高的「宇树机器人能学会拧螺丝吗」（#10，3416万热度）。正文 2000+ 字、数据密实（发行价/市值/市盈率/增速/募资投向齐全），无需换稿。

**⚠️ 目录险情（已纠正）**：Step 1 执行时 `10news_content` 已是 8/19 频准激光的工作目录，按「最大编号+1」规则今天应建 `11news_content`。文章最初误写入 10news_content，且素材 prompts 差点覆盖昨天的 4 个 prompt 文件（Write 的「先读后写」保护拦住了，未造成损失）。已建 11news_content 并迁移文章，昨天素材完好。

### Step 3 文章
沿用 03news_content 格式：元信息头 + 核心摘要 + 路演问答 + 资本赢家表 + 关键数据表 + 小脑/大脑核心矛盾 + 募资账本 + 行业意义。所有数字来自抓取正文（4400亿/1600倍PE/332%→68%/9万9/42亿募资等），无编造。

### Step 4 视觉笔记（ego-browser 驱动 Gemini，4/9:16 全成）
本日新踩并修复的坑：
1. **沙箱拦大 heredoc**（已知坑，memory 有案）：大脚本改「落盘 + `ego-browser nodejs < file` 管道执行」。
2. **新会话默认模型漂移**（新坑）：openOrReuseTab 新开会话时默认模型不固定（图1 会话默认 Pro，图2/图4 会话默认非 Pro）。Flash/Flash-Lite 系不生图，会把 prompt 当「帮 Midjourney 写提示词」直接回文本（stop 态仅 12~30s 且无图）。**修复：把 skill ③ 的 ensureProModel（切 3.1 Pro）补进生成脚本**；菜单实测 `["3.5 Flash-Lite","3.6 Flash","3.1 Pro","扩展思考"]`。probe `currentModel` 为空串 ≠ Pro，必须显式切。
3. **Pro 也可能回文本**（新坑）：切了 Pro 仍可能输出「优化后的提示词」而非生图。**修复：prompt 头部加一行「请直接生成图片，不要输出文字方案。」**（02/03 补后一次成功）。已回写 prompts/ 落盘文件。
4. **src 空串**（已知坑，照 memory 处理）：stop 态 imgCount>0 但 src 为空 → 恢复脚本同会话重查即拿到 blob URL。
5. **恢复脚本要先接管 task space**：heredoc 退出后 Node 状态清空，`useOrCreateTaskSpace('visual notes')` 复用 space 35（task id 34 是 Gemini 的）后再提取。

各图：图1 封面 572×1024 ✅（50s 出图+恢复提取）；图2 对比矩阵 3 次尝试（Flash 文本回复×2 → 加指令+Pro ✅）；图3 逻辑链 2 次（Pro 文本回复 1 次 → 加指令 ✅，62s）；图4 总结一次成功（ensureProModel 显式切 3.1 Pro，24s）。

### Step 5 抖音发布
- 上传：图文页原生 input 意外可用（无需注入），4 张一次上传，稳定完成
- 标题「机器人第一股不会拧螺丝？」+ 描述 1 钩子+2 说明+1 CTA + 4 话题实体化全成：#宇树科技(41.8亿) #人形机器人(64.3亿) #机器人概念股(1822.8万) #科技资讯(3.5亿)，无残留纯文本 #
- 配乐：搜「科技感」选第一首热门（**动感科技 01:52**）
- AIGC：配乐后设（顺序正确），复查 aigcSet=true
- 存草稿：「暂存离开」是 fixed-J9O8Yw 按钮且坐标在视口外(y=1206>871)，滚动无效（fixed 定位）→ **React onClick 直调成功**；草稿恢复验证：标题/AIGC/BGM/4图全保留
- 审批门：cloudflared 隧道 + 飞书卡片发出，约 6 分钟后 **APPROVED**
- 发布：CDP 人类化点击一次成功（未触发验证码/滑块，无需 React 兜底），URL 跳 `/content/manage?enter_from=publish` ✅

### Step 6 资源清理
cleanup_resources.py：关 agent-owned「visual notes」space 1 个；跳过 user-owned「douyin publish probe」（Daniel 手开，不碰）；douyin publish space 在发布后已随手 completeTaskSpace(keep:false)；/tmp 清 2 个临时文件。项目内 .tmp_ 脚手架 15 个文件已手动清。

## 产物清单

- 文章：`11news_content/toutiao_科技_2026-08-20_宇树科技上市4400亿机器人大脑补课.md`
- 视觉笔记：`11news_content/素材/visual-note-01-封面.png` / `02-对比矩阵.png` / `03-逻辑链.png` / `04-总结.png`（均 572×1024 竖版）
- Prompts：`11news_content/素材/prompts/01~04*.md`（02/03 已含「直接生成图片」指令）
- 截图：`/tmp/douyin_draft_preview.png`（草稿预览）、`/tmp/douyin_publish_after.png`（发布后 manage 页）

## 下一步建议

1. **把「新会话默认模型漂移 + Pro 回文本」两个新坑回写 longform-visual-notes SKILL.md**：ensureProModel 必须无条件跑（probe 空≠Pro）；prompt 头加「请直接生成图片」应进 Phase 2 模板。
2. Step 1 的「最大编号+1」判断建议在 SKILL.md 里显式写明「用日期检查目录是否属于今天」——今天靠 Write 的先读后写保护才没覆盖昨天素材。
3. 「暂存离开」fixed 按钮视口外问题可考虑直接默认用 React onClick（与发布按钮同款兜底），少一次滚动尝试。
