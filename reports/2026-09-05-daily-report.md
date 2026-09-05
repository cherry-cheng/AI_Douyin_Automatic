# 每日新闻抖音流水线日报 2026-09-05

## 概览

| 项 | 结果 |
|---|------|
| 选题 | 九月手机圈「Pro Max 大乱斗」（热榜 #31，热度 795,276，technology 分类） |
| 文章 | ✅ 25news_content/toutiao_technology_2026-09-05_九月ProMax大乱斗.md |
| 视觉笔记 | ✅ 4/4（07:35–07:40 由 Phase-1 生成，素材目录齐全） |
| 抖音草稿 | ✅（Phase-1 存草稿全要素：标题+描述+4 话题+BGM+AIGC） |
| 审批 | APPROVED（08:57:45，等待 ~68 分钟） |
| 发布 | ✅ 已发布（Phase-2 补跑完成，CDP 人类化点击一次成功，manage 页 `enter_from=publish` 确认） |
| 失败点 | ① Phase-1 07:49 发卡后提前退出（未消费审批结果）——两阶段机制按设计接管，无产出损失；② **审批窗内合盖睡眠杀断隧道**（08:32–08:52），08:53 首次点确认打到死 URL 报错——人工急救后 08:57 补发卡片重试成功（详见下方事故节） |
| 资源清理 | ✅ 关 1 space（douyin publish）/ /tmp 清 2 文件（详情 /tmp/cleanup_result.json） |

运行模式：launchd 7:00 定时 → Phase-1 提前退出 → **Phase-2 补跑**（两阶段+守护门设计当日实际生效）。

## 时间线（来自 ~/daily-news-douyin/logs/daily-2026-09-05.log）

- 07:14:55 Phase-1 启动（claude: ~/.npm-global/bin/claude，无 127）
- 07:34 文章落盘；07:35–07:40 四张视觉笔记生成
- 07:49:37 Phase-1 exit=0 退出——此时草稿已存、审批卡片已发飞书，但 claude 未做收尾（无 gate_done）
- 07:49:37 shell 层 Gate 接管等待（`--detach` 守护门独立于 claude 存活）
- 08:57:45 Daniel 飞书点「确认发布」（**补发卡片**）→ APPROVED 落盘 /tmp/douyin_approval_result.json

## 事故：合盖睡眠杀断审批隧道（已人工急救）

- **08:32:02 Mac 入睡**（pmset 日志 `Sleep Service Back to Sleep`）：07:32 起 DarkWake 预算耗尽后回睡，合盖状态下 `caffeinate -i` 拦不住（9/3 上线时注释已标注此缺口）。**08:52:50 开盖唤醒**（`LidOpen`）。
- 睡眠打断 cloudflared 边缘连接，醒后未重连成「植物人」：进程活着但零出站 TCP（健康时应常年挂 4 条长连接）。quick tunnel 随机域名绑定隧道实例，**旧卡片 URL 永久报废**。
- 08:53 Daniel 在旧卡片点「确认发布」→ trycloudflare 报错页；本地门/8848/草稿均无损，`douyin_approval_result.json` 不存在证实点击未到达。
- **急救（交互会话完成，<3 分钟）**：门不监控 cloudflared（杀隧道不影响门）→ 杀死死隧道、重开新隧道（带结果落盘即自杀的 wrapper 防孤儿）→ 用 current.json 里的**原 token** 复用 `send_feishu_card()` 补发新卡片（注明旧卡失效）→ 点新卡 = 点原卡，链路无损接回。
- **治本待办**：① run_daily.sh 的 `caffeinate -i -w $$` 加 `-s`（AC 下防合盖睡眠）；② await_approval.py 心跳时自检隧道出站连接，死则自动重开隧道+补发卡片（动 load-bearing 脚本前先读 SKILL.md）。
- 08:58:00 run_daily.sh 判定无 done 标记 → 拉起 Phase-2（本会话）
- ~09:05 Phase-2 完成恢复草稿→核验→发布→确认→清理→日报

## 详情

