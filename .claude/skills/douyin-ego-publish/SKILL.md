---
name: douyin-ego-publish
description: "用 ego lite 浏览器（ego-browser）把本地图文或视频发布到抖音创作者后台：内容适配→上传→填标题/描述/#话题→配乐→先存草稿→飞书发审批卡片等 Daniel 确认→确认后才点发布。默认只存草稿；只有 Daniel 在飞书点「确认发布」后才自动发布。覆盖图文(2-35张)/视频、标题(≤55字)、描述(≤200字)、#话题(3-5个)、配乐BGM(默认从抖音音乐库按内容主题自动选)、AIGC「内容由AI生成」声明。**默认不设封面，用抖音默认效果**（封面编辑器在自动化下「确定」按钮关不掉弹窗）。基于 ego-browser 自动化（复用登录态，绕过扫码风控）。触发：'发抖音'、'抖音发布'、'发图文到抖音'、'抖音视频'、'douyin publish'、'传到抖音'、'发布短视频'、'把这几张图发抖音'。只要用户提到要把本地图片或视频发到抖音，就用这个技能。"
author: Daniel Li
version: 0.1.0
---

# 抖音发布（ego-browser + 飞书审批门）

把本地图文/视频发到抖音，全程用 **ego-browser** 自动化；发布前必须经 **飞书审批卡片** 确认。

## 两个铁律

1. **默认只存草稿。** 自动化把标题/描述/话题/配乐/AIGC 声明都填好、存为草稿、截图。**绝不自动点「发布」。**
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
- **封面**：**默认不设封面，用抖音默认效果**（图文默认用第 1 张图、视频用首帧）。原因：封面编辑器在自动化下「确定」按钮怎么点都关不掉弹窗（2026-08-13 真机实测），强行设会卡死整个流程。Daniel 若明确要求设封面，转人工让他手动设——不要自动化碰封面编辑器。
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

// 图片绝对路径数组（按上传顺序，图文 2-35 张）。Claude 执行前替换为真实路径。
// 上传 helper 移植自 douyin.mjs L130 + wechat-channels.mjs L43/L84-87（accept 正则改 image）。完整源码见 references/upload-and-content.md A 节。
// 视频发布见文末注释。
const IMAGE_PATHS = ['/abs/path/img1.jpg','/abs/path/img2.jpg','/abs/path/img3.jpg']

// ===== 上传状态探针（正则必须字面内联进 js() 字符串，不能引用 Node 变量）=====
async function inspectImageUploadState() {
  return await js(String.raw`(() => {
    const compact = v => String(v||'').replace(/\s+/g,' ').trim()
    const text = compact(document.body.innerText||'')
    const editorReady = !!document.querySelector('[contenteditable="true"],[contenteditable=""]') && /暂存离开|存草稿/.test(text)
    return {
      text: text.slice(0,1200),
      // uploadSucceeded 不返回——稳定轮询只用 editorReady/uploading/uploadFailed，视频 adapter 的 gates 在本 skill 不存在
      uploading: /上传过程中|取消上传|上传剩余时间|已上传：|上传速度|当前速度/.test(text) && !/上传成功/.test(text),
      uploadFailed: /上传失败|网络错误|重新上传失败/.test(text),
      editorReady
    }
  })()`)
}

// ===== 定位真实图片 input 并打 id（主DOM + shadow root；accept 正则匹配 image）=====
async function exposeImageInput() {
  return await js(String.raw`(() => {
    const acceptRe = /image|png|jpe?g|webp/i
    const roots = [document, ...[...document.querySelectorAll('*')].map(el=>el.shadowRoot).filter(Boolean)]
    const inputs = roots.flatMap(r => [...r.querySelectorAll('input[type=file]')])
    let input = inputs.find(el => acceptRe.test(el.accept||''))
    if (!input) input = inputs[0] || null
    if (!input) return { ok:false, reason:'image input not found in main DOM or shadow roots' }
    input.value=''; input.id='vp2-douyin-image'
    return { ok:true, selector:'#vp2-douyin-image', multiple: input.hasAttribute('multiple') }
  })()`)
}

// ===== 注入自己的 input 到上传区（图文页主力方案，2026-08-12 实测验证）=====
// 为什么需要它：抖音图文页整页【不挂载持久 input[type=file]】——点击「点击上传」区在
// 自动化下不弹原生 dialog，input 永不创建。但抖音 dropzone 监听的是【事件冒泡】，
// 不在乎 input 是不是它自己的：主动注入一个 input → uploadFile 喂值 → dispatch change，
// 抖音就会响应并上传。视频页通常有原生 input（走 exposeImageInput），图文页靠这招。
async function injectImageInput() {
  return await js(String.raw`(() => {
    let old = document.querySelector('#ego-injected-upload'); if (old) old.remove()
    const dz = [...document.querySelectorAll('[class]')].find(e => /content-upload|upload-zone|dragger/i.test(String(e.className))) || document.body
    const input = document.createElement('input')
    input.type='file'; input.multiple=true; input.accept='image/*'; input.id='ego-injected-upload'
    // 几乎不可见，避免影响布局
    input.style.cssText='position:fixed;top:10px;left:10px;opacity:0.01;width:1px;height:1px;z-index:99999'
    dz.appendChild(input)
    return { ok:true, selector:'#ego-injected-upload' }
  })()`)
}

