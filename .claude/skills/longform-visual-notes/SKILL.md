---
name: longform-visual-notes
description: |
  长文知识提取转图Skill。将深度长文降维提取核心逻辑，生成3-5张高真实感、含密集中文文字信息的视觉笔记图。
  通过 ego-browser（ego lite）直接驱动 Gemini 官网生图，无需任何 API Key、不依赖 gemini-skill MCP 工具。
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

| 配置项  | 值                                            |
| ---- | -------------------------------------------- |
| 生成模型 | Gemini 官网（由 ego-browser / ego lite 直接驱动） |
| 图片数量 | 3-5张                                         |
| 图片文字 | 中文为主                                         |
| 输出比例 | 9:16（公众号/抖音）或 3:4（小红书）                       |
| 作者标注 | 有作者则在图底部标明                                   |
| 禁止项  | 不得显示"由xx生成该图片"等水印                            |

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

| 文章类型  | 推荐分镜 | 视觉形式                 |
| ----- | ---- | -------------------- |
| 测评/对比 | 4-5张 | 封面→对比矩阵→细节分析→终端截图→总结 |
| 行业分析  | 3-4张 | 概念图→数据图→趋势图→总结       |
| 教程/指南 | 4-5张 | 封面→流程图→代码图→架构图→总结    |
| 产品评测  | 3-4张 | 封面→参数对比→使用场景→总结      |

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

**调用方式**：通过 **ego-browser（ego lite）** 直接驱动 Gemini 官网生图，**无需任何 API Key、不依赖 gemini-skill MCP 工具**。所有浏览器操作走 `Bash` 工具跑 `ego-browser nodejs <<'EOF' ... EOF` heredoc（**不要**先写 .js 文件），详见 `ego-browser` skill。

> **为什么换 ego-browser**：gemini-skill 的 MCP 工具（`gemini_generate_image`）有几个顽固痛点——MCP 连接掉线需 `/mcp` 重连、daemon/浏览器要连 `.wjz_browser_data` 的 Chrome 一起杀、`fullSize` 下载按钮几乎必失败。ego-browser 复用 **ego lite** 的登录态（与 `douyin-ego-publish` 同一套基础设施），直接用 CDP 驱动 Gemini 网页，**绕开 MCP server 这一整层**，状态可观测、可即时排障。底层的 Gemini DOM 选择器与状态机沿用 gemini-skill 的 `gemini-ops.js`（已实测的 `promptInput` / `send-button-container` / `img.image.loaded` 等），只是执行器从 puppeteer 换成 ego-browser 的 `js()` / `cdp()`。

> ⚠️ **网络前提**：Gemini 官网（gemini.google.com）本机直连被墙，**ego lite 浏览器必须经本地代理**。确认 ego lite 走 Clash（127.0.0.1:7890），且代理把 `google.com` / `googleusercontent.com` 等域名路由到境外节点（不能 DIRECT、不能在 `GEOIP,CN,DIRECT` 之后）。生图前先验证（从 Node 侧发请求，不经浏览器）：`curl -x http://127.0.0.1:7890 -I https://gemini.google.com/` 返回**非** **`000`** 才可继续。

每张图彼此独立（非迭代关系），**每张图都新开一个 Gemini 会话**（导航到 `https://gemini.google.com/app` 开空白对话），避免上一张图的上下文污染下一张。

#### 3.1 单张图生成：`ego-browser` heredoc（完整可复用）

执行前把 `PROMPT` 换成 Phase 2 的 4 模块拼接成的完整英文提示词，把 `OUT_PATH` 换成目标保存路径。一个 heredoc = 一张图，同步阻塞跑完，返回保存好的本地路径。

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('visual notes')
cliLog('task id: ' + task.id)

// ── Phase 2 拼接好的完整英文 prompt（4 模块：Main/Content/Context/Quality）＋ 比例关键词 ──
const PROMPT = `<英文提示词>`
const OUT_PATH = '/abs/path/visual-note-XX-名称.png'   // 绝对路径

// ===== ① 开空白 Gemini 会话（等价 gemini-skill 的 newSession=true）=====
await openOrReuseTab('https://gemini.google.com/app', { wait: true, timeout: 30 })
await wait(2)   // 让 Angular SPA 渲染出输入框

