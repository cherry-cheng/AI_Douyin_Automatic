// Step 8 — 发布（APPROVED 后执行）：补 AIGC → 预热 → CDP 点击 → React onClick 兜底
const task = await useOrCreateTaskSpace("douyin publish")

// ===== ① 补 AIGC 自主声明（发布强制；暂存离开/配乐都会重置它）=====
await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden"};
  const t=(document.body.innerText||"");
  if(!/请选择自主声明/.test(t)) return {skip:true};
  const cands=[...document.querySelectorAll("div,span,button,[role=button]")].filter(el=>vis(el)&&/请选择自主声明/.test((el.textContent||"").trim())&&(el.textContent||"").trim().length<12);
  const pick=cands[cands.length-1];
  if(pick)pick.scrollIntoView({block:"center",inline:"center"});
  return {ok:!!pick};
})()`)
await wait(2.5)
const trig = await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
  let t=[...document.querySelectorAll(".semi-select,[class*=select]")].filter(el=>vis(el)&&/请选择自主声明/.test((el.textContent||""))&&(el.textContent||"").trim().length<15)[0];
  if(!t)t=[...document.querySelectorAll("div,span")].filter(el=>vis(el)&&(el.textContent||"").trim()==="请选择自主声明").sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height-b.getBoundingClientRect().width*b.getBoundingClientRect().height)[0];
  if(!t)return null;
  const r=t.getBoundingClientRect();
  return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight};
})()`)
if(trig && trig.y>40 && trig.y<trig.vh-40){
  await cdp("Input.dispatchMouseEvent",{type:"mouseMoved",x:trig.x,y:trig.y})
  await cdp("Input.dispatchMouseEvent",{type:"mousePressed",x:trig.x,y:trig.y,button:"left",clickCount:1,buttons:1})
  await cdp("Input.dispatchMouseEvent",{type:"mouseReleased",x:trig.x,y:trig.y,button:"left",clickCount:1,buttons:1})
  await wait(2)
  const opt = await js(String.raw`(() => {
    const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
    let o=[...document.querySelectorAll(".semi-select-option,[class*=select-option],[role=option]")].filter(el=>vis(el)&&/内容由AI生成/.test((el.textContent||"")))[0];
    if(!o)o=[...document.querySelectorAll("div,span,li")].filter(el=>vis(el)&&(el.textContent||"").trim()==="内容由AI生成")[0];
    if(!o)return null;
    const r=o.getBoundingClientRect();
    return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight};
  })()`)
  if(opt && opt.y>40 && opt.y<opt.vh-40){
    await cdp("Input.dispatchMouseEvent",{type:"mouseMoved",x:opt.x,y:opt.y})
    await cdp("Input.dispatchMouseEvent",{type:"mousePressed",x:opt.x,y:opt.y,button:"left",clickCount:1,buttons:1})
    await cdp("Input.dispatchMouseEvent",{type:"mouseReleased",x:opt.x,y:opt.y,button:"left",clickCount:1,buttons:1})
    await wait(2)
  }
  const aigc = await js(String.raw`(() => {const t=(document.body.innerText||"").replace(/\s+/g," ");return {aigcSet:/内容由AI生成/.test(t)&&!/请选择自主声明/.test(t)}})()`)
  cliLog("AIGC 补设: " + JSON.stringify(aigc))
} else {
  cliLog("⚠️ AIGC trigger 不在安全区: " + JSON.stringify(trig))
}

// ===== ② 行为预热：滚动 + 人类停顿（所有滚动必须在测坐标之前）=====
await scroll({ dy: 160 + Math.random() * 100 }); await wait(0.5 + Math.random() * 0.5)
await wait(1.5 + Math.random() * 2)

// ===== ③ 发布按钮滚进视口，等 ≥2s 停稳 =====
await js(String.raw`(() => {
  const b = [...document.querySelectorAll('button')]
    .find(x => (x.textContent || '').trim() === '发布' && x.offsetParent && !x.disabled);
  if (b) b.scrollIntoView({ block: 'center' });
  return 1;
})()`)
await wait(2.5)

// ===== ④ 测坐标（之后到点击之间零滚动）=====
const center = await js(String.raw`(() => {
  const b = [...document.querySelectorAll('button')]
    .find(x => (x.textContent || '').trim() === '发布' && x.offsetParent && !x.disabled);
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), vh: innerHeight, cls: String(b.className||"").slice(0,50) };
})()`)
cliLog("publish btn: " + JSON.stringify(center))

if (!center) {
  cliLog("⚠️ 找不到「发布」按钮")
} else if (center.y < 40 || center.y > center.vh - 40) {
  cliLog("⚠️ 发布按钮不在安全区 y=" + center.y)
} else {
  // ===== ⑤ CDP 单步真实点击 =====
  await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', x: center.x, y: center.y })
  await cdp('Input.dispatchMouseEvent', { type: 'mousePressed',  x: center.x, y: center.y, button: 'left', clickCount: 1, buttons: 1 })
  await cdp('Input.dispatchMouseEvent', { type: 'mouseReleased', x: center.x, y: center.y, button: 'left', clickCount: 1, buttons: 1 })
}

await wait(4)
let after = await snapshotText()
let hitCode = /验证码|短信验证码|发送验证码/.test(after)
let hitSlider = /滑块|拖动|滑动验证|请按住/.test(after)
let ok = /发布成功|成功发布|\/manage/.test(after)
cliLog("CDP点击后: 正在发布=" + after.includes('正在发布') + " 验证码=" + hitCode + " 滑块=" + hitSlider + " 成功=" + ok)

// ===== ⑥ fixed 主按钮「点击被吞」兜底：React onClick 直调 =====
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

cliLog('最终: 正在发布=' + after.includes('正在发布') + ' 验证码=' + hitCode + ' 滑块=' + hitSlider + ' 成功=' + ok)
const url = await js(String.raw`(() => { return location.href })()`)
cliLog("url: " + url)
await captureScreenshot('/tmp/douyin_publish_after.png')
cliLog('screenshot saved')
