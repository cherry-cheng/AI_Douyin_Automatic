// Step 5.5 — AIGC 自主声明（配乐弹窗之后最后设）+ 复查
const task = await useOrCreateTaskSpace("douyin publish")

// 自主声明入口在「扩展信息」上方，先滚到位
await scroll({ dy: -300 })
await wait(1.5)

// 定位「请选择自主声明」下拉并点开
const aigcEntry = await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
  const cands=[...document.querySelectorAll('div,span,button,[role="button"]')].filter(el=>vis(el)&&/请选择自主声明|自主声明/.test((el.textContent||'').trim())&&(el.textContent||'').trim().length<12);
  const pick=cands[cands.length-1];
  if(!pick)return null;
  const r=pick.getBoundingClientRect();
  return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight,text:(pick.textContent||'').trim()};
})()`)
cliLog('aigcEntry: ' + JSON.stringify(aigcEntry))

if(!aigcEntry){ cliLog('⚠️ 没找到自主声明入口') }
else if(aigcEntry.y<40||aigcEntry.y>aigcEntry.vh-40){ cliLog('⚠️ 入口不在安全区 y='+aigcEntry.y+'，先滚动') }
else {
  await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:aigcEntry.x,y:aigcEntry.y})
  await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:aigcEntry.x,y:aigcEntry.y,button:'left',clickCount:1,buttons:1})
  await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:aigcEntry.x,y:aigcEntry.y,button:'left',clickCount:1,buttons:1})
  await wait(1.5)

  // 在下拉选项里找「内容由AI生成」
  const option = await js(String.raw`(() => {
    const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
    const opts=[...document.querySelectorAll('div,span,li,[role="option"]')].filter(el=>vis(el)&&/内容由AI生成|AI生成/.test((el.textContent||'').trim())&&(el.textContent||'').trim().length<15);
    const pick=opts[0];
    if(!pick)return null;
    const r=pick.getBoundingClientRect();
    return {x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight,text:(pick.textContent||'').trim()};
  })()`)
  cliLog('aigcOption: ' + JSON.stringify(option))

  if(!option){ cliLog('⚠️ 下拉里没找到「内容由AI生成」，snapshot: '); cliLog((await snapshotText()).slice(0,800)) }
  else {
    await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:option.x,y:option.y})
    await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:option.x,y:option.y,button:'left',clickCount:1,buttons:1})
    await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:option.x,y:option.y,button:'left',clickCount:1,buttons:1})
    await wait(1.5)
  }
}

// 复查：AIGC 是否已设 + 配乐是否还在 + 描述/话题是否完好
const verify = await js(String.raw`(() => {
  const text=(document.body.innerText||'').replace(/\s+/g,' ');
  const aigcSet=/内容由AI生成/.test(text)&&!/请选择自主声明/.test(text);
  const musicSet=/修改音乐|更换音乐/.test(text);
  const e=document.querySelector('#vp2-douyin-editor');
  const mentionCount=e?e.querySelectorAll('[data-mention="#"], [data-mention="activity"]').length:0;
  const descText=e?(e.innerText||'').slice(0,40):'';
  const title=[...document.querySelectorAll('input')].find(el=>/标题/.test(el.placeholder||''))?.value||'';
  return {aigcSet, musicSet, mentionCount, descText, title};
})()`)
cliLog('复查: ' + JSON.stringify(verify))
