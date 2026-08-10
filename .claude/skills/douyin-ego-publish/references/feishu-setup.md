# 飞书审批门：一次性配置

审批机制：本地起一个 HTTP 回调服务 → cloudflared 临时隧道把它暴露成公网 URL → 飞书卡片上的「✅确认发布 / ❌取消」按钮用 open_url 指向该 URL → Daniel 点击即一次 GET → 本地收到信号 → 脚本继续点发布。

**为什么用 open_url 按钮而不是飞书回调订阅**：open_url 按钮点击就是一次普通网页访问，不需要在飞书预注册回调地址，因此**临时隧道的 URL 每次变也没关系**，零额外配置。纯自定义机器人 webhook 即可。

## 三步配置

### 1. 飞书群自定义机器人
1. 在飞书群里：群设置 → 群机器人 → 添加机器人 → **自定义机器人**
2. 起个名字（如「抖音发布审批」），保存
3. 拿到 **webhook URL**：`https://open.feishu.cn/open-apis/bot/v2/hook/xxxx`
4. （可选但推荐）安全设置选 **「加签」**，拿到 secret（`SECxxxx`）

> 不要选「自定义关键词」安全校验——会和卡片消息冲突。

### 2. 安装 cloudflared
临时隧道用，无需 Cloudflare 账号。

**macOS 13 注意**：homebrew 在 mac13 **没有 cloudflared 的预编译包**（`no bottle available`），`brew install cloudflared` 会失败。改用官方二进制：

```bash
# Intel (x86_64)
curl -fL -o /tmp/cloudflared.tgz \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz"
# Apple Silicon 换 cloudflared-darwin-arm64.tgz
tar -xzf /tmp/cloudflared.tgz -C /tmp
install -m 0755 /tmp/cloudflared ~/.local/bin/cloudflared
xattr -dr com.apple.quarantine ~/.local/bin/cloudflared 2>/dev/null || true
~/.local/bin/cloudflared --version
```

**墙网慢**：GitHub 直连可能只有 ~13KB/s（19MB 要 25 分钟）。本机有 Clash 代理 7890，加 `-x http://127.0.0.1:7890` 走代理，25 秒下完。

> 已安装情况：本机已装在 `~/.local/bin/cloudflared`（v2026.7.3），无需重复。

### 3. 写配置文件
```bash
mkdir -p ~/.config/douyin-ego-publish
cat > ~/.config/douyin-ego-publish/config.json <<'EOF'
{
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/把你的换上",
  "feishu_secret": "SEC把你的换上或留空字符串",
  "approval_port": 8848,
  "approval_timeout_sec": 540
}
EOF
```
- `approval_port`：本地回调服务端口，8848 被占会自动换空闲端口
- `approval_timeout_sec`：等待 Daniel 点击的最长时间，默认 540 秒(9 分钟)，受 Claude Code 单次 Bash 超时(10 分钟)限制，**不要设超过 560**

## 验证
配好后，让 Claude 跑一次 dry-run（或直接在 SKILL.md Step 7 触发一次），飞书群里应收到一张橙色标题「🎬 抖音发布待审批」卡片，带预览和两个按钮。点「确认发布」会打开一个绿色「✅ 已确认发布」页面，Claude 那边脚本会返回 `RESULT=APPROVED`。

## 安全说明
- 每次发布生成随机 token，按钮 URL 带 token，无 token 或 token 不对的请求一律 404
- 隧道 URL 是随机英文词，难猜；用完（脚本退出）隧道立即关闭
- 这是个人审批工具，token+随机域名足够；如需更强可加固定签名校验

## 排错
| 现象 | 原因 / 处理 |
|------|------|
| `RESULT=NOCONFIG` | config.json 不存在或缺 webhook，重做第 3 步 |
| `RESULT=NO_CF` | cloudflared 没装/不在 PATH，`brew install cloudflared` |
| `RESULT=SEND_FAILED` | webhook URL 错或加签 secret 不匹配；检查 URL 和 secret |
| `RESULT=TIMEOUT` | 9 分钟没点；可调大 `approval_timeout_sec` 或下次快点 |
| 飞书收到卡片但按钮点了没反应 | 隧道可能掉了；看脚本输出里 `🌐 隧道已就绪` 那行的 URL 是否能在浏览器打开 |
| 加签报 `sign match fail` | secret 复制错了，或选了「自定义关键词」而非「加签」 |