// ===== 4 级 fallback 链 =====
async function uploadImagesWithFallback(paths) {
  // ① 找抖音原生 input（视频页通常有；图文页通常没有）。轮询 ~8s 即可，别长等。
  let exposed = null
  for (let i=0; i<16; i++) { exposed = await exposeImageInput(); if (exposed.ok) break; await wait(0.5) }
  if (exposed?.ok) cliLog('① 找到原生 input: ' + exposed.selector)

  // ② 注入自己的 input（图文页主力！原生 input 找不到时立即注入，已验证可行）
  if (!exposed?.ok) {
    const inj = await injectImageInput()
    cliLog('② 注入 input: ' + (inj.ok ? inj.selector : inj))
    exposed = inj   // { ok:true, selector:'#ego-injected-upload' }（multiple 固定 true）
  }

  if (!exposed?.ok) {
    // ③ 注入也失败（极端情况：连 document.body 都 append 不了）→ handOff
    cliLog('⚠️ 注入 input 失败，转人工拖拽')
    await handOffTaskSpace(task.id)
    return { ok:false, mode:'handoff', reason: exposed?.reason || 'inject failed' }
  }

  // 喂文件：multiple input 一次性 uploadFile 数组；失败降级逐张
  const sel = exposed.selector
  try {
    await uploadFile(sel, paths)
    cliLog('✅ uploadFile(' + sel + ', ' + paths.length + ' 张) 完成')
    // dispatch change/input 让抖音 dropzone 响应（注入的 input 必须主动派发；
    // 原生 input 的 change 由 uploadFile 内部已触发，但再派发一次无副作用）
    await js(String.raw`(() => { const i=document.querySelector(${JSON.stringify(sel)}); if(i){i.dispatchEvent(new Event('change',{bubbles:true}));i.dispatchEvent(new Event('input',{bubbles:true}));} return 1 })()`)
    return { ok:true, mode:'array', count:paths.length }
  } catch (e) {
    cliLog('一次性数组失败，降级逐张: ' + (e?.message||e))
    for (const p of paths) {
      await js(String.raw`(() => { const i=document.querySelector(${JSON.stringify(sel)}); if(i){i.value='';} return 1 })()`)
      try { await uploadFile(sel, p) } catch (e2) { return { ok:false, mode:'per_file', failedPath:p, reason:String(e2?.message||e2) } }
      await js(String.raw`(() => { const i=document.querySelector(${JSON.stringify(sel)}); if(i){i.dispatchEvent(new Event('change',{bubbles:true}));} return 1 })()`)
      await wait(0.8)
    }
    return { ok:true, mode:'per_file', count:paths.length }
  }
}

// ===== 执行 + 稳定完成轮询 =====
const result = await uploadImagesWithFallback(IMAGE_PATHS)
cliLog('upload result: ' + JSON.stringify(result))
if (result.ok) {
  let stableSince = 0
  for (let i=0; i<120; i++) {
    await wait(i === 0 ? 0.5 : 5)   // 首次快速探一次（上传可能已完成），之后 5s 节奏
    const s = await inspectImageUploadState()
    if (s.editorReady && !s.uploading && !s.uploadFailed) {
      if (!stableSince) stableSince = Date.now()
      if (Date.now()-stableSince >= 10000) { cliLog('✅ 图文上传稳定完成'); break }
    } else stableSince = 0
    if (s.uploadFailed) { cliLog('⚠️ 明确上传失败: ' + s.text.slice(0,200)); break }
  }
}
cliLog(await snapshotText())

