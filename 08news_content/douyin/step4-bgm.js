// Step 5.4 — 配乐 BGM（关键词: 大气）+ 入口在视口外先滚动
const task = await useOrCreateTaskSpace("douyin publish")
const KEYWORD = "大气"

// 配乐入口常在视口外，先滚动再测坐标
await scroll({ dy: 300 })
await wait(1)

// ① 定位真正的配乐入口按钮：cursor:pointer + 含 svg
const entry = await js(String.raw`(() => {
  const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
  const want=['添加音乐','选择音乐','配乐','选择配乐'];
  const cands=[...document.querySelectorAll('button,div,span,a')].filter(el=>vis(el)&&want.some(w=>(el.textContent||'').trim()===w));
  let pick=cands.find(el=>getComputedStyle(el).cursor==='pointer');
  if(!pick)pick=cands.find(el=>el.querySelector('svg'));
  if(!pick)pick=cands[0];
  if(!pick)return null;
  const r=pick.getBoundingClientRect();
  return{x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight};
})()`)

if(!entry){ cliLog('ℹ️ 没找到配乐入口（可能已配乐/该图集无配乐入口），跳过配乐') }
else if(entry.y<40||entry.y>entry.vh-40){ cliLog('⚠️ 配乐入口不在视口安全区(y='+entry.y+')，再滚一次')
  await scroll({ dy: 300 }); await wait(1.5)
  const entry2 = await js(String.raw`(() => {
    const vis=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'};
    const want=['添加音乐','选择音乐','配乐','选择配乐'];
    const cands=[...document.querySelectorAll('button,div,span,a')].filter(el=>vis(el)&&want.some(w=>(el.textContent||'').trim()===w));
    let pick=cands.find(el=>getComputedStyle(el).cursor==='pointer');
    if(!pick)pick=cands.find(el=>el.querySelector('svg'));
    if(!pick)pick=cands[0];
    if(!pick)return null;
    const r=pick.getBoundingClientRect();
    return{x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight};
  })()`)
  if(entry2&&entry2.y>40&&entry2.y<entry2.vh-40){
    await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:entry2.x,y:entry2.y})
    await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:entry2.x,y:entry2.y,button:'left',clickCount:1,buttons:1})
    await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:entry2.x,y:entry2.y,button:'left',clickCount:1,buttons:1})
    await wait(2.5)
    await doSearchAndPick()
  } else { cliLog('⚠️ 二次滚动后仍不在安全区，跳过配乐') }
}
else {
  await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:entry.x,y:entry.y})
  await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:entry.x,y:entry.y,button:'left',clickCount:1,buttons:1})
  await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:entry.x,y:entry.y,button:'left',clickCount:1,buttons:1})
  await wait(2.5)
  await doSearchAndPick()
}

async function doSearchAndPick() {
  const searchOk = await js(String.raw`(() => {
    const inp=[...document.querySelectorAll('input')].find(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&/搜索音乐/.test(el.placeholder||'')});
    if(!inp)return{ok:false};
    inp.focus(); inp.click();
    inp.id='ego-music-search';
    return{ok:true};
  })()`)
  if(!searchOk.ok){ cliLog('⚠️ 没找到搜索音乐框，面板状态: '); cliLog((await snapshotText()).slice(0,600)); return }
  await js(String.raw`(() => {const inp=document.querySelector('#ego-music-search');const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;setter.call(inp,${JSON.stringify(KEYWORD)});inp.dispatchEvent(new Event('input',{bubbles:true}));inp.dispatchEvent(new Event('change',{bubbles:true}));return 1})()`)
  await wait(0.8)
  await cdp('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13})
  await cdp('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13})
  await wait(3)

  const card = await js(String.raw`(() => {const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};const c=[...document.querySelectorAll('.card-wrapper-JTleG1, [class*="card-wrapper"]')].filter(vis);if(!c.length)return null;const r=c[0].getBoundingClientRect();return{x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2),vh:innerHeight}})()`)
  if(!card){ cliLog('⚠️ 搜索结果无曲目卡片'); return }
  if(card.y<=40||card.y>=card.vh-40){ cliLog('⚠️ 曲目卡片不在安全区 y='+card.y); return }
  await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:card.x,y:card.y})
  await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:card.x,y:card.y,button:'left',clickCount:1,buttons:1})
  await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:card.x,y:card.y,button:'left',clickCount:1,buttons:1})
  await wait(2)
  const useBtn=await js(String.raw`(() => {const vis=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&el.offsetParent!==null};const u=[...document.querySelectorAll('*')].filter(vis).find(el=>(el.textContent||'').trim()==='使用'&&getComputedStyle(el).cursor==='pointer');if(!u)return null;const r=u.getBoundingClientRect();return{x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)}})()`)
  if(!useBtn){ cliLog('⚠️ 使用按钮未浮现'); return }
  await cdp('Input.dispatchMouseEvent',{type:'mouseMoved',x:useBtn.x,y:useBtn.y})
  await cdp('Input.dispatchMouseEvent',{type:'mousePressed',x:useBtn.x,y:useBtn.y,button:'left',clickCount:1,buttons:1})
  await cdp('Input.dispatchMouseEvent',{type:'mouseReleased',x:useBtn.x,y:useBtn.y,button:'left',clickCount:1,buttons:1})
  await wait(2.5)
  const s=await snapshotText()
  cliLog('配乐结果: ' + (/修改音乐|创作的原声|更换音乐/.test(s)?'✅已选':'⚠️未确认'))
  // 抓曲目名
  const musicName = await js(String.raw`(() => {const t=(document.body.innerText||'').slice(0,3000);const m=t.match(/《([^》]{2,30})》/);return m?m[1]:''})()`)
  cliLog('曲目: ' + musicName)
}
