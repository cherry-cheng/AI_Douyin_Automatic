// Step 5.3 — 填标题 + 描述 + #话题实体化
const task = await useOrCreateTaskSpace("douyin publish")

const TITLE = "全球粮食危机，明年或爆发？"
const DESCRIPTION = "🌍投行警告：下一轮全球粮食危机可能正在酝酿！五大风险叠加：战争、天气、仓储、水、浪费，食品通胀或从2.8%飙到5%，21亿人粮食不安全。化肥是最脆弱一环，下一轮冲击不在加油站，在超市货架！关注我，每天3分钟看懂财经热点📈"
const TOPICS = ["全球粮食危机", "粮食安全", "财经", "科技资讯"]

// 标题：fillInput
await fillInput('input[placeholder*="标题"]', TITLE).catch(e=>cliLog('title fill err: '+e))
await wait(0.6 + Math.random()*1.2)

// ===== 描述/话题 helper（移植自 video-publisher douyin.mjs）=====
async function locateDouyinEditor() {
  return await js(String.raw`(() => {
    const compact=v=>String(v||'').replace(/\s+/g,' ').trim()
    const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>180&&r.height>50&&s.display!=='none'&&s.visibility!=='hidden'}
    const rows=[...document.querySelectorAll('[contenteditable="true"],[contenteditable=""]')].map(el=>{const r=el.getBoundingClientRect();let p=el.parentElement,context='';for(let i=0;p&&i<5;i+=1){context+=' '+compact(p.innerText||p.textContent||'');p=p.parentElement}return {el,r,context,cls:String(el.className||'')}}).filter(item=>visible(item.el)&&!item.el.closest('[role="dialog"],[class*="modal"],[class*="dialog"]')).sort((a,b)=>Number(/作品描述|#添加话题|@好友/.test(b.context))-Number(/作品描述|#添加话题|@好友/.test(a.context))||Number(/editor|zone|ace/.test(b.cls))-Number(/editor|zone|ace/.test(a.cls))||b.r.width*b.r.height-a.r.width*a.r.height)
    const item=rows[0];if(!item)return {ok:false,reason:'douyin description editor missing'};item.el.id='vp2-douyin-editor';item.el.scrollIntoView({block:'center',inline:'center'});return {ok:true,selector:'#vp2-douyin-editor',text:item.el.innerText||item.el.textContent||'',className:item.cls,point:{x:item.r.left+Math.min(24,item.r.width/4),y:item.r.top+Math.min(24,item.r.height/3)}}
  })()`)
}
async function focusDouyinEditorEnd() {
  const located=await locateDouyinEditor();if(!located.ok)return located
  const endpoint=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return {ok:false,reason:'douyin editor lost'};const walker=document.createTreeWalker(editor,NodeFilter.SHOW_TEXT);let node,last=null;while((node=walker.nextNode())){if(String(node.nodeValue||'').length)last=node}const er=editor.getBoundingClientRect();if(!last)return {ok:true,point:{x:er.left+12,y:er.top+20}};const range=document.createRange();range.setStart(last,Math.max(0,last.nodeValue.length-1));range.setEnd(last,last.nodeValue.length);const rect=range.getBoundingClientRect();return {ok:true,point:{x:Math.min(er.right-6,Math.max(er.left+6,rect.right+2)),y:Math.min(er.bottom-6,Math.max(er.top+6,rect.top+rect.height/2))}}})()`)
  if(!endpoint.ok)return endpoint
  try{await click([endpoint.point.x,endpoint.point.y],{label:'focus douyin body end'})}catch(error){return {ok:false,reason:String(error?.message||error)}}
  const focused=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return{ok:false,reason:'douyin editor lost before focus confirmation'};editor.focus();const selection=window.getSelection(),range=document.createRange();range.selectNodeContents(editor);range.collapse(false);selection.removeAllRanges();selection.addRange(range);const active=document.activeElement;return{ok:active===editor||editor.contains(active),activeTag:active?.tagName||'',activeId:active?.id||''}})()`)
  await wait(0.2);return focused.ok?{ok:true,point:endpoint.point,focus:focused}:{ok:false,reason:'douyin description editor did not retain focus',evidence:focused}
}
async function clearAndFillDouyinBody(description) {
  let located=await locateDouyinEditor();if(!located.ok)return located
  for(let attempt=0;attempt<3;attempt+=1){
    try{await click([located.point.x,located.point.y],{label:'focus douyin body'})}catch(error){return {ok:false,reason:String(error?.message||error)}}
    const selected=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return{ok:false,reason:'douyin editor lost while selecting body'};editor.focus();const selection=window.getSelection(),range=document.createRange();range.selectNodeContents(editor);range.collapse(false);selection.removeAllRanges();selection.addRange(range);const active=document.activeElement;return{ok:active===editor||editor.contains(active),activeTag:active?.tagName||'',activeId:active?.id||''}})()`)
    if(!selected.ok)return {ok:false,reason:'douyin description editor did not retain selection focus',evidence:selected}
    await pressKey('Backspace').catch(()=>{});await wait(0.7)
    located=await locateDouyinEditor();if(!String(located.text||'').replace(/[\s​]/g,''))break
  }
  const cleared=await locateDouyinEditor();if(String(cleared.text||'').replace(/[\s​]/g,''))return {ok:false,reason:'douyin description editor did not clear',text:cleared.text}
  if(description){const focused=await focusDouyinEditorEnd();if(!focused.ok)return focused;await cdp('Input.insertText',{text:description});await wait(1)}
  const after=await locateDouyinEditor();const ok=String(after.text||'').replace(/[\s​]/g,'')===String(description||'').replace(/[\s​]/g,'');return ok?{ok:true,text:after.text}:{ok:false,reason:'douyin description did not persist exact value',expected:description,actual:after.text}
}
async function inspectDouyinTrailingPlainText(expectedDescription) {
  return await js(String.raw`((expectedDescription) => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return {ok:false,reason:'douyin editor missing during tail inspection'};const walker=document.createTreeWalker(editor,NodeFilter.SHOW_TEXT);let node,lastPlain=null;while((node=walker.nextNode())){if(!node.parentElement?.closest('[data-mention], [contenteditable="false"]')&&String(node.nodeValue||'').replace(/​/g,'').length)lastPlain=node}let value=String(lastPlain?.nodeValue||'').replace(/​/g,'');if(expectedDescription&&value.startsWith(expectedDescription))value=value.slice(expectedDescription.length);const entities=[...editor.querySelectorAll('[data-mention="#"], [data-mention="activity"]')].map(el=>String(el.innerText||el.textContent||'').replace(/[\s​ ]+/g,'').replace(/^#/,'').toLowerCase()).filter(Boolean);return {ok:true,value,trimmed:value.trim(),entities,editorText:String(editor.innerText||editor.textContent||'')}})(${JSON.stringify(expectedDescription)})`)
}
async function removeDouyinTrailingTopicQuery(tag, expectedDescription) {
  const expected='#'+String(tag).replace(/\s+/g,'').toLowerCase()
  const before=await inspectDouyinTrailingPlainText(expectedDescription);if(!before.ok)return before
  const initial=String(before.trimmed||'').toLowerCase()
  if(!initial)return {ok:true,alreadyClean:true,before}
  if(!initial.startsWith('#')||!expected.startsWith(initial))return {ok:false,reason:'douyin trailing text is not a provable prefix of the failed topic query',expected,actual:before.trimmed,evidence:before}
  const focused=await focusDouyinEditorEnd();if(!focused.ok)return focused
  for(let attempt=0;attempt<expected.length+4;attempt+=1){const current=await inspectDouyinTrailingPlainText(expectedDescription);if(!current.ok)return current;const tail=String(current.trimmed||'').toLowerCase();if(!tail||!tail.startsWith('#'))break;if(!expected.startsWith(tail))return {ok:false,reason:'douyin failed-topic tail changed into an unsafe value during cleanup',expected,actual:current.trimmed};await pressKey('Backspace').catch(()=>{});await wait(0.18)}
  const tail=await inspectDouyinTrailingPlainText(expectedDescription);const clean=!String(tail.trimmed||'').startsWith('#');return clean?{ok:true,before,after:tail}:{ok:false,reason:'douyin trailing tail could not be removed',tail}
}
async function addDouyinTopic(tag, description) {
  const queryTag=String(tag).replace(/^\s*#/,'').replace(/\s+/g,'')
  const beforeEntities=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return [];return [...editor.querySelectorAll('[data-mention="#"], [data-mention="activity"]')].map(el=>String(el.innerText||el.textContent||'').replace(/[\s​]+/g,'').replace(/^#/,'').toLowerCase()).filter(Boolean)})()`)
  if(beforeEntities.includes(queryTag.toLowerCase()))return {ok:true,already:true}
  const focused=await focusDouyinEditorEnd();if(!focused.ok)return focused
  await cdp('Input.insertText',{text:' '});await wait(0.2)
  const buttonPoint=await js(String.raw`(() => {const c=v=>String(v||'').replace(/\s+/g,' ').trim();const item=[...document.querySelectorAll('button,[role="button"],div,span')].map(el=>({el,text:c(el.innerText||el.textContent||''),r:el.getBoundingClientRect()})).filter(x=>x.text==='#添加话题'&&x.r.width>20&&x.r.width<140&&x.r.height>=8&&x.r.height<50).sort((a,b)=>a.r.width*a.r.height-b.r.width*b.r.height)[0];if(!item)return null;item.el.scrollIntoView({block:'center',inline:'center'});const r=item.el.getBoundingClientRect();return {x:r.left+r.width/2,y:r.top+r.height/2}})()`)
  if(!buttonPoint)return {ok:false,reason:'douyin add-topic button missing'}
  try{await click([buttonPoint.x,buttonPoint.y],{label:'open douyin topic '+queryTag})}catch(error){return {ok:false,reason:String(error?.message||error)}}
  await wait(0.7);await cdp('Input.insertText',{text:queryTag});await wait(1.4)
  const findRow=()=>js(String.raw`((tag) => {const c=v=>String(v||'').replace(/\s+/g,' ').trim();const expected='#'+String(tag).toLowerCase();const containers=[...document.querySelectorAll('[class*="mention-suggest-item-container"],.mention-suggest-mount-dom')].filter(el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'});const rows=containers.flatMap(container=>[...container.querySelectorAll('*')]).map(el=>({text:c(el.innerText||el.textContent||''),r:el.getBoundingClientRect()})).filter(item=>item.r.height>20&&item.r.height<90&&item.r.width>150&&(item.text.toLowerCase()===expected||item.text.toLowerCase().startsWith(expected+' '))).sort((a,b)=>a.text.length-b.text.length);const item=rows[0];return item?{x:item.r.left+Math.min(56,item.r.width/3),y:item.r.top+item.r.height/2,text:item.text}:null})(${JSON.stringify(queryTag)})`)
  let row=null;for(let poll=0;poll<12&&!row;poll+=1){row=await findRow();if(!row)await wait(0.8)}
  if(!row){const cleanup=await removeDouyinTrailingTopicQuery(queryTag,description);return cleanup.ok?{ok:false,reason:'topic suggestion_missing (cleaned)'}:{ok:false,reason:cleanup.reason}}
  try{await click([row.x,row.y],{label:'commit douyin topic '+queryTag})}catch(error){return {ok:false,reason:String(error?.message||error)}}
  await wait(1.4);await pressKey('ArrowRight').catch(()=>{});await cdp('Input.insertText',{text:' '}).catch(()=>{});await wait(0.3)
  const afterEntities=await js(String.raw`(() => {const editor=document.querySelector('#vp2-douyin-editor');if(!editor)return [];return [...editor.querySelectorAll('[data-mention="#"], [data-mention="activity"]')].map(el=>String(el.innerText||el.textContent||'').replace(/[\s​]+/g,'').replace(/^#/,'').toLowerCase()).filter(Boolean)})()`)
  if(!afterEntities.includes(queryTag.toLowerCase())){const cleanup=await removeDouyinTrailingTopicQuery(queryTag,description);return {ok:false,reason:cleanup.ok?'topic entity_not_committed (cleaned)':cleanup.reason}}
  return {ok:true,text:row.text}
}

// ===== 描述：清空再单次插入 =====
const body = await clearAndFillDouyinBody(DESCRIPTION)
if (!body.ok) { cliLog('⚠️ 描述填写失败: ' + body.reason + '，转人工'); await handOffTaskSpace(task.id) }
else cliLog('✅ 描述已写入: ' + (body.text||'').slice(0,80))
await wait(0.8 + Math.random()*1.0)

// ===== 话题：逐个实体化 =====
for (const tag of TOPICS) {
  const r = await addDouyinTopic(tag, DESCRIPTION)
  cliLog('话题 #' + tag + ': ' + (r.ok ? '✅ '+(r.already?'已存在':(r.text||'已提交')) : '⚠️ '+r.reason))
  await wait(0.6 + Math.random()*0.8)
}

// ===== 校验：实体数 + 残留纯文本 # =====
const verify = await js(String.raw`(() => {const e=document.querySelector('#vp2-douyin-editor');if(!e)return{mentionCount:0,residue:''};const mentionCount=e.querySelectorAll('[data-mention="#"], [data-mention="activity"]').length;const c=e.cloneNode(true);c.querySelectorAll('[data-mention],[data-fake-text],[class*="mention"],[class*="topic"],[class*="hash"]').forEach(el=>el.remove());const residue=(c.innerText||c.textContent||'').replace(/​/g,' ').trim();return{mentionCount,residue}})()`)
cliLog('话题实体数=' + verify.mentionCount + '/' + TOPICS.length + ' 残留纯文本#' + (/#/.test(verify.residue)?'有':'无'))
await wait(1)

// ===== 标题复核 =====
const titleCheck = await js(String.raw`(() => {const i=[...document.querySelectorAll('input')].find(el=>/标题/.test(el.placeholder||''));return {found:!!i, value:i?i.value:''}})()`)
cliLog('标题复核: ' + JSON.stringify(titleCheck))
