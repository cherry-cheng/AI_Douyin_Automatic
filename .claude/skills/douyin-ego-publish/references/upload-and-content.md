# 图文上传 + 描述/话题填写：可复用源码

> 本文件是 `SKILL.md` Step 2 / Step 4 内联代码块的**完整可复用源码**与权威版本。SKILL.md 里是缩略注释版（标注函数名 + 参考行号），**维护时改本文件，再同步到 SKILL.md**。
>
> 移植自生产验证的实现：
> - `video-publisher/scripts/v2/platforms/douyin.mjs`（视频页 adapter，已验证）L118-161（上传）、L186-223（编辑器清空填写）、L275-314（话题实体化）
> - `video-publisher/scripts/v2/platforms/wechat-channels.mjs` L43 / L84-87（CDP `DOM.setFileInputFiles` 注入 + image accept 正则）
>
> 适配点（image vs video）：
> - input 的 accept 正则从 `/video|\.mp4.../i` 改为 `/image|png|jpe?g|webp/i`，找不到则取第一个 `input[type=file]`（图文页 accept 可能为空/通用）。
> - 多文件：input 若 `multiple` 则一次性 `files:[所有路径]`；否则逐张 `uploadFile(id, path)`（每次前 `input.value=''`）。
> - 全部依赖 ego-browser 原语：`js`、`cdp`、`click`、`uploadFile`、`pressKey`、`wait`、`snapshotText`、`handOffTaskSpace`。
> - **铁律**：`js(codeString)` 是 CDP `Runtime.evaluate` 的薄包装，**不捕获闭包变量**。所有正则、待写文本都必须**字面内联**进传给 `js()` 的字符串里，不能引用 Node 侧变量。

---

## A. 上传相关（Step 2）

### A1. `inspectImageUploadState()` — 上传状态探针
来源：`douyin.mjs` `inspectDouyin` L10-98（裁剪，只保留上传/编辑器就绪信号）。

```js
async function inspectImageUploadState() {
  return await js(String.raw`(() => {
    const compact = v => String(v||'').replace(/\s+/g,' ').trim()
    const text = compact(document.body.innerText||'')
    const editorReady = !!document.querySelector('[contenteditable="true"],[contenteditable=""]') && /暂存离开|存草稿/.test(text)
    return {
      text: text.slice(0,1200),
      // uploadSucceeded 不返回——稳定轮询只用 editorReady/uploading/uploadFailed
      uploading: /上传过程中|取消上传|上传剩余时间|已上传：|上传速度|当前速度/.test(text) && !/上传成功/.test(text),
      uploadFailed: /上传失败|网络错误|重新上传失败/.test(text),
      editorReady
    }
  })()`)
}
```

### A2. `exposeImageInput()` — 定位真实图片 input 并打 id
来源：`douyin.mjs` L130（accept 正则改 image + shadow root 遍历）。

```js
async function exposeImageInput() {
  return await js(String.raw`(() => {
    const acceptRe = /image|png|jpe?g|webp/i
    const roots = [document, ...[...document.querySelectorAll('*')].map(el=>el.shadowRoot).filter(Boolean)]
    const inputs = roots.flatMap(r => [...r.querySelectorAll('input[type=file]')])
    let input = inputs.find(el => acceptRe.test(el.accept||''))
    if (!input) input = inputs[0] || null          // fallback：accept 为空/通用时取第一个
    if (!input) return { ok:false, reason:'image input not found in main DOM or shadow roots' }
    input.value=''; input.id='vp2-douyin-image'
    return { ok:true, selector:'#vp2-douyin-image', multiple: input.hasAttribute('multiple') }
  })()`)
}
```

### A3. `injectImageInput()` — 注入自己的 input（图文页主力，2026-08-12 实测验证）
**为什么需要它**：抖音图文页整页**不挂载持久 `input[type=file]`**——点击「点击上传」区在自动化下不弹原生 dialog，input 永不创建（详见底部「图文页上传机制实测结论」）。但抖音 dropzone 监听的是**事件冒泡**，不在乎 input 是不是它自己的：主动注入一个 input → `uploadFile` 喂值 → dispatch change，抖音就会响应并上传。视频页通常有原生 input（走 A2 `exposeImageInput`），图文页靠这招。

