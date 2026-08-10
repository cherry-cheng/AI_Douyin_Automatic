---
name: douyin-ego-publish
description: "用 ego lite 浏览器（ego-browser）把本地图文或视频发布到抖音创作者后台：内容适配→上传→填标题/描述/#话题→封面→先存草稿→飞书发审批卡片等 Daniel 确认→确认后才点发布。默认只存草稿；只有 Daniel 在飞书点「确认发布」后才自动发布。覆盖图文(2-35张)/视频、标题(≤55字)、描述(≤200字)、#话题(3-5个)、封面(用户提供优先否则自动选)、配乐BGM(默认从抖音音乐库按内容主题自动选)、AIGC「内容由AI生成」声明。基于 ego-browser 自动化（复用登录态，绕过扫码风控）。触发：'发抖音'、'抖音发布'、'发图文到抖音'、'抖音视频'、'douyin publish'、'传到抖音'、'发布短视频'、'把这几张图发抖音'。只要用户提到要把本地图片或视频发到抖音，就用这个技能。"
author: Daniel Li
version: 0.1.0
---

# 抖音发布（ego-browser + 飞书审批门）

把本地图文/视频发到抖音，全程用 **ego-browser** 自动化；发布前必须经 **飞书审批卡片** 确认。

## 两个铁律

1. **默认只存草稿。** 自动化把标题/描述/话题/封面/AIGC 声明都填好、存为草稿、截图。**绝不自动点「发布」。**
2. **只有 Daniel 在飞书点「确认发布」后，才点发布。** 飞书审批由 `scripts/await_approval.py` 负责：起一条 cloudflared 临时隧道，发一张带「✅确认发布 / ❌取消」按钮的卡片到飞书，按钮用 open_url 指向隧道，点击即触发本地回调 → 脚本在同一个回合内阻塞拿到结果 → 通过才继续点发布。

## 前置依赖（一次性配置）

读 `references/feishu-setup.md` 完成以下三项，配好后写到 `~/.config/douyin-ego-publish/config.json`：

1. **ego lite 已装且登录抖音**（`ego-browser` 命令可用，creator.douyin.com 已登录）。
2. **飞书自定义机器人**：建一个群机器人，拿到 webhook URL（和加签 secret，若启用）。
3. **cloudflared**：`brew install cloudflared`（临时隧道用，无需账号）。

config.json 模板：
```json
{
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx",
  "feishu_secret": "SECxxxx 或留空",
  "approval_port": 8848,
  "approval_timeout_sec": 540
}
```

> 若 `config.json` 缺失或字段不全，先引导 Daniel 完成 `references/feishu-setup.md`，不要硬跑。

## 发布流程

### Step 0 — 搞清输入

从 Daniel 的话里确定：
- **类型**：图文（图片 2-35 张）还是视频（单个视频文件）。拿不准就问。
- **素材文件**：本地绝对路径。图文要 ≥2 张；图片格式 JPG/PNG/WebP（**不支持 GIF**），单张 ≤50MB；视频 MP4/WebM，竖屏 9:16 最优。
- **标题**：≤55 字（可选；不给就不填或从内容提炼，先问）。
- **描述 + #话题**：可选；不给就按 `templates/desc-template.md` 和 `references/content-rules.md` 起草，**起草后让 Daniel 过目**再填。
- **封面**：Daniel 给了封面图就用他的；**没给就自动选第 1 张已上传图**（图文）/ 视频首帧（视频）。
- **配乐/BGM**：默认自动配一首贴合氛围的（**只从抖音音乐库选**，自动授权、无版权风险，别上传本地音频）；Daniel 可指定风格（如「科技感/lofi/大气」）或要求不配。
- **是否 AIGC**：默认开启「内容由AI生成」声明（发布时强制，存草稿不强制）。

素材格式/数量不符先指出，别硬传。完整规则见 `references/content-rules.md`。

### Step 1 — 用 ego-browser 打开上传页并确认登录

通过 `Bash` 工具跑 `ego-browser nodejs <<'EOF' ... EOF`（所有浏览器操作都走这条路，**不要**先写 .js 文件）。详见 ego-browser skill。

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')
cliLog('task id: ' + task.id)

