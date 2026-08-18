// Step 5.5b — AIGC 直调兜底：scrollIntoView(block:center) + window.scrollTo
const task = await useOrCreateTaskSpace("douyin publish")

// 找「请选择自主声明」元素，scrollIntoView center
const r1 = await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden"};
  const cands=[...document.querySelectorAll("div,span,button,[role=button]")].filter(el=>vis(el)&&/请选择自主声明/.test((el.textContent||"").trim())&&(el.textContent||"").trim().length<12);
  const pick=cands[cands.length-1];
  if(!pick)return {ok:false};
  pick.scrollIntoView({block:"center",inline:"center"});
  return {ok:true};
})()`)
cliLog("scrollIntoView: " + JSON.stringify(r1))
await wait(2.5)   // 等滚动彻底停稳

const aigcEntry = await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=="none"&&s.visibility!=="hidden"};
  const cands=[...document.querySelectorAll("div,span,button,[role=button]")].filter(el=>vis(el)&&/请选择自主声明/.test((el.textContent||"").trim())&&(el.textContent||"").trim().length<12);
  const pick=cands[cands.length-1];
  if(!pick)return null;
  const r=pick.getBoundingClientRect();
  return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight};
})()`)
cliLog("entry: " + JSON.stringify(aigcEntry))

if(aigcEntry && aigcEntry.y>40 && aigcEntry.y<aigcEntry.vh-40){
  await cdp("Input.dispatchMouseEvent",{type:"mouseMoved",x:aigcEntry.x,y:aigcEntry.y})
  await cdp("Input.dispatchMouseEvent",{type:"mousePressed",x:aigcEntry.x,y:aigcEntry.y,button:"left",clickCount:1,buttons:1})
  await cdp("Input.dispatchMouseEvent",{type:"mouseReleased",x:aigcEntry.x,y:aigcEntry.y,button:"left",clickCount:1,buttons:1})
  await wait(1.5)
  const option = await js(String.raw`(() => {
    const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
    const opts=[...document.querySelectorAll("div,span,li,[role=option]")].filter(el=>vis(el)&&/内容由AI生成|AI生成/.test((el.textContent||"").trim())&&(el.textContent||"").trim().length<15);
    const pick=opts[0];
    if(!pick)return null;
    const r=pick.getBoundingClientRect();
    return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight,text:(pick.textContent||"").trim()};
  })()`)
  cliLog("option: " + JSON.stringify(option))
  if(option){
    await cdp("Input.dispatchMouseEvent",{type:"mouseMoved",x:option.x,y:option.y})
    await cdp("Input.dispatchMouseEvent",{type:"mousePressed",x:option.x,y:option.y,button:"left",clickCount:1,buttons:1})
    await cdp("Input.dispatchMouseEvent",{type:"mouseReleased",x:option.x,y:option.y,button:"left",clickCount:1,buttons:1})
    await wait(1.5)
  } else {
    cliLog("⚠️ 没找到 AI 生成选项，抓下拉 snapshot")
    const snap = await snapshotText()
    const i = snap.indexOf("AI")
    cliLog(snap.slice(Math.max(0,i-200), i+500))
  }
  const verify = await js(String.raw`(() => {
    const text=(document.body.innerText||"").replace(/\s+/g," ");
    const aigcSet=/内容由AI生成/.test(text)&&!/请选择自主声明/.test(text);
    const musicSet=/修改音乐|更换音乐/.test(text);
    return {aigcSet, musicSet};
  })()`)
  cliLog("verify: " + JSON.stringify(verify))
} else {
  cliLog("⚠️ scrollIntoView 后仍不在安全区")
}
