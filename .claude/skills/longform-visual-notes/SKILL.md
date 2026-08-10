---
name: longform-visual-notes
description: |
  长文知识提取转图Skill。将深度长文降维提取核心逻辑，生成3-5张高真实感、含密集中文文字信息的视觉笔记图。
  通过 gemini-skill（gemini_generate_image MCP 工具）调用 Gemini 官网生成图片，无需任何 API Key。
  用法: (1) content-ops-toolkit配图阶段调用 (2) daily-gzh-content/daily-xhs-content/daily-douyin-content配图
  (3) 独立的长文转图任务 (4) Claude vs Codex等测评文章配套素材。
  Trigger: "长文转图", "知识笔记图", "视觉笔记", "浓缩长文", "文章转图", "降维提取", "visual notes".
  Author: Daniel Li
---

# 长文知识提取转图

> 将深度长文降维为3-5张高真实感视觉笔记图

## 定位

MediaClaw内容生产的核心配图skill。当有长篇文章需要转化为可传播的视觉笔记时调用。

**与其他skill的关系**：
- `content-ops-toolkit` → 素材配图阶段调用本skill
- `daily-gzh-content` → 公众号文章配图
- `daily-xhs-content` → 小红书笔记配图
- `daily-douyin-content` → 抖音图文配图
- `article-material-collect` → 素材收集后可补充本skill生成图

## 默认配置

| 配置项 | 值 |
|--------|-----|
| 生成模型 | gemini-skill（gemini_generate_image MCP 工具） |
| 图片数量 | 3-5张 |
| 图片文字 | 中文为主 |
| 输出比例 | 16:9（公众号/抖音）或 3:4（小红书） |
| 作者标注 | 有作者则在图底部标明 |
| 禁止项 | 不得显示"由xx生成该图片"等水印 |

## Workflow

### Phase 1: 知识拆解与分镜规划

阅读输入文章，输出中文摘要和分镜方案：

```
📊 知识拆解与分镜规划
- 图1：黄金标题与核心定调 — 概念图/手写大纲 — [核心文字概览]
- 图2：核心竞争力矩阵 — 手写对比表/数据图表 — [核心文字概览]
- 图3：深度分析 — 思维导图/双边对比图 — [核心文字概览]
- 图4：总结与展望 — 白板架构图/手写红框总结 — [核心文字概览]
```

**分镜策略**：

| 文章类型 | 推荐分镜 | 视觉形式 |
|---------|---------|---------|
| 测评/对比 | 4-5张 | 封面→对比矩阵→细节分析→终端截图→总结 |
| 行业分析 | 3-4张 | 概念图→数据图→趋势图→总结 |
| 教程/指南 | 4-5张 | 封面→流程图→代码图→架构图→总结 |
| 产品评测 | 3-4张 | 封面→参数对比→使用场景→总结 |

### Phase 2: 生成图像提示词

为每张图生成纯英文Prompt，**严格遵循4模块结构**：

#### 模块结构

```
[模块1: 主提示词 Main Description]
描述整体环境、视角、材质、光线。
Example: A photorealistic, ultra-clear, high-resolution close-up photograph of a hand-written note on a piece of textured paper...

[模块2: 内容和排版 Content and Layout (Verbatim)]
极度详细地规定每一个文本的位置、颜色、排版层级。
使用粗体和引号圈定必须生成的文字。
1. Top: Main title "[提取的中文标题]"
2. Chart Structure: Three columns "[列名1]" | "[列名2]"...

[模块3: 上下文细节 Context & Environment Details]
背景环境、增加真实感的细节。
Example: The paper note is on a smartphone screen. Visible at the top is the phone status bar... natural imperfections...

[模块4: 质量和风格关键词 Quality & Style Keywords]
Example: Hand-written, detailed texture, legible, varied ink colors, accurate content reproduction, photorealistic, 8k...
```

### Phase 3: 调用模型生成图片

