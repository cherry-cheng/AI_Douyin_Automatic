# 每日新闻抖音流水线日报 2026-08-24

## 概览
| 项 | 结果 |
|---|------|
| 选题 | 机器人要开始「自己拿主意」了（热榜 #8，热度 6,995,666，technology） |
| 文章 | ✅ 15news_content/toutiao_科技_2026-08-24_机器人自己拿主意.md |
| 视觉笔记 | ✅ 4/4（图1 24s 一次过；图2 重试 4 次；图3 18s 一次过；图4 20s 一次过） |
| 抖音草稿 | ✅（标题/描述/4话题/配乐/AIGC 全部核验在位） |
| 审批 | ✅ APPROVED（09:52 发卡 → 09:03 确认，等待约 10 分钟） |
| 发布 | ✅ 已发布（09:04，manage 页作品 11→12，无验证码无滑块） |
| 失败点 | 无阻断性失败；两个非阻断问题见详情（CDP 限流、截图不可用） |
| 资源清理 | ✅ 关 1 space（douyin publish）/ 跳过 user-owned（douyin publish probe）/ 清 1 个临时文件（详情 /tmp/cleanup_result.json） |

## 详情

### 环境自检（Step 0）
①~④ 30s 内全过（ego-browser / Clash 7890 → 200 / 抖音 config / cloudflared）；⑤ Gemini 登录态健康（Pro 可用）。

### 选稿（Step 2）
热榜 50 条里 4 条 technology 分类，取最高热度的 #8「机器人要开始'自己拿主意'了」（新华日报，2026 世界机器人大会走访，正文 4036 字，数据密集）。关联条目：#20 天工队夺人形机器人运动会首金、#32 机器人娇羞跑姿。

### 视觉笔记（Step 4）——一次流程坑 + 一次选择器坑
- **图1 封面**：24s 一次过，572×1024 竖版，视觉核验文字清晰无水印。
- **图2 对比矩阵**：**重试 4 次**。①第一次出横版（SKILL 排障②已知症候）→ 强化竖版措辞重试；②②③三次「取图失败」实际是**假阴性**——两次 Gemini 把 prompt 当待评审文本回了聊天（8/20 记忆症候，prompt 头加「请直接生成图片」+ 新开会话解决）、一次页面**图片实际已生成**（有分享/下载按钮、img 708×1267 在 DOM）但取图选择器没匹配到。根因：**Gemini 现在 img class 是 `image animate loaded`，通配扫描全部 `img` 取 blob:/googleusercontent 的最后一张**才稳。手动提取落盘成功，572×1024 竖版，内容完整。已把取图逻辑改为通配版（当日脚本 /tmp/ego_note_01.js）。
- **图3 逻辑链**：18s 一次过（新取图逻辑生效）。
- **图4 总结**：20s 一次过。
- 4 张全部过视觉核验（竖版/中文清晰/无水印/无多余日期戳）。

### 抖音发布（Step 5）
- **上传**：原生 input 一次过（本次图文页有原生 input，无需注入），4 张稳定完成。
- **标题/描述/话题**：标题「机器人开始自己拿主意了」；描述精确写入（clearAndFillDouyinBody 校验相等）；4/4 话题实体化（#世界机器人大会 5.9亿 / #人形机器人 65.3亿 / #机器人 485.6亿 / #科技资讯 3.5亿），无残留纯文本 #。
- **配乐**：搜索「科技感」→「动感科技」（时代环球娱乐，00:51）。**重试 4 轮才配上**：①入口在视口外被安全区拦截 → 滚动后重测；②CDP 点击遭 **Input.dispatchMouseEvent 限流超时** → 全链改 element.click()；③面板开了但「使用」按钮找不到 → dump 子树发现它在卡片右区是 `button.semi-button-primary` 但 **w=0（hover 前不渲染宽）**，`offsetParent` 过滤会误杀 → 直接按文本匹配 querySelectorAll('button') 点击成功。**锚定核验 ✅**：空态提示「点击添加合适作品风格音乐」消失 + 入口变「修改音乐」。
- **AIGC**：selectBox →「内容由AI生成」选定，复查在位（配乐后设置，未被重置）。
- **存草稿**：CDP 点击被吞（fixed 按钮已知坑）→ React onClick 直调 ✅。草稿核验（继续编辑提示法）：标题/描述/4话题/配乐（修改音乐）/AIGC（内容由AI生成）全部在位。
- **截图**：❌ Page.captureScreenshot 被 CDP 限流卡死（重试 3 次超时），系统 screencapture 需要授权未批。改落盘 `/tmp/douyin_draft_state.json`（全字段 JSON）作草稿证据；审批卡片无图发出。
- **审批门**：`--detach --timeout 7200` 守护化启动，08:52:55 current.json 出现（门活），Daniel 09:03:19 飞书点「确认发布」→ APPROVED。
- **发布**：恢复草稿 → 发布前核验全过（标题/4话题/配乐/ AIGC）→ CDP 点击仍限流 → React onClick 直调「发布」fixed 主按钮 → **成功，无验证码无滑块**，URL 跳 `content/manage?enter_from=publish`，作品数 11→12，新帖 09:04 已发布。

### 当日新增坑（建议回写 SKILL）
1. **CDP 集中限流**：Input.dispatchMouseEvent / Page.captureScreenshot 在连续操作后会集体超时（本次配乐阶段开始出现，持续约 20 分钟）。element.click() / React onClick / js() 不受影响。对策：CDP 超时后立即全链切 element.click()；截图改落盘状态 JSON 或等限流窗口过去。
2. **Gemini 取图选择器漂移**：`img.image.loaded` 失配（现为 `image animate loaded`），且「页面有图但选择器没匹配」会被误判为生成失败。通配扫描全部 img（blob:/googleusercontent + ≥80px + 取最后一张）更稳。
3. **抖音音乐「使用」按钮 w=0**：hover 前宽度为 0，visible 过滤（offsetParent/width>0）会误杀。按文本精确匹配 button 再 .click() 即可。

## 产物清单
- 文章：`15news_content/toutiao_科技_2026-08-24_机器人自己拿主意.md`
- 图：`15news_content/素材/visual-note-01-封面.png` / `visual-note-02-对比矩阵.png` / `visual-note-03-逻辑链.png` / `visual-note-04-总结.png`
- Prompt：`15news_content/素材/prompts/01-cover.md` ~ `04-summary.md`
- 草稿状态：`/tmp/douyin_draft_state.json`（截图限流的替代证据）
- 清理详情：`/tmp/cleanup_result.json`

## 下一步建议
- 把「当日新增坑」3 条回写 longform-visual-notes / douyin-ego-publish SKILL.md（取图通配、CDP 限流切换 element.click、使用按钮 w=0）。
- 审批门卡片本次无截图——可考虑 await_approval.py 支持附带 draft_state.json 文本摘要作替代证据。