```js
async function injectImageInput() {
  return await js(String.raw`(() => {
    let old = document.querySelector('#ego-injected-upload'); if (old) old.remove()
    const dz = [...document.querySelectorAll('[class]')].find(e => /content-upload|upload-zone|dragger/i.test(String(e.className))) || document.body
    const input = document.createElement('input')
    input.type='file'; input.multiple=true; input.accept='image/*'; input.id='ego-injected-upload'
    input.style.cssText='position:fixed;top:10px;left:10px;opacity:0.01;width:1px;height:1px;z-index:99999'
    dz.appendChild(input)
    return { ok:true, selector:'#ego-injected-upload' }
  })()`)
}
```

> 历史兜底：曾有 `cdpInjectImages(paths)`（原始 CDP `DOM.setFileInputFiles` via `Runtime.evaluate` objectId，移植自 `wechat-channels.mjs` L43/L84-87）。**2026-08-12 实测在图文页无效**——因为图文页根本没有 input 可被 `Runtime.evaluate` 解析出 objectId。注入 input（本函数）是更可靠的替代：创建 input 后 `uploadFile` 能直接喂值。该 CDP 注入法在视频页（有持久 input）仍可用，故保留概念说明。

### A4. `uploadImagesWithFallback(paths)` — fallback 链（注入 input 为主力）
来源：`douyin.mjs` `uploadDouyin` L118-161（结构）+ 注入 input 法（2026-08-12 实测）。

```js
async function uploadImagesWithFallback(paths) {
  // ① 找抖音原生 input（视频页通常有；图文页通常没有）。轮询 ~8s 即可，别长等。
  let exposed = null
  for (let i=0; i<16; i++) { exposed = await exposeImageInput(); if (exposed.ok) break; await wait(0.5) }

  // ② 注入自己的 input（图文页主力！原生 input 找不到时立即注入，已验证可行）
  if (!exposed?.ok) {
    const inj = await injectImageInput()
    exposed = inj   // { ok:true, selector:'#ego-injected-upload' }（multiple 固定 true）
  }

  // ③ 注入也失败（极端情况）→ handOff
  if (!exposed?.ok) {
    cliLog('⚠️ 注入 input 失败，转人工拖拽')
    await handOffTaskSpace(task.id)
    return { ok:false, mode:'handoff', reason: exposed?.reason || 'inject failed' }
  }

  // 喂文件：multiple input 一次性 uploadFile 数组；失败降级逐张
  const sel = exposed.selector
  try {
    await uploadFile(sel, paths)
    // dispatch change/input 让抖音 dropzone 响应（注入的 input 必须主动派发）
    await js(String.raw`(() => { const i=document.querySelector(${JSON.stringify(sel)}); if(i){i.dispatchEvent(new Event('change',{bubbles:true}));i.dispatchEvent(new Event('input',{bubbles:true}));} return 1 })()`)
    return { ok:true, mode:'array', count:paths.length }
  } catch (e) {
    for (const p of paths) {
      await js(String.raw`(() => { const i=document.querySelector(${JSON.stringify(sel)}); if(i){i.value='';} return 1 })()`)
      try { await uploadFile(sel, p) } catch (e2) { return { ok:false, mode:'per_file', failedPath:p, reason:String(e2?.message||e2) } }
      await js(String.raw`(() => { const i=document.querySelector(${JSON.stringify(sel)}); if(i){i.dispatchEvent(new Event('change',{bubbles:true}));} return 1 })()`)
      await wait(0.8)
    }
    return { ok:true, mode:'per_file', count:paths.length }
  }
}
```