**调用方式**：通过 `gemini-skill` 的 `gemini_generate_image` MCP 工具调用 Gemini 官网生图，**无需任何 API Key**。

> ⚠️ **网络前提**：gemini-skill 走 Gemini 官网（gemini.google.com）。本机直连被墙，**必须经本地代理**（如 Clash，gemini-skill 的 `.env` 设 `BROWSER_PROXY=http://127.0.0.1:7890`），且代理需把 `google.com` / `googleusercontent.com` 等域名路由到境外节点（不能 DIRECT、不能在 `GEOIP,CN,DIRECT` 之后）。生图前先验证：`curl -x http://127.0.0.1:7890 -I https://gemini.google.com/` 返回**非 `000`** 才可继续。

每张图彼此独立（非迭代关系），均以 `newSession=true` 新建会话生成，避免上一张图的上下文污染下一张。

```
# 为每张图调用 MCP 工具（同步阻塞，耗时长）
gemini_generate_image(
  prompt="<英文提示词（Phase 2 的 4 模块拼接成的完整 prompt）>",
  newSession=true,      # 新建会话，独立生成，避免上下文串扰
  fullSize=false,       # 默认预览图模式！fullSize=true 高清下载按钮不稳定、几乎必失败
  timeout=180000        # 必须 ≥3 分钟；生图通常 60~120 秒
)
# 返回值 = 本地图片文件路径（由 gemini-skill 决定，不含目标命名）
```

**关键规则（沿用 gemini-skill，必须遵守）：**
- 本工具为**同步阻塞**调用，会等到最终结果才返回，不存在"中间状态"需轮询。
- `timeout` **必须**设为 `180000`（≥3 分钟），否则传输层可能提前超时截断。
- **禁止**在未收到工具最终返回前结束对话，或向用户报告"还在运行 / 工具超时"。
- 生图期间每隔 15~30 秒向用户发一条进度消息（如"正在等待 Gemini 生成第 2 张…已等待 30 秒…"）。
- 拿到返回的文件路径后**立即**进入下一步。
- **默认用 `fullSize=false`**（预览图模式，实测稳定）。`fullSize=true` 的「下载高清原图」按钮在本环境几乎 100% 失败（`full_size_download_btn_not_found`），且疑似会拖垮 MCP server，**不要用**。
- **MCP 工具失灵排查**：若 `gemini_*` 连续调用几次后突然失效（调用被错误路由、返回无关结果），是 gemini MCP 连接掉线 —— 让用户 `/mcp` 重连 gemini，重连后**立刻批量做完所有生图**，别拖。若重启 daemon，要把 gemini-skill 的浏览器（`--user-data-dir=.../.wjz_browser_data` 的 Chrome）也一起杀掉，否则 daemon 会复用卡死的旧浏览器。

**保存到目标目录：**

`gemini_generate_image` 返回的是 gemini-skill 自行决定的本地路径，**不含目标命名**。需把返回的文件移动/复制到本 skill 的输出目录并按分镜命名：

```bash
mv "<返回的图片路径>" "{OUTPUT_DIR}/素材/visual-note-XX-名称.png"
```

**输出比例控制（无 size 参数，通过 prompt 控制）：**

`gemini_generate_image` 没有 `size` 入参，需在 Phase 2 的 prompt 中用关键词指定比例：
- 16:9（公众号 / 抖音）→ 加入 `wide 16:9 landscape orientation, horizontal layout`
- 3:4（小红书）→ 加入 `portrait 3:4 vertical orientation, vertical layout`

**生成优先级链：**
```
1. gemini-skill 的 gemini_generate_image（首选，无需 API Key，文字生成质量高）
2. image_generate 默认模型（兜底，仅当 gemini-skill 不可用时）
```

### Phase 4: 保存与整理

```
{OUTPUT_DIR}/素材/
├── visual-note-01-封面.png
├── visual-note-02-对比矩阵.png
├── visual-note-03-深度分析.png
├── visual-note-04-总结.png
└── prompts/
    ├── 01-cover.md
    ├── 02-comparison.md
    ├── 03-analysis.md
    └── 04-summary.md
```