// 视频发布：把 IMAGE_PATHS 换成单个 videoPath，accept 正则改 /video|\.mp4|\.mov|\.mkv|\.flv/i，
// 去掉多文件循环，单次 uploadFile('#vp2-douyin-image', videoPath)（或同款 CDP 注入）。
EOF
```

**图文上传完成的判据**：编辑器就绪 = 出现 `[contenteditable]` 描述区 **且** 底部出现「暂存离开」按钮，且持续 10s 稳定（脚本内置 `inspectImageUploadState` 轮询）。上传 toast 信号（被动读 `[class*=semi-toast-content-text]`）：成功=`上传成功`/`已添加 N 张`/`N/35`；上传中=`上传过程中`/`取消上传`；失败=`上传失败`/`网络错误`。

⚠️ **风控坑 + input 缺失**（实战实测）：两种失败模式——
1. **风控拦字节**：卡 `0% 0/N`（auth 接口 200 但字节不上传），secsdk 签名失败。**别死磕、别反复点「编辑封面」**，立刻 `handOffTaskSpace`。
2. **input 不挂载**（图文页常态）：抖音图文页整页**不挂载持久 `input[type=file]`**——点「点击上传」区在自动化下不弹原生 dialog，input 永不创建；`DOM.setFileInputFiles` 无 objectId、ego-browser 也**没有** `Page.handleFileChooser`。**唯一可行路径 = 注入自己的 input**：脚本内置 `injectImageInput()` 往上传区 append 一个 `input[type=file][multiple]`，`uploadFile('#ego-injected-upload', paths)` 喂值后 dispatch change——抖音 dropzone 监听事件冒泡，照单全收（2026-08-12 实测验证，4 张图一次性上传成功）。视频页有原生 input，走 `exposeImageInput()` 即可。注入也失败才 `handOffTaskSpace`。

### Step 3 — 等上传/转码彻底完成

图文：被动读 toast，等「请等待上传完成」消失后再操作。视频：等转码完成（进度条到头、出现可编辑描述区）。

### Step 4 — 填标题 + 描述 + #话题

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')

// Claude 执行前替换为真实内容。DESCRIPTION 不含 #话题；TOPICS 带或不带 # 都行。
const TITLE = '你的标题'                    // ≤55字（图文实测上限常为 20，超了会被截）
const DESCRIPTION = '描述正文，不含#话题'    // ≤200字
const TOPICS = ['话题1','话题2','话题3']     // 3-5个

// 标题：保持 fillInput（实测可用）
await fillInput('input[placeholder*="标题"]', TITLE).catch(e=>cliLog('title fill err: '+e))
await wait(0.6 + Math.random()*1.2)

// ===== 描述/话题 helper（移植自 video-publisher douyin.mjs，完整版见 references/upload-and-content.md）=====
async function locateDouyinEditor() {
  return await js(String.raw`(() => {
    const compact=v=>String(v||'').replace(/\s+/g,' ').trim()
    const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>180&&r.height>50&&s.display!=='none'&&s.visibility!=='hidden'}
    const rows=[...document.querySelectorAll('[contenteditable="true"],[contenteditable=""]')].map(el=>{const r=el.getBoundingClientRect();let p=el.parentElement,context='';for(let i=0;p&&i<5;i+=1){context+=' '+compact(p.innerText||p.textContent||'');p=p.parentElement}return {el,r,context,cls:String(el.className||'')}}).filter(item=>visible(item.el)&&!item.el.closest('[role="dialog"],[class*="modal"],[class*="dialog"]')).sort((a,b)=>Number(/作品描述|#添加话题|@好友/.test(b.context))-Number(/作品描述|#添加话题|@好友/.test(a.context))||Number(/editor|zone|ace/.test(b.cls))-Number(/editor|zone|ace/.test(a.cls))||b.r.width*b.r.height-a.r.width*a.r.height)
    const item=rows[0];if(!item)return {ok:false,reason:'douyin description editor missing'};item.el.id='vp2-douyin-editor';item.el.scrollIntoView({block:'center',inline:'center'});return {ok:true,selector:'#vp2-douyin-editor',text:item.el.innerText||item.el.textContent||'',className:item.cls,point:{x:item.r.left+Math.min(24,item.r.width/4),y:item.r.top+Math.min(24,item.r.height/3)}}
  })()`)
}
async function focusDouyinEditorEnd() {
  const located=await locateDouyinEditor();if(!located.ok)return located
  const endpoint=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return {ok:false,reason:'douyin editor lost'};const walker=document.createTreeWalker(editor,NodeFilter.SHOW_TEXT);let node,last=null;while((node=walker.nextNode())){if(String(node.nodeValue||'').length)last=node}const er=editor.getBoundingClientRect();if(!last)return {ok:true,point:{x:er.left+12,y:er.top+20}};const range=document.createRange();range.setStart(last,Math.max(0,last.nodeValue.length-1));range.setEnd(last,last.nodeValue.length);const rect=range.getBoundingClientRect();return {ok:true,point:{x:Math.min(er.right-6,Math.max(er.left+6,rect.right+2)),y:Math.min(er.bottom-6,Math.max(er.top+6,rect.top+rect.height/2))}}})()`)
  if(!endpoint.ok)return endpoint
  try{await click([endpoint.point.x,endpoint.point.y],{label:'focus douyin body end'})}catch(error){return {ok:false,reason:String(error?.message||error)}}
  const focused=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return{ok:false,reason:'douyin editor lost before focus confirmation'};editor.focus();const selection=window.getSelection(),range=document.createRange();range.selectNodeContents(editor);range.collapse(false);selection.removeAllRanges();selection.addRange(range);const active=document.activeElement;return{ok:active===editor||editor.contains(active),activeTag:active?.tagName||'',activeId:active?.id||''}})()`)
  await wait(0.2);return focused.ok?{ok:true,point:endpoint.point,focus:focused}:{ok:false,reason:'douyin description editor did not retain focus',evidence:focused}
}
async function clearAndFillDouyinBody(description) {
  let located=await locateDouyinEditor();if(!located.ok)return located
  for(let attempt=0;attempt<3;attempt+=1){
    try{await click([located.point.x,located.point.y],{label:'focus douyin body'})}catch(error){return {ok:false,reason:String(error?.message||error)}}
    const selected=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return{ok:false,reason:'douyin editor lost while selecting body'};editor.focus();const selection=window.getSelection(),range=document.createRange();range.selectNodeContents(editor);selection.removeAllRanges();selection.addRange(range);const active=document.activeElement;return{ok:active===editor||editor.contains(active),activeTag:active?.tagName||'',activeId:active?.id||''}})()`)
    if(!selected.ok)return {ok:false,reason:'douyin description editor did not retain selection focus',evidence:selected}
    await pressKey('Backspace').catch(()=>{});await wait(0.7)
    located=await locateDouyinEditor();if(!String(located.text||'').replace(/[\s\u200b]/g,''))break
  }
  const cleared=await locateDouyinEditor();if(String(cleared.text||'').replace(/[\s\u200b]/g,''))return {ok:false,reason:'douyin description editor did not clear',text:cleared.text}
  if(description){const focused=await focusDouyinEditorEnd();if(!focused.ok)return focused;await cdp('Input.insertText',{text:description});await wait(1)}
  const after=await locateDouyinEditor();const ok=String(after.text||'').replace(/[\s\u200b]/g,'')===String(description||'').replace(/[\s\u200b]/g,'');return ok?{ok:true,text:after.text}:{ok:false,reason:'douyin description did not persist exact value',expected:description,actual:after.text}
}
async function inspectDouyinTrailingPlainText(expectedDescription) {
  // 不再前置 locateDouyinEditor()——clearAndFillDouyinBody 已设 #vp2-douyin-editor id，且 DOM 未变
  return await js(String.raw`((expectedDescription) => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return {ok:false,reason:'douyin editor missing during tail inspection'};const walker=document.createTreeWalker(editor,NodeFilter.SHOW_TEXT);let node,lastPlain=null;while((node=walker.nextNode())){if(!node.parentElement?.closest('[data-mention], [contenteditable="false"]')&&String(node.nodeValue||'').replace(/\u200b/g,'').length)lastPlain=node}let value=String(lastPlain?.nodeValue||'').replace(/\u200b/g,'');if(expectedDescription&&value.startsWith(expectedDescription))value=value.slice(expectedDescription.length);const entities=[...editor.querySelectorAll('[data-mention="#"], [data-mention="activity"]')].map(el=>String(el.innerText||el.textContent||'').replace(/[\s\u200b ]+/g,'').replace(/^#/,'').toLowerCase()).filter(Boolean);return {ok:true,value,trimmed:value.trim(),entities,editorText:String(editor.innerText||editor.textContent||'')}})(${JSON.stringify(expectedDescription)})`)
}
async function removeDouyinTrailingTopicQuery(tag, expectedDescription) {
  const expected='#'+String(tag).replace(/\s+/g,'').toLowerCase()
  const before=await inspectDouyinTrailingPlainText(expectedDescription);if(!before.ok)return before
  const initial=String(before.trimmed||'').toLowerCase()
  if(!initial)return {ok:true,alreadyClean:true,before}
  if(!initial.startsWith('#')||!expected.startsWith(initial))return {ok:false,reason:'douyin trailing text is not a provable prefix of the failed topic query',expected,actual:before.trimmed,evidence:before}
  const focused=await focusDouyinEditorEnd();if(!focused.ok)return focused
  for(let attempt=0;attempt<expected.length+4;attempt+=1){const current=await inspectDouyinTrailingPlainText(expectedDescription);if(!current.ok)return current;const tail=String(current.trimmed||'').toLowerCase();if(!tail||!tail.startsWith('#'))break;if(!expected.startsWith(tail))return {ok:false,reason:'douyin failed-topic tail changed into an unsafe value during cleanup',expected,actual:current.trimmed};await pressKey('Backspace').catch(()=>{});await wait(0.18)}
  const tail=await inspectDouyinTrailingPlainText(expectedDescription);const clean=!String(tail.trimmed||'').startsWith('#');return clean?{ok:true,before,after:tail}:{ok:false,reason:'douyin failed-topic tail could not be removed',tail}
}
async function addDouyinTopic(tag, description) {
  const queryTag=String(tag).replace(/^\s*#/,'').replace(/\s+/g,'')
  const beforeEntities=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return [];return [...editor.querySelectorAll('[data-mention="#"], [data-mention="activity"]')].map(el=>String(el.innerText||el.textContent||'').replace(/[\s\u200b]+/g,'').replace(/^#/,'').toLowerCase()).filter(Boolean)})()`)
  if(beforeEntities.includes(queryTag.toLowerCase()))return {ok:true,already:true}
  const focused=await focusDouyinEditorEnd();if(!focused.ok)return focused
  await cdp('Input.insertText',{text:' '});await wait(0.2)
  const buttonPoint=await js(String.raw`(() => {const c=v=>String(v||'').replace(/\s+/g,' ').trim();const item=[...document.querySelectorAll('button,[role="button"],div,span')].map(el=>({el,text:c(el.innerText||el.textContent||''),r:el.getBoundingClientRect()})).filter(x=>x.text==='#添加话题'&&x.r.width>20&&x.r.width<140&&x.r.height>=8&&x.r.height<50).sort((a,b)=>a.r.width*a.r.height-b.r.width*b.r.height)[0];if(!item)return null;item.el.scrollIntoView({block:'center',inline:'center'});const r=item.el.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()`)
  if(!buttonPoint)return {ok:false,reason:'douyin add-topic button missing'}
  try{await click([buttonPoint.x,buttonPoint.y],{label:'open douyin topic '+queryTag})}catch(error){return {ok:false,reason:String(error?.message||error)}}
  await wait(0.7);await cdp('Input.insertText',{text:queryTag});await wait(1.4)
  const findRow=()=>js(String.raw`((tag) => {const c=v=>String(v||'').replace(/\s+/g,' ').trim();const expected='#'+String(tag).toLowerCase();const containers=[...document.querySelectorAll('[class*="mention-suggest-item-container"],.mention-suggest-mount-dom')].filter(el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'});const rows=containers.flatMap(container=>[...container.querySelectorAll('*')]).map(el=>({text:c(el.innerText||el.textContent||''),r:el.getBoundingClientRect()})).filter(item=>item.r.height>20&&item.r.height<90&&item.r.width>150&&(item.text.toLowerCase()===expected||item.text.toLowerCase().startsWith(expected+' '))).sort((a,b)=>a.text.length-b.text.length);const item=rows[0];return item?{x:item.r.left+Math.min(56,item.r.width/3),y:item.r.top+item.r.height/2,text:item.text}:null})(${JSON.stringify(queryTag)})`)
  let row=null;for(let poll=0;poll<12&&!row;poll+=1){row=await findRow();if(!row)await wait(0.8)}
  if(!row){const cleanup=await removeDouyinTrailingTopicQuery(queryTag,description);return cleanup.ok?{ok:false,reason:'topic suggestion_missing (cleaned)'}:{ok:false,reason:cleanup.reason}}
  try{await click([row.x,row.y],{label:'commit douyin topic '+queryTag})}catch(error){return {ok:false,reason:String(error?.message||error)}}
  await wait(1.4);await pressKey('ArrowRight').catch(()=>{});await cdp('Input.insertText',{text:' '}).catch(()=>{});await wait(0.3)
  const afterEntities=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return [];return [...editor.querySelectorAll('[data-mention="#"], [data-mention="activity"]')].map(el=>String(el.innerText||el.textContent||'').replace(/[\s\u200b]+/g,'').replace(/^#/,'').toLowerCase()).filter(Boolean)})()`)
  if(!afterEntities.includes(queryTag.toLowerCase())){const cleanup=await removeDouyinTrailingTopicQuery(queryTag,description);return {ok:false,reason:cleanup.ok?'topic entity_not_committed (cleaned)':cleanup.reason}}
  return {ok:true,text:row.text}
}

// ===== 描述：清空再单次插入（根因修复：Input.insertText @ caret after provable clear）=====
const body = await clearAndFillDouyinBody(DESCRIPTION)
if (!body.ok) { cliLog('⚠️ 描述填写失败: ' + body.reason + '，转人工'); await handOffTaskSpace(task.id) }
else cliLog('✅ 描述已写入: ' + (body.text||'').slice(0,80))
await wait(0.8 + Math.random()*1.0)

// ===== 话题：逐个实体化 =====
for (const tag of TOPICS) {
  const r = await addDouyinTopic(tag, DESCRIPTION)
  cliLog('话题 #' + tag + ': ' + (r.ok ? '✅ '+(r.already?'已存在':(r.text||'已提交')) : '⚠️ '+r.reason))
  if (!r.ok) { /* 单话题失败只 log 不 handOff，继续下一个 */ }
  await wait(0.6 + Math.random()*0.8)
}

// ===== 校验：实体数 + 残留纯文本 #（一次 js() 往返取两个值）=====
const verify = await js(String.raw`(() => {const e=document.querySelector('#vp2-douyin-editor');if(!e)return{mentionCount:0,residue:''};const mentionCount=e.querySelectorAll('[data-mention="#"], [data-mention="activity"]').length;const c=e.cloneNode(true);c.querySelectorAll('[data-mention],[data-fake-text],[class*="mention"],[class*="topic"],[class*="hash"]').forEach(el=>el.remove());const residue=(c.innerText||c.textContent||'').replace(/\u200b/g,' ').trim();return{mentionCount,residue}})()`)
cliLog('话题实体数=' + verify.mentionCount + '/' + TOPICS.length + ' 残留纯文本#' + (/#/.test(verify.residue)?'有':'无'))
await wait(1)
cliLog(await snapshotText())
EOF
```

描述/话题起草规则见 `references/content-rules.md` 与 `templates/desc-template.md`：1 句钩子 + 1-2 句说明 + 1 句 CTA；话题 3-5 个（1-2 精准 + 2-3 泛），别堆「上热门/涨粉」低质话题。

> Step 4 内联的 helper（`locateDouyinEditor`/`clearAndFillDouyinBody`/`addDouyinTopic` 等）完整可复用源码在 `references/upload-and-content.md` B 节，移植自 video-publisher 的 douyin.mjs。**维护时改 reference 文件，再同步到 SKILL.md。** 描述的根因修复要点：先 Selection API 全选 → `pressKey('Backspace')` 真实删除 → 校验空 → `cdp('Input.insertText')` 单次插入；**别用 `fillInput`**（会追加，React contenteditable 清不净）。

### Step 5 — 配乐（BGM）

**封面：默认跳过，用抖音默认效果。** 图文默认用第 1 张图作封面、视频用首帧，不需要进封面编辑器。**原因**：封面编辑器在自动化下「确定」按钮关不掉弹窗（2026-08-13 真机实测，合成 click / CDP 真实点击 / React onClick 直调 / transform 上移全部无效），强行设会卡死流程。Daniel 若要求设封面，`handOffTaskSpace` 让他手动设——**不要自动化碰封面编辑器**。

**配乐（BGM）**：图文/视频都能在编辑器里配乐，**默认要配**（无配乐的图文观感差、完播低）。只从抖音音乐库选（自动授权、无版权风险），**不要上传本地音频**。配乐不是敏感动作，用普通 `click` 即可，不必走发布那套人类化点击。

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')
const KEYWORD = '科技感'   // ← 按内容主题换：AI/科技→科技感；技术→lofi；商业→大气 …

// ===== 配乐三坑（2026-08-13 真机实测，全部踩过并验证）=====
// ① 入口「选择音乐」页面有多个同名元素，但只有 **cursor:pointer + 含 svg** 的那个能点开面板；
//    其余是 cursor:auto 的纯文字标签，点不动。别靠「猜宽度 w<70」——会撞到不可点的副本。
// ② 搜索框 placeholder 是「搜索音乐」(不是泛"搜索")——`fillInput('input[placeholder*="搜索"]')` 会撞到话题搜索框。
//    且必须用 **React setter + dispatch input/change + 回车** 触发搜索；`Input.insertText` 只改值不触发请求。
// ③ 曲目是虚拟滚动卡片，每首的「使用」按钮**初始不渲染**——先 **点曲目卡片**(整张 pointer)让「使用」浮现，再点它。
//    别去 `===使用` 文本匹配(它是「X万人使用使用」的一部分，永远匹配不到独立按钮)。

// ① 定位真正的配乐入口按钮：cursor:pointer + 含 svg
const entry = await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
  const want=['添加音乐','选择音乐','配乐','选择配乐'];
  const cands=[...document.querySelectorAll('button,div,span,a')].filter(el=>vis(el)&&want.some(w=>(el.textContent||'').trim()===w));
  let pick=cands.find(el=>getComputedStyle(el).cursor==='pointer');
  if(!pick)pick=cands.find(el=>el.querySelector('svg'));
  if(!pick)pick=cands[0];
  if(!pick)return null;
  const r=pick.getBoundingClientRect();
  return{x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight};
})()`)

if(!entry){ cliLog('ℹ️ 没找到配乐入口（可能已配乐/该图集无配乐入口），跳过配乐') }
else if(entry.y<40||entry.y>entry.vh-40){ cliLog('⚠️ 配乐入口不在视口安全区(y='+entry.y+')，先滚动再试') }
else {
  // 点入口开面板（CDP 人类化点击）
  await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:entry.x,y:entry.y})
  await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:entry.x,y:entry.y,button:'left',clickCount:1,buttons:1})
  await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:entry.x,y:entry.y,button:'left',clickCount:1,buttons:1})
  await wait(2.5)

  // ② 聚焦「搜索音乐」框 → React 兼容填值 → 回车触发搜索
  const searchOk = await js(String.raw`(() => {
    const inp=[...document.querySelectorAll('input')].find(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&/搜索音乐/.test(el.placeholder||'')});
    if(!inp)return{ok:false};
    inp.focus(); inp.click();
    inp.id='ego-music-search';
    return{ok:true};
  })()`)
  if(searchOk.ok){
    const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
    await js(String.raw`(() => {const inp=document.querySelector('#ego-music-search');const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;setter.call(inp,${JSON.stringify(KEYWORD)});inp.dispatchEvent(new Event('input',{bubbles:true}));inp.dispatchEvent(new Event('change',{bubbles:true}));return 1})()`)
    await wait(0.8)
    // 回车触发搜索请求
    await cdp('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13})
    await cdp('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13})
    await wait(3)

    // ③ 点第一首曲目卡片（card-wrapper 整张 pointer，第一首通常最热门）
    const card = await js(String.raw`(() => {const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};const c=[...document.querySelectorAll('.card-wrapper-JTleG1, [class*="card-wrapper"]')].filter(vis);if(!c.length)return null;const r=c[0].getBoundingClientRect();return{x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight}})()`)
    if(card&&card.y>40&&card.y<card.vh-40){
      await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:card.x,y:card.y})
      await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:card.x,y:card.y,button:'left',clickCount:1,buttons:1})
      await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:card.x,y:card.y,button:'left',clickCount:1,buttons:1})
      await wait(2)
      // 点完卡片，「使用」按钮浮现，点它
      const useBtn=await js(String.raw`(() => {const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&el.offsetParent!==null};const u=[...document.querySelectorAll('*')].filter(vis).find(el=>(el.textContent||'').trim()==='使用'&&getComputedStyle(el).cursor==='pointer');if(!u)return null;const r=u.getBoundingClientRect();return{x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()`)
      if(useBtn){await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:useBtn.x,y:useBtn.y});await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:useBtn.x,y:useBtn.y,button:'left',clickCount:1,buttons:1});await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:useBtn.x,y:useBtn.y,button:'left',clickCount:1,buttons:1});await wait(2.5)}
    }
  }
  const s=await snapshotText()
  cliLog('配乐结果: ' + (/修改音乐|创作的原声|更换音乐/.test(s)?'✅已选':'⚠️未确认'))
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

