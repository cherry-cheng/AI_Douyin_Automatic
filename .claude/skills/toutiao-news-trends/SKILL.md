---
name: toutiao-news-trends
description: 获取今日头条(www.toutiao.com)新闻热榜/热搜榜数据，包含时政要闻、财经、社会事件、国际新闻、科技发展及娱乐八卦等多领域的热门中文资讯，并输出热点标题、热度值、跳转链接，以及单篇热点正文内容。
---

# 今日头条新闻热榜

## 技能概述

此技能用于抓取今日头条 PC 端热榜（hot-board）数据，包括：
- 热点标题
- 热度值（HotValue）
- 详情跳转链接（去除冗余查询参数，便于分享）
- 封面图（如有）
- 标签（如"热门事件"等）
- **正文内容**（标题、来源、发布时间、纯文本正文、互动数据）

数据来源：今日头条 (www.toutiao.com)

## 获取热榜

获取热榜（默认 50 条，按榜单顺序返回）：

```bash
node scripts/toutiao.js hot
```

获取热榜前 N 条：

```bash
node scripts/toutiao.js hot 10
```

## 获取正文内容

本技能支持抓取单条热点的**正文**，数据来自移动端 info 接口 `https://m.toutiao.com/i{id}/info/`。
该接口免签名、免 Cookie，对两种 ID 均生效：
- **普通文章**：用热榜 `link` 中 `/article/{id}` 提取的文章 ID
- **热点聚合（话题）**：直接用 `clusterId`（话题聚合页 ID），同样会返回该热点的正文

### 抓取单篇正文

```bash
# id 可为热榜中的文章 ID 或聚合 clusterId
node scripts/toutiao.js detail 7666646939391639615
```

### 热榜 + 正文（批量）

抓取热榜并为每条补充正文（默认 10 条；条与条之间内置 250ms 间隔以规避风控）：

```bash
# 热榜前 5 条 + 正文
node scripts/toutiao.js content 5
```

> 批量抓取默认上限 50 条；正文请求较慢，建议按需指定较小的 limit。

## 返回数据字段说明

### 热榜条目（hot）

| 字段 | 类型 | 说明 |
|------|------|------|
| rank | number | 榜单排名（从 1 开始） |
| title | string | 热点标题 |
| popularity | number | 热度值（HotValue，已转为数字；解析失败时为 0） |
| link | string | 热点详情链接（已清理 query/hash） |
| cover | string \| null | 封面图 URL（如有） |
| label | string \| null | 标签/标识（如有） |
| clusterId | string | 聚合 ID（字符串化） |
| categories | string[] | 兴趣分类（如有） |

### 正文条目（detail）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 文章 ID / 聚合 ID |
| title | string | 正文标题 |
| source | string \| null | 来源 / 媒体名 |
| publishTime | string \| null | 发布时间（YYYY-MM-DD HH:mm:SSZ，UTC） |
| url | string \| null | 正文原文链接 |
| isHot | boolean | 是否为热榜事件 |
| contentText | string | 正文纯文本（HTML 已清洗，段落以换行分隔） |
| contentHtml | string | 正文原始 HTML（含 `<p>`、`<img>` 等） |
| diggCount | number | 点赞数 |
| commentCount | number | 评论数 |
| repostCount | number | 转发数 |

### 批量结果（content）

返回热榜条目数组，每条在其基础上增加两个字段：
- `detail`：正文对象（同上）；失败时为 `null`
- `detailError`：抓取失败时的错误信息，成功时为 `null`

## 注意事项

- 该接口为网页端公开接口，返回结构可能变动；若字段缺失可适当容错
- 访问频繁可能触发风控，脚本内置随机 User-Agent、超时控制与请求间隔
- 正文抓取使用移动端 UA + 移动端 Referer，以匹配 info 接口预期
- 个别热点可能无正文（如纯视频/图集），届时 `detailError` 会给出原因，不影响其余条目