// ===== ② 探测页面 + 确认登录 + 确认模型 =====
// 选择器/状态机移植自 gemini-ops.js 的 SELECTORS / getStatus / getCurrentModel。
const PROMPT_SELS = [
  'div.ql-editor[contenteditable="true"][role="textbox"]',
  '[contenteditable="true"][aria-label*="Gemini"]',
  'div[contenteditable="true"][role="textbox"]',
]
const probe = await js(String.raw`((promptSels) => {
  const bar = document.querySelector('div.boqOnegoogleliteOgbOneGoogleBar');
  const barText = (bar?.innerText || '').trim();
  const loggedIn = bar ? !/登录|sign in/i.test(barText) : false;
  let input = null;
  for (const s of promptSels) { try { input = document.querySelector(s); } catch {} if (input) break; }
  const r = input ? input.getBoundingClientRect() : null;
  const inputReady = !!input && r.width > 0 && r.height > 0;
  // 当前模型名（实测贴在输入栏 input-area 区域文本里，不是旧的 logo-pill-label-container）
  let modelArea = null;
  for (const s of ['.input-area','.text-input-field','input-area-v2','fieldset.input-area-container']) { try { modelArea = document.querySelector(s); } catch {} if (modelArea) break; }
  const modelText = ((modelArea?.innerText) || (document.body.innerText || '')).toLowerCase();
  const currentModel = /flash-?lite/.test(modelText) ? 'flash-lite' : (/flash/.test(modelText) ? 'flash' : (/\bpro\b/.test(modelText) ? 'pro' : ''));
  return { loggedIn, barText: barText.slice(0,80), inputReady, currentModel };
})(${JSON.stringify(PROMPT_SELS)})`)
cliLog('probe: ' + JSON.stringify(probe))

// 未登录 → 交接给 Daniel 手动登录，别自己重试
if (!probe.loggedIn) {
  cliLog('⚠️ Gemini 未登录，转人工登录')
  await handOffTaskSpace(task.id)
} else if (!probe.inputReady) {
  cliLog('⚠️ 输入框未就绪，snapshot 排查：')
  cliLog((await snapshotText()).slice(0, 800))
}

// ===== ③ 确保是 Pro 模型（可选；Flash-Lite 不支持生图，会回 "image creation isn't available"）=====
// ⚠️ 软化处理：很多账号/Gemini 版本【根本没有可见的模型选择器 UI】（2026-08-12 自测：本账号
//    输入区 0 个模型按钮，logo-pill 选择器全失配）。所以这一步「能读就读、能切就切，没有就跳过」，
//    不当硬错误——默认模型若支持生图就直接用；真不支持时会在 ⑦ 取不到图，按排障①处理（切/重开会话）。
async function ensureProModel() {
  // 读当前模型：gemini-skill 旧选择器 logo-pill-label-container 已漂移失配。
  // 实测（2026-08-12）模型名贴在输入栏 input-area 区域文本里（如 "Flash-Lite"/"Pro"）。
  const cur = await js(String.raw`(() => { const area=document.querySelector('.input-area, .text-input-field, input-area-v2, fieldset.input-area-container'); const t=((area?.innerText)||(document.body.innerText||'')).toLowerCase(); if(/flash-?lite/.test(t)) return 'flash-lite'; if(/flash/.test(t)) return 'flash'; if(/\bpro\b/.test(t)) return 'pro'; return 'unknown'; })()`)
  if (cur === 'pro') return { ok:true, already:true, model:cur }
  // 打开模型菜单（没有选择器 UI 就跳过，不算失败）
  const opened = await js(String.raw`(() => { const sels=['[data-test-id="bard-mode-menu-button"]','button[aria-label="打开模式选择器"]','button[aria-label*="mode selector" i]','button.mat-mdc-menu-trigger.input-area-switch']; let b=null; for (const s of sels){ try{ b=document.querySelector(s);}catch{} if(b)break;} if(!b) return {ok:false, skipped:'no_model_switcher'}; b.click(); return {ok:true}; })()`)
  if (!opened.ok) return { ok:true, skipped: opened.skipped, model:cur || 'unknown' }   // 跳过，非错误
  await wait(0.4)
  // 文本匹配 "3.x Pro"（排除 flash/lite/think），点它
  const picked = await js(String.raw`(() => { const items=[...document.querySelectorAll('gem-menu-item, [data-test-id^="bard-mode-option"]')].filter(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0}); const labelOf=el=>(el.querySelector('.label')?.textContent||el.textContent||'').trim(); const t=items.find(el=>{const l=labelOf(el);return /pro/i.test(l)&&!/flash|lite|扩展思考|think/i.test(l)}); if(!t) return {ok:false}; t.click(); return {ok:true, matched:labelOf(t).slice(0,40)}; })()`)
  if (!picked.ok) { await pressKey('Escape').catch(()=>{}); return { ok:true, skipped:'pro_option_not_found', model:cur||'unknown' } }   // 跳过
  await wait(0.8)
  return { ok:true, switched:true, model:cur }
}
const mp = await ensureProModel()
cliLog('model: ' + JSON.stringify(mp))

