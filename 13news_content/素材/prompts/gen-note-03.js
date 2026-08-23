const task = await useOrCreateTaskSpace('visual notes')
cliLog('task id: ' + task.id)

const PROMPT = `请直接生成图片，不要输出文字方案。

[Main Description]
A photorealistic, ultra-clear, high-resolution close-up photograph of a hand-drawn causal-chain diagram on a slightly yellowed grid-notebook page, tilted slightly, warm desk-lamp lighting from upper right, pencil shavings near the corner. Portrait 9:16 vertical phone-screen orientation, vertical top-to-bottom layout.

[Content and Layout (Verbatim)]
1. Top center, bold black marker title: "平板手机 为何此时回归"
2. A vertical chain of 4 hand-drawn stage boxes connected by thick downward arrows, each box contains a short phrase in blue ink and one line of black ink detail, the key phrase underlined in red:
   - Box 1: "换机意愿减弱" / "直板机五年千篇一律 审美疲劳"
   - Box 2: "参数卷不动了" / "原材料涨价 芯片难拿 配置差距利润薄"
   - Box 3: "AI手机要大屏" / "IDC:2026爆发年 分屏+AI助手分栏施展不开"
   - Box 4: "形态创新突围" / "阔折叠阔直板键盘机 平板手机重新回归"
3. Right side of Box 4, a red-ink side annotation with arrow: "新形态=重新制造新鲜感 刺激换机"
4. Below the chain, one sentence in blue ink quoted with rough quotation marks: "厂商几个月前还在卷小屏 转头又冲向又阔又大"
5. Bottom conclusion line, written larger in red marker, boxed with a rough rectangle: "AI是最大的屏幕需求发动机"
6. Bottom left corner, small black text: "手机形态多样化观察"

[Context & Environment]
Grid lines of the notebook faintly visible under the diagram, natural hand-drawn line wobble, slight ink shading, warm ambient desk-lamp glow.

[Quality & Style Keywords]
Hand-written note style, causal chain diagram, legible Chinese characters, varied ink colors black blue red, accurate content reproduction, detailed paper texture, photorealistic, 8k resolution, study-note aesthetic, portrait 9:16 vertical orientation, vertical top-to-bottom layout.`

const OUT_PATH = '/Users/plato/Documents/trae_projects/Trae_Agent_First_Project/13news_content/素材/visual-note-03-逻辑链.png'