**每个prompt文件保存完整的4模块英文提示词**，便于复用和调整。

## 视觉风格规范

### 可选视觉载体

| 风格 | 描述 | 适用场景 |
|------|------|---------|
| **Hand-written Note** | 手机/平板/纸张上的高密度手写图表 | 知识笔记、测评总结 |
| **Mind Map** | 手绘感或极简现代风白板思维导图 | 概念梳理、逻辑拆解 |
| **Architecture Diagram** | 专业批注的系统演算图 | 技术架构、流程分析 |
| **Comparison Chart** | 高对比度重点标红的参数对比表 | 产品对比、功能矩阵 |

### 强制规则

1. **中文文字** — 图片中必须包含中文文字内容，清晰可读
2. **作者标注** — 如原文有作者，图底部标明作者信息
3. **禁止生成水印** — 不得显示"由xx生成该图片"、"AI generated"等
4. **真实感** — 模拟真实场景（纸张纹理、手机屏幕、白板等）
5. **高信息密度** — 每张图包含足够多的有效信息，不是空洞装饰

### 排版规范

```
┌─────────────────────────────────┐
│  [主标题 - 大号粗体]             │  ← 顶部标题区
│  [副标题 - 中号]                │
├─────────────────────────────────┤
│                                 │
│  [核心内容区域]                  │  ← 主体内容区
│  - 文字说明、数据、图表          │     占图面70-80%
│  - 对比表格、流程箭头            │
│  - 关键数据用颜色/加粗突出       │
│                                 │
├─────────────────────────────────┤
│  [作者: xxx | 来源: xxx]        │  ← 底部信息区
└─────────────────────────────────┘
```

## 提示词样板

### 样板1: 手写笔记风

```
[Main Description]
A photorealistic, ultra-clear, high-resolution close-up photograph of a hand-written technical note on a piece of cream-colored textured paper. The paper is slightly tilted on a dark wooden desk. Natural lighting from the left creates subtle shadows. A black gel pen and a red highlighter are visible at the bottom corner.

[Content and Layout]
1. Top center, written in bold black marker: "Claude Code vs Codex — 终极对决"
2. Below the title, a horizontal red line separator
3. Left column header: "Claude Code" in blue ink, with 4 bullet points:
   - "✅ 原生终端体验" 
   - "✅ 200k上下文窗口"
   - "✅ 实时代码执行"
   - "✅ Anthropic生态"
4. Right column header: "Codex" in green ink, with 4 bullet points:
   - "✅ OpenAI模型驱动"
   - "✅ 多模型切换"
   - "✅ 云端沙箱"
   - "✅ 插件市场"
5. Bottom right corner, small text: "作者: Daniel Li"
6. Key comparisons circled in red highlighter

[Context & Environment]
The paper has slight coffee stain in the corner. A phone edge is visible at the top of the frame. Natural handwriting imperfections visible. Slight paper grain texture.

[Quality & Style Keywords]
Hand-written, detailed texture, legible Chinese characters, varied ink colors (black, blue, red), accurate content reproduction, photorealistic, 8k resolution, warm ambient lighting, depth of field, professional knowledge note aesthetic.
```

### 样板2: 思维导图风

```
[Main Description]
A clean, modern mind map on a large whiteboard in a tech startup office. The mind map is drawn with colorful dry-erase markers. Clean white background with subtle grid pattern visible.

[Content and Layout]
1. Center node (large red circle): "AI编程工具"
2. Branch 1 (blue, upper left): "Claude Code" → sub-nodes: "终端原生", "200k上下文", "Anthropic"
3. Branch 2 (green, upper right): "Codex" → sub-nodes: "多模型", "云端", "OpenAI"
4. Branch 3 (orange, bottom left): "共同点" → sub-nodes: "代码补全", "项目理解", "Git集成"
5. Branch 4 (purple, bottom right): "选择建议" → sub-nodes: "个人→Claude", "团队→Codex"

[Context & Environment]
Whiteboard has slight smudge marks. A coffee cup shadow on the left edge. Office background slightly blurred.

[Quality & Style Keywords]
Clean mind map, colorful markers, whiteboard texture, professional tech aesthetic, modern office, legible text, clear hierarchy, 8k resolution.
```