// ===== ④ 填 prompt（CDP 真实点击聚焦 + CDP Input.insertText）=====
// ⚠️ 不要用 document.execCommand('insertText')！自测发现它有时进不了 Gemini 的 Angular 模型——
//   DOM 显示有字、实际提交时是空的，Gemini 收到空 prompt 直接忽略（不报错、不响应、不进 stop 态）。
//   正确做法：CDP 真实点击聚焦输入框（isTrusted）→ CDP Input.insertText 灌入（等价真人粘贴，operator.js paste 模式）。
const focusPt = await js(String.raw`((promptSels) => { let el=null; for(const s of promptSels){ try{ el=document.querySelector(s);}catch{} if(el)break;} const r=el.getBoundingClientRect(); return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)}; })(${JSON.stringify(PROMPT_SELS)})`)
await cdp('Input.dispatchMouseEvent', { type:'mouseMoved', x:focusPt.x, y:focusPt.y })
await cdp('Input.dispatchMouseEvent', { type:'mousePressed', x:focusPt.x, y:focusPt.y, button:'left', clickCount:1, buttons:1 })
await cdp('Input.dispatchMouseEvent', { type:'mouseReleased', x:focusPt.x, y:focusPt.y, button:'left', clickCount:1, buttons:1 })
await wait(0.5)
await cdp('Input.insertText', { text: PROMPT })
await wait(0.8)
// 校验文本真的进了模型（关键：防 execCommand 那种「假填入」）
const fillRes = await js(String.raw`((promptSels) => { let el=null; for(const s of promptSels){try{el=document.querySelector(s);}catch{} if(el)break;} const sc=document.querySelector('div.send-button-container'); const btn=sc?.querySelector('button'); return { inputText:(el?.innerText||'').trim(), inputLen:(el?.innerText||'').length, sendAria:btn?.getAttribute('aria-label')||'' }; })(${JSON.stringify(PROMPT_SELS)})`)
cliLog('fill: ' + JSON.stringify(fillRes))
if (!fillRes.inputLen) { cliLog('⚠️ 填入失败（空输入），别点发送'); }

// ===== ⑤ 点发送按钮（CDP 真实点击，isTrusted=true）=====
// ⚠️ 判据用 aria-label，不要用 class！gemini-ops 旧版靠 class 含 submit/stop 判状态，但当前
//    Gemini 版本发送按钮 class 里【既无 submit 也无 stop】，只有 aria-label 会变（见 ⑥ 实测表）。
async function clickSend() {
  // 定位 .send-button-container 内按钮，优先 aria-label=发送/Send；校验它不是「停止回答/Stop」态
  const pt = await js(String.raw`(() => { const c=document.querySelector('.send-button-container'); if(!c) return {ok:false,reason:'send_container_not_found'}; const btns=[...c.querySelectorAll('button')]; const b=btns.find(x=>/发送|send/i.test(x.getAttribute('aria-label')||'')) || btns.find(x=>/停止|stop/i.test(x.getAttribute('aria-label')||'')) || c.querySelector('button'); if(!b) return {ok:false,reason:'send_btn_not_found'}; const aria=(b.getAttribute('aria-label')||'').trim(); const r=b.getBoundingClientRect(); if(r.width===0||r.height===0) return {ok:false,reason:'send_btn_not_visible'}; return {ok:true, aria, isStop:/停止|stop/i.test(aria), isSend:/发送|send/i.test(aria), x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)}; })()`)
  if (!pt.ok) return pt
  if (pt.isStop) return { ok:true, alreadyGenerating:true }
  if (!pt.isSend) return { ok:false, reason:'send_btn_not_ready', aria:pt.aria }
  // CDP 单步 mouseMoved → press → release（沿用 douyin-ego-publish 的反检测点击法）
  await cdp('Input.dispatchMouseEvent', { type:'mouseMoved', x:pt.x, y:pt.y })
  await cdp('Input.dispatchMouseEvent', { type:'mousePressed', x:pt.x, y:pt.y, button:'left', clickCount:1, buttons:1 })
  await cdp('Input.dispatchMouseEvent', { type:'mouseReleased', x:pt.x, y:pt.y, button:'left', clickCount:1, buttons:1 })
  return { ok:true, x:pt.x, y:pt.y }
}
const sendRes = await clickSend()
cliLog('send: ' + JSON.stringify(sendRes))