> ⚠️ **AIGC 声明必须最后设（顺序坑）**：任何弹窗交互（配乐面板等）**都会重置 AIGC 自主声明**（实测配乐选完 AIGC 从 SET 变 NOT_SET）。所以执行顺序 = 上传 → 标题/描述/话题 → **配乐**（弹窗操作）→ **最后才设 AIGC**（紧接 Step 8 发布前补）。别在中间设完就以为稳了，发弹窗操作后要复查 `aigcSet`、掉了就重设。

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

草稿存好后、**发布前**，跑审批脚本。它会：起 cloudflared 临时隧道 → 发飞书卡片（含标题/描述/话题/封面(默认不设) + 截图链接 + ✅确认发布/❌取消 按钮）→ 阻塞等待 Daniel 点击（默认 9 分钟）→ 返回结果。

```bash
python3 scripts/await_approval.py \
  --config ~/.config/douyin-ego-publish/config.json \
  --screenshot /tmp/douyin_draft_preview.png \
  --type "图文" \
  --title "标题" \
  --desc "描述 #话题1 #话题2" \
  --cover "默认(不设，抖音用首图/首帧)"
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

> ✅ 上述「CDP 单步 mouseMoved + press/release」点击法 **2026-08-10 真机实测通过**：游戏原画图文帖发布成功、**未触发短信验证**。风控仍是概率性的（不同账号/时段/内容可能不同），但这是目前验证过最稳的写法。万一**仍触发短信验证码**，走 **Step 8b 验证码中继**（发飞书让 Daniel 回填，不是转人工）；**滑块/操作频繁**才转人工。

8. **⚠️ semi-design `fixed` 主按钮「点击被吞」坑（2026-08-13 实测）**：发布按钮（`button.fixed-J9O8Yw.primary`）和封面编辑器「确定」按钮都是 semi-design 的 fixed 定位 primary 主按钮。CDP 真实点击会**命中按钮本身**（`elementFromPoint` 返回它、`isTrusted=true`、未禁用、`pointer-events:auto`），却**毫无反应**——不是风控、不是 disabled、不是被遮挡，就是事件被吞。封面确定按钮此坑无解（已改为默认跳过封面）；**发布按钮的解法 = React onClick 直调兜底**：从 `__reactProps` 取出 `onClick` 用 mock event 直接调用（见 Step 8 脚本）。✅ 实测发布成功、未触发验证码、跳转 `/manage`。此兜底是 `isTrusted=false` 合成事件，有触发风控的理论风险——但 CDP 点击已死、先试一次：触发短信验证码走 Step 8b 中继，触发滑块才转人工。

   **判断「点击是否被吞」**：CDP 点击后等 4s，snapshot 既无「正在发布/发布成功/验证码/滑块」任何信号 = 被吞 → 立刻 fallback 到 React onClick 直调，别反复点 CDP。

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
  cliLog('⚠️ 找不到可点的「发布」按钮——多半是自主声明没完成，先补上再发布')
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
let after = await snapshotText()
let hitCode = /验证码|短信验证码|发送验证码/.test(after)
let hitSlider = /滑块|拖动|滑动验证|请按住/.test(after)
let ok = /发布成功|成功发布|\/manage/.test(after)

// —— ⚠️ fixed 主按钮「点击被吞」兜底（2026-08-13 实测）：——
// 抖音发布按钮是 semi-design 的 `fixed-J9O8Yw` primary 主按钮。CDP 真实点击 elementFromPoint 命中按钮本身、
// isTrusted=true、未禁用，却【毫无反应】（没有正在发布/成功/验证码任何信号）——和封面编辑器「确定」按钮同一个坑。
// 此时 CDP 点击已确认无效，唯一能触发发布的是 React onClick 直调（从 __reactProps 取 onClick 直接调用）。
// ✅ 2026-08-13 实测：CDP 点击无反应 → React onClick 直调 → 立即发布成功、未触发验证码、跳转 /manage。
// 风控说明：React onClick 是 isTrusted=false 的合成事件，理论上有触发风控风险；但 CDP 点击已死、转人工又得 Daniel 介入，
// 先用此兜底试一次——若因此触发短信验证码，照常走 Step 8b 中继；触发滑块才转人工。
if (!ok && !hitCode && !hitSlider) {
  cliLog('⚠️ CDP 点击发布无反应，改用 React onClick 直调')
  const r = await js(String.raw`(() => {
    const c=v=>String(v||'').replace(/\s+/g,' ').trim()
    const btn=[...document.querySelectorAll('button')].find(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&!el.disabled&&c(el.textContent)==='发布'&&/fixed/i.test(String(el.className))})
    if(!btn)return {ok:false,reason:'发布btn not found'}
    const reactKey=Object.keys(btn).find(k=>k.startsWith('__reactProps'))
    const props=reactKey?btn[reactKey]:null
    if(props&&typeof props.onClick==='function'){ try{props.onClick({preventDefault(){},stopPropagation(){},currentTarget:btn,target:btn,nativeEvent:{},type:'click'});return{ok:true}}catch(e){return{ok:false,reason:String(e)}} }
    return {ok:false,reason:'no onClick'}
  })()`)
  cliLog('React onClick: ' + JSON.stringify(r))
  await wait(4)
  after = await snapshotText()
  hitCode = /验证码|短信验证码|发送验证码/.test(after)
  hitSlider = /滑块|拖动|滑动验证|请按住/.test(after)
  ok = /发布成功|成功发布|\/manage/.test(after)
}

// 发布结果三类信号：成功 / 验证码(走 Step 8b 中继) / 风控(转人工)
// 「验证码/短信」命中 = 触发了短信验证 → 下一步跑 scripts/await_verification_code.py 中继
// 注意：只认「短信验证码」，滑块/「操作频繁」是另一类风控，转人工（见末尾兜底）。
cliLog('正在发布=' + after.includes('正在发布') + ' 验证码=' + hitCode + ' 滑块=' + hitSlider + ' 成功=' + ok)
EOF
```

