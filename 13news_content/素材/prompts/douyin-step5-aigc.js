const task = await useOrCreateTaskSpace('douyin publish')

// ===== AIGC 自主声明：入口在视口外先滚动，用 React 兼容方式选「内容由AI生成」=====
// 探测「自主声明」区域当前状态 + 定位下拉
const aigcProbe = await js(String.raw`(() => {
  const compact = v => String(v||'').replace(/\s+/g,' ').trim()
  const text = compact(document.body.innerText||'')
  const hasAigcSet = /内容由AI生成/.test(text)
  // 找「自主声明」/「请选择自主声明」行的可点元素（semi-design 下拉触发器）
  let trigger = null
  const cands = [...document.querySelectorAll('div,span,button,[role="button"]')].filter(el=>{
    const t = compact(el.textContent||'')
    const r = el.getBoundingClientRect()
    return r.width>0 && r.height>0 && (t==='请选择自主声明' || t==='自主声明' || t==='内容由AI生成')
  })
  if (cands.length) {
    // 取最内层（通常是最小宽度的那个可点元素）
    cands.sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height - b.getBoundingClientRect().width*b.getBoundingClientRect().height)
    trigger = cands[0]
    trigger.scrollIntoView({block:'center'})
  }
  return { hasAigcSet, triggerFound: !!trigger, triggerText: trigger ? compact(trigger.textContent||'') : '' }
})()`)
cliLog('aigc probe: ' + JSON.stringify(aigcProbe))

if (!aigcProbe.hasAigcSet) {
  await wait(2.2)   // scrollIntoView 平滑动画停稳
  const tp = await js(String.raw`(() => {
    const compact = v => String(v||'').replace(/\s+/g,' ').trim()
    const cands = [...document.querySelectorAll('div,span,button,[role="button"]')].filter(el=>{
      const t = compact(el.textContent||'')
      const r = el.getBoundingClientRect()
      return r.width>0 && r.height>0 && (t==='请选择自主声明' || t==='内容由AI生成')
    })
    if (!cands.length) return null
    cands.sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height - b.getBoundingClientRect().width*b.getBoundingClientRect().height)
    const el = cands[0]
    const r = el.getBoundingClientRect()
    return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), vh:innerHeight, text:compact(el.textContent||'')}
  })()`)
  cliLog('aigc trigger: ' + JSON.stringify(tp))
  if (tp && tp.y>40 && tp.y<tp.vh-40) {
    await wait(1 + Math.random()*1.5)
    await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:tp.x,y:tp.y})
    await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:tp.x,y:tp.y,button:'left',clickCount:1,buttons:1})
    await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:tp.x,y:tp.y,button:'left',clickCount:1,buttons:1})
    await wait(1.5)
    // 下拉选项里点「内容由AI生成」
    const opt = await js(String.raw`(() => {
      const compact = v => String(v||'').replace(/\s+/g,' ').trim()
      const opts = [...document.querySelectorAll('li,div[role="option"],[class*="option"],div,span')].filter(el=>{
        const t = compact(el.textContent||'')
        const r = el.getBoundingClientRect()
        const s = getComputedStyle(el)
        return t==='内容由AI生成' && r.width>0 && r.height>0 && s.visibility!=='hidden'
      })
      if (!opts.length) return null
      opts.sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height - b.getBoundingClientRect().width*b.getBoundingClientRect().height)
      const el = opts[0]
      const r = el.getBoundingClientRect()
      return {x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2), vh:innerHeight}
    })()`)
    cliLog('aigc option: ' + JSON.stringify(opt))
    if (opt && opt.y>40 && opt.y<opt.vh-40) {
      await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:opt.x,y:opt.y})
      await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:opt.x,y:opt.y,button:'left',clickCount:1,buttons:1})
      await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:opt.x,y:opt.y,button:'left',clickCount:1,buttons:1})
      await wait(1.5)
    }
  }
}

// 复查 AIGC 状态（配乐后必须复查，弹窗会重置）
const recheck = await js(String.raw`(() => { const t = (document.body.innerText||'').replace(/\s+/g,' '); return { aigcSet: /内容由AI生成/.test(t), musicSet: /修改音乐|创作的原声|更换音乐/.test(t), snippet: t.slice(0, 400) } })()`)
cliLog('recheck: aigc=' + recheck.aigcSet + ' music=' + recheck.musicSet)

// 标题/话题最终校验
const finalCheck = await js(String.raw`(() => {
  const title = (document.querySelector('input[placeholder*="标题"]')||{}).value || ''
  const e = document.querySelector('#vp2-douyin-editor')
  const mentionCount = e ? e.querySelectorAll('[data-mention="#"], [data-mention="activity"]').length : 0
  const editorText = e ? String(e.innerText||'').slice(0,150) : ''
  return { title, titleLen: title.length, mentionCount, editorText }
})()`)
cliLog('finalCheck: ' + JSON.stringify(finalCheck))