// ===== ⑥ 轮询等生成完成 =====
// 实测（2026-08-12）当前 Gemini 版本发送按钮 aria-label 转换：
//   可发送(有字) → "发送" ；生成中 → "停止回答" ；生成完成 → ""（按钮退场/回到输入态，hasResponse:true）
// 旧版 gemini-ops 靠 class 的 submit/stop/mic-hidden 判状态已全部失配，必须用 aria-label。
async function getStatus() {
  return await js(String.raw`(() => {
    const sc=document.querySelector('div.send-button-container');
    const btns=sc?[...sc.querySelectorAll('button')]:[];
    const sendBtn=btns.find(x=>/发送|send/i.test(x.getAttribute('aria-label')||''));
    const stopBtn=btns.find(x=>/停止|stop/i.test(x.getAttribute('aria-label')||''));
    const hasResponse = !!(document.querySelector('div.response-content, message-content, .model-response-text, [data-message-id]'));
    // status: 'submit'(可发送) / 'stop'(生成中) / 'done'(已完成有回复且无 stop) / 'idle'(空)
    let status='idle';
    if (stopBtn) status='stop';
    else if (sendBtn) status='submit';
    else if (hasResponse) status='done';
    return { status, hasResponse, sendAria: sendBtn?.getAttribute('aria-label')||'', stopAria: stopBtn?.getAttribute('aria-label')||'' };
  })()`)
}

// 等到首次进入 stop（开始生成），再等到离开 stop（生成完毕，按钮退场或变回发送 + hasResponse）。整体上限 ~180s。
let started = false, done = false, waited = 0
for (let i = 0; i < 90; i++) {            // 90 × 2s = 180s 上限
  const s = await getStatus()
  if (s.status === 'stop') started = true
  if (started && s.status !== 'stop') { done = true; break }   // stop 消失 = 生成完毕
  await wait(2); waited += 2
  if (i % 5 === 0) cliLog('⏳ 生成中… 已等 ' + waited + 's status=' + s.status)
}
cliLog('wait done=' + done + ' waited=' + waited + 's')
await wait(2)   // 让图片渲染稳定

// ===== ⑦ 取最新生成图 + CDP Network.loadNetworkResource 提取（绕过 CORS，不要截图）=====
// 严禁用 captureScreenshot 当成图——必须拿真原图。选择器 img.image.loaded（gemini-ops generatedImageImg）。
// blob: URL 走 canvas drawImage，googleusercontent URL 走 CDP loadNetworkResource。
async function getLatestImgUrl() {
  return await js(String.raw`(() => {
    const sels=['generated-image img','.generated-image img','img.image.loaded'];
    const seen=new Set(), imgs=[];
    for (const s of sels){ let f; try{ f=document.querySelectorAll(s);}catch{continue} for(const el of f){ if(seen.has(el))continue; seen.add(el); const r=el.getBoundingClientRect(); if(r.width<80&&r.height<80) continue; imgs.push(el); } }
    if(!imgs.length) return {ok:false};
    const img=imgs[imgs.length-1];
    return {ok:true, src: img.src||img.currentSrc||''};
  })()`)
}

let img = await getLatestImgUrl()
if (!img.ok) { await wait(4); img = await getLatestImgUrl() }   // 再给 4s
cliLog('img: ' + JSON.stringify(img))