// 图文: default-tab=3 ；视频: default-tab=1
const url = 'https://creator.douyin.com/creator-micro/content/upload?default-tab=3'
await openOrReuseTab(url, { wait: true, timeout: 30 })

// 确认登录：creator 后台即使 URL 对，仍可能是扫码登录态
const snap = await snapshotText()
cliLog(snap)
EOF
```

**登录判断**（来自实战，别只看 URL）：snapshot 里若出现「扫码登录 / 二维码 / 抖音号登录」字样 → **未登录**。ego-browser 复用 ego lite 的登录态，正常应已登录。若未登录：用 `await handOffTaskSpace(task.id)` 把控制权交给 Daniel 扫码，**不要自己重试**；等 Daniel 说「好了」再用 `takeOverTaskSpace(task.id)` 继续。

### Step 2 — 上传素材

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')
// input[type=file] 在重 SPA 里要轮询出现，别单次检测
await waitForElement('input[type="file"]', { timeout: 20 })
// 图文：逐张上传（uploadFile 单文件，多图循环）
await uploadFile('input[type="file"]', '/abs/path/img1.jpg')
await uploadFile('input[type="file"]', '/abs/path/img2.jpg')
// 视频：单个文件
// await uploadFile('input[type="file"]', '/abs/path/video.mp4')
await wait(3)
cliLog(await snapshotText())
EOF
```

**图文上传完成的判据**：编辑器就绪 = 出现 `[contenteditable]` 描述区 **且** 底部出现「暂存离开」按钮。用 `snapshotText()` 看到这两样才算上传成功。

⚠️ **风控坑**（来自过往实测）：若图片上传一直卡在 `0% 0/N`（auth 接口 200 但字节不上传），是抖音风控在自动化环境拦上传。**别死磕、别反复点「编辑封面」**——立刻 `handOffTaskSpace` 交给 Daniel 在 ego lite 里手动拖图，然后接管继续。被动读 toast 用 `[class*=semi-toast-content-text]` 即可。

### Step 3 — 等上传/转码彻底完成

图文：被动读 toast，等「请等待上传完成」消失后再操作。视频：等转码完成（进度条到头、出现可编辑描述区）。

### Step 4 — 填标题 + 描述 + #话题

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')
// 填写也留人类节奏：字段之间随机停顿（理由见下方「反检测要点」）
// 标题：input[placeholder*='标题']，≤55字
await fillInput('input[placeholder*="标题"]', '你的标题')
await wait(0.6 + Math.random() * 1.2)
// 描述：contenteditable 描述区
await fillInput('[class*="desc"] [contenteditable]', '描述文字 #话题1 #话题2 #话题3')
// 话题：在描述里输入 # 会触发话题搜索弹窗，选第一个匹配项确认；或直接把 #话题 作为纯文本写入
cliLog(await snapshotText())
EOF
```

描述/话题起草规则见 `references/content-rules.md` 与 `templates/desc-template.md`：1 句钩子 + 1-2 句说明 + 1 句 CTA；话题 3-5 个（1-2 精准 + 2-3 泛），别堆「上热门/涨粉」低质话题。

### Step 5 — 封面 + 配乐（BGM）

**封面**：
- Daniel 给了封面图 → 上传/选用该图。
- 没给 → **自动选第 1 张已上传图**（图文）/ 视频首帧（视频）。不选封面发布时会被「没有选择封面」拦截。

**配乐（BGM）**：图文/视频都能在编辑器里配乐，**默认要配**（无配乐的图文观感差、完播低）。只从抖音音乐库选（自动授权、无版权风险），**不要上传本地音频**。配乐不是敏感动作，用普通 `click` 即可，不必走发布那套人类化点击。

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')

// 配乐入口文案/DOM 以 snapshot 为准（class 是 hash，靠文本定位）。先打开配乐面板：
const entry = await js(String.raw`(() => {
  const want = ['添加音乐','选择音乐','配乐','选择配乐'];
  const hit = [...document.querySelectorAll('button,div,span,a')].find(n => {
    const t = (n.textContent || '').trim();
    return t.length < 8 && want.some(w => t === w || t.includes(w)) && n.offsetParent !== null;
  });
  if (!hit) return null;
  const r = hit.getBoundingClientRect();
  return { x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2) };
})()`)

if (!entry) {
  cliLog('ℹ️ 没找到配乐入口（可能已配乐/该图集无配乐入口），跳过配乐')
} else {
  await click([entry.x, entry.y], { label: '打开配乐面板' })
  await wait(1.5)

  // ① 优先「推荐/热门」里挑一首贴合的（算法推荐≈当前热门，曝光更高）
  await click('xpath=(//*[normalize-space(text())="推荐" or normalize-space(text())="热门"])[1]', { label: '切推荐/热门' }).catch(() => {})

  // ② 没合适的就按内容主题搜（关键词见下表，按本次内容替换 KEYWORD）
  const KEYWORD = '科技感'  // ← 按内容主题换：AI/科技→科技感；技术→lofi；商业→大气 …
  await fillInput('input[placeholder*="搜索"]', KEYWORD).catch(() => {})
  await wait(1.5)

  // ③ 选第一首结果，点「使用」（面板 DOM 各版本有差异，必要时先 snapshot 确认）
  await click('xpath=(//*[normalize-space(text())="使用"])[1]', { label: '使用这首' }).catch(() => {})
  await wait(1)
  const s = await snapshotText()
  cliLog(s.slice(0, 1200))
}
EOF
```

