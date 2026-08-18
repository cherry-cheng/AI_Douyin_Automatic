// Step 5.5d — AIGC 第三次设置：scrollIntoView + 立即测坐标点击（不等 2.5s）+ React 兜底
const task = await useOrCreateTaskSpace("douyin publish")

await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden"};
  const cands=[...document.querySelectorAll("div,span,button,[role=button]")].filter(el=>vis(el)&&/请选择自主声明/.test((el.textContent||"").trim())&&(el.textContent||"").trim().length<12);
  const pick=cands[cands.length-1];
  if(pick)pick.scrollIntoView({block:"center",inline:"center"});
  return 1;
})()`)
await wait(2.5)

// 点击下拉触发器：找紧邻「自主声明」标签右侧的下拉框元素（semi Select trigger）
const trig = await js(String.raw`(() => {
  // semi-design Select: .semi-select-selection 或含「请选择」文本的 trigger
  const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
  let t=[...document.querySelectorAll(".semi-select,[class*=select]")].filter(el=>vis(el)&&/请选择自主声明/.test((el.textContent||""))&&(el.textContent||"").trim().length<15)[0];
  if(!t){
    // 兜底:任意可见元素文本=请选择自主声明
    t=[...document.querySelectorAll("div,span")].filter(el=>vis(el)&&(el.textContent||"").trim()==="请选择自主声明").sort((a,b)=>a.getBoundingClientRect().width*a.getBoundingClientRect().height-b.getBoundingClientRect().width*b.getBoundingClientRect().height)[0];
  }
  if(!t)return null;
  const r=t.getBoundingClientRect();
  return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight,cls:String(t.className||"").slice(0,60)};
})()`)
cliLog("trigger: " + JSON.stringify(trig))

if(trig && trig.y>40 && trig.y<trig.vh-40){
  await cdp("Input.dispatchMouseEvent",{type:"mouseMoved",x:trig.x,y:trig.y})
  await cdp("Input.dispatchMouseEvent",{type:"mousePressed",x:trig.x,y:trig.y,button:"left",clickCount:1,buttons:1})
  await cdp("Input.dispatchMouseEvent",{type:"mouseReleased",x:trig.x,y:trig.y,button:"left",clickCount:1,buttons:1})
  await wait(2)

  // 选项：semi-select-option
  const opt = await js(String.raw`(() => {
    const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
    let o=[...document.querySelectorAll(".semi-select-option,[class*=select-option],[role=option]")].filter(el=>vis(el)&&/内容由AI生成/.test((el.textContent||"")))[0];
    if(!o)o=[...document.querySelectorAll("div,span,li")].filter(el=>vis(el)&&(el.textContent||"").trim()==="内容由AI生成").sort((a,b)=>a.getBoundingClientRect().width*b.getBoundingClientRect().height)[0];
    if(!o)return null;
    const r=o.getBoundingClientRect();
    return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight,cls:String(o.className||"").slice(0,60)};
  })()`)
  cliLog("option: " + JSON.stringify(opt))
  if(opt && opt.y>40 && opt.y<opt.vh-40){
    await cdp("Input.dispatchMouseEvent",{type:"mouseMoved",x:opt.x,y:opt.y})
    await cdp("Input.dispatchMouseEvent",{type:"mousePressed",x:opt.x,y:opt.y,button:"left",clickCount:1,buttons:1})
    await cdp("Input.dispatchMouseEvent",{type:"mouseReleased",x:opt.x,y:opt.y,button:"left",clickCount:1,buttons:1})
    await wait(2)
  }

  const area = await js(String.raw`(() => {
    const t=(document.body.innerText||"").replace(/\s+/g," ");
    const i=t.search(/自主声明/);
    return {area:t.slice(i, i+25), aigcSet:/内容由AI生成/.test(t)&&!/请选择自主声明/.test(t)};
  })()`)
  cliLog("after: " + JSON.stringify(area))
}
