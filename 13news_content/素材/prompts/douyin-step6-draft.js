const task = await useOrCreateTaskSpace('douyin publish')

// 「暂存离开」是 fixed 定位按钮，已知会被 CDP 点击吞 → 直接 React onClick 直调兜底优先，失败再试 CDP
const r = await js(String.raw`(() => {
  const compact = v => String(v||'').replace(/\s+/g,' ').trim()
  const btn = [...document.querySelectorAll('button')].find(el=>{
    const r = el.getBoundingClientRect()
    return r.width>0 && r.height>0 && !el.disabled && /暂存离开|存草稿/.test(compact(el.textContent||''))
  })
  if (!btn) return {ok:false, reason:'draft btn not found'}
  const reactKey = Object.keys(btn).find(k=>k.startsWith('__reactProps'))
  const props = reactKey ? btn[reactKey] : null
  if (props && typeof props.onClick === 'function') {
    try { props.onClick({preventDefault(){},stopPropagation(){},currentTarget:btn,target:btn,nativeEvent:{},type:'click'}); return {ok:true, via:'react'} } catch(e) { return {ok:false, reason:String(e)} }
  }
  // 无 reactProps → 返回坐标走 CDP
  const rect = btn.getBoundingClientRect()
  return {ok:true, via:'cdp', x:Math.round(rect.left+rect.width/2), y:Math.round(rect.top+rect.height/2)}
})()`)
cliLog('draft click: ' + JSON.stringify(r))

if (r.via === 'cdp') {
  await wait(1 + Math.random())
  await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:r.x,y:r.y})
  await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:r.x,y:r.y,button:'left',clickCount:1,buttons:1})
  await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:r.x,y:r.y,button:'left',clickCount:1,buttons:1})
}
await wait(3)
const snap = await snapshotText()
cliLog(snap.replace(/\s+/g,' ').slice(0, 500))
await wait(2)
await captureScreenshot('/tmp/douyin_draft_preview.png')
cliLog('saved /tmp/douyin_draft_preview.png')