let savedPath = null
if (img.ok && img.src) {
  // —— 统一路径：blob:→canvas→data URL→Node 解码；googleusercontent→CDP Network.loadNetworkResource+IO.read ——
  // 不用 browserFetch/serverFetch 取二进制（它们返回 body 文本，对 PNG 字节流会损坏）。
  savedPath = await (async () => {
    const { writeFileSync } = await import('node:fs')
    let targetUrl = img.src
    if (img.src.startsWith('blob:')) {
      const b64 = await js(String.raw`((url) => { const sels=['generated-image img','.generated-image img','img.image.loaded']; const seen=new Set(), imgs=[]; for(const s of sels){ let f; try{ f=document.querySelectorAll(s);}catch{continue} for(const el of f){ if(seen.has(el))continue; seen.add(el); const r=el.getBoundingClientRect(); if(r.width<80&&r.height<80) continue; imgs.push(el); } } const img = imgs.find(i=>(i.src||i.currentSrc)===url) || imgs[imgs.length-1]; if(!img) return null; const w=img.naturalWidth||img.width, h=img.naturalHeight||img.height; try { const c=document.createElement('canvas'); c.width=w; c.height=h; c.getContext('2d').drawImage(img,0,0); return c.toDataURL('image/png'); } catch { return null; } })(${JSON.stringify(img.src)})`)
      if (!b64) return null
      targetUrl = b64
    }
    // data: URL 直接在 Node 里解码落盘（无需 CDP）
    if (targetUrl.startsWith('data:')) {
      const m = targetUrl.match(/^data:([^;]+)?;base64,(.*)$/)
      if (m) { writeFileSync(OUT_PATH, Buffer.from(m[2], 'base64')); return OUT_PATH }
    }
    // googleusercontent URL → CDP Network.loadNetworkResource（绕 CORS）+ IO.read 分块
    const frame = await cdp('Page.getFrameTree').catch(()=>null)
    const frameId = frame?.frameTree?.frame?.id
    const res = await cdp('Network.loadNetworkResource', { frameId, url: targetUrl, options:{ disableCache:false, includeCredentials:true } }).catch(e=>({error:String(e)}))
    if (res.error || !res.resource?.success) return null
    const handle = res.resource.stream
    if (!handle) return null
    const chunks = []
    let eof = false
    while (!eof) {
      const r = await cdp('IO.read', { handle, size: 1024*1024 })
      if (r.data) chunks.push(r.base64Encoded ? Buffer.from(r.data,'base64') : Buffer.from(r.data))
      eof = r.eof
    }
    await cdp('IO.close', { handle }).catch(()=>{})
    writeFileSync(OUT_PATH, Buffer.concat(chunks))
    return OUT_PATH
  })()
}

