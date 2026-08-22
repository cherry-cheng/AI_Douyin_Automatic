# 抖音创作者后台：选择器、按钮变体、上传与风控排坑

> 来自 douyin-smart-publish 实战 + 2026-08 排坑记忆。抖音是 React + CSS Modules，class 名含 hash，**优先按文本/placeholder 定位**。
>
> ⚠️ **但 ego-browser 不支持 `:has-text()` 伪类**（Playwright 专属语法，2026-08-21 实测报错）。「按文案找按钮」在 ego-browser 里的正确姿势 = **JS 遍历 `querySelectorAll('button')` 按文本精确匹配拿坐标 → CDP 点击**（见 SKILL.md Step 6 脚本）。下表 `has-text` 写法仅作元素/文案索引，不是可执行选择器。

## 平台入口
- 创作者中心：https://creator.douyin.com
- 内容上传：https://creator.douyin.com/creator-micro/content/upload
- **图文上传**：`?default-tab=3`
- **视频上传**：`?default-tab=1`（默认）
- 草稿箱：⚠️ **manage 页实际没有「草稿」tab**（2026-08-21 实测）。**草稿找回路径 = 打开 upload 页 → 点「继续编辑」**（出现「你还有上次未发布的图文，是否继续编辑？」提示即草稿在）

## 发布类型
| 类型 | URL 参数 | 说明 |
|------|---------|------|
| 视频 | `default-tab=1`(默认) | 短视频/长视频 |
| 图文 | `default-tab=3` | 图片轮播+描述 |
| 文章 | `default-tab=4` | 长文(≤8000字+30图) |

## UI 选择器参考
| 元素 | 定位策略 | 说明 |
|------|----------|------|
| 上传区域 | `input[type="file"]` / 按文案「上传视频」找 button | **先确认已登录**，未登录时可能为 0 |
| 描述输入 | `[class*="desc"] [contenteditable]` / `textarea` / `[placeholder*="添加作品描述"]` | 描述编辑区 |
| 话题输入 | 描述区中输入 `#` 触发话题搜索 | 弹窗选第一个匹配 |
| 封面选择 | `[class*="cover"]` / 封面编辑弹窗 | **默认不设（用抖音默认效果）**；编辑器「确定」按钮在自动化下关不掉，要设转人工 |
| 发布按钮 | 按文案「发布」找 button（`button.fixed-J9O8Yw.primary`） | 发布确认。⚠️ CDP 点击可能被吞，需 React onClick 直调兜底（见风控坑） |
| 草稿按钮 | 按文案「暂存离开」/「存草稿」/「草稿」找 button | **图文页常见为「暂存离开」**；fixed 主按钮同有被吞坑，React onClick 直调兜底 |
| 标题栏 | `input[placeholder*="标题"]` | ≤55 字（图文实测 ≤20 更稳） |

## 草稿按钮文案变体
| 文案 | 场景 |
|------|------|
| `存草稿` | 视频上传页 |
| `暂存离开` | 图文上传页（当前最常见） |
| `草稿` | 部分版本 |

ego-browser 点击时三个变体都试：`暂存离开` → `存草稿` → `草稿`（JS 文本匹配，**不是** `has-text` 选择器——ego-browser 不支持，见文首警告）。

## 登录判断（实战经验，别只看 URL）
- 即使 URL 已在 `creator-micro/*` 下，页面仍可能是扫码登录态
- 要同时检查 snapshot 文案：出现「扫码登录 / 二维码 / 抖音号登录」= 未登录
- 排查顺序：①确认是否真登录 → ②确认 `input[type=file]` 是否存在 → ③确认底部按钮文案变体 → ④才改 selector

## 图文上传完整判据
1. **定位 input（图文页主力 = 注入自己的 input）**，别只 `waitForElement('input[type=file]')`：
   - ① 先找抖音原生 input（`exposeImageInput`，主 DOM + shadowRoot，按 `/image|png|jpe?g|webp/i` 匹配 accept；找不到取第一个 `input[type=file]`），轮询 ~8s。视频页通常有。
   - ② 找不到 → **注入自己的 input**（`injectImageInput`，往上传区 append `input[type=file][multiple]#ego-injected-upload`）→ `uploadFile('#ego-injected-upload', paths)` 喂值 → dispatch change。**图文页靠这招**（2026-08-12 实测，抖音 dropzone 监听事件冒泡，照单全收）。
   - ③ 注入也失败 → `handOffTaskSpace` 转人工拖图。
   - 完整源码见 `references/upload-and-content.md` A2-A4