> **2026-08-12 图文页上传机制实测结论**：抖音图文页整页**不挂载持久 `input[type=file]`**（主 DOM + shadow DOM + outerHTML 全无），点击「点击上传」区在自动化下不弹原生 dialog（input 永不创建）。`DOM.setFileInputFiles` 因无 objectId 失败；`Page.setInterceptFileChooserDialog` 可开启但 ego-browser **没有** `Page.handleFileChooser` 方法。唯一可行路径 = **注入自己的 input + `uploadFile` 喂值 + dispatch change**（抖音 dropzone 监听事件冒泡）。视频页有原生 input，走 A2 即可。

### A5. 稳定完成轮询（上传后等待）
来源：`douyin.mjs` L133-157。10s 稳定窗口，区分明确失败/卡住/进行中。

```js
// 在 uploadImagesWithFallback 返回 ok 后调用
let stableSince = 0
for (let i=0; i<120; i++) {
  await wait(5)
  const s = await inspectImageUploadState()
  if (s.editorReady && !s.uploading && !s.uploadFailed) {
    if (!stableSince) stableSince = Date.now()
    if (Date.now()-stableSince >= 10000) { cliLog('✅ 图文上传稳定完成'); break }
  } else stableSince = 0
  if (s.uploadFailed) { cliLog('⚠️ 明确上传失败: ' + s.text.slice(0,200)); break }
}
```

---

## B. 描述/话题相关（Step 4）

### B1. `locateDouyinEditor()` — 定位描述编辑器并打 id
来源：`douyin.mjs` L186-192（原文，图文页同样适用）。