**内容 × BGM 搜索关键词**（推荐/热门里挑不到合适的时，按内容类型搜）：

| 内容类型 | 搜这些词 | 风格 |
|---|---|---|
| AI/科技 | 科技感 / 电子 / 赛博朋克 | 节奏感、未来感 |
| 编程/技术 | 轻音乐 / lofi / 学习 | 舒适、不干扰 |
| 行业/商业分析 | 商务 / 沉稳 / 大气 | 专业、可信 |
| 对比/评测 | 节奏 / 悬念 / 动感 | 起伏、抓注意力 |
| 工具推荐 | 轻快 / 活力 / 阳光 | 积极、轻快 |
| 深度解读 | 史诗 / 电影感 / 沉浸 | 大气、有层次 |

**选择策略**：推荐/热门前几首里挑贴合氛围的 → 没有就按上表搜、选播放量高的 → 再不合适就**跳过**（宁可没 BGM 也不用不搭的音乐）。Daniel 若指定了风格，按他给的词搜。

### Step 6 — 存草稿（默认）

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')
// 草稿按钮文案有变体，全试
await click('button:has-text("暂存离开")', { label: '存草稿' })
  .catch(() => click('button:has-text("存草稿")'))
  .catch(() => click('button:has-text("草稿")'))
await wait(2)
cliLog(await snapshotText())
EOF
```

存草稿成功后，**截图留证**：

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')
await captureScreenshot('/tmp/douyin_draft_preview.png')   // ⚠️ 位置参数；传 {path:...} 会报 "path must be string"
cliLog('saved /tmp/douyin_draft_preview.png')
EOF
```

### Step 7 — 飞书审批门（关键）

草稿存好后、**发布前**，跑审批脚本。它会：起 cloudflared 临时隧道 → 发飞书卡片（含标题/描述/话题/封面状态 + 截图链接 + ✅确认发布/❌取消 按钮）→ 阻塞等待 Daniel 点击（默认 9 分钟）→ 返回结果。

```bash
python3 scripts/await_approval.py \
  --config ~/.config/douyin-ego-publish/config.json \
  --screenshot /tmp/douyin_draft_preview.png \
  --type "图文" \
  --title "标题" \
  --desc "描述 #话题1 #话题2" \
  --cover "已自动选取(第1张)"
```

脚本 stdout 最后一行是结果：`RESULT=APPROVED` / `RESULT=REJECTED` / `RESULT=TIMEOUT`。

- **APPROVED** → 继续 Step 8 点发布。
- **REJECTED / TIMEOUT** → **停止，保留草稿**，告诉 Daniel 草稿还在草稿箱（`creator.douyin.com/creator-micro/content/manage`）。

> 这个脚本一次 Bash 调用会阻塞最多 ~9 分钟（在 Bash 超时内）。Daniel 通常几分钟内就会点。cloudflared 进程由脚本自己起停，用完即关。

### 反检测要点（发布尤其关键）