2. 多图：multiple input → 一次性 `uploadFile(sel, [所有路径])`；失败降级逐张（每次前 `input.value=''` + dispatch change）
3. **编辑器就绪 = `[contenteditable]` 描述区 + 「暂存离开」按钮同时出现**，且 10s 稳定窗口（上传状态探针见 A1）
4. 上传 toast 信号（被动读 `[class*=semi-toast-content-text]`）：成功=`上传成功`/`已添加 N 张`/`N/35`；上传中=`上传过程中`/`取消上传`；失败=`上传失败`/`网络错误`
5. **不要反复点「编辑封面」读 toast**，会干扰上传

## ⚠️ 风控坑（2026-08 实测，重要）
- **普通自动化 Chrome（Playwright CDP）的图文图片上传会被风控卡死**：永远卡在 `0% 0/N`，`media/upload/auth/v5` 返回 200 但字节不上传，控制台报 `[secsdk][csrf] setDowngradeLimit is not a function`
- 根因：抖音 secsdk 在 CDP 自动化环境签名失败，上传被静默拦截
- **ego lite 是反检测 Chromium，理论上能绕过**；但若仍卡 0%，按下方「转接管」处理
- **2026-08-11 新坑**：图文页整页可能**完全没有 `input[type=file]`**（主 DOM + shadow DOM + outerHTML 都没有，连点「点击上传」区都不挂载）——这不是风控拦字节，是 input 压根不挂载。此时走 fallback ③（CDP 注入）；若 CDP 也找不到 objectId，才走 ④ handOff。
- **2026-08-13 新坑：semi-design `fixed` 主按钮「点击被吞」**：发布按钮（`button.fixed-J9O8Yw.primary`）和封面编辑器「确定」按钮都是 fixed 定位 primary 主按钮。CDP 真实点击命中按钮本身（`elementFromPoint` 返回它、`isTrusted=true`、未禁用、`pointer-events:auto`）却**毫无反应**——非风控、非 disabled、非遮挡，事件被吞。
  - **封面确定按钮**：此坑无解（合成 click / CDP 真实点击 / React onClick 直调 / transform 上移全无效）→ 已改为**默认跳过封面**。
  - **发布按钮**：解法 = **React onClick 直调兜底**。从 `__reactProps` 取 `onClick` 用 mock event 调用。✅ 实测发布成功、未触发验证码、跳转 `/manage`。
  - **判断被吞**：CDP 点击后等 4s，snapshot 既无「正在发布/发布成功/验证码/滑块」任何信号 = 被吞 → 立刻 fallback React onClick，别反复点 CDP。完整脚本见 SKILL.md Step 8。

## 发布（非草稿）额外步骤
1. 等图片真正上传完（toast「请等待上传完成」消失）
2. **封面：默认不设，用抖音默认效果**（图文用第 1 张图、视频用首帧）。**不要自动化碰封面编辑器**——其「确定」按钮在自动化下关不掉弹窗（2026-08-13 真机实测，合成 click / CDP 真实点击 / React onClick 直调 / transform 上移全无效）。Daniel 要设封面就 `handOffTaskSpace` 让他手动设。
3. 「自主声明」下拉选「内容由AI生成」（发布时强制）

## 错误处理
| 错误 | 处理 |
|------|------|
| 登录过期 | `handOffTaskSpace` 交给 Daniel 扫码，别自己重试 |
| 滑块验证 | 暂停，`handOffTaskSpace` |
| 上传超时 | 转接管（见下），勿反复重试 |
| 描述过长 | 截断到 200 字并告知 |
| 频率限制 | 每天建议 ≤3 条，间隔 ≥30 分钟 |

## 转接管（出现任一即停）
1. 登录/风控：扫码、滑块、二次验证、「操作频繁」
2. 上传卡住 >8 分钟仍 0%，或描述区迟迟不出现
3. 发布/草稿按钮长时间 disabled 或点不动
4. 选择器漂移：描述区定位不到
5. 发布时被「请完成自主声明」拦截

处理：`await handOffTaskSpace(task.id)` + `captureScreenshot` + 告诉 Daniel 当前 URL/状态/草稿箱链接。**不要重复点击导致更强风控。**