## 调用入口

### 独立调用

```
请将以下文章转化为视觉笔记图：
- 文章路径: /path/to/article.md
- 图片数量: 3-5
- 目标平台: gzh/xhs/douyin
- 输出目录: /path/to/output/素材/
- 作者: Daniel Li（如有）
```

### 从content-ops-toolkit调用

在素材配图阶段，优先使用本skill：

```
素材配图策略（优先级）：
1. longform-visual-notes — 长文核心知识转图（首选）
2. content-cover-gen — 封面图生成
3. image_generate — 兜底AI生图
```

### 从daily系列调用

```
# daily-gzh-content 配图阶段
优先调用 longform-visual-notes 生成文章配套视觉笔记图

# daily-xhs-content 配图阶段
优先调用 longform-visual-notes，图片比例改为 3:4

# daily-douyin-content 配图阶段
优先调用 longform-visual-notes，图片比例改为 16:9
```

## 依赖

| 依赖 | 说明 | 必需 |
|------|------|------|
| gemini-skill | gemini_generate_image MCP 工具，调用 Gemini 官网生图 | ✅（首选） |
| image_generate | 兜底生图（仅当 gemini-skill 不可用） | ⬜（兜底） |
| 内容文章 | 输入的长文 | ✅ |

## 质量标准

- [ ] 每张图包含清晰可读的中文文字
- [ ] 图片信息密度高（非空洞装饰）
- [ ] 有作者标注（如原文有作者）
- [ ] 无"AI生成"等水印
- [ ] 3-5张图覆盖文章核心内容
- [ ] prompt文件已保存（可复用）
- [ ] 图片保存到指定素材目录

## 铁律

1. **中文文字优先** — 图片必须含中文，清晰可读
2. **禁止AI水印** — 不得出现"由xx生成"等文字
3. **作者必须标注** — 原文有作者则图底部标明
4. **高信息密度** — 每张图都是知识载体，不是装饰
5. **4模块Prompt** — 生成提示词严格按 Main/Content/Context/Quality 结构
6. **优先 gemini-skill** — 通过 gemini_generate_image 调用 Gemini 生图，无需 API Key，文字生成质量最高，优先使用
7. **保存Prompt** — 每张图的提示词保存为.md文件，便于复用

## 更新日志

- **v1.2.0** (2026-08-05): 基于 AI剧漫剧 文章实测的稳定性优化
  - Phase 3 默认改为 `fullSize=false`（实测 `fullSize=true` 下载按钮 100% 失败，且会拖垮 MCP server）
  - 新增「网络前提」：Gemini 官网需经本地代理（Clash 7890 + Google 域名走代理）+ 自检命令
  - 新增 MCP 工具失灵排查（/mcp 重连 + 连浏览器一起重启）
- **v1.1.0** (2026-08-04): 切换生图后端至 gemini-skill
  - 弃用 qingyun-api（需额外 API Key），改用 gemini-skill 的 `gemini_generate_image` MCP 工具
  - 无需任何 API Key，通过 Gemini 官网生图
  - 新增长耗时工具调用规则（timeout ≥180000、进度同步、禁止提前结束）
  - 新增输出比例控制说明（无 size 参数，通过 prompt 控制比例）
- **v1.0.0** (2026-04-16): 初始版本
  - 4模块Prompt结构
  - 4种视觉风格（手写笔记/思维导图/架构图/对比矩阵）
  - qingyun-api gemini-3-pro-image 优先
  - daily系列skills集成指南