**为什么自动点发布会触发短信验证、手动不会**：抖音把「发布」当高风险动作，会校验输入像不像真人。`click(selector)` 是"瞬移点击"——直接落在元素中心、没有鼠标移动轨迹、动作间隔毫秒级，这些都和真人不同。手动发布时鼠标会一路移过去、有停顿，点击是浏览器内核派发的可信事件（`isTrusted=true`）。

**降低触发概率的做法**（对发布、AIGC 声明等敏感动作都适用）：

1. **用 CDP 真实输入事件点击，别用原生 `click()`**：✅ **实测验证（2026-08-10）**——`cdp mouseMoved`（1 步移到目标中心）→ `mousePressed` → `mouseReleased` 这套**能成功发布、且不触发短信验证**。关键是点击走 CDP 内核派发的可信事件（`isTrusted=true`）；而原生 `click(selector)` / `click([x,y])` 是瞬移点击，**照样触发验证码**。
2. **用 CDP 派发点击**：`mousePressed`→`mouseReleased` 走内核、`isTrusted=true`；**别用 `js(() => el.click())`**（那是 `isTrusted=false` 的合成事件，一眼假）。
3. **人类化节奏**：填标题→描述→话题之间各停 0.6~2s 随机；填完到点发布前停 1.5~4s。
4. **行为预热**：进编辑页后先滚两下、挪下鼠标，造一段交互历史，再做敏感动作。
5. **mouseMoved 别用长轨迹，1 步即可**：实测 18 步 `mouseMoved` 轨迹会让发布按钮**点不动**（press 失效，cdp 连发疑似被限流）。只用 **1 步**移到目标中心就够——风控靠的是「真实输入事件」本身、不是轨迹长度。务必 `mouseMoved`→`mousePressed`→`mouseReleased` 全走 CDP，中间别夹原生 `click()`。
6. **测坐标后到点击之间「零滚动」**：`scrollIntoView` 默认可能是平滑动画，会在你测完坐标后继续漂移（实测页面 `sy` 从测量时漂到 898，CDP 按旧坐标**点到了空白处、根本没触发发布**）。对策：测坐标前等 ≥2s 让滚动彻底停稳；测完后到点击之间**只允许 `cdp mouseMoved`**（它不触发滚动）；并先校验按钮在视口安全区（`y` 在 `40~vh-40`），不在就放弃，别点空。
7. **`press/release` 带 `buttons:1`**：左键位掩码，部分 CDP 实现缺了它点击不生效（点了像没点）。

> ✅ 上述「CDP 单步 mouseMoved + press/release」点击法 **2026-08-10 真机实测通过**：游戏原画图文帖发布成功、**未触发短信验证**。风控仍是概率性的（不同账号/时段/内容可能不同），但这是目前验证过最稳的写法。兜底见 Step 8 末尾：万一仍触发验证码，转人工，不要硬刚。

### Step 8 — 确认通过后，点发布

只有 Step 7 返回 `APPROVED` 才执行。**发布这一步务必走「反检测要点」的人类化点击**，不要瞬移 `click`：

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')

// —— 发布前：补 AIGC 自主声明（发布强制，草稿不强制）——
// 入口文案/DOM 以当前 snapshot 为准（常为「自主声明」下拉 →「内容由AI生成」）
// 选它也用反检测的人类化点击，别瞬移。

// —— 行为预热：滚一下、停一停，造真实交互历史（注意：所有滚动必须在「测坐标」之前做完）——
await scroll({ dy: 160 + Math.random() * 100 }); await wait(0.5 + Math.random() * 0.5)
await wait(1.5 + Math.random() * 2)              // 填完→发布前的人类停顿

// —— 把「发布」按钮滚进视口。⚠️ scrollIntoView 默认可能是平滑动画，测坐标前必须等 ≥2s
//    让它彻底停稳，否则测到的坐标会在点击前继续漂移（实测 sy 从测量时漂到 898，
//    CDP 按旧坐标点到了空白处、没触发发布）。
await js(String.raw`(() => {
  const b = [...document.querySelectorAll('button')]
    .find(x => (x.textContent || '').trim() === '发布' && x.offsetParent && !x.disabled);
  if (b) b.scrollIntoView({ block: 'center' });
  return 1;
})()`)
await wait(2.5)

