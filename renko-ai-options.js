/* Dedicated AI mode: independent draft and standalone execution, never legacy fallback. */
(function(root){
'use strict';
const MODE='AI_RENKO_OPTIONS';
function sizingContext(symbol,broker,category){
 if(!symbol)throw Error('Select an underlying instrument.');
 if(broker==='DELTA_INDIA'&&symbol.includes(':'))throw Error('Select an instrument supported by this broker.');
 let market=symbol.includes(':')?symbol.split(':')[0]:(broker==='DELTA_INDIA'?'CRYPTO':null);
 let parentHours,asset;
 if(category==='GOLD'||/^MCX:GOLD/.test(symbol)){parentHours=22;asset='GOLD';}
 else if(['NSE','BSE'].includes(market))parentHours=6;
 else if(market==='CRYPTO')parentHours=23;
 else if(market==='MCX')parentHours=14;
 else throw Error('The selected market needs an explicit parent duration.');
 return {market,asset,parentHours,baselineMinutes:30,divisor:parentHours*2};
}
function verifiedReference(data,symbol,context,now=Date.now()/1000){
 return (data.native_references||[data.native_reference]).filter(Boolean).filter(r=>{
  if((r.broker_symbol||r.symbol)!==symbol||!String(r.status||'').startsWith('VERIFIED_')||r.parent_hours!==context.parentHours||r.atr_length!==5||!(Number.isFinite(r.native_box)&&r.native_box>0))return false;
  if(['NSE','BSE'].includes(context.market))return r.chart_session==='Regular trading hours'&&!!data.expected_reference_session&&r.reference_session===data.expected_reference_session;
  return Number.isFinite(r.completed_parent_at)&&now>=r.completed_parent_at&&now-r.completed_parent_at<=context.parentHours*3600;
 }).sort((a,b)=>(b.completed_parent_at||0)-(a.completed_parent_at||0)||String(b.observed_at||'').localeCompare(String(a.observed_at||'')))[0]||null;
}
function chartView(draft,heartbeat,running,broker){
 const frozen=heartbeat?.position||heartbeat?.pending?.intent?.position||(running?heartbeat?.selected_contract:null);
 const underlying=frozen?.underlying||draft.underlying;
 const context=sizingContext(underlying,broker,frozen?frozen.asset==='GOLD'?'GOLD':undefined:draft.category);
 const base=frozen?.spot_brick??Number(draft.reference)/context.divisor;
 return {underlying,context,base,frozen:!!frozen,timeframe:frozen&&heartbeat?.timeframe?({1:'1 minute',5:'5 minutes',30:'30 minutes'}[heartbeat.timeframe]):draft.timeframe,route:frozen?.execution_route==='DIRECT'?'DIRECT':frozen?.option_type?'OPTIONS':draft.route};
}
function chartContracts(preview,heartbeat,underlying){
 const contracts={...(preview?.underlying===underlying?preview.contracts:{})};
 for(const c of [heartbeat?.selected_contract,heartbeat?.pending?.intent?.position,heartbeat?.position])if(c?.option_type&&c.underlying===underlying)contracts[c.option_type]=c;
 return contracts;
}
function configuration(fields,account,preview=false){
 if(!['FYERS','DELTA_INDIA'].includes(account?.broker))throw Error('Select a supported FYERS or Delta account.');
 const context=sizingContext(fields.underlying,account.broker,fields.category);
 const reference=Number(fields.reference),value=Number.isFinite(reference)&&reference>0&&fields.session&&fields.evidence?reference:null;if(!preview&&value===null)throw Error('A verified native ATR5 reference for the selected instrument is required.');
 const lots=Number(fields.lots);if(!preview&&(!Number.isInteger(lots)||lots<1))throw Error('Enter whole lots or contracts.');
 if(!preview&&(!fields.session||!fields.evidence))throw Error('Previous session and reference evidence are required.');
 if(!preview&&account.broker==='FYERS'&&!(fields.route==='DIRECT'?['MARGIN','INTRADAY','CNC']:['MARGIN','INTRADAY']).includes(fields.product))throw Error('Choose a product.');
 if(!['1 minute','5 minutes','30 minutes'].includes(fields.timeframe))throw Error('Choose 1, 5 or 30 minutes.');
 if(!(Number(fields.premium||40)>0))throw Error('Enter a positive premium target.');
 return {strategy_mode:MODE,broker:account.broker,account_id:account.id,underlying:fields.underlying,timeframe:fields.timeframe,
 mode:fields.execution,lots:preview?null:lots,preview_options:preview,target_premium:Number(fields.premium||40),ai_product:fields.product,
 ai_execution_route:fields.route||'OPTIONS',ai_market:context.market,ai_asset:context.asset,ai_parent_hours:context.parentHours,ai_baseline_minutes:30,
 ai_expiry_policy:'nearest_tradable',ai_reference_value:value,ai_reference_session:fields.session,ai_reference_symbol:fields.underlying,
 ai_reference_evidence:fields.evidence,ai_sma_exit_enabled:fields.sma===true,ai_accept_chart_basis:fields.accept===true};
}
function mount(){
 const section=document.getElementById('renko-supertrend'),mode=document.getElementById('renko-strategy-mode');
 if(!section||!mode||section.dataset.aiOptionsMounted)return;
 section.dataset.aiOptionsMounted='1';
 const aiOption=new Option('AI Renko Supertrend',MODE);
 aiOption.disabled=section.dataset.aiContextReady!=='1';mode.add(aiOption);
 root.addEventListener('renko-ai-context-ready',()=>{aiOption.disabled=section.dataset.aiContextReady!=='1';});

 const toolbar=document.createElement('div');toolbar.className='renko-ai-toolbar field-grid';
 const modeLabel=mode.closest('label');modeLabel.querySelector('small').textContent='Choose a strategy. Paper / Live is selected separately.';
 toolbar.append(modeLabel);section.querySelector('.head').after(toolbar);
 const broker=document.getElementById('renko-broker');if(broker)toolbar.append(broker.closest('label'));
 const panel=document.createElement('section');panel.className='panel renko-ai-panel';panel.hidden=true;
 panel.innerHTML=`<div class="step-title"><div><span class="label">AI RENKO SUPERTREND</span><h2>Selected instrument · AI Renko signals</h2></div><span class="badge">SELECTED INSTRUMENT</span></div>
 <p>Instrument-specific parent ATR5 scaled to a fixed 30-minute baseline. Options multiply by absolute provider delta; direct instruments use the base brick. Execution timeframe does not resize the brick.</p><p class="renko-ai-rules"></p>
 <div class="field-grid">
 <label class="field">Trade instrument<select data-ai="route"><option value="OPTIONS">Bought options · Call / Put</option><option value="DIRECT">Direct stock / future / perpetual</option></select></label><label class="field">Sizing category<select data-ai="category"><option value="">Selected market</option><option value="GOLD">Gold · 22-hour parent</option></select></label><label class="field">Execution<select data-ai="execution"><option value="PAPER">Paper</option><option value="LIVE">Live · real orders</option></select></label>
 <label class="field">Source timeframe<select data-ai="timeframe"><option>1 minute</option><option>5 minutes</option><option>30 minutes</option></select></label>
 <label class="field">Target premium · quote currency<input data-ai="premium" type="number" min="0.01" step="0.01" value="40"></label>
 <label class="field">Lots<input data-ai="lots" type="number" min="1" step="1" placeholder="Choose quantity"></label>
 <label class="field">Product<select data-ai="product"><option value="">Choose product</option><option value="MARGIN">MARGIN · carry forward</option><option value="INTRADAY">INTRADAY · broker square-off applies</option><option value="CNC">CNC · cash shares</option></select></label>
 <div class="field">Option expiry<small data-ai-expiry>Automatic · nearest tradable broker expiry, resolved at preflight and each new selection</small></div>
 <label class="field">Previous completed trading session<input data-ai="session" type="date"></label>
 <label class="field">Selected parent native Renko ATR5 reference<input data-ai="reference" type="number" min="0.00000001" step="any" placeholder="Verified chart value"></label>
 <label class="field renko-ai-wide">Reference evidence<input data-ai="evidence" placeholder="Chart source, date and verified six-hour ATR setting"></label>
 <label class="field renko-ai-wide"><span><input data-ai="sma" type="checkbox"> Optional SMA30 exit · one-minute underlying</span><small>OFF by default. Call: cross below; Put: cross above. Independent of source timeframe.</small></label>
 <label class="field renko-ai-wide"><span><input data-ai="accept" type="checkbox"> I reviewed the close-source, no-wick Renko basis</span><small>Full precision sizing. Native TradingView history and hosted marker parity remain unverified.</small></label>
 </div><p class="renko-ai-capability muted"></p><p class="renko-ai-sizing" role="status"></p>
 <div class="renko-ai-preview" role="status"></div><div class="packet-actions"><button class="button secondary" data-ai-action="preview">Preview selected instrument · read only</button><button class="button secondary" data-ai-action="prepare">Prepare Python configuration</button><button class="button" data-ai-action="start">Start AI runtime</button><button class="button secondary" data-ai-action="stop" disabled>Stop AI runtime</button></div>
 <p class="renko-ai-status" role="status">Standalone runtime · stopped. Preparing a configuration does not start monitoring.</p>`;
 toolbar.after(panel);
 const charts=document.createElement('section');charts.className='panel renko-ai-charts';charts.hidden=true;
 charts.innerHTML='<h2>Strategy charts</h2><p>Underlying · Call · Put. Selected contracts and full-precision sizing stay scoped to this strategy.</p><div class="renko-ai-chart-grid"></div>';panel.after(charts);
 const style=document.createElement('style');style.textContent='#renko-supertrend.renko-ai-active>:not(.head):not(.renko-ai-toolbar):not(.renko-ai-panel):not(.renko-ai-charts){display:none!important}.renko-ai-toolbar{margin:14px 0}.renko-ai-active>.head small:not(.renko-ai-summary),.renko-ai-active>.head #renko-state{display:none!important}#renko-supertrend .renko-ai-panel .field-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:16px}.renko-ai-toolbar>label{max-width:440px}.renko-ai-wide{grid-column:1/-1}.renko-ai-panel input[type=checkbox]{width:18px!important;min-width:18px!important;vertical-align:middle}.renko-ai-sizing{padding:12px 16px;border-left:3px solid #75b6de;background:#15334a;color:#d7e7f3}.renko-ai-chart-grid{display:grid;gap:18px;grid-template-columns:minmax(0,1fr)}.renko-ai-chart-grid iframe{width:100%;height:780px;border:1px solid #334154;border-radius:8px}.renko-ai-chart-grid h3{margin:8px 0}.renko-ai-chart-grid .contract-details{min-height:48px;color:#a8bfd0;font-size:12px;line-height:1.6}@media(min-width:1500px){.renko-ai-chart-grid.options-charts{grid-template-columns:repeat(3,minmax(0,1fr))}.renko-ai-chart-grid.options-charts iframe{height:640px}}.renko-ai-panel .packet-actions{display:flex;flex-wrap:wrap;gap:10px}@media(max-width:600px){.renko-ai-panel .packet-actions>button{flex:1 1 100%}.renko-ai-chart-grid iframe{height:650px}}';document.head.append(style);
 const inputs=[...panel.querySelectorAll('[data-ai]')],status=panel.querySelector('.renko-ai-status'),sizing=panel.querySelector('.renko-ai-sizing');
 const selected=()=>root.BrokerForms?.account('renko'),storage=()=> 'sector-pulse:ai-renko-options:'+ (selected()?.id||'unselected');
 const values=()=>({...Object.fromEntries(inputs.map(n=>[n.dataset.ai,n.type==='checkbox'?n.checked:n.value])),underlying:document.getElementById('renko-symbol')?.value,instrument_market:document.getElementById('renko-market')?.value});
 let current=null,snapshot=null,legacyFields=null,legacyOptions=null,referenceLoaded=false,referenceSymbol=null,optionPreview=null;
 const instrumentControls=['market','search','symbol'].map(id=>document.getElementById('renko-'+id)?.closest('label')).filter(Boolean).map(node=>{const anchor=document.createComment('AI instrument control position');node.before(anchor);return {node,parent:node.parentNode,anchor};});
 const aiSummary=document.createElement("small");aiSummary.className="renko-ai-summary muted";aiSummary.textContent="AI Renko Supertrend · selected instrument · fixed 30-minute sizing baseline";section.querySelector(".head h1").parentElement.append(aiSummary);aiSummary.hidden=true;
 function show(){
  const ai=mode.value===MODE,account=selected();for(const c of instrumentControls){if(ai)toolbar.append(c.node);else if(c.node.parentNode===toolbar)c.parent.insertBefore(c.node,c.anchor.nextSibling);}section.classList.toggle('renko-ai-active',ai);panel.hidden=charts.hidden=!ai;aiSummary.hidden=!ai;
  const option=[...mode.options].find(o=>o.value===MODE);option.disabled=!['FYERS','DELTA_INDIA'].includes(account?.broker);
  if(!ai)return;
  if(referenceSymbol!==values().underlying){for(const key of ['reference','evidence'])panel.querySelector('[data-ai='+key+']').value='';referenceSymbol=null;referenceLoaded=false;}
  const v=values(),reference=Number(v.reference);
  let context=null;try{context=sizingContext(v.underlying,account?.broker,v.category);}catch{}
  sizing.textContent=reference>0&&context?'Base Traditional brick: '+new Intl.NumberFormat('en-IN',{maximumFractionDigits:2}).format(reference/context.divisor)+' · '+context.parentHours+'H ATR5 ÷ '+context.divisor+' · fixed 30-minute baseline · '+(v.route==='DIRECT'?'direct instrument, no option delta':'option brick = base × absolute provider delta')+'.':'Select an instrument and obtain its own native parent ATR5 reference.';
  const supported=account?.broker==='FYERS'&&(v.route==='DIRECT'?['NSE','BSE','MCX']:['NSE','BSE']).includes(context?.market)||account?.broker==='DELTA_INDIA'&&context?.market==='CRYPTO';
  panel.querySelector('.renko-ai-capability').textContent=supported?(v.route==='DIRECT'?'Direct instrument: Paper simulation or explicit user-started Live orders.':'Bought options: Paper simulation or explicit user-started Live orders.'):!v.underlying?'Select your broker, market and underlying above.':'This selected broker/product execution adapter is not deployed yet. Sizing and chart integration are in progress; no execution fallback.';
  panel.querySelector('[data-ai=product]').closest('label').hidden=account?.broker==='DELTA_INDIA';
  panel.querySelector('[data-ai=premium]').closest('label').hidden=v.route==='DIRECT';panel.querySelector('[data-ai-expiry]').closest('.field').hidden=v.route==='DIRECT';
  panel.querySelector('.renko-ai-rules').textContent=v.route==='DIRECT'?(v.product==='CNC'?'Delivery shares: bullish underlying AI flip buys; bearish flip sells the owned shares.':'Direct instrument: bullish / bearish underlying AI flip opens Long / Short; opposing flip exits.'):'Options: underlying AI flip plus bullish selected premium AI Supertrend enters; bearish premium AI flip exits.';
  const stop=panel.querySelector('[data-ai-action=stop]');stop.disabled=!snapshot?.running&&snapshot?.phase!=='PREFLIGHT';
  let complete=false;try{configuration(v,account);complete=true;}catch{}
  panel.querySelector('[data-ai-action=prepare]').disabled=!complete;
  panel.querySelector('[data-ai-action=start]').disabled=!complete||!v.accept||!!snapshot?.running||snapshot?.phase==='PREFLIGHT'||!supported||!!snapshot?.heartbeat?.position||!!snapshot?.heartbeat?.pending;
  drawCharts(v);
 }
 function hydrate(data){
  if(data.resolved_expiry)panel.querySelector('[data-ai-expiry]').textContent='Automatic · '+new Date(Number(data.resolved_expiry)*1000).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short',year:'numeric'});
  const selectedSymbol=values().underlying;
  if(!selectedSymbol)return;
  let candidate=null;
  try{candidate=verifiedReference(data,selectedSymbol,sizingContext(selectedSymbol,selected()?.broker,values().category));}catch{}
  referenceLoaded=!!candidate;referenceSymbol=candidate?selectedSymbol:null;
  for(const [key,value] of Object.entries({reference:candidate?.native_box??'',session:candidate?.reference_session??'',evidence:candidate?((candidate.source||'')+' · '+(candidate.url||'')):''})){
   const input=panel.querySelector('[data-ai='+key+']');input.value=value;input.readOnly=true;
  }
 }
 function drawCharts(v){
  const account=selected();if(!account)return;
  const grid=charts.querySelector('.renko-ai-chart-grid');
  let view;try{view=chartView(v,snapshot?.heartbeat,snapshot?.running,account.broker);}catch{view=null;}
  if(!view){grid.replaceChildren();const message=document.createElement('p');message.textContent='Select a supported underlying to show its chart panels.';grid.append(message);return;}
  if(grid.firstElementChild?.tagName==='P')grid.replaceChildren();
  const held=snapshot?.heartbeat?.position,pending=snapshot?.heartbeat?.pending?.intent?.position;
  const {context}=view;
  const contracts=chartContracts(optionPreview,snapshot?.heartbeat,view.underlying);
  grid.dataset.underlying=view.underlying;grid.dataset.previewUnderlying=optionPreview?.underlying||'';grid.dataset.contractSides=Object.keys(contracts).join(',');
  const entries=[{title:'Underlying · '+view.underlying,symbol:view.underlying,brick:view.base,details:view.base>0?context.parentHours+'H ATR5 ÷ '+context.divisor+' · fixed 30-minute baseline':'Waiting for verified '+context.parentHours+'H native ATR5 reference for '+view.underlying}];
  if(view.route!=='DIRECT')for(const side of ['CE','PE']){
   const c=contracts[side];
   entries.push(c?{title:(side==='CE'?'Call':'Put')+(held?.symbol===c.symbol?' · HELD':pending?.symbol===c.symbol?' · PENDING':''),symbol:c.symbol,brick:c.option_brick,details:c.symbol+' · expiry '+(c.expiry_date||new Date(Number(c.expiry)*1000).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata'}))+' · delta '+Number(c.delta??c.selection_delta).toFixed(2)+' · '+(c.option_brick>0?'brick '+Number(c.option_brick).toFixed(2):'native sizing reference pending')}:{title:side==='CE'?'Call':'Put',details:'Use read-only preview to resolve the exact nearest-expiry contract and its delta.'});
  }
  grid.classList.toggle('options-charts',view.route!=='DIRECT');
  for(const [i,item] of entries.entries()){
   let card=grid.children[i];if(!card){card=document.createElement('article');card.innerHTML='<h3></h3><p class="contract-details"></p><iframe loading="lazy"></iframe>';grid.append(card);}
   card.querySelector('h3').textContent=item.title;card.querySelector('.contract-details').textContent=item.details;
   const frame=card.querySelector('iframe');frame.title=item.title;frame.hidden=!item.symbol||!(item.brick>0);
   if(frame.hidden){frame.removeAttribute('src');continue;}
   const sourceRun=view.frozen&&snapshot?.chart_source_series?.some(c=>c.symbol===item.symbol&&c.frame===Number.parseInt(view.timeframe||v.timeframe,10)&&c.brick===item.brick)?current?.run_id:null;
   const url=root.RenkoSupertrend.embeddedRenkoChartUrl(location.href,{accountId:account.id,broker:account.broker,symbol:item.symbol,instance:'ai-'+(sourceRun||'draft')+'-'+i,timeframe:view.timeframe||v.timeframe,brick:item.brick,ai:true,runId:sourceRun});
   const publishMarkers=()=>{const params=new URL(url).searchParams;frame.contentWindow?.postMessage({type:'sector-pulse-ai-runtime-markers',account:account.id,instance:params.get('chartInstance'),symbol:item.symbol,events:sourceRun?(snapshot?.markers||[]):[]},location.origin);};
   frame.onload=publishMarkers;
   if(frame.getAttribute('src')!==url)frame.src=url;else publishMarkers();
  }
  while(grid.children.length>entries.length)grid.lastElementChild.remove();
 }
 function restore(){
  try{const v=JSON.parse(localStorage.getItem(storage())||'null');referenceSymbol=v?.underlying||null;if(!v?.route&&selected()?.broker==='DELTA_INDIA')panel.querySelector('[data-ai=route]').value='DIRECT';if(v?.underlying){const symbol=document.getElementById('renko-symbol');if(![...symbol.options].some(o=>o.value===v.underlying))symbol.add(new Option(v.underlying,v.underlying));symbol.value=v.underlying;if(v.instrument_market)document.getElementById('renko-market').value=v.instrument_market;}if(v)for(const n of inputs)if(Object.hasOwn(v,n.dataset.ai)){if(n.type==='checkbox')n.checked=v[n.dataset.ai]===true;else n.value=v[n.dataset.ai];}}catch{}
 }
 async function request(action,body){
  const response=await root.BrokerForms.fetch('renko','/api/renko-supertrend/ai-options/'+action,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
  const result=await response.json();if(!response.ok||result.error)throw Error(result.error||'AI strategy request failed');return result;
 }
 let aiSearchTimer,aiSearchSequence=0;
 function clearInstrumentReference(){referenceLoaded=false;referenceSymbol=null;optionPreview=null;for(const key of ['reference','evidence'])panel.querySelector('[data-ai='+key+']').value='';panel.querySelector('.renko-ai-preview').replaceChildren();}
 async function searchAiInstruments(){
  const sequence=++aiSearchSequence,market=document.getElementById('renko-market').value,q=document.getElementById('renko-search').value;
  status.textContent='Searching current broker instruments…';
  try{
   const data=await request('search?'+new URLSearchParams({q,market,route:values().route}));if(sequence!==aiSearchSequence||mode.value!==MODE)return;
   const symbol=document.getElementById('renko-symbol'),prior=symbol.value,label=symbol.selectedOptions[0]?.textContent;
   symbol.replaceChildren(new Option('Select an underlying',''));
   for(const item of data.matches||[]){const option=new Option((item.underlying||item.description||item.symbol)+' · '+item.symbol,item.symbol);option.dataset.aiProductType=item.product_type||'';symbol.add(option);}
   if(prior){if(![...symbol.options].some(o=>o.value===prior))symbol.add(new Option(label||prior,prior));symbol.value=prior;}
   status.textContent=(data.matches||[]).length+' instruments · '+(data.message||'');show();
  }catch(error){status.textContent=error.message;}
 }
 document.addEventListener('input',event=>{if(mode.value!==MODE||event.target.id!=='renko-search')return;event.stopImmediatePropagation();clearTimeout(aiSearchTimer);aiSearchTimer=setTimeout(searchAiInstruments,300);},true);
 document.addEventListener('change',event=>{
  if(mode.value===MODE&&['renko-symbol','renko-market'].includes(event.target.id)){
   event.stopImmediatePropagation();clearInstrumentReference();
   if(event.target.id==='renko-market'){document.getElementById('renko-symbol').value='';document.getElementById('renko-search').value='';searchAiInstruments();}
   else if(event.target.selectedOptions[0]?.dataset.aiProductType==='FUTURE')panel.querySelector('[data-ai=route]').value='DIRECT';
   localStorage.setItem(storage(),JSON.stringify(values()));show();refreshStatus();return;
  }
  if(event.target!==mode)return;
  if(mode.value===MODE){
   event.stopImmediatePropagation();
   root.dispatchEvent(new CustomEvent('renko-ai-mode-enter'));
   legacyOptions=[...section.querySelectorAll('#renko-symbol,#renko-market')].map(n=>[n,[...n.options].map(o=>o.cloneNode(true))]);
   legacyFields=[...section.querySelectorAll('input,select')].filter(n=>!n.hasAttribute('data-ai')&&n!==mode).map(n=>[n,n.type==='checkbox'?n.checked:n.value]);
   const markets=document.getElementById('renko-market');for(const [value,label] of [['NSE_FUTURE','NSE futures'],['BSE_FUTURE','BSE futures']])if(![...markets.options].some(o=>o.value===value))markets.add(new Option(label,value));
   restore();show();refreshStatus();
  }else if(legacyFields){
   const saved=legacyFields,options=legacyOptions;legacyFields=null;legacyOptions=null;queueMicrotask(()=>{for(const [n,nodes] of options||[])n.replaceChildren(...nodes);for(const [n,v] of saved){if(n.type==='checkbox')n.checked=v;else n.value=v;}show();});
  }
 },true);
 panel.addEventListener('change',event=>{event.stopPropagation();if(['reference','evidence'].includes(event.target.dataset.ai))referenceSymbol=values().underlying;localStorage.setItem(storage(),JSON.stringify(values()));show();});
 panel.addEventListener('input',event=>{event.stopPropagation();if(['reference','evidence'].includes(event.target.dataset.ai))referenceSymbol=values().underlying;});
 panel.addEventListener('click',async event=>{
  const action=event.target.closest('[data-ai-action]')?.dataset.aiAction;if(!action)return;event.preventDefault();event.stopPropagation();status.dataset.userMessage='1';
  try{
   const payload=action==='stop'?{broker:selected()?.broker,account_id:selected()?.id,underlying:values().underlying}:configuration(values(),selected(),action==='preview');
   if(action==='stop'){snapshot=await request('stop',{...payload,run_id:current?.run_id});}
   else if(action==='preview'){
    status.textContent='Reading current FYERS expiry, chain and contract master…';
    const prepared=await request('prepare',payload),preview=prepared.preview;
    if(preview?.direct){panel.querySelector('.renko-ai-preview').textContent=preview.direct.symbol+' · '+(preview.direct.product_type||'PERPETUAL')+' · base brick '+(preview.spot_brick===null?'unavailable · native reference pending':Number(preview.spot_brick).toFixed(2))+' · no option delta';drawCharts(values());status.textContent='Read-only direct-instrument metadata preview complete · no monitoring or orders.';return;}
    if(!preview?.contracts)throw Error('Option sizing preview unavailable');
    if(prepared.config?.underlying!==payload.underlying)throw Error('Backend did not confirm the selected underlying; preview charts remain unavailable.');
    if(values().underlying!==payload.underlying)throw Error('Instrument changed during preview; previous response discarded.');
    optionPreview={...preview,underlying:prepared.config.underlying};panel.dataset.previewUnderlying=optionPreview.underlying;panel.dataset.previewSides=Object.keys(optionPreview.contracts).join(',');
    panel.querySelector('[data-ai-expiry]').textContent='Automatic · '+preview.contracts.CE.expiry_date;
    const box=panel.querySelector('.renko-ai-preview');box.replaceChildren();
    for(const [side,c] of Object.entries(preview.contracts)){const line=document.createElement('p');line.textContent=side+' · '+c.symbol+' · expiry '+c.expiry_date+' · premium '+(c.quote_currency||'INR')+' '+Number(c.selection_ltp).toFixed(2)+' · delta '+Number(c.delta).toFixed(2)+' · option brick '+(c.option_brick===null?'unavailable · native reference pending':Number(c.option_brick).toFixed(2));box.append(line);}
    const note=document.createElement('small');note.textContent='Read-only snapshot '+preview.checked_at+' · '+(preview.reference_value>0?'Underlying reference '+Number(preview.reference_value).toFixed(2)+' ('+preview.reference_session+') ÷ '+sizingContext(payload.underlying,payload.broker,values().category).divisor:'Native parent reference pending · price and delta preview only')+'. '+preview.quote_note;box.append(note);
    drawCharts(values());status.textContent='Read-only sizing preview complete · no monitoring or orders.';return;
   }else if(action==='prepare'){
    const prepared=await request('prepare',payload);
    const blob=new Blob([JSON.stringify(prepared.config,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='ai-renko-supertrend.json';a.click();URL.revokeObjectURL(url);
    status.textContent='Python configuration prepared. Run the read-only preflight before activation.';return;
   }else{
    if(payload.mode==='LIVE'){const confirmation=root.prompt('Real '+payload.broker+' orders · '+payload.underlying+' · '+payload.ai_execution_route+' · quantity '+payload.lots+'. Type START AI RENKO LIVE to confirm.');if(confirmation!=='START AI RENKO LIVE')return;payload.confirmation=confirmation;}
    snapshot=await request('start',payload);current=snapshot;
   }
   status.textContent=snapshot.phase+' · '+(snapshot.error||snapshot.notice||snapshot.run_id||'stopped');show();
  }catch(error){status.textContent=error.message;}
 });
 async function refreshStatus(){
  if(mode.value!==MODE)return;
  if(!['FYERS','DELTA_INDIA'].includes(selected()?.broker)){status.textContent='Waiting for the selected broker account…';return;}
  if(!snapshot&&!status.dataset.userMessage)status.textContent='Reading strategy status…';
  try{snapshot=await request('status');current=snapshot;hydrate(snapshot);if(!status.dataset.userMessage)status.textContent=snapshot.phase+' · '+(snapshot.error||snapshot.run_id||'stopped');show();}
  catch(error){status.textContent='Backend activation pending: '+error.message;}
 }
 setInterval(refreshStatus,5000);
 root.addEventListener('broker-accounts-ready',()=>{show();refreshStatus();});
 show();
}
if(typeof module!=='undefined')module.exports={configuration,sizingContext,chartContracts,chartView,verifiedReference};
if(typeof document!=='undefined'){
 const observer=new MutationObserver(()=>mount());observer.observe(document.documentElement,{childList:true,subtree:true});
 root.addEventListener('broker-accounts-ready',mount);if(document.readyState!=='loading')mount();else document.addEventListener('DOMContentLoaded',mount);
}
})(typeof window==='undefined'?globalThis:window);
