// Step 5.2 — 上传 4 张视觉笔记（原生 input 优先 → 注入 input 兜底）+ 稳定轮询
const task = await useOrCreateTaskSpace("douyin publish")

const IMAGE_PATHS = [
  "/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/08news_content/素材/visual-note-01-封面.png",
  "/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/08news_content/素材/visual-note-02-对比矩阵.png",
  "/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/08news_content/素材/visual-note-03-逻辑链.png",
  "/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/08news_content/素材/visual-note-04-总结.png",
]

// ===== 上传状态探针（正则字面内联）=====
async function inspectImageUploadState() {
  return await js(String.raw`(() => {
    const compact = v => String(v||'').replace(/\s+/g,' ').trim()
    const text = compact(document.body.innerText||'')
    const editorReady = !!document.querySelector('[contenteditable="true"],[contenteditable=""]') && /暂存离开|存草稿/.test(text)
    return {
      text: text.slice(0,1200),
      uploading: /上传过程中|取消上传|上传剩余时间|已上传：|上传速度|当前速度/.test(text) && !/上传成功/.test(text),
      uploadFailed: /上传失败|网络错误|重新上传失败/.test(text),
      editorReady
    }
  })()`)
}

// ===== 定位真实图片 input（主DOM + shadow root）=====
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

// ===== 注入自己的 input（图文页主力方案）=====
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

// ===== 4 级 fallback 链 =====
async function uploadImagesWithFallback(paths) {
  let exposed = null
  for (let i=0; i<16; i++) { exposed = await exposeImageInput(); if (exposed.ok) break; await wait(0.5) }
  if (exposed?.ok) cliLog('① 找到原生 input: ' + exposed.selector)

  if (!exposed?.ok) {
    const inj = await injectImageInput()
    cliLog('② 注入 input: ' + (inj.ok ? inj.selector : JSON.stringify(inj)))
    exposed = inj
  }

  if (!exposed?.ok) {
    cliLog('⚠️ 注入 input 失败，转人工拖拽')
    await handOffTaskSpace(task.id)
    return { ok:false, mode:'handoff', reason: exposed?.reason || 'inject failed' }
  }

  const sel = exposed.selector
  try {
    await uploadFile(sel, paths)
    cliLog('✅ uploadFile(' + sel + ', ' + paths.length + ' 张) 完成')
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

const result = await uploadImagesWithFallback(IMAGE_PATHS)
cliLog('upload result: ' + JSON.stringify(result))
if (result.ok) {
  let stableSince = 0
  for (let i=0; i<120; i++) {
    await wait(i === 0 ? 0.5 : 5)
    const s = await inspectImageUploadState()
    if (s.editorReady && !s.uploading && !s.uploadFailed) {
      if (!stableSince) stableSince = Date.now()
      if (Date.now()-stableSince >= 10000) { cliLog('✅ 图文上传稳定完成'); break }
    } else stableSince = 0
    if (s.uploadFailed) { cliLog('⚠️ 明确上传失败: ' + s.text.slice(0,200)); break }
  }
}
const s2 = await snapshotText()
cliLog(s2.slice(0, 1500))
