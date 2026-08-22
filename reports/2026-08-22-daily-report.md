# 每日新闻抖音流水线日报 2026-08-22

## 概览

| 项 | 结果 |
|---|------|
| 选题 | 荣耀"平板手机"会掀起形态复兴吗（热榜 #27，热度 164 万，technology 分类） |
| 文章 | ✅ `13news_content/toutiao_科技_2026-08-22_荣耀平板手机形态复兴.md`（3085 字） |
| 视觉笔记 | ✅ 4/4 全部一次过（封面 24s / 对比矩阵 26s / 逻辑链 26s / 总结 22s） |
| 抖音草稿 | ⚠️ 定时段草稿未存住（React 直调返回成功但保存未生效，且旧验证法误判）；晚间重建后 ✅ 验证通过 |
| 审批（定时段） | ❌ 门被误杀：claude 08:44 提前退出 → 审批门成孤儿被兜底清理收割 → 隧道死 → Daniel 点击报错 |
| 审批（补发段） | ✅ APPROVED（19:58，新 --detach 守护门） |
| 发布 | ✅ 已发布、审核中（manage 页确认：4张图文在列表首位） |
| 资源清理 | ✅ 定时段关 2 space + 补发段关 1 space / 临时文件已清 |

## 详情

### 定时段（08:00-08:44）
- 流水线本体全通：自检 ①~⑤ → 选稿（5 候选唯一科技类）→ 文章 → 4 图零重试 → 填内容+配乐「动感科技」+AIGC → 存草稿（React 直调）→ 审批门起跑（run_in_background）
- **事故**：claude 发完进度文本即 `end_turn` 退出（前 4 天都有 TaskOutput 保活循环，当天没做）→ 审批门成孤儿 → 兜底清理杀门+隧道 → Daniel ~10 点点飞书「确认发布」打到死 URL 报错
- **次生发现**：`start_tunnel` 旧正则会截胡 `api.trycloudflare.com`（非隧道域，概率性竞态）
- **草稿丢失**：定时段的「暂存离开」React 直调虽返回成功，实际保存未生效；且验证在未刷新 tab 上测（`继续编辑`来自页面残留文案）→ 误判已存。晚间开 upload 页无提示坐实草稿不存在

### 根治改造（当天完成并实测）
1. **`await_approval.py` v0.3.0**：`--detach` 双 fork 守护化（门独立于 claude，只由 timeout 决定生死）；活门登记 `/tmp/douyin_approval_current.json`（pid+60s 心跳）；终态写 `/tmp/douyin_approval_result.json`（全路径含 KILLED/SEND_FAILED/NO_CF）；防叠门；SIGTERM 也落盘；隧道正则改双正则（横幅优先+多词随机子域，排除 api./www.）；修 APPROVE_HTML 双花括号
2. **`run_daily.sh` 两阶段**：Phase1 claude（--detach 起门+轮询结果文件+收尾写 `/tmp/daily_gate_done`）→ shell 层 Gate 等结果（门活就等，最长 timeout+600s；门死无结果写 KILLED）→ 无 done 标记则 Phase2 补跑 claude 消费结果（APPROVED→恢复草稿发布；其余保草稿）→ 兜底清理殿后（活门豁免）。陈锁 3h→4h。已 cp 同步 `~/daily-news-douyin/`
3. **`cleanup_resources.py` 活门豁免**：current.json 登记的活门（pid 活+python3 直跑）不杀；未登记审批门 etime>3h15m 才 TERM；修 bash -c 包装命令误匹配（须 `^python3?\s` 开头）

### 补发段（19:00-20:00）
- 重建：step1 开页 → step2 上传 4 图（原生 input 一次成）→ step3 标题/描述/4 话题 → **修描述吞字**（`爆耀`→`爆料称荣耀`，Range 选中+insertText，话题实体无损）→ step4 配乐（动感科技，37.6万人使用那首）→ step5 AIGC → step6 存草稿（CDP 被吞→React 直调生效，以「离开编辑器」判据确认）
- **草稿验证升级**：全新开 tab 强刷 upload 页 → 「继续编辑」提示在 → 点恢复 → 标题 13 字/描述含修复文本/4 话题实体/4 图/配乐/AIGC 七项全过 + 截图
- 审批门 `--detach` 起跑（pid 5016）→ Daniel 19:58 点确认 → `RESULT=APPROVED` 落盘
- 发布：CDP 单步点击**一次生效**（未触发验证码、未走兜底）→ URL 跳 `/content/manage?enter_from=publish` → manage 页作品列表首位「4张 7.5英寸平板手机杀回来了…」审核中 ✅

### 发布内容
- 标题：`7.5英寸平板手机杀回来了`（13/20）
- 描述：钩子（嫌弃屏幕不够大了 📱）+ 荣耀 7.5 英寸 16:10 宽屏/骁龙旗舰/万级电池/主动散热 + AI 手机爆发年归因 + CTA（裤兜塞得下吗/评论区聊聊 👇）
- 话题：#平板手机 #荣耀手机 #数码科技 #科技资讯（4/4 实体化）
- 配乐：动感科技（抖音音乐库）✅；AIGC「内容由AI生成」✅（发布前复查过）

## 产物清单
- 文章：`13news_content/toutiao_科技_2026-08-22_荣耀平板手机形态复兴.md`
- 图 1-4：`13news_content/素材/visual-note-0{1..4}-*.png`
- Prompt：`13news_content/素材/prompts/01~04-*.md` + douyin-step1~6.js（发布全流程脚本）
- 发布后截图：`/tmp/douyin_after_publish.png`（CDN 留证）

## 经验固化（当日已回写 SKILL/脚本/记忆）
- 审批门架构：守护化+两阶段+活门豁免（await_approval.py v0.3.0 / run_daily.sh / cleanup_resources.py / SKILL.md×2 / 记忆 approval-gate-detach-2026-08-22）
- **草稿验证必须新开 tab 强刷**（旧 tab 会有残留文案误判）——已作为硬规则写入补发实践
- has-text 不可用 / 暂存离开 React 直调 / manage 页无草稿 tab → 上轮已回写，本轮全部实战复用生效

## 下一步建议
1. 观察作品审核结果（正常 1-2h，若未通过按抖音通知调整）
2. 明早 8:00 定时轮将首次全流程跑新架构（--detach 门+两阶段），留意日志 `~/daily-news-douyin/logs/daily-2026-08-23.log`
3. git 提交今日全部修复（脚本+SKILL+日报）