发布后确认页面变化（出现「发布成功」或跳转到管理页），再截图回传 Daniel。

**若触发了验证码**（上面 `验证码=true`）→ 走 **Step 8b 验证码中继**，不要直接 handOff。**滑块**（`滑块=true`）或「操作频繁」→ 仍按末尾兜底转人工，中继只处理短信验证码。

### Step 8b — 验证码中继（发布后弹短信验证码时）

⚠️ **与 Step 7 审批门完全独立、不同时**：Step 7 是「发布前」的审批卡片；本步是「点了发布、抖音弹出验证码之后」发的**另一条**飞书消息。技术模式一样（隧道+本地HTTP），但触发时机、消息、用途都不同。

**整体闭环**：点发布后 snapshot 命中验证码 → **先抓出抖音弹窗里的手机尾号提示**（写在飞书卡片上，Daniel 才知道验证码发到哪了）→ 跑 `scripts/await_verification_code.py` 发飞书卡片 + 起 webhook 阻塞等码 → Daniel 在飞书点「📝 输入验证码」填入收到的短信码 → 脚本返回 `RESULT=CODE_RECEIVED` + `CODE=xxxx` → **把这个 CODE 填回抖音验证码输入框、点「确认/提交」** → 重新检测发布是否成功。

**① 先从抖音页面抓验证码相关文案**（手机尾号、验证码发送方），供飞书卡片展示：

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')
// 抓抖音验证码弹窗里的手机尾号 + 文案。抖音文案变体多，尽量捞全。
const probe = await js(String.raw`(() => {
  const text = (document.body.innerText || '').replace(/\s+/g, ' ')
  // 手机尾号：常见「尾号 1234」「****1234」「已发送至 1234」
  const m = text.match(/(?:尾号|已发送至|发送至|短信将发送至)[^\d]{0,4}(\d{4})/) || text.match(/\*{4}(\d{4})/)
  // 验证码输入框（抖音常为数字输入或带 placeholder 的 input）
  const inputs = [...document.querySelectorAll('input')].map(el => ({ph: el.placeholder || '', type: el.type || '', vis: !!el.offsetParent}))
  return { phoneTail: m ? m[1] : '', snippet: text.slice(text.search(/验证码|短信/) - 30, text.search(/验证码|短信/) + 120), inputCount: inputs.filter(i=>i.vis).length, inputs: inputs.slice(0,6) }
})()`)
cliLog('VERIFY_PROBE=' + JSON.stringify(probe))
await captureScreenshot('/tmp/douyin_captcha.png')
EOF
```

**② 跑验证码中继脚本**（阻塞，默认等 300s，贴合短信时效；cloudflared 进程脚本自管）：

```bash
# PHONE_TAIL 从上一步 cliLog 的 phoneTail 抓到；抓不到就传空串，用默认文案
python3 scripts/await_verification_code.py \
  --config ~/.config/douyin-ego-publish/config.json \
  --phone-hint "尾号 1234"   # ← 替换成真实尾号；抓不到就删掉这行