### Phase-1 挂点分析
- 日志末行：Phase-1 发卡后输出「轮询器在后台盯着结果文件，出结果会自动唤醒我继续」，随后 end_turn 退出。`claude -p` 单发模式下 end_turn 即进程结束，后台轮询器随会话消亡——**它无法被唤醒**，这是对运行模式的误判（与 8/22 事故同源的认知）。
- 幸运点：审批门 8/22 起已 `--detach` 守护化（双 fork 脱离进程树），门与结果文件独立存活，shell 层正确接管。**两阶段设计今日首次在真实 APPROVED 场景下端到端走通**。
- 结论：无产出损失（草稿全要素在、审批结果在），Phase-2 无缝续跑。属设计内降级路径，非事故。

### Phase-2 发布过程（douyin-ego-publish）
1. **恢复草稿**：重开 upload 页（`?default-tab=3`）→「你还有上次未发布的图文，是否继续编辑？」在 → CDP 点击「继续编辑」→ 编辑页就绪（「暂存离开」+描述区在）。
2. **核验（全绿，无需补）**：
   - 标题「六家Pro Max大乱斗，别被参数裹挟」✅（与审批卡标题一致）
   - 描述全文 + 4 话题实体（旗舰手机/手机选购/数码科技/科技资讯，`data-mention="#"` 计数）✅
   - 「已添加4张图片」✅
   - 配乐锚定判定 ✅：空态提示「点击添加合适作品风格音乐」消失 + 入口按钮(pointer+svg)变「修改音乐」，已选「动感科技」（未用全页正则，8/23 教训）
   - AIGC ✅：「自主声明 → 内容由AI生成」——恢复草稿**未**重置 AIGC（顺序坑未触发）；发布前二次复查仍 ✅
   - 发布设置「立即发布」✅
3. **发布**：预热滚动（测坐标前完成）→ 发布按钮 scrollIntoView 等 2.8s 停稳 → 测坐标 (340,672) 视口安全区内 → **CDP 单步 mouseMoved + press/release(buttons:1) 一次成功**，未触发短信验证码/滑块（无需 React onClick 兜底、无需验证码中继）。
4. **成功确认**：URL 跳 `creator-micro/content/manage?enter_from=publish` + manage 页内容在；截图 /tmp/douyin_published_0905.png。

### 与 9/4 的对比（CDP 可用性）
- 9/4 CDP dispatchMouseEvent 全程限流，被迫改 js scrollTo + React onClick 直调；**今日 CDP 点击完全正常一次过**——CDP 限流是间歇性的（可能与当日系统负载/连接数相关），发布脚本保留双路径（CDP 优先 + React 兜底）是正确姿势，勿因昨日限流直接砍掉 CDP 路径。

### 收尾
- task space 47「douyin publish」正常关闭（keep:false）。
- cleanup_resources.py：无残留 space，/tmp 清 2 文件。
- /tmp/daily_gate_done 已补写（`2026-09-05 APPROVED published`）。
- git：Phase-2 会话白名单不含 git（8/31 先例），产物留工作区，待交互会话补 commit。

## 产物清单
- 文章：`25news_content/toutiao_technology_2026-09-05_九月ProMax大乱斗.md`
- 4 张图：`25news_content/素材/visual-note-01-封面.png` / `-02-对比矩阵.png` / `-03-逻辑链.png` / `-04-总结.png`
- prompts：`25news_content/素材/prompts/`
- Phase-2 过程脚本：`/tmp/ego_p2_probe.js` / `ego_p2_restore.js` / `ego_p2_verify.js` / `ego_p2_publish.js`
- 发布留证：`/tmp/douyin_published_0905.png`

## 下一步建议
- Phase-1 提示词可加一句纠偏：发卡后**不要**描述「轮询器会唤醒我」——`-p` 模式下应直接说明「等审批期间退出是预期行为，收尾由 Phase-2 完成」，避免日报/日志出现误导性叙述。
- 今日两阶段链路（守护门 → shell Gate → Phase-2 恢复草稿 → 发布）全绿，可视为该设计的验证样本；若后续想减少 Phase-2 依赖，可研究 claude 会话内挂起等外部文件变化的可行方案（此前 run_in_background 方案已被 8/22 事故否决，勿回退）。
