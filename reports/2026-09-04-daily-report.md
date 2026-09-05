# 每日新闻抖音流水线日报 2026-09-04

## 概览

| 项 | 结果 |
|---|------|
| 选题 | 苹果折叠屏 iPhone Ultra（热榜 #29，热度 870,591） |
| 文章 | ✅ 24news_content/toutiao_technology_2026-09-04_iPhoneUltra折叠屏.md |
| 视觉笔记 | ✅ 4/4（等待 14s/20s/18s/16s，零重试） |
| 抖音草稿 | ✅（标题+描述 154 字+4 话题实体化+BGM+AIGC 全要素） |
| 审批 | APPROVED（等待 ~5.5 分钟） |
| 发布 | ✅ 已发布（manage 列表确认：2026-09-04 07:21 已发布，4 张图） |
| 失败点 | 无致命失败；2 个非致命坑（CDP 限流、manage 虚拟列表）均已绕过，见详情 |
| 资源清理 | ✅ 关 1 space（douyin publish）/ /tmp 清 2 文件（详情 /tmp/cleanup_result.json） |

运行模式：手动会话（用户指令触发完整流水线，非 launchd 定时）。

## 详情

### 选稿
- rank 4（热度 10.6M）正文仅 ~150 字，太薄弃；rank 18 正文 305 字边缘薄弃。
- rank 29「苹果折叠屏」正文 718 字，数据密度最佳（关键数据表凑满 12 行），选定。
- clusterId 7681130841283723827。

### 视觉笔记（longform-visual-notes）
- 4 张全 572×1024（9:16），PNG 有效性 IHDR 校验通过，analyze_image 抽查中文清晰、无水印。
- 全部快速路径出图（等待 14s/20s/18s/16s），零重试零重开 session。
- 03 因果链用了手写笔记风（白板风连败禁用），4/4 一次过。

### 抖音发布（douyin-ego-publish）
- 上传：原生 input `#vp2-douyin-image` array 模式 4/4。
- 内容：标题「苹果折叠屏卖1.5万，先砍FaceID」+ 描述 154 字 + 4 话题全部实体化（`data-mention="#"` 结构核验），无残留。
- 配乐：**「动感科技 | Kasol | 01:52」**，锚定核验 ✅（空态提示消失 + 入口变「修改音乐」，未用全页正则）。
- AIGC：「内容由AI生成」已设置（selectBox `selectText-XSrMFZ selected-Vx6wO5` 类核验）。⚠️ 复查脚本一次误报——「自主声明」label 与 selectBox 是**兄弟列**，zone 探测法在此布局失效，须按 selectBox selected 类判。
- 草稿：暂存离开（React onClick 直调）✅；草稿恢复核验：重开 upload 页点「继续编辑」后标题/描述/话题/配乐全在 ✅。

### 坑与绕法（今日新沉淀）
1. **「继续编辑」是 span 不是 button**：CDP 点击被吞 10 次（熔断上限内停手）→ DOM 探查发现 `span.hint-text-mk8oZE.continue-s888XU` 带 React onClick → 直调成功。
2. **CDP dispatchMouseEvent 再限流**：发布脚本 warmup 滚动阶段即超时死亡 → 整个发布改 js scrollTo + React onClick 直调 fixed 主按钮，一次成功。
3. **manage 列表虚拟化**：发布后按标题搜列表 initially 不命中（条目不滚动不渲染）→ 滚动列表容器后条目渲染，确认今日作品在列（**不是没发出去**）。以后验发布别只信首轮 innerText。

### 审批与发布
- 审批门 `--detach` 守护化启动，~5.5 分钟后读得 APPROVED。
- 发布点击：React onClick 直调，无验证码、无滑块。
- 成功信号：URL 跳 `/content/manage?enter_from=publish` + manage 列表出现今日作品（07:21 已发布）。
- 发布后确认截图：/tmp/douyin_published_manage.png、/tmp/douyin_manage_scrolled.png。

### 收尾
- cleanup_resources.py：关 1 space（douyin publish），清 2 个 /tmp 临时文件。
- /tmp/daily_gate_done 已写（`2026-09-04 APPROVED published`）。

## 产物清单
- 文章：`24news_content/toutiao_technology_2026-09-04_iPhoneUltra折叠屏.md`
- 4 张图：`24news_content/素材/visual-note-01-封面.png` / `-02-对比矩阵.png` / `-03-因果链.png` / `-04-总结.png`
- 4 个 prompt：`24news_content/素材/prompts/01-cover.md` ~ `04-summary.md`
- 过程脚本：`.tmp_ego/ego_note_01.js`、`.tmp_ego/ego_douyin_01~21_*.js`

## 下一步建议
- 「继续编辑 = span」「manage 虚拟列表」两条新坑建议回写 douyin-ego-publish SKILL.md（本日报已记录细节）。
- 今天为手动会话运行；launchd 7:00 若也已触发需留意防重入锁是否拦住（无重复发布迹象，作品列表仅一条今日内容）。