cliLog('✅ savedPath=' + savedPath)
EOF
```

heredoc 跑完后，`savedPath` 即本地图片绝对路径（就是 `OUT_PATH`）。**直接按分镜命名落盘**，无需再 `mv`。

> ⚠️ **`browserFetch`/`serverFetch` 不能用来取二进制图**：它们返回的是 body 文本，对 PNG 字节流会损坏。图片字节必须走上面 ⑦ 的 **canvas→data URL→Node 解码**（blob:）或 **CDP `Network.loadNetworkResource`+`IO.read`**（googleusercontent），二者都拿到原始 Buffer 再 `writeFileSync`。

#### 3.2 多张图：循环跑 3.1

每张图 = 一个独立的 `ego-browser nodejs` heredoc（**各自新开 Gemini 会话**）。不要在一个 heredoc 里循环多张——每个 heredoc 跑完会清 Node 状态，且单张 heredoc 失败可单独重试。

```bash
# 伪代码：Claude 按分镜逐张生成，PROMPT_1..N / OUT_PATH_1..N 来自 Phase 1/2/4
# 图1
ego-browser nodejs <<'EOF'   # PROMPT=<PROMPT_1>, OUT_PATH=<…/visual-note-01-封面.png>  …（同 3.1）   EOF
# 图2 …（同上，换 PROMPT / OUT_PATH）
# …
```

**关键规则（ego-browser + Gemini）：**

- 每个 heredoc **同步阻塞**跑完一张图（通常 60\~120 秒）。`wait()` 单位是**秒**（ego-browser 约定：只有名字带 `Ms` 的才是毫秒）。
- **禁止**在 heredoc 未返回 `savedPath` 前结束对话或向用户报告"还在生成"。生图期间每隔 15\~30 秒向用户发一条进度消息（如"正在等 Gemini 生成第 2 张…已等 30 秒…"）。
- **每张图务必新开会话**（`openOrReuseTab('https://gemini.google.com/app')`）。复用会话会让上一张图的上下文污染下一张。
- **默认用预览图提取（canvas / CDP loadNetworkResource 取 DOM 上的图）**——稳定。**不要**去点「下载完整尺寸」按钮（gemini-skill 实测它几乎 100% 失败且会拖垮流程）。
- **登录态靠 ego lite**：ego-browser 的 task space 复用 ego lite 浏览器的登录态，正常应已登录 Google。未登录就 `handOffTaskSpace` 让 Daniel 手动登，别自己重试。
- 拿到 `savedPath` 后**立即**进入 Phase 4。

**输出比例控制（无 size 参数，通过 prompt 控制）：**

ego-browser 驱动的 Gemini 同样没有尺寸入参，在 Phase 2 的 prompt 里用关键词指定比例：

- 9:16（公众号 / 抖音）→ 加入 `portrait 9:16 vertical phone-screen orientation, vertical top-to-bottom layout`（竖版见排障节，措辞要强）
- 3:4（小红书）→ 加入 `portrait 3:4 vertical orientation, vertical layout`

**生成优先级链：**

```
1. ego-browser 直接驱动 Gemini 官网（首选，无需 API Key、无 MCP 依赖、文字生成质量高）
2. image_generate 默认模型（兜底，仅当 ego-browser / Gemini 不可用时）
```

#### 3.3 排障（ego-browser 驱动 Gemini 实测坑）

1. **`no_image_found` / "image creation isn't available in your location" / 生成 stop 仅 2\~3s 就回 idle 且无回复无图**：根因是**当前模型是 Flash-Lite**（不支持生图）。**怎么确诊**：发送后抓页面文本 `(document.body.innerText)`，若含 `Flash-Lite`（它贴在用户消息下方的输入栏里），就是这个。`gemini-skill` 时代的 `logo-pill-label-container` 选择器已读不到模型名，③ 的读模型逻辑改成抓 `input-area` 区域文本里的 `Flash-Lite`/`Pro` 关键字。**对策**：① 先试开新会话（导航 `/app`）；② 若该账号**没有模型切换器 UI**（输入区无可点的模型按钮、无 `aria-haspopup` 菜单触发器，③ 返回 `skipped:'no_model_switcher'`）→ 说明此 ego-lite 登录态的 Google 账号被限制在 Flash-Lite，**本环境生不了图**，`handOffTaskSpace` 让 Daniel 在 ego lite 里换一个有 Pro 权限的 Google 账号登录，再用 `takeOverTaskSpace` 继续。这是账号权限问题，不是提示词/网络/skill 的 bug。
2. **竖版封面/笔记顽固出横版**：Gemini 对 9:16/3:4 本就不听话，文字密集的封面/笔记尤其顽固。措辞用 `phone-screen shape` + `top-to-bottom 堆叠` + 结尾再强调 `portrait`；同一 prompt 复用会话重排一次。**重试 2-3 次仍横就别硬试**，直接交付或改用纯纵向结构（竖向流程图/路线图天然更易出竖版）。封面横版还常多出幻觉日期 → prompt 加 `no date stamps`。
3. **发送按钮判据用 aria-label，别用 class（2026-08-12 自测）**：当前 Gemini 版本发送按钮 `class` 里**既无 `submit` 也无 `stop`**，gemini-ops 旧版靠 class 判状态的逻辑已全部失配。必须用 `aria-label`：可发送=`发送`、生成中=`停止回答`、完成=按钮退场（aria 空）+`hasResponse:true`。skill ⑤⑥ 已按此实现。若仍 `send_btn_not_found`：填字后等 1\~2s 让按钮浮现（空输入时发送按钮不显示），再 `snapshotText()` 看真实结构。
4. **图提取失败（canvas_tainted / loadNetworkResource 无 stream）**：blob: URL 优先 canvas，被 taint 才回退；googleusercontent URL 走 CDP `Network.loadNetworkResource`+`IO.read` 分块（见 ⑦）。两路都失败通常是图还没渲染完，多 `wait(4)` 再取一次。**严禁**用 `captureScreenshot` 代替取图。
5. **task space 对用户不可见**：agent 的隔离 task space 不在 Daniel 平时窗口，`handOffTaskSpace` 后 Daniel 要在 ego lite 里另找（Cmd+~ 切窗口 / 找 Gemini 标签）。交接时说清在哪找。

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

| 风格                       | 描述                | 适用场景      |
| ------------------------ | ----------------- | --------- |
| **Hand-written Note**    | 手机/平板/纸张上的高密度手写图表 | 知识笔记、测评总结 |
| **Mind Map**             | 手绘感或极简现代风白板思维导图   | 概念梳理、逻辑拆解 |
| **Architecture Diagram** | 专业批注的系统演算图        | 技术架构、流程分析 |
| **Comparison Chart**     | 高对比度重点标红的参数对比表    | 产品对比、功能矩阵 |

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
优先调用 longform-visual-notes，图片比例改为 9:16
```

