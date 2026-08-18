// Step 5.5c — AIGC 重设（scrollIntoView 居中 + 点击 + 等 2s + 选项确认）
const task = await useOrCreateTaskSpace("douyin publish")

const r1 = await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden"};
  const cands=[...document.querySelectorAll("div,span,button,[role=button]")].filter(el=>vis(el)&&/请选择自主声明/.test((el.textContent||"").trim())&&(el.textContent||"").trim().length<12);
  const pick=cands[cands.length-1];
  if(!pick)return {ok:false};
  pick.scrollIntoView({block:"center",inline:"center"});
  return {ok:true};
})()`)
await wait(2.5)

const entry = await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden"};
  const cands=[...document.querySelectorAll("div,span,button,[role=button]")].filter(el=>vis(el)&&/请选择自主声明/.test((el.textContent||"").trim())&&(el.textContent||"").trim().length<12);
  const pick=cands[cands.length-1];
  if(!pick)return null;
  const r=pick.getBoundingClientRect();
  return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight};
})()`)
cliLog("entry: " + JSON.stringify(entry))

if(entry && entry.y>40 && entry.y<entry.vh-40){
  await cdp("Input.dispatchMouseEvent",{type:"mouseMoved",x:entry.x,y:entry.y})
  await cdp("Input.dispatchMouseEvent",{type:"mousePressed",x:entry.x,y:entry.y,button:"left",clickCount:1,buttons:1})
  await cdp("Input.dispatchMouseEvent",{type:"mouseReleased",x:entry.x,y:entry.y,button:"left",clickCount:1,buttons:1})
  await wait(2)   // 下拉动画多等

  // 抓下拉面板全部选项文本
  const panel = await js(String.raw`(() => {
    const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
    // semi-design 下拉挂在 portal，找含「AI生成」的可视元素
    const opts=[...document.querySelectorAll("div,span,li,[role=option],[class*=option]")].filter(el=>vis(el)&&/AI生成|AI 内容|内容.*AI/.test((el.textContent||""))&&(el.textContent||"").trim().length<20);
    return opts.slice(0,5).map(el=>({text:(el.textContent||"").trim(), x:Math.round(el.getBoundingClientRect().left+el.getBoundingClientRect().width/2), y:Math.round(el.getBoundingClientRect().top+el.getBoundingClientRect().height/2)}));
  })()`)
  cliLog("panel opts: " + JSON.stringify(panel))

  const pick = panel.find(o=>/内容由AI生成/.test(o.text)) || panel[0]
  if(pick){
    await cdp("Input.dispatchMouseEvent",{type:"mouseMoved",x:pick.x,y:pick.y})
    await cdp("Input.dispatchMouseEvent",{type:"mousePressed",x:pick.x,y:pick.y,button:"left",clickCount:1,buttons:1})
    await cdp("Input.dispatchMouseEvent",{type:"mouseReleased",x:pick.x,y:pick.y,button:"left",clickCount:1,buttons:1})
    await wait(2)
  } else {
    const snap = await snapshotText()
    const i = snap.indexOf("声明")
    cliLog("panel snapshot: " + snap.slice(Math.max(0,i-100), i+600))
  }

  const verify = await js(String.raw`(() => {
    const t=(document.body.innerText||"").replace(/\s+/g," ");
    const i=t.search(/自主声明/);
    return {area:t.slice(i, i+40), aigcSet:/内容由AI生成/.test(t)&&!/请选择自主声明/.test(t), musicSet:/修改音乐|更换音乐/.test(t)};
  })()`)
  cliLog("verify: " + JSON.stringify(verify))
}
