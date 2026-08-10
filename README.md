# Trae Agent First Project

基于 AI Agent 的可复用技能集合。每个技能封装为一组脚本 + 说明文档，可在 Claude Code / Trae 中直接调用。

## 技能

### toutiao-news-trends — 今日头条热点抓取

抓取今日头条（www.toutiao.com）热榜数据，包含：

- 热点标题、热度值、详情链接、封面图、标签
- **单篇热点正文内容**（标题、来源、发布时间、纯文本正文、互动数据）

#### 快速使用

```bash
SKILL=.claude/skills/toutiao-news-trends

node $SKILL/scripts/toutiao.js hot          # 热榜（默认 50 条）
node $SKILL/scripts/toutiao.js hot 10       # 热榜前 10 条
node $SKILL/scripts/toutiao.js detail <id>  # 单篇正文（文章 ID 或聚合 ID 均可）
node $SKILL/scripts/toutiao.js content 10   # 热榜 + 正文（前 10 条）
```

#### 正文抓取原理

正文来自移动端 info 接口 `https://m.toutiao.com/i{id}/info/`，免签名、免 Cookie，对两种 ID 都生效：

- **普通文章**：用热榜链接中 `/article/{id}` 提取的文章 ID
- **话题聚合**：直接用 `clusterId`（聚合页 ID）

脚本会自动清洗 HTML（剔除 `<img>`，将 `<p>` 转为换行），输出纯文本正文。

#### 输出示例

- `toutiao_hot_news.md` — 带正文的热榜报告示例（由 `content` 命令生成）

完整字段说明与注意事项见 [技能文档](.claude/skills/toutiao-news-trends/SKILL.md)。

## 目录结构

```
.
├── README.md               # 本文件
├── toutiao_hot_news.md     # 带正文的热榜报告示例
└── .claude/
    └── skills/
        └── toutiao-news-trends/
            ├── SKILL.md            # 技能说明文档
            └── scripts/
                └── toutiao.js      # 抓取脚本
```