```js
async function locateDouyinEditor() {
  return await js(String.raw`(() => {
    const compact=v=>String(v||'').replace(/\s+/g,' ').trim()
    const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>180&&r.height>50&&s.display!=='none'&&s.visibility!=='hidden'}
    const rows=[...document.querySelectorAll('[contenteditable="true"],[contenteditable=""]')].map(el=>{const r=el.getBoundingClientRect();let p=el.parentElement,context='';for(let i=0;p&&i<5;i+=1){context+=' '+compact(p.innerText||p.textContent||'');p=p.parentElement}return {el,r,context,cls:String(el.className||'')}}).filter(item=>visible(item.el)&&!item.el.closest('[role="dialog"],[class*="modal"],[class*="dialog"]')).sort((a,b)=>Number(/作品描述|#添加话题|@好友/.test(b.context))-Number(/作品描述|#添加话题|@好友/.test(a.context))||Number(/editor|zone|ace/.test(b.cls))-Number(/editor|zone|ace/.test(a.cls))||b.r.width*b.r.height-a.r.width*a.r.height)
    const item=rows[0]
    if(!item) return {ok:false,reason:'douyin description editor missing'}
    item.el.id='vp2-douyin-editor'; item.el.scrollIntoView({block:'center',inline:'center'})
    return {ok:true,selector:'#vp2-douyin-editor',text:item.el.innerText||item.el.textContent||'',className:item.cls,point:{x:item.r.left+Math.min(24,item.r.width/4),y:item.r.top+Math.min(24,item.r.height/3)}}
  })()`)
}
```

### B2. `focusDouyinEditorEnd()` — 聚焦编辑器末尾（插入前定位 caret）
来源：`douyin.mjs` L194-209（原文）。

```js
async function focusDouyinEditorEnd() {
  const located = await locateDouyinEditor()
  if (!located.ok) return located
  const endpoint = await js(String.raw`(() => {
    const editor=document.querySelector('#vp2-douyin-editor'); if(!editor) return {ok:false,reason:'douyin editor lost'}
    const walker=document.createTreeWalker(editor,NodeFilter.SHOW_TEXT); let node,last=null
    while((node=walker.nextNode())){ if(String(node.nodeValue||'').length) last=node }
    const er=editor.getBoundingClientRect()
    if(!last) return {ok:true,point:{x:er.left+12,y:er.top+20}}
    const range=document.createRange(); range.setStart(last,Math.max(0,last.nodeValue.length-1)); range.setEnd(last,last.nodeValue.length)
    const rect=range.getBoundingClientRect()
    return {ok:true,point:{x:Math.min(er.right-6,Math.max(er.left+6,rect.right+2)),y:Math.min(er.bottom-6,Math.max(er.top+6,rect.top+rect.height/2))}}
  })()`)
  if (!endpoint.ok) return endpoint
  try { await click([endpoint.point.x,endpoint.point.y],{label:'focus douyin body end'}) } catch(error){ return {ok:false,reason:String(error?.message||error)} }
  const focused = await js(String.raw`(() => {
    const editor=document.querySelector('#vp2-douyin-editor'); if(!editor) return{ok:false,reason:'douyin editor lost before focus confirmation'}
    editor.focus()
    const selection=window.getSelection(),range=document.createRange()
    range.selectNodeContents(editor); range.collapse(false)
    selection.removeAllRanges(); selection.addRange(range)
    const active=document.activeElement
    return {ok:active===editor||editor.contains(active),activeTag:active?.tagName||'',activeId:active?.id||''}
  })()`)
  await wait(0.2)
  return focused.ok ? {ok:true,point:endpoint.point,focus:focused} : {ok:false,reason:'douyin description editor did not retain focus',evidence:focused}
}
```

### B3. `clearAndFillDouyinBody(description)` — 描述根因修复
来源：`douyin.mjs` L211-223（参数化：`description` 作参数传入，而非模块变量）。

**根治追加 bug 的核心**：先 Selection API 全选 → `pressKey('Backspace')` 真实删除 → 校验 `innerText` 空（重试 3 次）→ `focusDouyinEditorEnd` → `cdp('Input.insertText')` 单次插入。`Input.insertText` 仅在 caret 处插入，且前置已证空，不会追加。

```js
async function clearAndFillDouyinBody(description) {
  let located = await locateDouyinEditor()
  if (!located.ok) return located
  for (let attempt=0; attempt<3; attempt+=1) {
    try { await click([located.point.x,located.point.y],{label:'focus douyin body'}) } catch(error){ return {ok:false,reason:String(error?.message||error)} }
    const selected = await js(String.raw`(() => {
      const editor=document.querySelector('#vp2-douyin-editor'); if(!editor) return{ok:false,reason:'douyin editor lost while selecting body'}
      editor.focus()
      const selection=window.getSelection(),range=document.createRange()
      range.selectNodeContents(editor); selection.removeAllRanges(); selection.addRange(range)
      const active=document.activeElement
      return {ok:active===editor||editor.contains(active),activeTag:active?.tagName||'',activeId:active?.id||''}
    })()`)
    if (!selected.ok) return {ok:false,reason:'douyin description editor did not retain selection focus',evidence:selected}
    await pressKey('Backspace').catch(()=>{}); await wait(0.7)
    located = await locateDouyinEditor()
    if (!String(located.text||'').replace(/[\s\u200b]/g,'')) break
  }
  const cleared = await locateDouyinEditor()
  if (String(cleared.text||'').replace(/[\s\u200b]/g,'')) return {ok:false,reason:'douyin description editor did not clear',text:cleared.text}
  if (description) {
    const focused = await focusDouyinEditorEnd()
    if (!focused.ok) return focused
    await cdp('Input.insertText',{text:description}); await wait(1)
  }
  const after = await locateDouyinEditor()
  const ok = String(after.text||'').replace(/[\s\u200b]/g,'') === String(description||'').replace(/[\s\u200b]/g,'')
  return ok ? {ok:true,text:after.text} : {ok:false,reason:'douyin description did not persist exact value',expected:description,actual:after.text}
}
```

### B4. 话题支持函数
来源：`douyin.mjs` L225-273（`normalizeDouyinTopic` + `inspectDouyinTrailingPlainText` + `removeDouyinTrailingTopicQuery`，原文）。

```js
const normalizeDouyinTopic = value => String(value || '').replace(/^#/, '').replace(/\s+/g, '').toLowerCase()

async function inspectDouyinTrailingPlainText(expectedDescription) {
  // 不再前置 locateDouyinEditor()——clearAndFillDouyinBody 已设 id
  return await js(String.raw`((expectedDescription) => {
    const editor=document.querySelector('#vp2-douyin-editor'); if(!editor) return {ok:false,reason:'douyin editor missing during tail inspection'}
    const walker=document.createTreeWalker(editor,NodeFilter.SHOW_TEXT); let node,lastPlain=null
    while((node=walker.nextNode())){ if(!node.parentElement?.closest('[data-mention], [contenteditable="false"]')&&String(node.nodeValue||'').replace(/\u200b/g,'').length) lastPlain=node }
    let value=String(lastPlain?.nodeValue||'').replace(/\u200b/g,'')
    if(expectedDescription&&value.startsWith(expectedDescription)) value=value.slice(expectedDescription.length)
    const entities=[...editor.querySelectorAll('[data-mention="#"], [data-mention="activity"]')].map(el=>String(el.innerText||el.textContent||'').replace(/[\s\u200b ]+/g,'').replace(/^#/,'').toLowerCase()).filter(Boolean)
    return {ok:true,value,trimmed:value.trim(),entities,editorText:String(editor.innerText||editor.textContent||'')}
  })(${JSON.stringify(expectedDescription)})`)
}

async function removeDouyinTrailingTopicQuery(tag, expectedDescription) {
  const expected='#'+String(tag).replace(/\s+/g,'').toLowerCase()
  const before = await inspectDouyinTrailingPlainText(expectedDescription)
  if (!before.ok) return before
  const initial = String(before.trimmed||'').toLowerCase()
  if (!initial) return {ok:true,alreadyClean:true,before}
  if (!initial.startsWith('#')||!expected.startsWith(initial)) return {ok:false,reason:'douyin trailing text is not a provable prefix of the failed topic query',expected,actual:before.trimmed,evidence:before}
  const focused = await focusDouyinEditorEnd(); if(!focused.ok) return focused
  for (let attempt=0; attempt<expected.length+4; attempt+=1) {
    const current = await inspectDouyinTrailingPlainText(expectedDescription)
    if(!current.ok) return current
    const tail = String(current.trimmed||'').toLowerCase()
    if(!tail||!tail.startsWith('#')) break
    if(!expected.startsWith(tail)) return {ok:false,reason:'douyin failed-topic tail changed into an unsafe value during cleanup',expected,actual:current.trimmed}
    await pressKey('Backspace').catch(()=>{}); await wait(0.18)
  }
  const tail = await inspectDouyinTrailingPlainText(expectedDescription)
  const clean = !String(tail.trimmed||'').startsWith('#')
  return clean ? {ok:true,before,after:tail} : {ok:false,reason:'douyin failed-topic tail could not be removed',tail}
}
```

### B5. `addDouyinTopic(tag, description)` — 话题实体化
来源：`douyin.mjs` L275-314（参数化：`tag` + `description` 作参数）。点真实 `#添加话题` → insertText 输入 → 等建议面板 → 点精确行 → ArrowRight+空格提交。

```js
async function addDouyinTopic(tag, description) {
  const queryTag = String(tag).replace(/^\s*#/,'').replace(/\s+/g,'')
  const findRow = () => js(String.raw`((tag) => {
    const c=v=>String(v||'').replace(/\s+/g,' ').trim()
    const expected='#'+String(tag).toLowerCase()
    const containers=[...document.querySelectorAll('[class*="mention-suggest-item-container"],.mention-suggest-mount-dom')].filter(el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'})
    const rows=containers.flatMap(container=>[...container.querySelectorAll('*')]).map(el=>({text:c(el.innerText||el.textContent||''),r:el.getBoundingClientRect()})).filter(item=>item.r.height>20&&item.r.height<90&&item.r.width>150&&(item.text.toLowerCase()===expected||item.text.toLowerCase().startsWith(expected+' '))).sort((a,b)=>a.text.length-b.text.length)
    const item=rows[0]
    return item?{x:item.r.left+Math.min(56,item.r.width/3),y:item.r.top+item.r.height/2,text:item.text}:null
  })(${JSON.stringify(queryTag)})`)

  // 检查是否已是实体（防重复）
  const beforeEntities = await js(String.raw`(() => {
    const editor=document.querySelector('#vp2-douyin-editor'); if(!editor) return []
    return [...editor.querySelectorAll('[data-mention="#"], [data-mention="activity"]')].map(el=>String(el.innerText||el.textContent||'').replace(/[\s\u200b]+/g,'').replace(/^#/,'').toLowerCase()).filter(Boolean)
  })()`)
  if (beforeEntities.includes(queryTag.toLowerCase())) return {ok:true,already:true}

  const focused = await focusDouyinEditorEnd(); if(!focused.ok) return focused
  await cdp('Input.insertText',{text:' '}); await wait(0.2)

  // 点真实 #添加话题 控件
  const buttonPoint = await js(String.raw`(() => {
    const c=v=>String(v||'').replace(/\s+/g,' ').trim()
    const item=[...document.querySelectorAll('button,[role="button"],div,span')].map(el=>({el,text:c(el.innerText||el.textContent||''),r:el.getBoundingClientRect()})).filter(x=>x.text==='#添加话题'&&x.r.width>20&&x.r.width<140&&x.r.height>=8&&x.r.height<50).sort((a,b)=>a.r.width*a.r.height-b.r.width*b.r.height)[0]
    if(!item) return null
    item.el.scrollIntoView({block:'center',inline:'center'})
    const r=item.el.getBoundingClientRect()
    return {x:r.left+r.width/2,y:r.top+r.height/2}
  })()`)
  if(!buttonPoint) return {ok:false,reason:'douyin add-topic button missing'}
  try { await click([buttonPoint.x,buttonPoint.y],{label:'open douyin topic '+queryTag}) } catch(error){ return {ok:false,reason:String(error?.message||error)} }
  await wait(0.7); await cdp('Input.insertText',{text:queryTag}); await wait(1.4)

  // 等建议面板精确匹配行
  let row=null
  for (let poll=0; poll<12&&!row; poll+=1) { row=await findRow(); if(!row) await wait(0.8) }
  if(!row){
    const cleanup = await removeDouyinTrailingTopicQuery(queryTag, [], description)
    return cleanup.ok ? {ok:false,reason:'topic suggestion_missing (cleaned up)'} : {ok:false,reason:cleanup.reason}
  }
  try { await click([row.x,row.y],{label:'commit douyin topic '+queryTag}) } catch(error){ return {ok:false,reason:String(error?.message||error)} }
  await wait(1.4)

  // 提交实体：ArrowRight + 空格
  await pressKey('ArrowRight').catch(()=>{}); await cdp('Input.insertText',{text:' '}).catch(()=>{}); await wait(0.3)

  // 校验是否成了实体
  const afterEntities = await js(String.raw`(() => {
    const editor=document.querySelector('#vp2-douyin-editor'); if(!editor) return []
    return [...editor.querySelectorAll('[data-mention="#"], [data-mention="activity"]')].map(el=>String(el.innerText||el.textContent||'').replace(/[\s\u200b]+/g,'').replace(/^#/,'').toLowerCase()).filter(Boolean)
  })()`)
  const committed = afterEntities.includes(queryTag.toLowerCase())
  if(!committed){
    const cleanup = await removeDouyinTrailingTopicQuery(queryTag, afterEntities, description)
    return {ok:false,reason: cleanup.ok ? 'topic entity_not_committed (cleaned up)' : cleanup.reason, residue: !cleanup.ok}
  }
  return {ok:true,text:row.text}
}
```

---

## 一次性校验（写入后用）
```js
// 数实体节点 = 话题数
const mentionCount = await js(`(() => { const e=document.querySelector('#vp2-douyin-editor'); return e?e.querySelectorAll('[data-mention="#"], [data-mention="activity"]').length:0 })()`)
// 残留纯文本 # 检查
const residue = await js(String.raw`(() => {
  const e=document.querySelector('#vp2-douyin-editor'); if(!e) return ''
  const clone=e.cloneNode(true)
  clone.querySelectorAll('[data-mention], [data-fake-text], [class*="mention"], [class*="topic"], [class*="hash"]').forEach(el=>el.remove())
  return (clone.innerText||clone.textContent||'').replace(/\u200b/g,' ').trim()
})()`)
```