## 依赖

| 依赖              | 说明                                            | 必需    |
| --------------- | --------------------------------------------- | ----- |
| ego-browser (ego lite) | 直接驱动 Gemini 官网生图（`ego-browser nodejs` heredoc） | ✅（首选） |
| image\_generate | 兜底生图（仅当 ego-browser / Gemini 不可用）             | ⬜（兜底） |
| 内容文章            | 输入的长文                                         | ✅     |

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
6. **优先 ego-browser 驱动 Gemini** — 通过 `ego-browser nodejs` heredoc 直接驱动 Gemini 官网生图，无需 API Key、不依赖 gemini-skill MCP 工具，文字生成质量最高，优先使用
7. **保存Prompt** — 每张图的提示词保存为.md文件，便于复用

## 更新日志

- **v1.3.1** (2026-08-12): ego-browser 真机自测修正 + 端到端验证通过
  - **端到端实测通过** ✅：Pro 账号下「画一个红色苹果在白色盘子上」→ Gemini 进 `Creating your image` → 出图 → blob URL canvas 提取 → 落盘 `/tmp/visual-notes-selftest.png`（有效 PNG 1024×559）。整条 ①\~⑦ 链路验证完毕。
  - **填 prompt 改 CDP `Input.insertText`**（关键修复）：`document.execCommand('insertText')` 有时进不了 Gemini 的 Angular 模型——DOM 显示有字、提交时却是空的，Gemini 收到空 prompt 直接忽略（不响应、不进 stop）。改为 CDP 真实点击聚焦 + CDP `Input.insertText`（等价真人粘贴），并加填入校验（读 `inputLen`，空就别点发送）。
  - **状态机判据改 aria-label**：当前 Gemini 版本发送按钮 `class` 里既无 `submit` 也无 `stop`，gemini-ops 旧版靠 class 判状态的逻辑全部失配。⑤`clickSend`/⑥`getStatus` 改用 `aria-label`（可发送=`发送`、生成中=`停止回答`、完成=按钮退场+`hasResponse`）。
  - **读模型选择器改 input-area 文本**：旧 `logo-pill-label-container span` 已漂移失配。模型名贴在输入栏 `.input-area` 区域文本里，②/③ 改抓该区域文本里的 `Flash-Lite`/`Pro` 关键字。
  - **③`ensureProModel` 软化为可选**：很多账号无模型切换器 UI（无 `aria-haspopup` 菜单触发器），改为「有就切、没有就 `skipped` 跳过」，不当硬错误。
  - **排障①更新**：Flash-Lite 拒绝生图 vs Pro 内容策略拒绝（"don't have access to that content"）的区分；后者多半是 prompt 触发内容策略或临时限流，换安全中文 prompt 重试。
- **v1.3.0** (2026-08-12): 生图后端从 gemini-skill MCP 切到 ego-browser
  - 弃用 `gemini_generate_image` MCP 工具，改用 **ego-browser（ego lite）直接驱动 Gemini 官网**：`ego-browser nodejs <<'EOF'` heredoc 全流程（新开会话 → ensureProModel → 填 prompt → CDP 点发送 → 轮询状态 → 取图落盘）。
  - 底层 Gemini DOM 选择器与状态机沿用 gemini-skill `gemini-ops.js`（`promptInput` / `send-button-container` submit↔stop↔mic / `img.image.loaded`），执行器从 puppeteer 换成 ego-browser 的 `js()` / `cdp()`。
  - 图提取统一走 **canvas→data URL→Node 解码**（blob:）或 **CDP `Network.loadNetworkResource`+`IO.read`**（googleusercontent），绕过 CORS、绕开不稳定的「下载完整尺寸」按钮。
  - 复用 `douyin-ego-publish` 的 ego lite 基础设施（登录态复用 + CDP 真实点击反检测）；与 daily-* / content-ops-toolkit 的调用契约不变（输入文章、输出 `素材/visual-note-XX-名称.png`）。
  - 新增 Phase 3.3 排障（会话退化/Flash-Lite、竖版顽固出横版、发送按钮点不动、图提取失败、task space 对用户不可见）。
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