```

脚本 stdout 最后一行 `RESULT=...`，成功时还有 `CODE=xxxx`：
- **`RESULT=CODE_RECEIVED` + `CODE=xxxx`** → 拿到码，继续 ③ 把它填进抖音。
- **`RESULT=TIMEOUT`** → 短信超时，**转人工**：保留草稿、`handOffTaskSpace`、告诉 Daniel 验证码页面还在，让他手动输。
- **`RESULT=SEND_FAILED` / `RESULT=NO_CF`** → 配置/隧道问题，**转人工**，别硬刚。

**③ 把验证码填回抖音验证框、点确认**（拿到 CODE 后执行）。验证码输入框 DOM 各版本不同，用 placeholder/文本定位；输入同样走 CDP 真实事件、人类化节奏（敏感动作）：

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('douyin publish')
const CODE = '123456'   // ← 替换成 await_verification_code.py 返回的 CODE

// 定位验证码输入框：placeholder 含「验证码」、或 type=tel/number、或弹窗内唯一可见 input
const target = await js(String.raw`((code) => {
  const vis = el => { const r = el.getBoundingClientRect(); return r.width>0 && r.height>0 }
  const all = [...document.querySelectorAll('input, [contenteditable="true"]')].filter(el => vis(el) && !el.disabled)
  // ① placeholder 命中「验证码」
  let el = all.find(e => /验证码|code/i.test(e.placeholder || ''))
  // ② 数字/tel 类型的单框
  if (!el) el = all.find(e => /^(tel|number|text)$/.test(e.type || '') && /验证码|code/i.test(e.getAttribute('aria-label') || e.placeholder || ''))
  // ③ 弹窗(dialog/modal)内唯一可见 input
  if (!el) {
    const dlg = [...document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="dialog"]')].find(d => d.querySelector('input'))
    if (dlg) { const ins = [...dlg.querySelectorAll('input')].filter(vis); if (ins.length) el = ins[0] }
  }
  if (!el) return { ok:false, reason:'验证码输入框未找到（可能弹窗已关/是 6 格分框）' }
  el.id = 'ego-verify-input'; el.scrollIntoView({ block:'center' })
  const r = el.getBoundingClientRect()
  return { ok:true, selector:'#ego-verify-input', tag: el.tagName, type: el.type, ph: el.placeholder, point:{x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)} }
})(${JSON.stringify(CODE)})`)
cliLog('VERIFY_INPUT=' + JSON.stringify(target))
if (!target.ok) { cliLog('⚠️ ' + target.reason + '，转人工'); await handOffTaskSpace(task.id) }
else {
  await wait(1.5 + Math.random()*1.5)   // 人类停顿
  // 点击聚焦（CDP），再单格单格 Input.insertText（部分抖音验证码是 6 格分框）
  await cdp('Input.dispatchMouseEvent', { type:'mouseMoved', x:target.point.x, y:target.point.y })
  await cdp('Input.dispatchMouseEvent', { type:'mousePressed',  x:target.point.x, y:target.point.y, button:'left', clickCount:1, buttons:1 })
  await cdp('Input.dispatchMouseEvent', { type:'mouseReleased', x:target.point.x, y:target.point.y, button:'left', clickCount:1, buttons:1 })
  await wait(0.6)
  // 整框：一次填入；若是分框，insertText 通常会自动分配，逐位填是更稳兜底
  try {
    await js(String.raw`(() => { const el=document.querySelector(${JSON.stringify(target.selector)}); if(el){el.focus(); el.value='';} return 1 })()`)
    await cdp('Input.insertText', { text: ${JSON.stringify(CODE)} })
    await wait(0.8)
  } catch (e) { cliLog('整框填入失败，试逐位: ' + e) }
  // 逐位兜底（应对 6 格分框）
  for (const ch of ${JSON.stringify(CODE)}.split('')) {
    await cdp('Input.dispatchKeyEvent', { type:'keyDown', key:ch, code:'Digit'+ch, text:ch }).catch(()=>{})
    await cdp('Input.dispatchKeyEvent', { type:'keyUp', key:ch, code:'Digit'+ch }).catch(()=>{})
    await wait(0.15 + Math.random()*0.2)
  }
  await wait(1)

  // 点「确认/提交/验证」按钮（CDP 人类化点击）
  const btn = await js(String.raw`(() => {
    const vis = el => { const r=el.getBoundingClientRect(); return r.width>0&&r.height>0 }
    const want = ['确认','验证','提交','确定']
    const b = [...document.querySelectorAll('button,[role="button"]')].find(el => vis(el) && !el.disabled && want.some(w => (el.textContent||'').trim()===w))
    if (!b) return null
    const r = b.getBoundingClientRect()
    return { x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), text:(b.textContent||'').trim() }
  })()`)
  if (btn) {
    cliLog('点确认按钮: ' + btn.text)
    await wait(0.8 + Math.random()*0.8)
    await cdp('Input.dispatchMouseEvent', { type:'mouseMoved', x:btn.x, y:btn.y })
    await cdp('Input.dispatchMouseEvent', { type:'mousePressed',  x:btn.x, y:btn.y, button:'left', clickCount:1, buttons:1 })
    await cdp('Input.dispatchMouseEvent', { type:'mouseReleased', x:btn.x, y:btn.y, button:'left', clickCount:1, buttons:1 })
  } else {
    cliLog('⚠️ 没找到确认按钮（可能填完自动校验），snapshot 确认')
  }
  await wait(4)
  const after = await snapshotText()
  cliLog('验证后 成功=' + /发布成功|成功发布|\/manage/.test(after) + ' 仍验证=' + /验证码|短信/.test(after))
  await captureScreenshot('/tmp/douyin_after_verify.png')
}
EOF
```