// —— 测量按钮「当前」视口坐标。⚠️ 从这里到点击之间【绝不能再有 scroll / scrollIntoView /
//    原生 click】——它们会改变滚动位置或瞬移，使坐标失效/轨迹脱节。下面只允许 cdp mouseMoved
//    （它本身不触发滚动）。
const center = await js(String.raw`(() => {
  const b = [...document.querySelectorAll('button')]
    .find(x => (x.textContent || '').trim() === '发布' && x.offsetParent && !x.disabled);
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), vh: innerHeight };
})()`)

if (!center) {
  cliLog('⚠️ 找不到可点的「发布」按钮——多半是自主声明/封面没完成，先补上再发布')
} else if (center.y < 40 || center.y > center.vh - 40) {
  cliLog('⚠️ 发布按钮不在视口安全区(y=' + center.y + ')，放弃点击以免点空')
} else {
  // —— 真实点击：CDP mouseMoved → mousePressed → mouseReleased（全走 CDP，isTrusted=true）。
  //    ✅ 实测（2026-08-10）：这套写法成功发布且【不触发短信验证】。三条铁律（都踩过）：
  //    ① 必须用 CDP 派发——原生 click(selector)/click([x,y]) 是瞬移点击，【照样触发短信验证】。
  //    ② mouseMoved 只用 1 步（直接移到目标中心）——实测 18 步长轨迹会让 press 失效、点不动发布按钮
  //       （cdp 连发疑似被限流）。风控靠的是「真实输入事件」本身，不是轨迹长度，1 步就够。
  //    ③ press/release 带 buttons:1（左键位掩码，缺了有的实现点击不生效）。
  await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', x: center.x, y: center.y })
  await cdp('Input.dispatchMouseEvent', { type: 'mousePressed',  x: center.x, y: center.y, button: 'left', clickCount: 1, buttons: 1 })
  await cdp('Input.dispatchMouseEvent', { type: 'mouseReleased', x: center.x, y: center.y, button: 'left', clickCount: 1, buttons: 1 })
}

await wait(4)
const after = await snapshotText()
// 发布结果三类信号：成功 / 验证码(转人工) / 风控
cliLog('正在发布=' + after.includes('正在发布') + ' 验证码=' + /验证码|短信/.test(after) + ' 成功=' + /发布成功|成功发布|\/manage/.test(after))
EOF
```

发布后确认页面变化（出现「发布成功」或跳转到管理页），再截图回传 Daniel。

**兜底（一旦触发验证码）**：风控是概率性的，反检测只能大幅降低、不能保证杜绝。若 snapshot 里出现「短信验证码 / 验证码 / 滑块」——**立刻 `await handOffTaskSpace(task.id)`** 把页面交给 Daniel，告诉他验证码发到了哪个手机尾号、请输入后说「好了」，再用 `takeOverTaskSpace(task.id)` 继续。**绝不要尝试自动读取/提交验证码或滑块。**

### Step 9 — 收尾

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')
// 默认关闭 task space；若 Daniel 想留着看页面则 keep:true
await completeTaskSpace(task.id, { keep: false })
EOF
```

## 何时停止自动化（转 Daniel 接管）

来自 `references/douyin-dom.md` 与实战，任一出现就 `handOffTaskSpace` + 截图 + 告诉 Daniel 当前状态，**别重试**：

1. 登录/风控：扫码、滑块、**短信验证码**、二次验证、「操作频繁」——见 Step 8，转人工别硬刚
2. 上传卡住 >8 分钟仍 0%，或描述区迟迟不出现
3. 发布/草稿按钮长时间 disabled 或点不动
4. 选择器漂移：描述区/封面弹窗定位不到
5. 发布时被「请先选择封面 / 请完成自主声明」拦截

## 回传给 Daniel 的标准信息

每次动作后回传：类型、标题、描述、话题、封面状态、**BGM（配乐名或风格）**、AIGC 是否勾、当前状态（已存草稿/待审批/已发布/待接管）、截图路径。

## 参考文件（按需读）

- `references/content-rules.md` — 标题/描述/话题/封面/AIGC 完整规范与适配模板
- `references/douyin-dom.md` — 创作者后台选择器、按钮文案变体、上传/风控排坑
- `references/feishu-setup.md` — 飞书机器人 + cloudflared 一次性配置
- `templates/desc-template.md` — 描述/话题起草模板