await openOrReuseTab('https://gemini.google.com/app', { wait: true, timeout: 30 })
await wait(2)

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
  let modelArea = null;
  for (const s of ['.input-area','.text-input-field','input-area-v2','fieldset.input-area-container']) { try { modelArea = document.querySelector(s); } catch {} if (modelArea) break; }
  const modelText = ((modelArea?.innerText) || (document.body.innerText || '')).toLowerCase();
  const currentModel = /flash-?lite/.test(modelText) ? 'flash-lite' : (/flash/.test(modelText) ? 'flash' : (/\bpro\b/.test(modelText) ? 'pro' : ''));
  return { loggedIn, barText: barText.slice(0,80), inputReady, currentModel };
})(${JSON.stringify(PROMPT_SELS)})`)
cliLog('probe: ' + JSON.stringify(probe))

if (!probe.loggedIn) {
  cliLog('GEMINI_NOT_LOGGED_IN')
  await handOffTaskSpace(task.id)
} else if (!probe.inputReady) {
  cliLog('INPUT_NOT_READY: ' + (await snapshotText()).slice(0, 800))
}

async function ensureProModel() {
  const cur = await js(String.raw`(() => { const area=document.querySelector('.input-area, .text-input-field, input-area-v2, fieldset.input-area-container'); const t=((area?.innerText)||(document.body.innerText||'')).toLowerCase(); if(/flash-?lite/.test(t)) return 'flash-lite'; if(/flash/.test(t)) return 'flash'; if(/\bpro\b/.test(t)) return 'pro'; return 'unknown'; })()`)
  if (cur === 'pro') return { ok:true, already:true, model:cur }
  const opened = await js(String.raw`(() => { const sels=['[data-test-id="bard-mode-menu-button"]','button[aria-label="打开模式选择器"]','button[aria-label*="mode selector" i]','button.mat-mdc-menu-trigger.input-area-switch']; let b=null; for (const s of sels){ try{ b=document.querySelector(s);}catch{} if(b)break;} if(!b) return {ok:false, skipped:'no_model_switcher'}; b.click(); return {ok:true}; })()`)
  if (!opened.ok) return { ok:true, skipped: opened.skipped, model:cur || 'unknown' }
  await wait(0.4)
  const picked = await js(String.raw`(() => { const items=[...document.querySelectorAll('gem-menu-item, [data-test-id^="bard-mode-option"]')].filter(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0}); const labelOf=el=>(el.querySelector('.label')?.textContent||el.textContent||'').trim(); const t=items.find(el=>{const l=labelOf(el);return /pro/i.test(l)&&!/flash|lite|扩展思考|think/i.test(l)}); if(!t) return {ok:false}; t.click(); return {ok:true, matched:labelOf(t).slice(0,40)}; })()`)
  if (!picked.ok) { await pressKey('Escape').catch(()=>{}); return { ok:true, skipped:'pro_option_not_found', model:cur||'unknown' } }
  await wait(0.8)
  return { ok:true, switched:true, model:cur }
}
const mp = await ensureProModel()
cliLog('model: ' + JSON.stringify(mp))

const focusPt = await js(String.raw`((promptSels) => { let el=null; for(const s of promptSels){ try{ el=document.querySelector(s);}catch{} if(el)break;} const r=el.getBoundingClientRect(); return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)}; })(${JSON.stringify(PROMPT_SELS)})`)
await cdp('Input.dispatchMouseEvent', { type:'mouseMoved', x:focusPt.x, y:focusPt.y })
await cdp('Input.dispatchMouseEvent', { type:'mousePressed', x:focusPt.x, y:focusPt.y, button:'left', clickCount:1, buttons:1 })
await cdp('Input.dispatchMouseEvent', { type:'mouseReleased', x:focusPt.x, y:focusPt.y, button:'left', clickCount:1, buttons:1 })
await wait(0.5)
await cdp('Input.insertText', { text: PROMPT })
await wait(0.8)
const fillRes = await js(String.raw`((promptSels) => { let el=null; for(const s of promptSels){try{el=document.querySelector(s);}catch{} if(el)break;} const sc=document.querySelector('div.send-button-container'); const btn=sc?.querySelector('button'); return { inputText:(el?.innerText||'').trim(), inputLen:(el?.innerText||'').length, sendAria:btn?.getAttribute('aria-label')||'' }; })(${JSON.stringify(PROMPT_SELS)})`)
cliLog('fill: ' + JSON.stringify(fillRes))

async function clickSend() {
  const pt = await js(String.raw`(() => { const c=document.querySelector('.send-button-container'); if(!c) return {ok:false,reason:'send_container_not_found'}; const btns=[...c.querySelectorAll('button')]; const b=btns.find(x=>/发送|send/i.test(x.getAttribute('aria-label')||'')) || btns.find(x=>/停止|stop/i.test(x.getAttribute('aria-label')||'')) || c.querySelector('button'); if(!b) return {ok:false,reason:'send_btn_not_found'}; const aria=(b.getAttribute('aria-label')||'').trim(); const r=b.getBoundingClientRect(); if(r.width===0||r.height===0) return {ok:false,reason:'send_btn_not_visible'}; return {ok:true, aria, isStop:/停止|stop/i.test(aria), isSend:/发送|send/i.test(aria), x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2)}; })()`)
  if (!pt.ok) return pt
  if (pt.isStop) return { ok:true, alreadyGenerating:true }
  if (!pt.isSend) return { ok:false, reason:'send_btn_not_ready', aria:pt.aria }
  await cdp('Input.dispatchMouseEvent', { type:'mouseMoved', x:pt.x, y:pt.y })
  await cdp('Input.dispatchMouseEvent', { type:'mousePressed', x:pt.x, y:pt.y, button:'left', clickCount:1, buttons:1 })
  await cdp('Input.dispatchMouseEvent', { type:'mouseReleased', x:pt.x, y:pt.y, button:'left', clickCount:1, buttons:1 })
  return { ok:true, x:pt.x, y:pt.y }
}
const sendRes = await clickSend()
cliLog('send: ' + JSON.stringify(sendRes))

async function getStatus() {
  return await js(String.raw`(() => {
    const sc=document.querySelector('div.send-button-container');
    const btns=sc?[...sc.querySelectorAll('button')]:[];
    const sendBtn=btns.find(x=>/发送|send/i.test(x.getAttribute('aria-label')||''));
    const stopBtn=btns.find(x=>/停止|stop/i.test(x.getAttribute('aria-label')||''));
    const hasResponse = !!(document.querySelector('div.response-content, message-content, .model-response-text, [data-message-id]'));
    let status='idle';
    if (stopBtn) status='stop';
    else if (sendBtn) status='submit';
    else if (hasResponse) status='done';
    return { status, hasResponse, sendAria: sendBtn?.getAttribute('aria-label')||'', stopAria: stopBtn?.getAttribute('aria-label')||'' };
  })()`)
}

let started = false, done = false, waited = 0
for (let i = 0; i < 125; i++) {
  const s = await getStatus()
  if (s.status === 'stop') started = true
  if (started && s.status !== 'stop') { done = true; break }
  await wait(2); waited += 2
  if (i % 5 === 0) cliLog('生成中… 已等 ' + waited + 's status=' + s.status)
}
cliLog('wait done=' + done + ' waited=' + waited + 's')
await wait(2)

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
if (!img.ok) { await wait(4); img = await getLatestImgUrl() }
if (!img.ok || !img.src) { await wait(4); img = await getLatestImgUrl() }
cliLog('img: ' + JSON.stringify(img))

let savedPath = null
if (img.ok && img.src) {
  savedPath = await (async () => {
    const { writeFileSync } = await import('node:fs')
    let targetUrl = img.src
    if (img.src.startsWith('blob:')) {
      const b64 = await js(String.raw`((url) => { const sels=['generated-image img','.generated-image img','img.image.loaded']; const seen=new Set(), imgs=[]; for(const s of sels){ let f; try{ f=document.querySelectorAll(s);}catch{continue} for(const el of f){ if(seen.has(el))continue; seen.add(el); const r=el.getBoundingClientRect(); if(r.width<80&&r.height<80) continue; imgs.push(el); } } const img = imgs.find(i=>(i.src||i.currentSrc)===url) || imgs[imgs.length-1]; if(!img) return null; const w=img.naturalWidth||img.width, h=img.naturalHeight||img.height; try { const c=document.createElement('canvas'); c.width=w; c.height=h; c.getContext('2d').drawImage(img,0,0); return c.toDataURL('image/png'); } catch { return null; } })(${JSON.stringify(img.src)})`)
      if (!b64) return null
      targetUrl = b64
    }
    if (targetUrl.startsWith('data:')) {
      const m = targetUrl.match(/^data:([^;]+)?;base64,(.*)$/)
      if (m) { writeFileSync(OUT_PATH, Buffer.from(m[2], 'base64')); return OUT_PATH }
    }
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

cliLog('SAVED_PATH=' + savedPath)