验证后若 snapshot 出现「发布成功 / 跳转 /manage」→ 发布完成，截图回传 Daniel。若**仍停在验证码页**（码错/过期）→ **转人工**：`handOffTaskSpace`，别自动重试（短时重发触发更强风控）。

**为什么用独立的表单页中继而不是飞书原生输入框**：飞书自定义机器人 + `open_url` 按钮点开即一次网页访问，**每次隧道的 URL 变都没关系、零额外配置**。飞书原生输入回调需预注册回调地址、走开放平台应用，配置重。复用审批门同一套隧道/直连 opener/加签件，所以**不发新消息、不碰飞书额外配置**。

**兜底（滑块 / 操作频繁 / 码超时）**：中继只覆盖短信验证码。其余风控仍是概率性的，反检测只能降低、不能杜绝：
- snapshot 出现「滑块 / 拖动 / 请按住」——**立刻 `handOffTaskSpace`**，让 Daniel 手动滑。
- 验证码中继 `RESULT=TIMEOUT`（短信超时）——保留草稿、转人工，别重发。
- 「操作频繁」——转人工，等一段时间再说。

一律 `handOffTaskSpace` + 截图 + 告诉 Daniel 当前状态/手机尾号，**绝不要自动重试滑块或重复点发布**。

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

1. 登录/风控：扫码、滑块、二次验证、「操作频繁」——转人工别硬刚。
   > ⚠️ **「短信验证码」是例外**——不转人工，走 **Step 8b 验证码中继**（发飞书让 Daniel 回填，Claude 自动填回抖音）。只有中继 `RESULT=TIMEOUT`（短信超时）才转人工。
2. 上传卡住 >8 分钟仍 0%，或描述区迟迟不出现
3. 发布/草稿按钮长时间 disabled 或点不动
4. 选择器漂移：描述区定位不到
5. 发布时被「请完成自主声明」拦截

## 回传给 Daniel 的标准信息

每次动作后回传：类型、标题、描述、话题、封面状态、**BGM（配乐名或风格）**、AIGC 是否勾、当前状态（已存草稿/待审批/已发布/**待回填验证码**/待接管）、截图路径。

## 参考文件（按需读）

- `references/content-rules.md` — 标题/描述/话题/封面/AIGC 完整规范与适配模板
- `references/douyin-dom.md` — 创作者后台选择器、按钮文案变体、上传/风控排坑
- `references/feishu-setup.md` — 飞书机器人 + cloudflared 一次性配置
- `templates/desc-template.md` — 描述/话题起草模板
