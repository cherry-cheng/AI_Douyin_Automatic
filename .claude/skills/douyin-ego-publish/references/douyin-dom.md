# 抖音创作者后台：选择器、按钮变体、上传与风控排坑

> 来自 douyin-smart-publish 实战 + 2026-08 排坑记忆。抖音是 React + CSS Modules，class 名含 hash，**优先用文本匹配 `has-text` 或 `placeholder` 定位**。

## 平台入口
- 创作者中心：https://creator.douyin.com
- 内容上传：https://creator.douyin.com/creator-micro/content/upload
- **图文上传**：`?default-tab=3`
- **视频上传**：`?default-tab=1`（默认）
- 草稿箱：https://creator.douyin.com/creator-micro/content/manage

## 发布类型
| 类型 | URL 参数 | 说明 |
|------|---------|------|
| 视频 | `default-tab=1`(默认) | 短视频/长视频 |
| 图文 | `default-tab=3` | 图片轮播+描述 |
| 文章 | `default-tab=4` | 长文(≤8000字+30图) |

## UI 选择器参考
| 元素 | 定位策略 | 说明 |
|------|----------|------|
| 上传区域 | `input[type="file"]` / `button:has-text("上传视频")` | **先确认已登录**，未登录时可能为 0 |
| 描述输入 | `[class*="desc"] [contenteditable]` / `textarea` / `[placeholder*="添加作品描述"]` | 描述编辑区 |
| 话题输入 | 描述区中输入 `#` 触发话题搜索 | 弹窗选第一个匹配 |
| 封面选择 | `[class*="cover"]` / 封面编辑弹窗 | 视频帧或自定义 |
| 发布按钮 | `button:has-text("发布")` | 发布确认 |
| 草稿按钮 | `button:has-text("暂存离开")` / `button:has-text("存草稿")` / `button:has-text("草稿")` | **图文页常见为「暂存离开」** |
| 标题栏 | `input[placeholder*="标题"]` | ≤55 字（图文实测 ≤20 更稳） |

## 草稿按钮文案变体
| 文案 | 场景 |
|------|------|
| `存草稿` | 视频上传页 |
| `暂存离开` | 图文上传页（当前最常见） |
| `草稿` | 部分版本 |

ego-browser 点击时三个变体都试：`暂存离开` → `存草稿` → `草稿`。

## 登录判断（实战经验，别只看 URL）
- 即使 URL 已在 `creator-micro/*` 下，页面仍可能是扫码登录态
- 要同时检查 snapshot 文案：出现「扫码登录 / 二维码 / 抖音号登录」= 未登录
- 排查顺序：①确认是否真登录 → ②确认 `input[type=file]` 是否存在 → ③确认底部按钮文案变体 → ④才改 selector

## 图文上传完整判据
1. `input[type=file]` 出现（轮询 ~12-20s，别单次检测）
2. `uploadFile` 后，**编辑器就绪 = `[contenteditable]` 描述区 + 「暂存离开」按钮同时出现**
3. 被动读 toast `[class*=semi-toast-content-text]`：等「请等待上传完成」消失
4. **不要反复点「编辑封面」读 toast**，会干扰上传

## ⚠️ 风控坑（2026-08 实测，重要）
- **普通自动化 Chrome（Playwright CDP）的图文图片上传会被风控卡死**：永远卡在 `0% 0/N`，`media/upload/auth/v5` 返回 200 但字节不上传，控制台报 `[secsdk][csrf] setDowngradeLimit is not a function`
- 根因：抖音 secsdk 在 CDP 自动化环境签名失败，上传被静默拦截
- **ego lite 是反检测 Chromium，理论上能绕过**；但若仍卡 0%，按下方「转接管」处理

## 发布（非草稿）额外步骤
1. 等图片真正上传完（toast「请等待上传完成」消失）
2. 「封面设置」选一张图作封面（不选会被「没有选择封面」拦截）
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
4. 选择器漂移：描述区/封面弹窗定位不到
5. 发布时被「请先选择封面 / 请完成自主声明」拦截

处理：`await handOffTaskSpace(task.id)` + `captureScreenshot` + 告诉 Daniel 当前 URL/状态/草稿箱链接。**不要重复点击导致更强风控。**
