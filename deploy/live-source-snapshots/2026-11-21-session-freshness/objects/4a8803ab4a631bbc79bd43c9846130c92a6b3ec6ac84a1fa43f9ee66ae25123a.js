/* Dedicated AI mode: independent draft and standalone execution, never legacy fallback. */
(function(root){
'use strict';
const MODE='AI_RENKO_OPTIONS';
function configuration(fields,account){
 if(account?.broker!=='FYERS')throw Error('Select a FYERS account for AI Renko Supertrend.');
 const value=Number(fields.reference);if(!Number.isFinite(value)||value<=0)throw Error('Enter the verified previous-session six-hour Renko ATR5 value.');
 const lots=Number(fields.lots);if(!Number.isInteger(lots)||lots<1)throw Error('Enter whole lots.');
 if(!fields.expiry||!fields.session||!fields.evidence)throw Error('Expiry, previous session and reference evidence are required.');
 if(!['MARGIN','INTRADAY'].includes(fields.product))throw Error('Choose a product.');
 if(!['1 minute','5 minutes','30 minutes'].includes(fields.timeframe))throw Error('Choose 1, 5 or 30 minutes.');
 if(!(Number(fields.premium||40)>0))throw Error('Enter a positive premium target.');
 return {strategy_mode:MODE,broker:'FYERS',account_id:account.id,underlying:'NSE:NIFTY50-INDEX',timeframe:fields.timeframe,
 mode:fields.execution,lots,target_premium:Number(fields.premium||40),ai_product:fields.product,
 ai_expiry:String(fields.expiry),ai_reference_value:value,ai_reference_session:fields.session,
 ai_reference_evidence:fields.evidence,ai_sma_exit_enabled:fields.sma===true,ai_accept_chart_basis:fields.accept===true};
}
function mount(){
 const section=document.getElementById('renko-supertrend'),mode=document.getElementById('renko-strategy-mode');
 if(!section||!mode||section.dataset.aiOptionsMounted)return;
 section.dataset.aiOptionsMounted='1';
 mode.add(new Option('AI Renko Supertrend',MODE));
 const toolbar=document.createElement('div');toolbar.className='renko-ai-toolbar field-grid';
 const modeLabel=mode.closest('label');modeLabel.querySelector('small').textContent='Choose a strategy. Paper / Live is selected separately.';
 toolbar.append(modeLabel);section.querySelector('.head').after(toolbar);
 const broker=document.getElementById('renko-broker');if(broker)toolbar.append(broker.closest('label'));
 const panel=document.createElement('section');panel.className='panel renko-ai-panel';panel.hidden=true;
 panel.innerHTML=`<div class="step-title"><div><span class="label">AI RENKO SUPERTREND</span><h2>Nifty options · premium signals</h2></div><span class="badge">BOUGHT OPTIONS</span></div>
 <p>Nifty’s confirmed flip chooses Call or Put. A bullish premium Supertrend permits entry; its bearish flip exits. Parent 6H ATR5 ÷ 12 · premium brick × absolute delta · fixed per selection · AI factor 3.</p>
 <div class="field-grid">
 <label class="field">Execution<select data-ai="execution"><option value="PAPER">Paper</option><option value="LIVE">Live · real orders</option></select></label>
 <label class="field">Source timeframe<select data-ai="timeframe"><option>1 minute</option><option>5 minutes</option><option>30 minutes</option></select></label>
 <label class="field">Target premium · ₹<input data-ai="premium" type="number" min="0.01" step="0.01" value="40"></label>
 <label class="field">Lots<input data-ai="lots" type="number" min="1" step="1" placeholder="Choose quantity"></label>
 <label class="field">Product<select data-ai="product"><option value="">Choose product</option><option value="MARGIN">MARGIN · carry forward</option><option value="INTRADAY">INTRADAY · broker square-off applies</option></select></label>
 <label class="field">Option expiry<select data-ai="expiry"><option value="">Choose expiry</option></select></label>
 <label class="field">Previous completed trading session<input data-ai="session" type="date"></label>
 <label class="field">Six-hour native Renko ATR5 reference<input data-ai="reference" type="number" min="0.00000001" step="any" placeholder="Verified chart value"></label>
 <label class="field renko-ai-wide">Reference evidence<input data-ai="evidence" placeholder="Chart source, date and verified six-hour ATR setting"></label>
 <label class="field renko-ai-wide"><span><input data-ai="sma" type="checkbox"> Optional SMA30 exit · one-minute Nifty</span><small>OFF by default. Call: cross below; Put: cross above. Independent of source timeframe.</small></label>
 <label class="field renko-ai-wide"><span><input data-ai="accept" type="checkbox"> I reviewed the close-source, no-wick Renko basis</span><small>Full precision sizing. Native TradingView history and hosted marker parity remain unverified.</small></label>
 </div><p class="renko-ai-sizing" role="status"></p>
 <div class="packet-actions"><button class="button secondary" data-ai-action="prepare">Prepare Python configuration</button><button class="button" data-ai-action="start">Start AI runtime</button><button class="button secondary" data-ai-action="stop" disabled>Stop AI runtime</button></div>
 <p class="renko-ai-status" role="status">Standalone runtime · stopped. Preparing a configuration does not start monitoring.</p>`;
 toolbar.after(panel);
 const charts=document.createElement('section');charts.className='panel renko-ai-charts';charts.hidden=true;
 charts.innerHTML='<h2>Strategy charts</h2><p>New chart engine · isolated from the standalone Charts workspace. Nifty gate and selected option use the same source timeframe.</p><div class="renko-ai-chart-grid"></div>';panel.after(charts);
 const style=document.createElement('style');style.textContent='#renko-supertrend.renko-ai-active>:not(.head):not(.renko-ai-toolbar):not(.renko-ai-panel):not(.renko-ai-charts){display:none!important}.renko-ai-toolbar{margin:14px 0}.renko-ai-active>.head small:not(.renko-ai-summary),.renko-ai-active>.head #renko-state{display:none!important}#renko-supertrend .renko-ai-panel .field-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:16px}.renko-ai-toolbar>label{max-width:440px}.renko-ai-wide{grid-column:1/-1}.renko-ai-panel input[type=checkbox]{width:18px!important;min-width:18px!important;vertical-align:middle}.renko-ai-sizing{padding:12px 16px;border-left:3px solid #75b6de;background:#15334a;color:#d7e7f3}.renko-ai-chart-grid{display:grid;gap:18px;grid-template-columns:minmax(0,1fr)}.renko-ai-chart-grid iframe{width:100%;height:780px;border:1px solid #334154;border-radius:8px}.renko-ai-chart-grid h3{margin:8px 0}.renko-ai-panel .packet-actions{display:flex;flex-wrap:wrap;gap:10px}@media(max-width:600px){.renko-ai-panel .packet-actions>button{flex:1 1 100%}.renko-ai-chart-grid iframe{height:650px}}';document.head.append(style);
 const inputs=[...panel.querySelectorAll('[data-ai]')],status=panel.querySelector('.renko-ai-status'),sizing=panel.querySelector('.renko-ai-sizing');
 const selected=()=>root.BrokerForms?.account('renko'),storage=()=> 'sector-pulse:ai-renko-options:'+ (selected()?.id||'unselected');
 const values=()=>Object.fromEntries(inputs.map(n=>[n.dataset.ai,n.type==='checkbox'?n.checked:n.value]));
 let current=null,snapshot=null,legacyFields=null,referenceLoaded=false;
 const aiSummary=document.createElement("small");aiSummary.className="renko-ai-summary muted";aiSummary.textContent="AI Renko Supertrend · Nifty options · premium entry and exit signals";section.querySelector(".head h1").parentElement.append(aiSummary);aiSummary.hidden=true;
 function show(){
  const ai=mode.value===MODE,account=selected();section.classList.toggle('renko-ai-active',ai);panel.hidden=charts.hidden=!ai;aiSummary.hidden=!ai;
  const option=[...mode.options].find(o=>o.value===MODE);option.disabled=account?.broker!=='FYERS';
  if(!ai)return;
  const v=values(),reference=Number(v.reference);
  sizing.textContent=reference>0?'Spot Traditional brick: '+new Intl.NumberFormat('en-IN',{maximumFractionDigits:2}).format(reference/12)+' · option brick = spot brick × absolute FYERS delta, frozen per selection.':'Supply the verified previous-session reference. The example ₹400 is not a measured baseline.';
  const stop=panel.querySelector('[data-ai-action=stop]');stop.disabled=!snapshot?.running&&snapshot?.phase!=='PREFLIGHT';
  let complete=false;try{configuration(v,account);complete=true;}catch{}
  panel.querySelector('[data-ai-action=prepare]').disabled=!complete;
  panel.querySelector('[data-ai-action=start]').disabled=!complete||!v.accept||!!snapshot?.running||snapshot?.phase==='PREFLIGHT'||account?.broker!=='FYERS';
  drawCharts(v);
 }
 function hydrate(data){
  const expiry=panel.querySelector('[data-ai=expiry]');
  if(data.available_expiries?.length&&!expiry.dataset.loaded){const prior=expiry.value;expiry.replaceChildren(new Option('Choose expiry',''),...data.available_expiries.map(r=>new Option(r.date,String(r.expiry))));expiry.value=prior;expiry.dataset.loaded='1';}
  if(!referenceLoaded&&data.native_reference){referenceLoaded=true;const r=data.native_reference;for(const [key,value] of Object.entries({reference:r.native_box,session:r.reference_session,evidence:r.source+' · '+r.url})){const input=panel.querySelector('[data-ai='+key+']');if(!input.value)input.value=value;}}
 }
 function drawCharts(v){
  const account=selected();if(!account)return;
  const grid=charts.querySelector('.renko-ai-chart-grid');
  if(!(Number(v.reference)>0)){grid.replaceChildren();const message=document.createElement('p');message.textContent='Chart waits for the verified previous-session sizing reference.';grid.append(message);return;}
  if(grid.firstElementChild?.tagName==='P')grid.replaceChildren();
  const position=snapshot?.heartbeat?.position||snapshot?.heartbeat?.selected_contract;
  const entries=[['Nifty · side gate','NSE:NIFTY50-INDEX',Number(v.reference)/12],...(position?[['Selected option · premium signals',position.symbol,position.option_brick]]:[])];
  for(const [i,[title,symbol,brick]] of entries.entries()){
   let card=grid.children[i];if(!card){card=document.createElement('article');card.innerHTML='<h3></h3><iframe loading="lazy"></iframe>';grid.append(card);}
   card.querySelector('h3').textContent=title;const frame=card.querySelector('iframe');frame.title=title;
   const url=root.RenkoSupertrend.embeddedRenkoChartUrl(location.href,{accountId:account.id,broker:account.broker,symbol,instance:'ai-'+(current?.run_id||'draft')+'-'+i,timeframe:v.timeframe,brick,ai:true});
   if(frame.getAttribute('src')!==url)frame.src=url;
  }
  while(grid.children.length>entries.length)grid.lastElementChild.remove();
 }
 function restore(){
  try{const v=JSON.parse(localStorage.getItem(storage())||'null');if(v)for(const n of inputs)if(Object.hasOwn(v,n.dataset.ai)){if(n.type==='checkbox')n.checked=v[n.dataset.ai]===true;else n.value=v[n.dataset.ai];}}catch{}
 }
 async function request(action,body){
  const response=await root.BrokerForms.fetch('renko','/api/renko-supertrend/ai-options/'+action,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
  const result=await response.json();if(!response.ok||result.error)throw Error(result.error||'AI strategy request failed');return result;
 }
 document.addEventListener('change',event=>{
  if(event.target!==mode)return;
  if(mode.value===MODE){
   event.stopImmediatePropagation();
   legacyFields=[...section.querySelectorAll('input,select')].filter(n=>!n.hasAttribute('data-ai')&&n!==mode).map(n=>[n,n.type==='checkbox'?n.checked:n.value]);
   restore();show();
  }else if(legacyFields){
   const saved=legacyFields;legacyFields=null;queueMicrotask(()=>{for(const [n,v] of saved){if(n.type==='checkbox')n.checked=v;else n.value=v;}show();});
  }
 },true);
 panel.addEventListener('change',event=>{event.stopPropagation();localStorage.setItem(storage(),JSON.stringify(values()));show();});
 panel.addEventListener('input',event=>{event.stopPropagation();});
 panel.addEventListener('click',async event=>{
  const action=event.target.closest('[data-ai-action]')?.dataset.aiAction;if(!action)return;event.preventDefault();event.stopPropagation();
  try{
   const payload=action==='stop'?{broker:'FYERS',account_id:selected()?.id,underlying:'NSE:NIFTY50-INDEX'}:configuration(values(),selected());
   if(action==='stop'){snapshot=await request('stop',{...payload,run_id:current?.run_id});}
   else if(action==='prepare'){
    const prepared=await request('prepare',payload);
    const blob=new Blob([JSON.stringify(prepared.config,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='nifty-ai-options.json';a.click();URL.revokeObjectURL(url);
    status.textContent='Python configuration prepared. Run the read-only preflight before activation.';return;
   }else{
    if(payload.mode==='LIVE'){const confirmation=root.prompt('Real option orders. Type START AI RENKO LIVE to confirm this account, expiry and quantity.');if(confirmation!=='START AI RENKO LIVE')return;payload.confirmation=confirmation;}
    snapshot=await request('start',payload);current=snapshot;
   }
   status.textContent=snapshot.phase+' · '+(snapshot.error||snapshot.notice||snapshot.run_id||'stopped');show();
  }catch(error){status.textContent=error.message;}
 });
 setInterval(async()=>{
  if(mode.value!==MODE||selected()?.broker!=='FYERS')return;
  try{snapshot=await request('status');current=snapshot;hydrate(snapshot);status.textContent=snapshot.phase+' · '+(snapshot.error||snapshot.run_id||'stopped');show();}
  catch(error){status.textContent='Backend activation pending: '+error.message;}
 },5000);
 root.addEventListener('broker-accounts-ready',show);
 show();
}
if(typeof module!=='undefined')module.exports={configuration};
if(typeof document!=='undefined'){
 const observer=new MutationObserver(()=>mount());observer.observe(document.documentElement,{childList:true,subtree:true});
 root.addEventListener('broker-accounts-ready',mount);if(document.readyState!=='loading')mount();else document.addEventListener('DOMContentLoaded',mount);
}
})(typeof window==='undefined'?globalThis:window);
