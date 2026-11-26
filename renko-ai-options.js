/* Dedicated AI mode: independent draft and standalone execution, never legacy fallback. */
(function(root){
'use strict';
const MODE='AI_RENKO_OPTIONS';
// An explicit alternative belongs to this visit, never to a later section entry.
function manualRequestLabel(snapshot){
 const receipt=snapshot?.manual_entry;if(!receipt)return 'Active quantity: '+(snapshot?.active_lots??'—')+' · '+(snapshot?.manual_entry_context?.mode||'runner stopped');
 const owned=snapshot?.ownership;
 const retained=owned?.pending||owned?.position||owned?.detached_position||owned?.stop_verification_position||(owned?.positions||[]).length||Object.keys(owned?.closing_legs||{}).length;
 if(!snapshot.running&&owned&&!retained&&receipt.phase==='FAILED_OR_PENDING')return 'Previous run · manual request error (historical)';
 return receipt.phase+(receipt.error?' · '+receipt.error:'');
}
function createStrategyVisit(){
 let active=false,selection=MODE;
 return {
  enter(){if(!active){active=true;selection=MODE;}return selection;},
  leave(){active=false;},
  choose(value){if(active&&[MODE,'SUPERTREND','SIMPLE_BRICK'].includes(value))selection=value;return selection;},
  selected(){return selection;}
 };
}


function positionControlView(snapshot){
 const ownership=snapshot?.ownership||{},control=snapshot?.position_control||{};
 const receipt=snapshot?.position_control_receipt;
 const busy=['QUEUED','CLAIMED','WAITING_FOR_SOURCE','VERIFYING_FLAT','HANDED_OVER'].includes(receipt?.phase);
 const detached=!!ownership.detached_position||control.mode==='DETACHED';
 const owned=ownership.position||snapshot?.heartbeat?.position;
 return {label:detached||!owned?'Attach':'Detach',operation:detached||!owned?'ATTACH':'DETACH',
  blocked:busy||!!ownership.pending,stopBlocked:busy,capable:snapshot?.position_control_capable===true,
  status:receipt?(receipt.error||({STOPPED:receipt.simulated_flat_confirmed?'Paper position closed · stopped':receipt.broker_flat_confirmed?'Squared off · stopped':'Stopped · no owned position',DETACHED:'Detached · broker holding remains open',ATTACHED:'Attached · managing selected holding; new entries paused'})[receipt.phase]||receipt.notice||receipt.phase):detached?'Detached · broker holding remains open':''};
}
function positionControlPayload(snapshot,values,account,operation,requestId,holding){
 const context=snapshot?.position_control_context;
 if(!context||!snapshot.position_control_capable)throw Error('Position controls are not loaded for this run.');
 if(context.account_id!==account?.id||context.broker!==account?.broker||context.underlying!==values.underlying)throw Error('Select the active strategy account and underlying.');
 if(values.execution&&context.mode!==values.execution)throw Error('Select the active run execution mode for position controls.');
 if(values.route&&context.route!==values.route)throw Error('Select the active run instrument route for position controls.');
 if(values.timeframe&&context.timeframe!==({'1 minute':1,'5 minutes':5,'30 minutes':30}[values.timeframe]))throw Error('Select the active run timeframe for position controls.');
 const body={...context,operation,request_id:requestId};
 if(operation==='ATTACH'){
  if(!holding||holding.account!==account.id||holding.underlying!==values.underlying)throw Error('Refresh and select an actual open broker position.');
  body.holding={symbol:holding.symbol,quantity:holding.quantity,product:holding.product};
 }
 return body;
}
function nativeBrokerReady(snapshot,account,values,now=Date.now()/1000){
 if(!['DHAN','MOTILAL_OSWAL'].includes(account?.broker))return true;
 const proof=snapshot?.native_broker_readiness;
 if(values.route==='DIRECT'&&(snapshot?.[account.broker==='DHAN'?'dhan_direct_ready':'motilal_direct_ready']!==true||proof?.execution_route!=='DIRECT'))return false;
 if((proof?.execution_route||'OPTIONS')!==(values.route||'OPTIONS'))return false;
 if(account.broker==='MOTILAL_OSWAL'&&(snapshot?.motilal_fyers_data_ready!==true||proof?.market_data_broker!=='FYERS'||!values.dataAccount||proof?.market_data_account!==values.dataAccount))return false;
 return snapshot?.native_broker_integration_ready===true&&proof?.ready===true
  &&proof.account_id===account.id&&proof.broker===account.broker&&proof.underlying===values.underlying
  &&proof.timeframe===({'1 minute':1,'5 minutes':5,'30 minutes':30}[values.timeframe])
  &&proof.product===values.product&&proof.signal_source===((values.underlyingSignals??values.underlyingEntry)===false?'PREMIUM':'UNDERLYING')
  &&proof.valid_until>now;
}
function expiryDeadline(row){
 if(Number.isFinite(row?.expires_at)&&row.expires_at>0)return row.expires_at*1000;
 return /^\d+$/.test(String(row?.value||''))?Number(row.value)*1000:NaN;
}
function retainAttachment(previous,rows,account,underlying){
 if(!previous||previous.account!==account||previous.underlying!==underlying)return null;
 const row=rows.find(r=>r.symbol===previous.symbol&&r.product===previous.product&&r.quantity===previous.quantity);
 return row?{...row,account,underlying}:null;
}

function capturedStrategyRules(snapshot,symbol,account){
 const owner=snapshot?.manual_entry_context?.account_id||snapshot?.position_control_context?.account_id||snapshot?.contracts_preview?.account_id;
 if(account&&owner!==account)return null;
 if(!snapshot?.run_id||snapshot.underlying!==symbol)return null;
 const h=snapshot.heartbeat||{},premium=snapshot.signal_source==='PREMIUM',st=snapshot.supertrend_enabled!==false;
 const bands=h.moving_bands?.bands;
 if(!Array.isArray(bands))return null;
 const lines=['Signals: '+(premium?'selected option premium':'underlying')+' · '+(snapshot.source_timeframe||h.timeframe||'?')+' minute candles.'];
 lines.push(snapshot.calculation_mode==='HYBRID'?'Confirmation: completed price brick first, or a completed candle body smaller than one brick. Partial units never qualify.':'Calculation: candle-only captured run. Changing chart display does not switch the running decision basis.');
 if(st)lines.push('Supertrend: length '+(snapshot.indicator_length||5)+' · multiplier '+(snapshot.indicator_factor||3)+'.');
 if(st)lines.push(premium?'Entry: bullish premium Supertrend flip; underlying direction selects Call / Put.':'Entry: a NEW confirmed Supertrend flip after Start — bullish buys Call; bearish buys Put. An already-aligned trend alone does not enter.');
 else lines.push('Entry: SMA band only; no Supertrend gate.');
 for(const b of bands){
  const title=b.kind+' '+b.period;
  if(b.entry)lines.push(title+' entry: '+(premium?'option close above the upper band.':'Call close above the upper band; Put close below the lower band.'));
 }
 const retest=snapshot.sma_retest_required??h.moving_bands?.retest_required;
 lines.push('SMA retest: '+(bands.some(b=>b.kind==='SMA'&&b.entry)?retest===false?'OFF — not required.':'ON — touch the band, then the immediately next completed directional confirmation candle.':'not used; SMA entry is off.'));
 const exits=[];
 if(st)exits.push(premium?'confirmed bearish premium Supertrend':'confirmed opposite underlying Supertrend');
 for(const b of bands)if(b.exit)exits.push(b.kind+' '+b.period+' adverse completed close '+(premium?'below its lower band':'(Call below lower band; Put above upper band)'));
 lines.push('Exit: '+(exits.length?exits.join(' OR ')+'. Any enabled exit can trigger independently.':'no enabled exit reported.'));
 if(snapshot.sizing_mode==='MANUAL_PARENT')lines.push('Sizing: manual parent '+Number(snapshot.manual_parent_value).toLocaleString('en-IN',{maximumFractionDigits:2})+' — user supplied, not independently verified.');
 if(h.position?.manual_override)lines.push('Current holding: entered by your manual override; strategy exits manage it.');
 else if(!h.position)lines.push('Current holding: flat. Entry rules still need to qualify.');
 lines.push('Runner: '+(snapshot.running?'ACTIVE':'STOPPED')+' · '+(snapshot.mode||'')+'.');
 return {running:!!snapshot.running,lines:snapshot.execution_route==='DIRECT'?lines.map(line=>line.replaceAll('Call','Long').replaceAll('Put','Short').replace('bullish buys Long; bearish buys Short','bullish opens Long; bearish opens Short')):lines};
}
function instrumentSettingsKey(user,account,symbol=''){
 if(!user||!account?.id||!account?.broker)return null;
 return 'sector-pulse:ai-renko-settings:v2:'+encodeURIComponent(user)+':'+encodeURIComponent(account.broker)+':'+encodeURIComponent(account.id)+(symbol?':'+encodeURIComponent(symbol):'');
}
function readInstrumentSettings(store,user,account,symbol){
 const key=instrumentSettingsKey(user,account,symbol);if(!key||!symbol)return null;
 try{const value=JSON.parse(store.getItem(key)||'null');return value?.user===user&&value.account===account.id&&value.broker===account.broker&&value.symbol===symbol?value.settings:null;}catch{return null;}
}
function writeInstrumentSettings(store,user,account,settings){
 const key=instrumentSettingsKey(user,account,settings?.underlying);if(!key||!settings?.underlying)return;
 const clean={...settings};for(const field of ['reference','session','evidence','decisionMode'])delete clean[field];
 store.setItem(key,JSON.stringify({user,account:account.id,broker:account.broker,symbol:settings.underlying,settings:clean}));
}
function createAiContextLoader(fetcher){
 let pending=null;
 return async context=>{
  if(context?.csrf)return context;
  if(!pending)pending=(async()=>{
   const response=await fetcher('/api/workspaces/me',{cache:'no-store'});
   if(!response.ok)throw Error('Sign in to Sector Pulse before preparing this strategy.');
   const user=await response.json();
   if(typeof user?.csrf!=='string'||!user.csrf)throw Error('Strategy session verification is unavailable. Refresh the dashboard.');
   return user;
  })().catch(error=>{pending=null;throw error;});
  const user=await pending;
  if(context?.username&&user.username!==context.username)throw Error('Strategy session user changed. Refresh the dashboard.');
  return user;
 };
}
function aiRequestOptions(body,context){
 return body?{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':context?.csrf||''},body:JSON.stringify(body)}:undefined;
}
function mappedChartOwnership(payload,mappings){
 const mapRow=row=>row?{...row,execution_symbol:row.symbol,execution_underlying:row.underlying,
  symbol:mappings[row.symbol]||row.symbol,underlying:mappings[row.underlying]||row.underlying}:null;
 return {...payload,active_position:mapRow(payload.active_position),active_trade:mapRow(payload.active_trade),
  events:(payload.events||[]).map(mapRow)};
}
function restoredDataAccount(current,accounts){
 const eligible=accounts.filter(a=>a.broker==='FYERS');
 if(eligible.some(a=>a.id===current))return current;
 return eligible.length===1?eligible[0].id:'';
}
function restoredInstrumentValues(defaults,saved,symbol){
 const values={...defaults,...(saved||{}),underlying:symbol};
 if(!saved){values.manualParent='';values.manualParentAt=null;}
 return values;
}
function manualSizingValues(fields){
 if(fields.sizingMode!=='MANUAL_PARENT')return fields;
 const value=Number(fields.manualParent);
 return {...fields,reference:Number.isFinite(value)&&value>0?String(value):'',
  session:'Manual parent override',evidence:'User-entered parent size; not independently verified'};
}
function chartFramePolicy(item){
 const pending=!(Number.isFinite(Number(item.brick))&&Number(item.brick)>0);
 return {hidden:!item.symbol,pending,instanceSuffix:pending?'-pending-size':'',type:null};
}
function optionMultiplier(moneyness='OTM'){
 if(!['OTM','ATM'].includes(moneyness))throw Error('Select OTM or ATM option classification.');
 return moneyness==='ATM'?0.5:0.25;
}
function responseError(result,httpOk){
 const snapshot=typeof result?.running==='boolean'&&typeof result?.phase==='string';
 return !httpOk||result?.error&&!snapshot?result?.error||'AI strategy request failed':null;
}
function marketWaitLabel(snapshot){
 if(!snapshot?.running)return null;
 return ({WAITING_FOR_MARKET:'Waiting for market open · runner active',WAITING_FOR_MARKET_STATUS:'Waiting for broker market status · orders paused'})[snapshot.heartbeat?.market_state]||null;
}

function selectionFrameUrl(frame,baseUrl,makeNavigation=()=>root.crypto.randomUUID()){
 if(frame.dataset.selectionBase!==baseUrl||!frame.dataset.selectionNavigation||(typeof frame.getAttribute==='function'&&!frame.getAttribute('src'))){
  frame.dataset.selectionBase=baseUrl;frame.dataset.selectionNavigation=makeNavigation();
  frame.dataset.selectionSequence='0';
 }
 const url=new URL(baseUrl);url.searchParams.set('aiNavigation',frame.dataset.selectionNavigation);
 return url.href;
}
function selectionIntentMatches(src,data,account,previousSequence,documentId){
 const params=new URL(src).searchParams,navigation=params.get('aiNavigation');
 return !!documentId&&data.document===documentId&&!!navigation&&data.navigation===navigation&&data.account===account
  &&data.account===params.get('chartSource')&&data.instance===params.get('chartInstance')
  &&Number.isInteger(data.sequence)&&data.sequence>previousSequence;
}
function sizingContext(symbol,broker,category){
 if(!symbol)throw Error('Select an underlying instrument.');
 if(broker==='DELTA_INDIA'&&symbol.includes(':'))throw Error('Select an instrument supported by this broker.');
 let market=symbol.includes(':')?symbol.split(':')[0]:(broker==='DELTA_INDIA'?'CRYPTO':null);
 if(broker==='DHAN')market=({NSE_EQ:'NSE',BSE_EQ:'BSE',NSE_FNO:'NSE',BSE_FNO:'BSE',MCX_COMM:'MCX'})[market]||market;
 let parentHours,asset;
 if(market==='MCX'){parentHours=14;}
 else if(category==='GOLD'||category==='GLOBAL_COMMODITY'){parentHours=22;asset='GOLD';}
 else if(['NSE','BSE'].includes(market))parentHours=6;
 else if(market==='CRYPTO')parentHours=23;
 else if(market==='MCX')parentHours=14;
 else throw Error('The selected market needs an explicit parent duration.');
 return {market,asset,parentHours,atrLength:parentHours===22||parentHours===23?7:5,baselineMinutes:30,divisor:parentHours*2};
}
function verifiedReference(data,symbol,context,now=Date.now()/1000){
 return (data.native_references||[data.native_reference]).filter(Boolean).filter(r=>{
  if(r.native_provider==='TRADINGVIEW'&&!(r.valid_until>now))return false;
  if((r.broker_symbol||r.symbol)!==symbol||!String(r.status||'').startsWith('VERIFIED_')||r.parent_hours!==context.parentHours||r.atr_length!==context.atrLength||!(Number.isFinite(r.native_box)&&r.native_box>0))return false;
  if(['NSE','BSE'].includes(context.market))return r.chart_session==='Regular trading hours'&&!!data.expected_reference_session&&r.reference_session===data.expected_reference_session;
  return Number.isFinite(r.completed_parent_at)&&now>=r.completed_parent_at&&(r.native_provider==='TRADINGVIEW'?r.chart_session==='Regular trading hours'&&r.valid_until>now:now-r.completed_parent_at<=context.parentHours*3600);
 }).sort((a,b)=>(b.completed_parent_at||0)-(a.completed_parent_at||0)||String(b.observed_at||'').localeCompare(String(a.observed_at||'')))[0]||null;
}
function chartView(draft,heartbeat,running,broker){
 const owned=heartbeat?.position||heartbeat?.pending?.intent?.position||(running?heartbeat?.selected_contract:null);
 const frozen=owned&&owned.underlying===draft.underlying?owned:null;
 const underlying=draft.underlying;
 const context=sizingContext(underlying,broker,frozen?frozen.asset==='GOLD'?'GOLD':undefined:draft.category);
 const base=frozen?.spot_brick??Number(draft.reference)/context.divisor;
 return {underlying,context,base,frozen:!!frozen,owned:owned&&owned.underlying!==underlying?owned:null,timeframe:frozen&&heartbeat?.timeframe?({1:'1 minute',5:'5 minutes',30:'30 minutes'}[heartbeat.timeframe]):draft.timeframe,route:frozen?.execution_route==='DIRECT'?'DIRECT':frozen?.option_type?'OPTIONS':draft.route};
}
function chartContracts(preview,heartbeat,underlying){
 const contracts={...(preview?.underlying===underlying?preview.contracts:{})};
 for(const c of [heartbeat?.selected_contract,heartbeat?.pending?.intent?.position,heartbeat?.position])if(c?.option_type&&c.underlying===underlying)contracts[c.option_type]=c;
 return contracts;
}
function configuration(fields,account,preview=false){
 if(!['FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'].includes(account?.broker))throw Error('Select a supported broker account.');
 if(account.broker==='MOTILAL_OSWAL'&&((fields.route||'OPTIONS')==='OPTIONS'?fields.product!=='NORMAL':!['INTRADAY','MARGIN'].includes(fields.product)))throw Error('Choose a supported Motilal product.');
 if(account.broker==='DHAN'&&((fields.route||'OPTIONS')==='OPTIONS'?fields.product!=='MARGIN':!['INTRADAY','MARGIN'].includes(fields.product||'INTRADAY')))throw Error('Choose the supported Dhan product.');
 const context=sizingContext(fields.underlying,account.broker,fields.category);
 if(['FYERS','DHAN','MOTILAL_OSWAL'].includes(account.broker)&&fields.route==='DIRECT'&&!fields.product)fields={...fields,product:'INTRADAY'};
 const moneyness=fields.moneyness||'OTM';optionMultiplier(moneyness);
 fields=manualSizingValues(fields);
 const sizingMode=fields.sizingMode||'AUTO';
 if(!['AUTO','MANUAL_PARENT'].includes(sizingMode))throw Error('Choose Auto or Manual parent sizing.');
 if(sizingMode==='MANUAL_PARENT'&&!(Number.isFinite(Number(fields.manualParent))&&Number(fields.manualParent)>0))throw Error('Enter a positive parent brick size.');
 const reference=Number(fields.reference),value=Number.isFinite(reference)&&reference>0&&fields.session&&fields.evidence?reference:null;
 const bands={};
 for(const kind of ['sma','ema']){
  const period=Number(fields[kind+'Period']??30);
  if(!Number.isInteger(period)||period<1||period>500)throw Error('Band period must be a whole number from 1 to 500.');
  bands['ai_'+kind+'_band_period']=period;
  bands['ai_'+kind+'_band_entry']=fields[kind+'Entry']===true;
  bands['ai_'+kind+'_band_exit']=fields[kind+'Exit']===true;
 }
 const factor=Number(fields.factor??3);
 if(fields.supertrend!==false&&(!Number.isFinite(factor)||factor<0.1))throw Error('Enter a Supertrend multiplier of at least 0.10.');
 const lots=Number(fields.lots);if(!preview&&(!Number.isInteger(lots)||lots<1))throw Error('Enter whole lots or contracts.');
 if(!preview&&account.broker==='FYERS'&&!(fields.route==='DIRECT'?['MARGIN','INTRADAY','CNC']:['MARGIN','INTRADAY']).includes(fields.product))throw Error('Choose a product.');
 if(!['1 minute','5 minutes','30 minutes'].includes(fields.timeframe))throw Error('Choose 1, 5 or 30 minutes.');
 if(moneyness==='OTM'&&!(Number(fields.premium||40)>0))throw Error('Enter a positive premium target.');
 return {...(account.broker==='MOTILAL_OSWAL'?{ai_market_data_broker:'FYERS',ai_market_data_account:fields.dataAccount}:{}),...bands,ai_sma_retest_required:fields.smaRetest===true,ai_sizing_mode:sizingMode,ai_manual_parent_value:sizingMode==='MANUAL_PARENT'?Number(fields.manualParent):null,...(sizingMode==='MANUAL_PARENT'&&fields.manualParentAt?{ai_manual_parent_entered_at:fields.manualParentAt}:{}),ai_supertrend_enabled:fields.supertrend!==false,ai_indicator_inputs:{length:5,factor,adx_enabled:false},strategy_mode:MODE,broker:account.broker,account_id:account.id,underlying:fields.underlying,timeframe:fields.timeframe,
 mode:fields.execution,ai_calculation_mode:fields.decisionMode||'HYBRID',ai_display_mode:fields.calculationMode||'CANDLES',ai_signal_source:(fields.underlyingSignals??fields.underlyingEntry)===false?'PREMIUM':'UNDERLYING',ai_entry_source:(fields.underlyingSignals??fields.underlyingEntry)===false?'PREMIUM':'UNDERLYING',ai_option_moneyness:moneyness,lots:preview?null:lots,preview_options:preview,target_premium:Number(fields.premium||40),ai_product:fields.product,
 ai_execution_route:fields.route||'OPTIONS',ai_market:context.market,ai_asset:context.asset,ai_parent_hours:context.parentHours,ai_atr_length:context.atrLength,ai_baseline_minutes:30,
 ai_expiry_policy:fields.expiry?'explicit_listed':'nearest_tradable',...(fields.expiry?{ai_expiry:String(fields.expiry)}:{}),ai_reference_value:value,ai_reference_session:fields.session,ai_reference_symbol:fields.underlying,
 ai_reference_evidence:fields.evidence,ai_sma_exit_enabled:fields.sma===true,ai_accept_chart_basis:true};
}
function manualEntryPayload(snapshot,fields,account,direction,requestId){
 const c=snapshot?.manual_entry_context,h=snapshot?.heartbeat;
 if(!snapshot?.running||!snapshot.manual_entry_ready||!c||h?.position||h?.pending)throw Error('Manual entry requires a ready, flat active runner.');
 if(c.account_id!==account?.id||c.broker!==account?.broker||c.underlying!==fields.underlying||c.mode!==fields.execution||c.route!==fields.route||c.timeframe!==Number.parseInt(fields.timeframe,10))throw Error('The form differs from the active runner. Restore its instrument, timeframe and execution mode.');
 if(!/^[a-f0-9]{32}$/.test(requestId))throw Error('A unique manual request is required.');
 if(!(c.route==='DIRECT'?['LONG','SHORT']:['CE','PE']).includes(direction))throw Error('Choose a manual entry direction.');
 return {...c,direction,request_id:requestId};
}
class SelectionSync{
 constructor(){this.version=0;}
 async change(next,commit,apply){
  const version=++this.version;
  const result=await commit(next);
  if(version!==this.version||result===false)return false;
  apply(next,result);return true;
 }
 cancel(){this.version++;}
}
function mount(){
 const section=document.getElementById('renko-supertrend'),mode=document.getElementById('renko-strategy-mode');
 if(!section||!mode||section.dataset.aiOptionsMounted)return;
 section.dataset.aiOptionsMounted='1';
 const aiOption=new Option('AI Renko Supertrend',MODE);
 aiOption.disabled=section.dataset.aiContextReady!=='1';mode.add(aiOption);
 root.addEventListener('renko-ai-context-ready',()=>{aiOption.disabled=section.dataset.aiContextReady!=='1';});

 const toolbar=document.createElement('div');toolbar.className='renko-ai-toolbar field-grid';
 const modeLabel=mode.closest('label');modeLabel.querySelector('small').textContent='';
 toolbar.append(modeLabel);section.querySelector('.head').after(toolbar);
 const broker=document.getElementById('renko-broker');if(broker)toolbar.append(broker.closest('label'));
 const panel=document.createElement('section');panel.className='panel renko-ai-panel';panel.hidden=true;
 panel.innerHTML=`<div class="step-title"><div><span class="label">AI RENKO SUPERTREND</span><h2>Selected instrument · AI Renko signals</h2></div><span class="badge">SELECTED INSTRUMENT</span></div>
 <a class="button secondary" href="/user-guide.html#ai-renko-position-controls" target="_blank" rel="noopener">Strategy help</a><span class="renko-ai-rules" hidden></span>
 <div class="field-grid">

<label class="field">Trade instrument<select data-ai="route"><option value="OPTIONS">Bought options · Call / Put</option><option value="DIRECT">Direct stock / future / perpetual</option></select></label><label class="field">Sizing category<select data-ai="category"><option value="">Selected market</option><option value="GOLD">Global Gold / Silver · 22H ATR7</option></select></label><label class="field">Execution<select data-ai="execution"><option value="PAPER">Paper</option><option value="LIVE">Live · real orders</option></select></label>
 <label class="field"><span>Signal rules</span><span><input data-ai="supertrend" type="checkbox" checked> Enable Supertrend</span><small>Off: SMA band alone controls entry and exit.</small></label>
 <div class="field" data-ai-source-field hidden><span>Chart and signal data</span><strong>FYERS</strong><input type="hidden" data-ai="dataBroker" value="FYERS"><small>Motilal remains the execution broker selected above.</small></div>
 <label class="field" data-ai-source-field hidden>FYERS data account<select data-ai="dataAccount"><option value="">Choose your FYERS account</option></select></label>
 <label class="field">Supertrend multiplier<input data-ai="factor" aria-label="Supertrend multiplier" type="number" min="0.1" step="0.01" value="3"><small>Applies to underlying, Call and Put.</small></label>
 <label class="field">Source timeframe<select data-ai="timeframe"><option>1 minute</option><option>5 minutes</option><option>30 minutes</option></select></label>
 <label class="field renko-ai-wide" data-ai-entry-source><span>Option entry and exit source</span><span class="renko-ai-toggle"><input type="checkbox" data-ai="underlyingSignals" aria-label="Use underlying chart for option entry and exit" checked>Use underlying chart</span><small data-ai-entry-running></small></label>
 <label class="field">Option selection<select data-ai="moneyness"><option value="OTM">OTM · premium target</option><option value="ATM">ATM · nearest strike</option></select><small hidden></small></label>
 <label class="field">Target premium · quote currency<input data-ai="premium" type="number" min="0.01" step="0.01" value="40"></label>
 <label class="field">Lots<input data-ai="lots" type="number" min="1" step="1" placeholder="Choose quantity"></label>
 <label class="field">Product<select data-ai="product"><option value="">Choose product</option><option value="MARGIN">MARGIN · carry forward</option><option value="INTRADAY">INTRADAY · broker square-off applies</option><option value="CNC">CNC · cash shares</option></select></label>
 <label class="field">Option expiry<select data-ai="expiry"><option value="">Automatic · nearest valid expiry</option></select><small data-ai-expiry hidden></small></label>
 <label class="field">Brick sizing<select data-ai="sizingMode"><option value="AUTO">Auto · native session size</option><option value="MANUAL_PARENT">Manual parent · incident override</option></select><small>Auto is the default. Manual uses your parent value for this session.</small></label>
 <label class="field" data-manual-parent-field hidden>Parent brick size<input data-ai="manualParent" aria-label="Parent brick size" type="number" min="0" step="any" placeholder="Enter parent timeframe brick size"><small data-manual-parent-help></small></label>
 <details class="renko-ai-reference-details renko-ai-wide"><summary>Automatic sizing details</summary><input data-ai="session" type="hidden"><input data-ai="reference" type="hidden"><input data-ai="evidence" type="hidden"><dl class="renko-ai-reference-grid"><div><dt>Completed reference session</dt><dd data-reference-display="session">Calculating…</dd></div><div><dt>Native parent brick</dt><dd data-reference-display="reference">Calculating…</dd></div><div><dt>Verified source</dt><dd data-reference-display="evidence">Calculating…</dd></div></dl></details>
 <div class="field renko-ai-wide"><strong>High / Low bands</strong></div>
 <div class="renko-ai-band-grid renko-ai-wide"><fieldset class="renko-ai-band-card sma-band"><legend>SMA · Simple moving average</legend><div class="renko-ai-band-row"><label class="field">Period<input data-ai="smaPeriod" aria-label="SMA band period" type="number" min="1" max="500" step="1" value="30"></label><label class="field">Entry filter<span class="renko-ai-toggle"><input data-ai="smaEntry" aria-label="SMA band entry filter" type="checkbox">Enabled</span></label><label class="field">Exit<span class="renko-ai-toggle"><input data-ai="smaExit" aria-label="SMA band exit" type="checkbox">Enabled</span></label></div></fieldset><fieldset class="renko-ai-band-card ema-band"><legend>EMA · Exponential moving average</legend><div class="renko-ai-band-row"><label class="field">Period<input data-ai="emaPeriod" aria-label="EMA band period" type="number" min="1" max="500" step="1" value="30"></label><label class="field">Entry filter<span class="renko-ai-toggle"><input data-ai="emaEntry" aria-label="EMA band entry filter" type="checkbox">Enabled</span></label><label class="field">Exit<span class="renko-ai-toggle"><input data-ai="emaExit" aria-label="EMA band exit" type="checkbox">Enabled</span></label></div></fieldset></div>
 <label class="field renko-ai-wide">SMA entry confirmation<span class="renko-ai-toggle"><input data-ai="smaRetest" aria-label="Require SMA band retest" type="checkbox">Require band retest and next completed confirmation candle</span><small>Optional · off by default. Off: use the band-side entry condition with the selected strategy rules.</small></label>
 <div class="field renko-ai-wide"><small data-ai-band-status></small></div>

 </div><p class="renko-ai-capability muted"></p><p class="renko-ai-sizing" role="status"></p>
 <fieldset class="renko-ai-attachment"><legend>Broker position</legend><p>Stop closes the managed holding. Detach leaves it open.</p><div class="field-grid"><label class="field">Open broker position<select data-ai-attachment><option value="">No external position selected</option></select></label><button type="button" class="button secondary" data-ai-action="positions">Refresh open positions · read only</button></div><p data-ai-attachment-status role="status">No position selected for attachment.</p></fieldset>
 <div class="renko-ai-preview" role="status"></div><p data-position-control-status role="status" aria-live="polite"></p><div class="packet-actions"><button class="button secondary" data-ai-action="preview">Preview contracts · read only</button><details class="renko-ai-export"><summary>Advanced</summary><button class="button secondary" data-ai-action="prepare">Export settings</button></details><button class="button" data-ai-action="start">Start AI runtime</button><button class="button secondary" data-ai-action="stop" disabled>Stop · square off</button><button class="button secondary" data-ai-action="position-toggle" disabled>Attach</button></div>
 <div class="renko-ai-manual"><h3>Manual entry · strategy-managed exit</h3><small data-ai-entry-order-type hidden></small><p hidden></p><div class="packet-actions"><label class="field">Direction<select data-manual-direction><option value="">Choose direction</option></select></label><button class="button secondary" data-ai-action="manual-entry" disabled>Request manual entry</button></div><p data-manual-status role="status"></p></div>
 <p class="renko-ai-status" role="status">Standalone runtime · stopped. Exporting settings does not start monitoring.</p>`;

 const journal=document.createElement('section');journal.className='panel renko-ai-journal';
 journal.innerHTML='<h3>Trade journal</h3><label>Execution <select data-journal-mode><option value="ALL">All</option><option value="PAPER">Paper</option><option value="LIVE">Live</option></select></label><p data-journal-note></p><div style="overflow:auto;max-height:420px"><table><thead><tr><th>Mode</th><th>Contract / strike</th><th>Entry time</th><th>Exit time</th><th>Quantity × multiplier</th><th>Entry premium</th><th>Exit premium</th><th>Gross P&amp;L</th><th>Costs</th><th>Net profit</th><th>Status</th></tr></thead><tbody></tbody></table></div>';
 // Journal is placed after every strategy chart, below the trading controls.
 const journalNumber=v=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2}):'Unavailable';
 const journalTime=v=>typeof v==='number'?new Date(v*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':'Unavailable';
 function renderJournal(){
  const data=snapshot?.trade_journal||{},filter=journal.querySelector('select').value,rows=(data.rows||[]).filter(r=>filter==='ALL'||r.mode===filter),body=journal.querySelector('tbody');
  body.replaceChildren();
  for(const r of rows){const tr=document.createElement('tr');for(const value of [r.mode,r.symbol,journalTime(r.entry_time),r.status==='OPEN'?'—':journalTime(r.exit_time),journalNumber(r.quantity)+' × '+journalNumber(r.multiplier),journalNumber(r.entry_premium),r.status==='OPEN'?'—':journalNumber(r.exit_premium),journalNumber(r.gross_profit),journalNumber(r.costs),journalNumber(r.net_profit),r.status==='OPEN'?'Exit not recorded':r.status]){const td=document.createElement('td');td.textContent=value;td.style.cssText='padding:8px;white-space:nowrap;border-bottom:1px solid #334154';tr.append(td);}tr.title=r.entry_time_basis+'; '+r.multiplier_source;body.append(tr);}
  journal.querySelector('[data-journal-note]').textContent=(data.sync?.state==='ERROR'?'Journal error: '+data.sync.error:((data.total||0)+' recorded trades · '+rows.length+' shown · '+(data.sync?.state==='RUNNING'?'Updating journal':data.sync?.state==='READY'?'Journal current':data.sync?.state||'Loading')))+' · Times IST. Unavailable costs mean net profit is unavailable; gross excludes costs. Historical holdings are recorded evidence, not confirmation of current broker exposure.';
 }
 journal.querySelector('select').addEventListener('change',renderJournal);
 toolbar.after(panel);
 const charts=document.createElement('section');charts.className='panel renko-ai-charts';charts.hidden=true;
 charts.innerHTML='<h2>Strategy charts</h2><p hidden></p><div class="renko-ai-chart-tabs" role="tablist" aria-label="Strategy chart selection"></div><div class="renko-ai-chart-grid"></div>';panel.after(charts);charts.after(journal);
 const style=document.createElement('style');style.textContent='#renko-supertrend.renko-ai-active>:not(.head):not(.renko-ai-toolbar):not(.renko-ai-panel):not(.renko-ai-charts):not(.renko-ai-journal){display:none!important}.renko-ai-toolbar{margin:14px 0}.renko-ai-active>.head small:not(.renko-ai-summary),.renko-ai-active>.head #renko-state{display:none!important}#renko-supertrend .renko-ai-panel .field-grid{grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:16px}.renko-ai-toolbar>label{max-width:440px}.renko-ai-wide{grid-column:1/-1}.renko-ai-panel input[type=checkbox]{width:18px!important;min-width:18px!important;vertical-align:middle}.renko-ai-sizing{padding:12px 16px;border-left:3px solid #75b6de;background:#15334a;color:#d7e7f3}.renko-ai-chart-grid{display:grid;gap:18px;grid-template-columns:minmax(0,1fr)}.renko-ai-chart-grid iframe{width:100%;height:clamp(520px,72vh,900px);border:1px solid #334154;border-radius:8px}.renko-ai-chart-grid h3{margin:8px 0}.renko-ai-chart-grid .contract-details{min-height:48px;color:#a8bfd0;font-size:12px;line-height:1.6}.renko-ai-panel .packet-actions{display:flex;flex-wrap:wrap;gap:10px}@media(max-width:600px){.renko-ai-panel .packet-actions>button{flex:1 1 100%}.renko-ai-chart-grid iframe{height:650px}}';style.textContent+='\n#renko-supertrend.renko-ai-active>.renko-ai-toolbar{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px 20px;align-items:start}\n#renko-supertrend.renko-ai-active>.renko-ai-toolbar>label{max-width:none;min-width:0;grid-column:span 4;position:relative;display:grid!important;grid-template-columns:minmax(0,1fr)!important;grid-template-rows:20px 42px minmax(16px,auto);gap:6px!important;align-content:start;align-items:start;padding:0!important;border:0!important}\n#renko-supertrend.renko-ai-active>.renko-ai-toolbar>label:nth-child(-n+2){grid-column:span 6}\n#renko-supertrend.renko-ai-active>.renko-ai-toolbar>label>.renko-setting-name{grid-row:1;grid-column:1;padding-right:30px}\n#renko-supertrend.renko-ai-active>.renko-ai-toolbar>label>select,#renko-supertrend.renko-ai-active>.renko-ai-toolbar>label>input{grid-row:2;grid-column:1;height:42px!important;min-height:42px;min-width:0;width:100%;max-width:100%;margin:0;box-sizing:border-box}\n#renko-supertrend.renko-ai-active>.renko-ai-toolbar>label>small{grid-row:3}\n#renko-supertrend.renko-ai-active>.renko-ai-toolbar>label>.renko-parameter-help{position:absolute;right:0;top:-2px;margin:0!important}\n#renko-supertrend .renko-ai-panel>.field-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:20px;align-items:start}\n#renko-supertrend .renko-ai-panel .field{min-width:0;align-content:start}\n#renko-supertrend .renko-ai-panel label.field{display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:20px 42px auto;gap:6px;justify-content:start;align-items:start}\n#renko-supertrend .renko-ai-panel label.field>input:not([type=checkbox]),#renko-supertrend .renko-ai-panel label.field>select{grid-row:2;min-width:0;width:100%;max-width:100%;height:42px;min-height:42px;margin:0;box-sizing:border-box}\n#renko-supertrend .renko-ai-panel label.field>small{grid-row:3;line-height:1.45;margin:0}\n#renko-supertrend .renko-ai-band-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}\n#renko-supertrend .renko-ai-band-card{min-width:0;margin:0;padding:16px;border:1px solid #334154;border-left:3px solid #38bdf8;border-radius:8px;background:#101e30}\n#renko-supertrend .renko-ai-band-card.ema-band{border-left-color:#a78bfa}\n#renko-supertrend .renko-ai-band-card>legend{padding:0 8px;font-size:13px;font-weight:600;color:#d7e7f3}\n#renko-supertrend .renko-ai-band-row{display:grid;grid-template-columns:minmax(90px,.7fr) repeat(2,minmax(0,1fr));gap:16px;align-items:start}\n#renko-supertrend .renko-ai-toggle{grid-row:2;display:flex;align-items:center;gap:10px;min-height:42px;padding:8px 12px;border:1px solid #334154;border-radius:6px;background:#0b1728;box-sizing:border-box;color:#c9dbea}\n#renko-supertrend .renko-ai-toggle input[type=checkbox]{height:18px!important;width:18px!important;min-width:18px!important;margin:0!important;flex:none;accent-color:#75b6de}\n#renko-supertrend .renko-ai-band-card>small{display:block;margin-top:8px;line-height:1.4;color:#a8bfd0}\n#renko-supertrend .renko-ai-reference-details{padding:12px 16px;border:1px solid #334154;border-radius:8px}\n#renko-supertrend .renko-ai-reference-details>summary{cursor:pointer;font-size:12px;font-weight:600;color:#a8bfd0}\n#renko-supertrend .renko-ai-reference-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 20px;margin:16px 0 0}\n#renko-supertrend .renko-ai-reference-grid>div:last-child{grid-column:1/-1}\n#renko-supertrend .renko-ai-reference-grid dt{font-size:11px;color:#a8bfd0;margin-bottom:5px}\n#renko-supertrend .renko-ai-reference-grid dd{margin:0;color:#d7e7f3;font-size:12px;overflow-wrap:anywhere}\n@media(max-width:1100px){#renko-supertrend .renko-ai-panel>.field-grid{grid-template-columns:repeat(2,minmax(0,1fr))}#renko-supertrend .renko-ai-band-grid{grid-template-columns:1fr}}\n@media(max-width:650px){#renko-supertrend.renko-ai-active>.renko-ai-toolbar{grid-template-columns:1fr;gap:12px}#renko-supertrend.renko-ai-active>.renko-ai-toolbar>label,#renko-supertrend.renko-ai-active>.renko-ai-toolbar>label:nth-child(-n+2){grid-column:1}#renko-supertrend .renko-ai-panel>.field-grid,#renko-supertrend .renko-ai-band-row,#renko-supertrend .renko-ai-reference-grid{grid-template-columns:1fr}}\n';style.textContent+='.renko-ai-export{align-self:center;position:relative;font-size:12px;color:#a8bfd0}.renko-ai-export summary{cursor:pointer;padding:10px}.renko-ai-export[open] .button{margin-top:8px}';style.textContent+='.renko-ai-attachment{margin:16px 0;padding:16px;border:1px solid #334154;border-radius:10px;min-width:0}.renko-ai-attachment legend{padding:0 6px;font-weight:600}.renko-ai-attachment p{font-size:12px;line-height:1.6}.renko-ai-attachment .field-grid{align-items:end}.renko-ai-attachment [data-ai-action=positions],.renko-ai-attachment select{height:42px;min-height:42px;box-sizing:border-box}.renko-ai-attachment [data-ai-action=positions]{align-self:end}';style.textContent+='#renko-supertrend .renko-ai-panel [data-ai-entry-source]{grid-template-rows:20px 42px auto auto}#renko-supertrend .renko-ai-panel [data-ai-entry-source]>*{grid-column:1;min-width:0}#renko-supertrend .renko-ai-panel [data-ai-entry-source]>[data-ai-entry-running]{grid-row:4}';document.head.append(style);
 const displayInput=document.createElement('input');displayInput.type='hidden';displayInput.dataset.ai='calculationMode';displayInput.value='RENKO';panel.append(displayInput);
 const chartViewInput=document.createElement('input');chartViewInput.type='hidden';chartViewInput.dataset.ai='chartView';chartViewInput.value='Renko';panel.append(chartViewInput);
 const inputs=[...panel.querySelectorAll('[data-ai]')],status=panel.querySelector('.renko-ai-status'),sizing=panel.querySelector('.renko-ai-sizing');
 let attachmentChoice=null,attachmentRows=[],restoredDraftAccount=null;
 const selected=()=>root.BrokerForms?.account('renko'),settingsUser=()=>root.BrokerForms?.context()?.username,
 storage=()=>instrumentSettingsKey(settingsUser(),selected())||'sector-pulse:ai-renko-settings:unavailable';
 const legacyStorage=()=> 'sector-pulse:ai-renko-options:'+(selected()?.id||'unselected');
 let manualParentAt=null;
 function saveDraft(){if(!settingsUser())return;const v=values();localStorage.setItem(storage(),JSON.stringify(v));writeInstrumentSettings(localStorage,settingsUser(),selected(),v);}
 const instrumentDefaults=Object.fromEntries(inputs.map(n=>[n.dataset.ai,n.type==='checkbox'?n.checked:n.value]));
 const strategyVisit=createStrategyVisit();let applyingViewDefault=false;
 const strategySectionVisible=()=>section.classList.contains('active')&&!section.hidden;
 function restoreAiView(){
  if(!strategySectionVisible()||section.dataset.aiContextReady!=='1'||!selected()?.id)return;
  const intended=strategyVisit.selected();
  try{
   if(mode.value!==intended){
    applyingViewDefault=true;
    try{mode.value=intended;mode.dispatchEvent(new Event('change',{bubbles:true}));}
    finally{applyingViewDefault=false;}
   }else if(mode.value===MODE&&restoredDraftAccount!==selected().id){restore();show();refreshStatus();}
  }catch{}
 }
 function strategySectionEntry(){
  if(!strategySectionVisible()){strategyVisit.leave();return;}
  strategyVisit.enter();restoreAiView();
 }
 const strategyEntryObserver=new MutationObserver(strategySectionEntry);
 strategyEntryObserver.observe(section,{attributes:true,attributeFilter:['class','hidden']});
 root.addEventListener('renko-ai-context-ready',restoreAiView);

 style.textContent+='.renko-ai-chart-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 16px;padding-bottom:12px;border-bottom:1px solid #334154}.renko-ai-chart-tabs[hidden]{display:none}.renko-ai-chart-tabs [role=tab]{min-height:42px;padding:9px 18px;border:1px solid #40536a;border-radius:7px;background:#142337;color:#bfd1e1;font-weight:600;cursor:pointer}.renko-ai-chart-tabs [role=tab][aria-selected=true]{background:#24567b;border-color:#78b7e4;color:#fff}.renko-ai-chart-tabs [role=tab]:focus-visible{outline:2px solid #9bd3ff;outline-offset:3px}.renko-ai-chart-grid>article{min-width:0;width:100%}.renko-ai-chart-grid>article[hidden]{display:none!important}';
 let activeChartTab='underlying',activeChartTabScope='',factorDraftValue=null,supertrendDraftValue=null,retestDraftValue=null;
 const values=()=>manualSizingValues({...Object.fromEntries(inputs.map(n=>[n.dataset.ai,n.type==='checkbox'?n.checked:n.value])),manualParentAt,underlying:document.getElementById('renko-symbol')?.value,instrument_market:document.getElementById('renko-market')?.value,decisionMode:snapshot?.running?snapshot.calculation_mode:(snapshot?.hybrid_completed_units_ready?'HYBRID':'CANDLES')});
 const selectionSync=new SelectionSync();
 let acceptedSelection=null;
 let expiryKey='',expiryReadAt=0,expiryInFlight=false,expiryDraft='',expiryRows=[];
 let current=null,snapshot=null,legacyFields=null,legacyOptions=null,referenceLoaded=false,referenceSymbol=null,optionPreview=null,lastDisplayReference=null;
 const instrumentControls=['market','search','symbol'].map(id=>document.getElementById('renko-'+id)?.closest('label')).filter(Boolean).map(node=>{const anchor=document.createComment('AI instrument control position');node.before(anchor);return {node,parent:node.parentNode,anchor};});
 const aiSummary=document.createElement("small");aiSummary.className="renko-ai-summary muted";aiSummary.textContent="";section.querySelector(".head h1").parentElement.append(aiSummary);aiSummary.hidden=true;
 function directMarketChoices(){const account=selected();if(!['DHAN','MOTILAL_OSWAL'].includes(account?.broker))return;const direct=mode.value===MODE&&values().route==='DIRECT';for(const o of document.getElementById('renko-market').options)if(['NSE_EQUITY','BSE_EQUITY'].includes(o.value))o.disabled=!direct;}
 function show(){
  const ai=mode.value===MODE,account=selected();for(const c of instrumentControls){if(ai&&c.node.parentNode!==toolbar)toolbar.append(c.node);else if(!ai&&c.node.parentNode===toolbar)c.parent.insertBefore(c.node,c.anchor.nextSibling);}section.classList.toggle('renko-ai-active',ai);panel.hidden=charts.hidden=journal.hidden=!ai;aiSummary.hidden=!ai;
  const option=[...mode.options].find(o=>o.value===MODE);option.disabled=!['FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'].includes(account?.broker);
  directMarketChoices();if(!ai){if(suggestionBox)suggestionBox.hidden=true;return;}
  if(referenceSymbol!==values().underlying){panel.dataset.lastReferenceClear=String(referenceSymbol)+' -> '+values().underlying;for(const key of ['reference','evidence','session'])panel.querySelector('[data-ai='+key+']').value='';referenceSymbol=null;referenceLoaded=false;}
  renderJournal();
  for(const field of panel.querySelectorAll('[data-ai-source-field]'))field.hidden=account?.broker!=='MOTILAL_OSWAL';
  const sourcePick=panel.querySelector('[data-ai=dataAccount]'),sourcePrior=sourcePick.value;
  const sourceAccounts=(root.BrokerForms?.accounts?.()||[]).filter(a=>a.broker==='FYERS');
  if(sourcePick.dataset.accounts!==sourceAccounts.map(a=>a.id).join(',')){
   sourcePick.replaceChildren(new Option('Choose your FYERS account',''),...sourceAccounts.map(a=>new Option(a.label||'FYERS',a.id)));
   sourcePick.dataset.accounts=sourceAccounts.map(a=>a.id).join(',');sourcePick.value=sourcePrior;
   if(!sourcePick.value&&sourceAccounts.length===1)sourcePick.value=sourceAccounts[0].id;
  }
  if(account?.broker==='MOTILAL_OSWAL'&&!snapshot?.running&&snapshot?.phase!=='PREFLIGHT')sourcePick.value=restoredDataAccount(sourcePick.value,sourceAccounts);
  for(const key of ['dataBroker','dataAccount'])panel.querySelector('[data-ai='+key+']').disabled=!!snapshot?.running||snapshot?.phase==='PREFLIGHT';
  const v=values();
  const directRouteOption=[...panel.querySelector('[data-ai=route]').options].find(o=>o.value==='DIRECT');directRouteOption.disabled=false;directRouteOption.title=account?.broker==='MOTILAL_OSWAL'?'Protected limit · 1 tick beyond fresh bid/ask · IOC; fill not guaranteed.':'';
  if(['FYERS','DHAN','MOTILAL_OSWAL'].includes(account?.broker)&&v.route==='DIRECT'&&!v.product&&!snapshot?.running){panel.querySelector('[data-ai=product]').value='INTRADAY';v.product='INTRADAY';}
  const manualMode=v.sizingMode==='MANUAL_PARENT';
  panel.querySelector('[data-manual-parent-field]').hidden=!manualMode;
  for(const key of ['sizingMode','manualParent'])panel.querySelector('[data-ai='+key+']').disabled=!!snapshot?.running||snapshot?.phase==='PREFLIGHT';
  let parentPolicy;try{parentPolicy=sizingContext(v.underlying,account?.broker,v.category);}catch{}
  panel.querySelector('[data-manual-parent-help]').textContent=parentPolicy?parentPolicy.parentHours+'H ATR'+parentPolicy.atrLength+' parent value ÷ '+parentPolicy.divisor+'; option factor follows ATM / OTM. Not independently verified.':'Select an instrument first.';
  const supertrendInput=panel.querySelector('[data-ai=supertrend]');
  if(snapshot?.running){
   if(supertrendDraftValue===null)supertrendDraftValue=supertrendInput.checked;
   supertrendInput.checked=snapshot.supertrend_enabled!==false;v.supertrend=supertrendInput.checked;
  }else if(supertrendDraftValue!==null){supertrendInput.checked=supertrendDraftValue;v.supertrend=supertrendDraftValue;supertrendDraftValue=null;}
  supertrendInput.disabled=!!snapshot?.running||snapshot?.phase==='PREFLIGHT';
  const factorInput=panel.querySelector('[data-ai=factor]');
  if(snapshot?.running){
   if(factorDraftValue===null)factorDraftValue=factorInput.value;
   factorInput.value=String(snapshot.indicator_factor||3);v.factor=factorInput.value;
  }else if(factorDraftValue!==null){factorInput.value=factorDraftValue;v.factor=factorDraftValue;factorDraftValue=null;}
  factorInput.disabled=!!snapshot?.running||snapshot?.phase==='PREFLIGHT';
  factorInput.title=factorInput.disabled?'Multiplier is captured by the active run. Stop before editing.':'Updates all three strategy charts.';
  if(['DHAN','MOTILAL_OSWAL'].includes(account?.broker)){
   const direct=v.route==='DIRECT';
   const product=direct?(['INTRADAY','MARGIN'].includes(v.product)?v.product:'INTRADAY'):account.broker==='DHAN'?'MARGIN':'NORMAL',pick=panel.querySelector('[data-ai=product]');
   if(![...pick.options].some(o=>o.value===product))pick.add(new Option('Normal · carry forward',product));
   for(const o of pick.options)o.hidden=direct?!['INTRADAY','MARGIN'].includes(o.value):o.value!==product;
   if(!snapshot?.running){pick.value=product;v.product=product;}
  }else for(const o of panel.querySelector('[data-ai=product]').options)o.hidden=o.value==='NORMAL';

  if(snapshot?.running&&snapshot.option_moneyness){panel.querySelector('[data-ai=moneyness]').value=snapshot.option_moneyness;v.moneyness=snapshot.option_moneyness;}
  for(const kind of ['sma','ema'])for(const use of ['Period','Entry','Exit'])panel.querySelector('[data-ai='+kind+use+']').disabled=!!snapshot?.running||snapshot?.phase==='PREFLIGHT';
  if(!v.supertrend){
   for(const kind of ['sma','ema'])for(const use of ['Entry','Exit']){
    const control=panel.querySelector('[data-ai='+kind+use+']');
    control.checked=kind==='sma';control.disabled=true;v[kind+use]=control.checked;
   }
  }
  const retest=panel.querySelector('[data-ai=smaRetest]');
  if(snapshot?.running){
   if(retestDraftValue===null)retestDraftValue=retest.checked;
   retest.checked=snapshot.sma_retest_required!==false;
  }else if(retestDraftValue!==null){retest.checked=retestDraftValue;retestDraftValue=null;}
  retest.disabled=!!snapshot?.running||snapshot?.phase==='PREFLIGHT'||!v.smaEntry;
  const entrySource=panel.querySelector('[data-ai=underlyingSignals]');
  entrySource.disabled=!!snapshot?.running||snapshot?.phase==='PREFLIGHT';
  panel.querySelector('[data-ai-entry-source]').hidden=v.route==='DIRECT';
  if(snapshot?.running&&snapshot.signal_source){entrySource.checked=snapshot.signal_source==='UNDERLYING';v.underlyingSignals=entrySource.checked;}
  panel.querySelector('[data-ai-entry-running]').textContent=snapshot?.running&&!snapshot.signal_source?'Active run retains its captured entry and exit rules. The shared source choice applies on the next Start.':!snapshot?.entry_exit_source_ready?'Entry/exit source update awaits the broker dashboard reload. Start remains unavailable until the backend is ready.':'';
  const bandState=snapshot?.running?snapshot?.heartbeat?.moving_bands:null;
  panel.querySelector('[data-ai-band-status]').textContent=bandState?.error?'Band unavailable · '+bandState.error:bandState?.bands?.length?bandState.bands.map(b=>b.kind+' '+b.period+' · '+(b.ready?'ready':'waiting for completed candles')).join(' · '):'';
  acceptedSelection={account:account?.id,underlying:v.underlying,timeframe:v.timeframe};const reference=manualMode||referenceLoaded?Number(v.reference):NaN;
  let context=null;try{context=sizingContext(v.underlying,account?.broker,v.category);}catch{}
  sizing.textContent=reference>0&&context?(manualMode?'Manual parent override · ':'')+'Underlying brick '+(reference/context.divisor).toLocaleString('en-IN',{maximumFractionDigits:2})+(v.route==='DIRECT'?'':' · Option brick '+(reference/context.divisor*optionMultiplier(v.moneyness||'OTM')).toLocaleString('en-IN',{maximumFractionDigits:2})):'Sizing unavailable';
  const supported=account?.broker==='FYERS'&&(v.route==='DIRECT'?['NSE','BSE','MCX']:['NSE','BSE','MCX']).includes(context?.market)||account?.broker==='DELTA_INDIA'&&context?.market==='CRYPTO'||['DHAN','MOTILAL_OSWAL'].includes(account?.broker)&&(v.route==='OPTIONS'||v.route==='DIRECT'&&snapshot?.[account.broker==='DHAN'?'dhan_direct_ready':'motilal_direct_ready']===true)&&['NSE','BSE','MCX'].includes(context?.market);
  panel.querySelector('.renko-ai-capability').textContent=supported?'':!v.underlying?'Select broker and instrument.':'Execution adapter unavailable for this selection.';
  panel.querySelector('[data-ai=product]').closest('label').hidden=account?.broker==='DELTA_INDIA';
  panel.querySelector('[data-ai=premium]').closest('label').hidden=v.route==='DIRECT'||v.moneyness==='ATM';
  panel.querySelector('[data-ai=moneyness]').closest('label').hidden=v.route==='DIRECT';
  panel.querySelector('[data-ai=moneyness]').disabled=!!snapshot?.running||snapshot?.phase==='PREFLIGHT';panel.querySelector('[data-ai-expiry]').closest('.field').hidden=v.route==='DIRECT';
  panel.querySelector('[data-ai=expiry]').disabled=!!snapshot?.running||snapshot?.phase==='PREFLIGHT';
  if(v.route!=='DIRECT')refreshExpiries();
  panel.querySelector('.renko-ai-rules').textContent='';
  panel.querySelector('.renko-ai-rules').textContent='';
  const attachmentPanel=panel.querySelector('.renko-ai-attachment');
  const orderNote=panel.querySelector('[data-ai-entry-order-type]');
  if(orderNote){
   orderNote.hidden=account?.broker!=='DELTA_INDIA'||snapshot?.next_entry_order_type!=='market_order';
   orderNote.textContent=snapshot?.running&&snapshot?.heartbeat?.entry_execution_policy!=='fresh-depth-market-entry-v1'?'Next Start: market orders for automatic and manual entries.':'Market orders for automatic and manual entries · execution price can vary.';
  if(account.broker==='MOTILAL_OSWAL'&&v.route==='DIRECT'){orderNote.hidden=false;orderNote.textContent='Protected limit IOC · 1 tick beyond fresh bid/ask · entry and exit may remain unfilled. Intraday uses Value Plus.';}
  if(account.broker==='DHAN'&&v.route==='DIRECT'){orderNote.hidden=false;orderNote.textContent='Market orders for direct entries and exits · Dhan applies market-price protection; fills are not guaranteed.';}
  }
  const controlView=positionControlView(snapshot);
  let positionContextReady=false,positionContextError='';
  try{positionControlPayload(snapshot,v,account,'STOP','0'.repeat(32));positionContextReady=true;}catch(error){positionContextError=error.message;}
  const canSelectHolding=!snapshot?.running||controlView.operation==='ATTACH';
  attachmentPanel.hidden=!['FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'].includes(account?.broker);
  panel.querySelector('[data-ai-attachment]').disabled=!canSelectHolding||v.execution!=='LIVE';
  panel.querySelector('[data-ai-action=positions]').disabled=!canSelectHolding||!v.underlying||v.execution!=='LIVE';
  const stop=panel.querySelector('[data-ai-action=stop]');
  stop.textContent=snapshot?.running?'Stop '+snapshot.mode+' · '+snapshot.underlying+' · square off':'Stopped';stop.disabled=controlView.stopBlocked||!controlView.capable||!positionContextReady;
  const toggle=panel.querySelector('[data-ai-action=position-toggle]');
  toggle.textContent=controlView.label;toggle.disabled=controlView.blocked||!controlView.capable||!positionContextReady||v.execution!=='LIVE'||(controlView.operation==='ATTACH'&&!attachmentChoice);
  const controlStatus=panel.querySelector('[data-position-control-status]');
  const disabledReasons=[];
  if(account?.broker==='MOTILAL_OSWAL'&&!snapshot?.motilal_fyers_data_ready)disabledReasons.push('Motilal FYERS-data update awaits a guarded backend reload. Trading remains unavailable.');
  if(snapshot?.release_ready!==true||snapshot?.execution_lifecycle_revision!=='option-legs-direct-reversal-v1')disabledReasons.push(snapshot?.release_notice||'AI execution update validation is in progress. Start remains unavailable.');
  if(!nativeBrokerReady(snapshot,account,v))disabledReasons.push(snapshot?.native_broker_readiness?.error||'Start unavailable: Preview contracts to verify the selected native account and source.');
  if(v.supertrend===false&&!snapshot?.sma_only_capable)disabledReasons.push('SMA-only runtime update is not loaded yet.');
  if(!snapshot?.hybrid_completed_units_ready)disabledReasons.push('Hybrid update awaits the broker dashboard reload. The active runner keeps its captured decision basis.');
  if(snapshot?.running)disabledReasons.push('Start unavailable: runner active.');
  if(controlView.capable&&!positionContextReady)disabledReasons.push(positionContextError);
  if(snapshot?.run_id&&!controlView.capable)disabledReasons.push('Stop / Detach unavailable: backend update pending.');
  if(controlStatus)controlStatus.textContent=controlView.status||disabledReasons.join(' ');
  stop.title=controlView.capable?(controlView.blocked?'Resolve the pending position request or broker order.':''):'Backend position-control update required.';
  toggle.title=stop.title;
  let complete=false;try{configuration(v,account);complete=true;}catch{}
  panel.querySelector('[data-ai-action=prepare]').disabled=!complete;
  panel.querySelector('[data-ai-action=start]').textContent='Start strategy · '+(v.execution==='LIVE'?'Live':'Paper');
  panel.querySelector('[data-ai-action=start]').disabled=snapshot?.release_ready!==true||snapshot?.execution_lifecycle_revision!=='option-legs-direct-reversal-v1'||(v.supertrend===false&&!snapshot?.sma_only_capable)||!nativeBrokerReady(snapshot,account,v)||!complete||!snapshot?.entry_exit_source_ready||!snapshot?.hybrid_completed_units_ready||!snapshot?.sma_retest_optional_ready||(manualMode?!snapshot?.manual_parent_override_ready:!snapshot?.native_acquisition_ready)||!!snapshot?.running||snapshot?.phase==='PREFLIGHT'||!!snapshot?.ownership?.detached_position||!!snapshot?.ownership?.pending||!supported;
  const manualDirection=panel.querySelector('[data-manual-direction]'),manualRoute=snapshot?.manual_entry_context?.route;
  if(manualDirection.dataset.route!==manualRoute){manualDirection.dataset.route=manualRoute||'';manualDirection.replaceChildren(new Option('Choose direction',''));for(const side of manualRoute==='DIRECT'?['LONG','SHORT']:['CE','PE'])manualDirection.add(new Option(side,side));}
  let manualReady=false;try{manualEntryPayload(snapshot,v,account,manualRoute==='DIRECT'?'LONG':'CE','0'.repeat(32));manualReady=true;}catch{}
  panel.querySelector('[data-ai-action=manual-entry]').disabled=!manualReady;
  const receipt=snapshot?.manual_entry;panel.querySelector('[data-manual-status]').textContent=manualRequestLabel(snapshot);panel.querySelector('[data-manual-status]').title=receipt?.error||'';
  drawCharts(v);
 }
 async function refreshExpiries(){
  const account=selected(),v=values(),key=account?.id+'|'+v.underlying;
  if(!v.underlying||!['FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'].includes(account?.broker))return;
  if(expiryKey===key&&Date.now()-expiryReadAt<60000&&!expiryRows.some(r=>expiryDeadline(r)<=Date.now()))return;
  if(expiryInFlight)return;
  expiryInFlight=true;expiryReadAt=Date.now();
  const control=panel.querySelector('[data-ai=expiry]'),note=panel.querySelector('[data-ai-expiry]');
  if(expiryKey!==key){expiryRows=[];control.replaceChildren(new Option('Automatic · nearest valid expiry',''));note.textContent='Loading broker-listed expiries…';}
  try{
   const body=configuration({...v,expiry:''},account,true);body.preview_options=false;body.expiry_options=true;
   const result=(await request('prepare',body)).expiry_options;
   if(selected()?.id!==account.id||values().underlying!==v.underlying)return;
   if(result?.account_id!==account.id||result.broker!==account.broker||result.underlying!==v.underlying||!result.expiries?.length)throw Error('No verified expiry list for this underlying.');
   const oldRows=JSON.stringify(expiryRows);expiryKey=key;expiryRows=result.expiries.filter(r=>expiryDeadline(r)>Date.now());
   if(!expiryRows.length)throw Error('No unexpired listed options for this underlying.');
   if(oldRows===JSON.stringify(expiryRows)&&control.options.length===expiryRows.length+1)return;
   const desired=expiryDraft||control.value;
   control.replaceChildren(new Option('Automatic · '+expiryRows[0].date+' · nearest valid',''));
   for(const row of expiryRows)control.add(new Option(row.date,row.value));
   const expired=desired&&!expiryRows.some(r=>r.value===desired);
   control.value=expired?'':desired;expiryDraft=control.value;
   note.textContent=(expired?'Previous expiry is no longer valid. Using automatic nearest expiry. ':'')+'Broker-listed dates · automatic refresh. '+(snapshot?.running?'Stop the runner before changing expiry; held contracts stay pinned.':'Choose another listed date if required.');
   if(expired){optionPreview=null;panel.querySelector('.renko-ai-preview').replaceChildren();saveDraft();}
  }catch(error){if(selected()?.id===account.id&&values().underlying===v.underlying){expiryKey=key;expiryRows=[];control.replaceChildren(new Option('Automatic · awaiting current broker dates',''));note.textContent='Expiry unavailable · '+error.message;}}
  finally{expiryInFlight=false;}
 }
 function hydrate(data){
  panel.dataset.sizingPolicyRevision=data.sizing_policy_revision||"unconfirmed";
  panel.dataset.nativeProviderRevision=data.native_provider_revision||"unconfirmed";
  panel.dataset.nativeProviderReady=String(data.native_acquisition_ready===true);
  const selectedSymbol=values().underlying;
  if(!selectedSymbol)return;
  if(values().sizingMode==='MANUAL_PARENT'){referenceLoaded=false;referenceSymbol=selectedSymbol;return;}
  let candidate=null;
  try{candidate=verifiedReference(data,selectedSymbol,sizingContext(selectedSymbol,selected()?.broker,values().category));delete panel.dataset.referenceError;}catch(error){panel.dataset.referenceError=error.message;}
  if(!candidate){const c=sizingContext(selectedSymbol,selected()?.broker,values().category);candidate=(data.manual_fallback_references||[]).find(r=>r.broker_symbol===selectedSymbol&&r.parent_hours===c.parentHours&&r.atr_length===c.atrLength&&r.valid_until>Date.now()/1000&&r.native_provider==='USER'&&Number(r.native_box)>0)||null;}
  panel.dataset.referenceResult=candidate?(candidate.native_provider==='USER'?'MANUAL_FALLBACK':'VERIFIED'):'UNAVAILABLE';panel.dataset.referenceBoundSymbol=selectedSymbol;panel.dataset.referenceActualBroker=selected()?.broker||'';panel.dataset.referenceNow=String(Date.now()/1000);
  referenceLoaded=!!candidate;
  if(candidate)lastDisplayReference={account:selected()?.id,symbol:selectedSymbol,category:values().category,reference:candidate};
  const display=candidate||(lastDisplayReference?.account===selected()?.id&&lastDisplayReference.symbol===selectedSymbol&&lastDisplayReference.category===values().category?lastDisplayReference.reference:null);
  referenceSymbol=display?selectedSymbol:null;
  for(const [key,value] of Object.entries({reference:display?.native_box??'',session:display?.reference_session??'',evidence:display?((display.source||'')+' · '+(display.url||'')):''})){
   const input=panel.querySelector('[data-ai='+key+']');input.value=value;input.readOnly=true;
   const output=panel.querySelector('[data-reference-display='+key+']');if(output)output.textContent=value?(key==='reference'?Number(value).toLocaleString('en-IN',{maximumFractionDigits:2}):value):'Awaiting verified native sizing';

  }
 }
 function renderExitNotices(){
  let banner=charts.querySelector('[data-exit-notices]');
  if(!banner){banner=document.createElement('div');banner.dataset.exitNotices='1';banner.setAttribute('role','alert');banner.style.cssText='margin:12px 0;padding:12px 16px;border:1px solid #c96c55;border-left:4px solid #ef866c;border-radius:7px;background:#321c20;color:#ffe1d8;overflow-wrap:anywhere';charts.querySelector('h2').after(banner);}
  const rows=(snapshot?.exit_notices||[]).filter(row=>row.account_id===selected()?.id&&row.symbol);
  banner.hidden=rows.length===0;banner.replaceChildren();
  for(const row of rows){const line=document.createElement('p');line.style.cssText='margin:4px 0;line-height:1.5';line.textContent='Exit not confirmed · '+row.symbol+(Number.isInteger(row.recorded_quantity)?' · recorded quantity '+row.recorded_quantity:'')+'. '+row.message;banner.append(line);}
 }
 function drawCharts(v){
  const account=selected();if(!account)return;
  renderExitNotices();
  const grid=charts.querySelector('.renko-ai-chart-grid');
  let view;try{view=chartView(v,snapshot?.heartbeat,snapshot?.running,account.broker);}catch{view=null;}
  if(!view){charts.querySelector('.renko-ai-chart-tabs').replaceChildren();grid.replaceChildren();const message=document.createElement('p');message.textContent='Select a supported underlying to show its chart panels.';grid.append(message);return;}
  if(grid.firstElementChild?.tagName==='P')grid.replaceChildren();
  const held=snapshot?.heartbeat?.position,pending=snapshot?.heartbeat?.pending?.intent?.position;
  const {context}=view;
  const preflightPreview=snapshot?.contracts_preview?.account_id===account.id?snapshot.contracts_preview:null;
  const mappingPreview=optionPreview?.underlying===view.underlying?optionPreview:preflightPreview;
  const contracts=chartContracts(mappingPreview,{...snapshot?.heartbeat,selected_contract:snapshot?.running?snapshot?.heartbeat?.selected_contract:null},view.underlying);
  if(attachmentChoice&&attachmentChoice.account===account.id&&attachmentChoice.underlying===view.underlying&&!snapshot?.running){
   const c=attachmentChoice;contracts[c.side]={symbol:c.symbol,option_type:c.side,underlying:view.underlying,expiry:c.expiry,option_brick:view.base*optionMultiplier(v.moneyness||'OTM'),attachment_preview:true};
  }
  grid.dataset.underlying=view.underlying;grid.dataset.previewUnderlying=optionPreview?.underlying||'';grid.dataset.contractSides=Object.keys(contracts).join(',');
  const entries=[{tab:'underlying',tabLabel:'Underlying',title:'Underlying · '+view.underlying,symbol:view.underlying,brick:view.base,details:view.base>0?(panel.dataset.referenceResult==='MANUAL_FALLBACK'?'Manual fallback · ':'')+(!referenceLoaded&&!view.frozen?'Last verified size · renewal pending · ':'')+context.parentHours+'H ATR'+context.atrLength+' ÷ '+context.divisor+' · fixed 30-minute baseline':'Waiting for verified '+context.parentHours+'H native ATR'+context.atrLength+' reference for '+view.underlying}];
  if(view.route!=='DIRECT')for(const side of ['CE','PE']){
   const c=contracts[side];
   entries.push(c?{tab:side==='CE'?'call':'put',tabLabel:side==='CE'?'Call':'Put',title:(side==='CE'?'Call':'Put')+(c.attachment_preview?' · ATTACH ON START':held?.symbol===c.symbol?' · HELD':pending?.symbol===c.symbol?' · PENDING':''),symbol:c.symbol,brick:c.option_brick,details:c.symbol+' · expiry '+(c.expiry_date||new Date(Number(c.expiry)*1000).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata'}))+' · delta '+(Number.isFinite(c.delta??c.selection_delta)?Number(c.delta??c.selection_delta).toFixed(2):'not loaded')+' · '+(c.option_brick>0?'brick '+Number(c.option_brick).toFixed(2):'native sizing reference pending')}:{tab:side==='CE'?'call':'put',tabLabel:side==='CE'?'Call':'Put',title:side==='CE'?'Call':'Put',details:'Preview contracts to resolve this chart.'});
  }
  if(view.owned){
   const c=view.owned,heldSymbol=c.symbol||c.underlying;
   entries.push({tab:'owned',tabLabel:'Owned position',title:'Owned position · '+heldSymbol,symbol:heldSymbol,brick:c.option_type?c.option_brick:c.spot_brick,timeframe:{1:'1 minute',5:'5 minutes',30:'30 minutes'}[snapshot?.heartbeat?.timeframe]||v.timeframe,owned:true,details:'Instrument change queued · this exact contract remains managed until exit.'});
  }
  const tabBar=charts.querySelector('.renko-ai-chart-tabs');
  const tabScope=storage()+':chart-tab:'+encodeURIComponent(view.underlying)+':'+view.route;
  if(activeChartTabScope!==tabScope){
   activeChartTabScope=tabScope;activeChartTab='underlying';
   try{activeChartTab=localStorage.getItem(tabScope)||'underlying';}catch{}
  }
  if(!entries.some(item=>item.tab===activeChartTab))activeChartTab='underlying';
  tabBar.hidden=entries.length<2;
  grid.classList.toggle('options-charts',view.route!=='DIRECT');
  for(const [i,item] of entries.entries()){
   let card=grid.children[i];if(!card){card=document.createElement('article');card.innerHTML='<h3></h3><p class="contract-details"></p><p class="chart-load-status" role="status" hidden></p><button class="button secondary chart-retry" type="button" hidden>Retry chart</button><iframe loading="lazy"></iframe>';grid.append(card);}
   const selectedTab=item.tab===activeChartTab;
   card.hidden=!selectedTab;card.dataset.chartTab=item.tab;card.id='ai-chart-panel-'+account.id+'-'+i;card.setAttribute('role','tabpanel');
   let tab=tabBar.children[i];
   if(!tab){tab=document.createElement('button');tab.type='button';tab.setAttribute('role','tab');tabBar.append(tab);}
   tab.dataset.chartTab=item.tab;tab.id='ai-chart-tab-'+account.id+'-'+i;
   if(tab.textContent!==item.tabLabel)tab.textContent=item.tabLabel;
   tab.setAttribute('aria-controls',card.id);tab.setAttribute('aria-selected',String(selectedTab));tab.tabIndex=selectedTab?0:-1;
   card.setAttribute('aria-labelledby',tab.id);
   tab.onclick=()=>{activeChartTab=item.tab;try{localStorage.setItem(activeChartTabScope,item.tab);}catch{}drawCharts(values());};
   tab.onkeydown=event=>{
    const buttons=[...tabBar.children];let next=buttons.indexOf(tab);
    if(event.key==='ArrowRight')next=(next+1)%buttons.length;
    else if(event.key==='ArrowLeft')next=(next+buttons.length-1)%buttons.length;
    else if(event.key==='Home')next=0;
    else if(event.key==='End')next=buttons.length-1;
    else return;
    event.preventDefault();buttons[next].click();buttons[next].focus();
   };
   card.querySelector('h3').textContent=item.title;card.querySelector('.contract-details').textContent=item.details;
   const framePolicy=chartFramePolicy(item);
   const frame=card.querySelector('iframe');frame.title=item.title;frame.hidden=framePolicy.hidden;
   if(frame.hidden){frame.removeAttribute('src');continue;}
   const sourceRun=!(account.broker==='MOTILAL_OSWAL')&&snapshot?.running&&(view.frozen||item.owned)&&snapshot?.chart_source_series?.some(c=>c.symbol===item.symbol&&c.frame===Number.parseInt(item.timeframe||view.timeframe||v.timeframe,10)&&c.brick===item.brick)?current?.run_id:null;
   const split=account.broker==='MOTILAL_OSWAL';
   const dataAccount=split?(root.BrokerForms?.accounts?.()||[]).find(a=>a.id===v.dataAccount&&a.broker==='FYERS'):account;
   const mapped=split?(i===0?((mappingPreview?.underlying===item.symbol&&mappingPreview?.market_data_account===dataAccount?.id?mappingPreview.market_data_underlying:null)||(['NSE','BSE'].includes(item.symbol.split(':')[0])?item.symbol:null)):Object.values(contracts).find(c=>c.symbol===item.symbol&&c.market_data_account===dataAccount?.id)?.market_data_symbol):item.symbol;
   if(!dataAccount||!mapped){frame.removeAttribute('src');frame.hidden=true;card.querySelector('.chart-load-status').hidden=false;card.querySelector('.chart-load-status').textContent='Preview contracts to verify this instrument in the selected FYERS data account.';continue;}
   const baseUrl=root.RenkoSupertrend.embeddedRenkoChartUrl(location.href,{accountId:dataAccount.id,broker:dataAccount.broker,symbol:mapped,instance:'ai-'+(split?'motilal-'+account.id+'-':'')+(sourceRun||'draft')+'-'+i+framePolicy.instanceSuffix,timeframe:item.timeframe||view.timeframe||v.timeframe,brick:item.brick,ai:true,runId:split?null:sourceRun});
   const chartLink=new URL(baseUrl);
   if(split){chartLink.searchParams.set('aiExecutionBroker','MOTILAL_OSWAL');chartLink.searchParams.set('aiExecutionAccount',account.id);}
   if(snapshot?.running?snapshot.supertrend_basis==='COMPLETED_RENKO':snapshot?.hybrid_completed_units_ready)chartLink.searchParams.set('aiSignalBasis','COMPLETED_RENKO');
   if(framePolicy.pending)chartLink.searchParams.set('aiSizingPending','1');
   if(snapshot?.run_id)chartLink.searchParams.set('aiLength',String(snapshot.indicator_length||5));
   const selectedFactor=snapshot?.running?Number(snapshot.indicator_factor||3):Number(v.factor||3);
   chartLink.searchParams.set('aiFactor',String(selectedFactor));
   // Multiplier changes use the existing chart's cached data, not a new iframe.
   try{
    const previous=new URL(frame.getAttribute('src'));
    if(previous.searchParams.get('chartSource')===account.id&&previous.searchParams.get('symbol')===item.symbol
      &&previous.searchParams.get('aiRun')===(sourceRun||null)&&previous.searchParams.get('interval')===chartLink.searchParams.get('interval'))
      chartLink.searchParams.set('aiFactor',previous.searchParams.get('aiFactor')||String(selectedFactor));
   }catch{}
   chartLink.searchParams.set('type',framePolicy.type||((snapshot?.running?snapshot.display_mode:v.calculationMode)==='RENKO'?'Renko':(['Candles','Line','Heikin Ashi'].includes(v.chartView)?v.chartView:'Candles')));
   const url=selectionFrameUrl(frame,chartLink.href);
   const publishMarkers=()=>{const params=new URL(url).searchParams;
    const bandSettings=['sma','ema'].filter(k=>v[k+'Entry']||v[k+'Exit']).map(k=>({kind:k.toUpperCase(),period:Number(v[k+'Period']||30)}));
const ownershipMappings=split?Object.fromEntries([[item.symbol,mapped],...(mappingPreview?.underlying===view.underlying&&mappingPreview?.market_data_account===dataAccount.id&&mappingPreview.market_data_underlying?[[view.underlying,mappingPreview.market_data_underlying]]:[]),...Object.values(contracts).filter(c=>c.market_data_account===dataAccount.id&&c.market_data_symbol).map(c=>[c.symbol,c.market_data_symbol])]):{};
frame.contentWindow?.postMessage(mappedChartOwnership({type:'sector-pulse-ai-runtime-markers',account:dataAccount.id,instance:params.get('chartInstance'),symbol:mapped,execution_account:account.id,execution_symbol:item.symbol,indicator_factor:selectedFactor,chart_visible:selectedTab,band_settings:bandSettings,run_rules:i===0?capturedStrategyRules(snapshot,item.symbol,account.id):null,band_basis:i===0?((snapshot?.running?snapshot.signal_source==='PREMIUM':v.underlyingSignals===false)?'CHART':'UNDERLYING'):'PREMIUM',run_id:sourceRun,runtime_frame:Number.parseInt(item.timeframe||view.timeframe||v.timeframe,10),run_pnl:i===0&&snapshot?.underlying===item.symbol?snapshot?.trade_journal?.current_run:null,run_running:!!snapshot?.running,active_position:snapshot?.running&&!snapshot?.ownership?.pending?snapshot?.heartbeat?.position:null,active_trade:snapshot?.running?(snapshot?.trade_journal?.rows||[]).find(row=>row.status==='OPEN'&&row.symbol===snapshot?.heartbeat?.position?.symbol&&(row.managed_run||row.run_id)===snapshot.run_id):null,runtime_bands:sourceRun&&i===0?snapshot?.heartbeat?.moving_bands:null,events:snapshot?.underlying===item.symbol?(snapshot?.markers||[]).map(event=>({...event,underlying:snapshot.underlying})):(sourceRun?(snapshot?.markers||[]):[])},ownershipMappings),location.origin);};
   if(!selectedTab){
    if(frame.hasAttribute('src')&&frame.getAttribute('src')!==url)frame.removeAttribute('src');
    else if(frame.hasAttribute('src'))publishMarkers();
    continue;
   }
   const loadStatus=card.querySelector('.chart-load-status'),retry=card.querySelector('.chart-retry');
   const retryLoad=()=>{
    if(frame.getAttribute('src')!==url)return;
    delete frame.dataset.loadFailedUrl;frame.hidden=false;loadStatus.hidden=retry.hidden=true;frame.src=url;
   };
   retry.onclick=()=>{frame.dataset.loadRetries='0';retryLoad();};
   frame.onload=()=>{
    let available=false;
    try{available=!!frame.contentDocument?.documentElement&&frame.contentDocument.URL!=='about:blank';}catch{}
    if(available){loadStatus.hidden=retry.hidden=true;frame.dataset.loadRetries='0';publishMarkers();return;}
    const count=Number(frame.dataset.loadRetries||0);
    loadStatus.hidden=false;loadStatus.textContent='Chart load interrupted. Your broker connection is unchanged.';
    if(count<2){frame.dataset.loadRetries=String(count+1);setTimeout(retryLoad,1000*(count+1));}
    else{frame.dataset.loadFailedUrl=url;frame.hidden=true;retry.hidden=false;}
   };
   if(frame.getAttribute('src')!==url){frame.dataset.loadRetries='0';delete frame.dataset.loadFailedUrl;frame.src=url;}else publishMarkers();
   if(frame.dataset.loadFailedUrl===url)frame.hidden=true;
  }
  while(grid.children.length>entries.length)grid.lastElementChild.remove();
  while(tabBar.children.length>entries.length)tabBar.lastElementChild.remove();
 }
 async function applySelection(next){
  const account=selected();
  if(!snapshot?.running&&next.underlying!==values().underlying){
   saveDraft();
   const saved=readInstrumentSettings(localStorage,settingsUser(),account,next.underlying);
   next=restoredInstrumentValues(instrumentDefaults,saved,next.underlying);
  }
  return selectionSync.change(next,async desired=>{
    sizingContext(desired.underlying,account.broker,desired.category);
    if(snapshot?.running){
     if(!root.confirm('The runner is active. Changing instrument or timeframe can affect entry and exit. Continue?'))return false;
     const change=await request('reconfigure',{broker:account.broker,account_id:account.id,run_id:snapshot.run_id,runtime_session:snapshot.heartbeat?.runtime_session,underlying:desired.underlying,timeframe:Number.parseInt(desired.timeframe,10),calculation_mode:snapshot.calculation_mode||'HYBRID',display_mode:desired.calculationMode||'CANDLES',confirmed:true});
     if(change.reconfiguration?.target_underlying){
      snapshot=change;current=change;status.textContent='Instrument change queued · existing position keeps its strategy exits until flat.';
      return selected()?.id===account.id;
     }
     const identifier=change.reconfiguration?.request_id;
     for(let attempt=0;attempt<65;attempt++){
      if(selected()?.id!==account.id||mode.value!==MODE)return false;
      const state=await request('status'),receipt=state.reconfiguration;
      if(receipt?.request_id!==identifier)throw Error('A newer runtime selection superseded this request.');
      if(receipt.phase==='APPLIED'){snapshot=state;current=state;break;}
      if(receipt.phase==='REJECTED')throw Error(receipt.error||'Runtime change rejected.');
      if(attempt===64)throw Error('Runtime change is still pending; the current runner selection remains in effect.');
      await new Promise(resolve=>setTimeout(resolve,500));
     }
    }
    return selected()?.id===account.id;
   },desired=>{
    const symbol=document.getElementById('renko-symbol');
    if(![...symbol.options].some(o=>o.value===desired.underlying))symbol.add(new Option(desired.underlying,desired.underlying));
    const changedInstrument=symbol.value!==desired.underlying;
    if(changedInstrument&&!snapshot?.running){
     clearInstrumentReference();
     for(const n of inputs)if(!['reference','session','evidence'].includes(n.dataset.ai)&&Object.hasOwn(desired,n.dataset.ai)){if(n.type==='checkbox')n.checked=desired[n.dataset.ai]===true;else n.value=desired[n.dataset.ai];}
     manualParentAt=desired.manualParentAt||null;
    }
    symbol.value=desired.underlying;panel.querySelector('[data-ai=timeframe]').value=desired.timeframe;displayInput.value=desired.calculationMode||'CANDLES';chartViewInput.value=desired.chartView||((desired.calculationMode||'CANDLES')==='RENKO'?'Renko':'Candles');
    if(referenceSymbol!==desired.underlying&&!changedInstrument)clearInstrumentReference();
    saveDraft();show();refreshStatus();
   });
 }
 root.addEventListener('message',async event=>{
  if(event.origin!==location.origin||mode.value!==MODE||event.data?.type!=='sector-pulse-ai-selection-intent')return;
  const data=event.data,account=selected();
  const frame=[...charts.querySelectorAll('iframe')].find(n=>n.contentWindow===event.source);
  if(!frame||!frame.getAttribute('src'))return;
  let documentId;try{documentId=frame.contentDocument?.documentElement?.dataset.aiSelectionDocument;}catch{return;}
  const previousSequence=frame.dataset.selectionDocument===documentId?Number(frame.dataset.selectionSequence||0):0;
  if(!selectionIntentMatches(frame.src,data,account?.id,previousSequence,documentId))return;
  frame.dataset.selectionDocument=documentId;
  frame.dataset.selectionSequence=String(data.sequence);
  try{
   const next={...values()},change=data.change||{};
   if(change.symbol){if(!data.instance.endsWith('-0'))throw Error('Change the underlying on its main strategy chart.');next.underlying=String(change.symbol);}
   if(change.interval){const label={1:'1 minute',5:'5 minutes',30:'30 minutes'}[change.interval];if(!label)throw Error('This strategy supports 1, 5 or 30 minutes.');next.timeframe=label;}
   if(change.chartType){if(!['Candles','Renko','Line','Heikin Ashi'].includes(change.chartType))throw Error('Unsupported strategy chart view.');next.calculationMode=change.chartType==='Renko'?'RENKO':'CANDLES';next.chartView=change.chartType;}
   await applySelection(next);
  }catch(error){status.textContent=error.message;}
 });
 function restore(){
  if(!selected()?.id)return;restoredDraftAccount=selected().id;
  try{const existing=localStorage.getItem(storage());
   const legacy=!existing&&settingsUser()&&snapshot?.settings_owner_username===settingsUser()?localStorage.getItem(legacyStorage()):null;
   const draft=JSON.parse(existing||legacy||'null');
   const saved=draft?.underlying?readInstrumentSettings(localStorage,settingsUser(),selected(),draft.underlying):null;
   const v=saved||draft;manualParentAt=v?.manualParentAt||null;
   if(v?.sizingMode==='MANUAL_PARENT'&&!manualParentAt){v.manualParent='';v.sizingMode='AUTO';}
   if(legacy&&v){localStorage.setItem(storage(),JSON.stringify(v));writeInstrumentSettings(localStorage,settingsUser(),selected(),v);}
referenceSymbol=v?.underlying||null;expiryDraft=v?.expiry||'';if(!v?.route&&selected()?.broker==='DELTA_INDIA')panel.querySelector('[data-ai=route]').value='DIRECT';if(v?.underlying){const symbol=document.getElementById('renko-symbol');if(![...symbol.options].some(o=>o.value===v.underlying))symbol.add(new Option(v.underlying,v.underlying));symbol.value=v.underlying;if(v.instrument_market)document.getElementById('renko-market').value=v.instrument_market;}if(v)for(const n of inputs)if(!['reference','session','evidence'].includes(n.dataset.ai)&&Object.hasOwn(v,n.dataset.ai)){if(n.type==='checkbox')n.checked=v[n.dataset.ai]===true;else n.value=v[n.dataset.ai];}}catch{}
  try{
   const saved=JSON.parse(localStorage.getItem(storage()+':attachment')||'null');
   if(saved?.account===selected()?.id&&saved.underlying===values().underlying){
    attachmentChoice=saved;attachmentRows=[saved];
    const pick=panel.querySelector('[data-ai-attachment]');pick.replaceChildren(new Option('No external position selected',''),new Option(saved.symbol+' · '+saved.quantity+' units · '+saved.product,saved.symbol+'|'+saved.product));pick.value=saved.symbol+'|'+saved.product;
    panel.querySelector('[data-ai-attachment-status]').textContent='Saved attachment selection: '+saved.symbol+' · '+saved.quantity+' units · '+saved.product+'. Broker holding is rechecked on Start; no new Buy.';
   }
  }catch{}

 }
 const aiContext=createAiContextLoader(root.fetch.bind(root));
 async function request(action,body){
  const context=body?await aiContext(root.BrokerForms?.context?.()||root.SectorPulseWorkspace):null;
  const response=await root.BrokerForms.fetch('renko','/api/renko-supertrend/ai-options/'+action,aiRequestOptions(body,context));
  if(!response.headers.get('Content-Type')?.includes('application/json'))throw Error('The selected broker backend has not loaded the AI strategy route.');
  const result=await response.json(),error=responseError(result,response.ok);if(error)throw Error(error);return result;
 }

 let suggestionBox;
 function renderSearchSuggestions(rows,query){
  const input=document.getElementById('renko-search');
  if(!suggestionBox){suggestionBox=document.createElement('div');suggestionBox.id='renko-ai-search-suggestions';suggestionBox.setAttribute('role','listbox');suggestionBox.setAttribute('aria-label','Matching broker instruments');suggestionBox.style.cssText='display:grid;gap:4px;max-height:240px;overflow:auto;padding:6px;border:1px solid #354a63;border-radius:8px;background:#101e30';input.after(suggestionBox);input.setAttribute('aria-controls',suggestionBox.id);input.setAttribute('aria-autocomplete','list');input.addEventListener('keydown',event=>{if(event.key==='ArrowDown'&&!suggestionBox.hidden){event.preventDefault();suggestionBox.querySelector('button')?.focus();}if(event.key==='Escape')suggestionBox.hidden=true;});}
  suggestionBox.replaceChildren();suggestionBox.hidden=mode.value!==MODE||!String(query||'').trim()||!rows.length;
  if(suggestionBox.hidden)return;
  for(const row of rows.slice(0,12)){
   const button=document.createElement('button');button.type='button';button.setAttribute('role','option');button.style.cssText='text-align:left;padding:9px 10px;white-space:normal;overflow-wrap:anywhere;background:#172b44;border:1px solid #2e4866;border-radius:5px;color:#edf4ff';
   button.textContent=(row.underlying||row.description||row.symbol)+' · '+row.symbol+(row.suggested?' · Close spelling':'');
   button.onclick=()=>{const pick=document.getElementById('renko-symbol');if(![...pick.options].some(o=>o.value===row.symbol))return;pick.value=row.symbol;suggestionBox.hidden=true;pick.dispatchEvent(new Event('change',{bubbles:true}));};
   suggestionBox.append(button);
  }
 }
 let aiSearchTimer,aiSearchSequence=0;
 function clearInstrumentReference(){panel.querySelector('[data-ai=manualParent]').value='';expiryKey='';expiryReadAt=0;expiryRows=[];expiryDraft='';panel.querySelector('[data-ai=expiry]').replaceChildren(new Option('Automatic · nearest valid expiry',''));panel.querySelector('[data-ai-expiry]').textContent='Loading the selected underlying’s listed expiries…';referenceLoaded=false;referenceSymbol=null;optionPreview=null;lastDisplayReference=null;for(const key of ['reference','evidence','session'])panel.querySelector('[data-ai='+key+']').value='';panel.querySelector('.renko-ai-preview').replaceChildren();}
 async function searchAiInstruments(){
  const sequence=++aiSearchSequence,market=document.getElementById('renko-market').value,q=document.getElementById('renko-search').value,accountId=selected()?.id,route=values().route;
  const isCurrent=()=>!(sequence!==aiSearchSequence||mode.value!==MODE||accountId!==selected()?.id||route!==values().route||market!==document.getElementById('renko-market').value||q!==document.getElementById('renko-search').value);
  status.textContent='Searching current broker instruments…';
  try{
   const data=await request('search?'+new URLSearchParams({q,market,route}));if(!isCurrent())return;
   const symbol=document.getElementById('renko-symbol'),prior=symbol.value,label=symbol.selectedOptions[0]?.textContent;
   symbol.replaceChildren(new Option('Select an underlying',''));
   for(const item of data.matches||[]){const option=new Option((item.underlying||item.description||item.symbol)+' · '+item.symbol,item.symbol);option.dataset.aiProductType=item.product_type||'';symbol.add(option);}
   if(prior){if(![...symbol.options].some(o=>o.value===prior))symbol.add(new Option(label||prior,prior));symbol.value=prior;}
   renderSearchSuggestions(data.matches||[],q);status.textContent=(data.matches||[]).length+' instruments · '+(data.message||'');show();
  }catch(error){if(isCurrent())status.textContent=error.message;}
 }
 document.addEventListener('input',event=>{if(mode.value!==MODE||event.target.id!=='renko-search')return;event.stopImmediatePropagation();if(suggestionBox)suggestionBox.hidden=true;clearTimeout(aiSearchTimer);aiSearchTimer=setTimeout(searchAiInstruments,300);},true);
 document.addEventListener('change',event=>{
  if(mode.value===MODE&&['renko-symbol','renko-market'].includes(event.target.id)){
   event.stopImmediatePropagation();
   if(event.target.id==='renko-symbol'){
    const next=values(),prior=acceptedSelection;
    if(prior?.account===selected()?.id){event.target.value=prior.underlying;}
    applySelection(next).catch(error=>{status.textContent=error.message;});return;
   }
   if(snapshot?.running){status.textContent='Select the instrument directly; the active runner market remains unchanged.';return;}
   clearInstrumentReference();
   if(event.target.id==='renko-market'){document.getElementById('renko-symbol').value='';document.getElementById('renko-search').value='';searchAiInstruments();}
   else if(event.target.selectedOptions[0]?.dataset.aiProductType==='FUTURE')panel.querySelector('[data-ai=route]').value='DIRECT';
   saveDraft();show();refreshStatus();return;
  }
  if(event.target!==mode)return;
  if(!applyingViewDefault)strategyVisit.choose(mode.value);
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
 panel.addEventListener('change',event=>{event.stopPropagation();
  if(event.target.dataset.ai==='route'&&event.target.value==='DIRECT'&&['FYERS','DHAN','MOTILAL_OSWAL'].includes(selected()?.broker)&&!snapshot?.running)panel.querySelector('[data-ai=product]').value='INTRADAY';
  if(event.target.dataset.ai==='moneyness'){
   optionMultiplier(event.target.value);optionPreview=null;attachmentChoice=null;attachmentRows=[];
   panel.querySelector('[data-ai-attachment]').replaceChildren(new Option('No external position selected',''));
   panel.querySelector('[data-ai-attachment-status]').textContent='Option classification changed. Refresh broker positions before selecting an attachment.';
   try{localStorage.removeItem(storage()+':attachment');}catch{}
  }

  if(event.target.hasAttribute('data-ai-attachment')){
   const row=attachmentRows.find(r=>r.symbol+'|'+r.product===event.target.value);
   attachmentChoice=row?{...row,account:selected()?.id,underlying:values().underlying}:null;
   try{if(attachmentChoice)localStorage.setItem(storage()+':attachment',JSON.stringify(attachmentChoice));else localStorage.removeItem(storage()+':attachment');}catch{}
   if(row){
    panel.querySelector('[data-ai=execution]').value='LIVE';panel.querySelector('[data-ai=product]').value=row.product;
    panel.querySelector('[data-ai=lots]').value=row.lots;
    panel.querySelector('[data-ai-attachment-status]').textContent='Selected '+row.symbol+' · '+row.quantity+' units · '+row.product+(Number.isFinite(row.average_price)&&row.average_price>0?' · Entry '+row.average_price.toFixed(2):' · Entry unavailable')+'. Click Attach to manage this holding; no new entry.';
   }else panel.querySelector('[data-ai-attachment-status]').textContent='No position selected for attachment.';
   saveDraft();show();return;
  }

  if(['sizingMode','manualParent'].includes(event.target.dataset.ai)){optionPreview=null;panel.querySelector('.renko-ai-preview').replaceChildren();}
  if(event.target.dataset.ai==='expiry'){
   expiryDraft=event.target.value;optionPreview=null;panel.querySelector('.renko-ai-preview').replaceChildren();
  }
  if(['timeframe','calculationMode'].includes(event.target.dataset.ai)){
   const next=values(),prior=acceptedSelection;
   if(prior?.account===selected()?.id)event.target.value=event.target.dataset.ai==='timeframe'?prior.timeframe:(prior.calculationMode||'CANDLES');
   applySelection(next).catch(error=>{status.textContent=error.message;});return;
  }
if(event.target.dataset.ai==='category'){clearInstrumentReference();refreshStatus();}if(['reference','evidence'].includes(event.target.dataset.ai))referenceSymbol=values().underlying;saveDraft();show();});
 panel.addEventListener('change',event=>{
  if(event.target.dataset.ai==='route'&&event.target.value==='DIRECT'&&['DHAN','MOTILAL_OSWAL'].includes(selected()?.broker)&&!snapshot?.running){
   panel.querySelector('[data-ai=product]').value='INTRADAY';saveDraft();show();
  }
 });
 panel.addEventListener('input',event=>{event.stopPropagation();if(['reference','evidence'].includes(event.target.dataset.ai))referenceSymbol=values().underlying;if(event.target.dataset.ai==='manualParent'){manualParentAt=Date.now()/1000;optionPreview=null;saveDraft();show();}});
 panel.addEventListener('click',async event=>{
  const action=event.target.closest('[data-ai-action]')?.dataset.aiAction;if(!action)return;event.preventDefault();event.stopPropagation();status.dataset.userMessage='1';
  if(action==='start'||action==='stop')delete status.dataset.userMessage;
  try{
   if(action==='positions'){
    if(snapshot?.running&&positionControlView(snapshot).operation!=='ATTACH')throw Error('Detach the managed holding before selecting an attachment.');
    const account=selected(),underlying=values().underlying;
    const result=await request('prepare',{...configuration(values(),account,true),list_positions:true});
    if(selected()?.id!==account.id||values().underlying!==underlying||result.account_id!==account.id||result.underlying!==underlying)throw Error('Broker selection changed; refresh positions again.');
    attachmentRows=result.positions||[];
    attachmentChoice=retainAttachment(attachmentChoice,attachmentRows,account.id,underlying);
    try{if(attachmentChoice)localStorage.setItem(storage()+':attachment',JSON.stringify(attachmentChoice));else localStorage.removeItem(storage()+':attachment');}catch{}
    const select=panel.querySelector('[data-ai-attachment]');select.replaceChildren(new Option('No external position selected',''));
    for(const row of attachmentRows)select.add(new Option(row.symbol+' · '+row.quantity+' units · '+row.product,row.symbol+'|'+row.product));
    if(attachmentChoice)select.value=attachmentChoice.symbol+'|'+attachmentChoice.product;
    panel.querySelector('[data-ai-attachment-status]').textContent=attachmentChoice?'Attachment retained and refreshed: '+attachmentChoice.symbol+' · '+attachmentChoice.quantity+' units · '+attachmentChoice.product+'. Rechecked when you click Attach.':attachmentRows.length+' eligible open position(s). Select one, then Attach.';
    status.textContent='Broker position read complete · no runner or orders started.';return;
   }
   if(action==='stop'||action==='position-toggle'){
    const operation=action==='stop'?'STOP':positionControlView(snapshot).operation;
    const body=positionControlPayload(snapshot,values(),selected(),operation,root.crypto.randomUUID().replaceAll('-',''),attachmentChoice);
    const message=operation==='STOP'?'Square off the exact strategy-managed holding and stop? Completion requires broker confirmation.':operation==='DETACH'?'Leave the broker holding open and pause strategy management and new entries?':'Attach the selected existing holding without a new entry? New entries remain paused.';
    if(operation!=='STOP'&&!root.confirm(message))return;
    snapshot=await request(operation==='STOP'?'stop':'position-control',body);current=snapshot;
    status.textContent=snapshot.notice||'Position request accepted; awaiting confirmation.';show();return;
   }
   if(action==='manual-entry'){
    const id=root.crypto.randomUUID().replaceAll('-',''),direction=panel.querySelector('[data-manual-direction]').value;
    const body=manualEntryPayload(snapshot,values(),selected(),direction,id);
    if(!root.confirm('Request '+direction+' for '+body.underlying+' · '+body.mode+' · '+snapshot.active_lots+' lots/contracts? Strategy exits will manage the confirmed position.'))return;
    snapshot=await request('manual-entry',body);current=snapshot;status.textContent=snapshot.notice||'Manual entry requested.';show();return;
   }
   const payload=action==='stop'?{broker:selected()?.broker,account_id:selected()?.id,underlying:values().underlying}:configuration(values(),selected(),action==='preview');
   if(action==='start'&&values().supertrend===false&&!snapshot?.sma_only_capable)throw Error('SMA-only runtime update is not loaded yet.');
   if(action==='start'&&values().supertrend!==false){
    const chart=charts.querySelector('iframe');
    let indicator;
    try{indicator=chart?.contentWindow?.SectorPulseAiIndicatorContract?.();}catch{}
    if(!indicator?.compatible)throw Error('Start unavailable: the plotted indicator source/settings have not matched the supported strategy indicator.');
    if(Number(indicator.factor)!==Number(values().factor||3))throw Error('The chart multiplier is synchronizing; wait for the chart before Start.');
    payload.ai_indicator_inputs={length:indicator.length,factor:indicator.factor,adx_enabled:indicator.adx_enabled};
    payload.ai_display_mode=indicator.displayType==='Renko'?'RENKO':'CANDLES';
   }

   if(action==='stop'){snapshot=await request('stop',{...payload,run_id:current?.run_id});}
   else if(action==='preview'){
    status.textContent='Reading the selected broker’s current expiry, chain and contract master…';
    const prepared=await request('prepare',payload),preview=prepared.preview;
    if(preview?.direct){panel.querySelector('.renko-ai-preview').textContent=preview.direct.symbol+' · '+(preview.direct.product_type||'PERPETUAL')+' · base brick '+(preview.spot_brick===null?'unavailable · native reference pending':Number(preview.spot_brick).toFixed(2))+' · no option delta';drawCharts(values());status.textContent='Read-only direct-instrument metadata preview complete · no monitoring or orders.';return;}
    if(!preview?.contracts)throw Error('Option sizing preview unavailable');
    if((prepared.config?.option_moneyness||'OTM')!==(values().moneyness||'OTM'))throw Error('Option classification changed; repeat the read-only preview.');
    if(prepared.config?.underlying!==payload.underlying)throw Error('Backend did not confirm the selected underlying; preview charts remain unavailable.');
    if(selected()?.id!==payload.account_id||values().underlying!==payload.underlying||values().expiry!==(payload.ai_expiry||''))throw Error('Instrument or expiry changed during preview; previous response discarded.');
    optionPreview={...preview,underlying:prepared.config.underlying};panel.dataset.previewUnderlying=optionPreview.underlying;panel.dataset.previewSides=Object.keys(optionPreview.contracts).join(',');
    panel.querySelector('[data-ai-expiry]').textContent=(payload.ai_expiry?'Selected · ':'Automatic · ')+preview.contracts.CE.expiry_date+' · verified broker contracts';
    const box=panel.querySelector('.renko-ai-preview');box.replaceChildren();
    for(const [side,c] of Object.entries(preview.contracts)){const line=document.createElement('p');line.textContent=side+' · '+c.symbol+' · expiry '+c.expiry_date+' · premium '+(c.quote_currency||'INR')+' '+Number(c.selection_ltp).toFixed(2)+' · delta '+Number(c.delta).toFixed(2)+' · option brick '+(c.option_brick===null?'unavailable · native reference pending':Number(c.option_brick).toFixed(2));box.append(line);}
    const note=document.createElement('small');note.textContent='Read-only snapshot '+preview.checked_at+' · '+(preview.reference_value>0?'Underlying reference '+Number(preview.reference_value).toFixed(2)+' ('+preview.reference_session+') ÷ '+sizingContext(payload.underlying,payload.broker,values().category).divisor:'Native parent reference pending · price and delta preview only')+'. '+preview.quote_note;box.append(note);
    drawCharts(values());status.textContent='Read-only sizing preview complete · no monitoring or orders.';return;
   }else if(action==='prepare'){
    const prepared=await request('prepare',payload);
    const blob=new Blob([JSON.stringify(prepared.config,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='ai-renko-supertrend.json';a.click();URL.revokeObjectURL(url);
    status.textContent='Python configuration prepared. Run the read-only preflight before activation.';return;
   }else{
    if(attachmentChoice){
     if(attachmentChoice.account!==selected()?.id||attachmentChoice.underlying!==values().underlying)throw Error('Attachment belongs to a different selection; refresh open positions.');
     const selectedAttachment={...attachmentChoice},account=selected(),underlying=values().underlying;
     const verified=await request('prepare',{...configuration(values(),account,true),list_positions:true});
     if(selected()?.id!==account.id||values().underlying!==underlying||verified.account_id!==account.id||verified.underlying!==underlying)throw Error('Selection changed during attachment verification; Start was not sent.');
     attachmentRows=verified.positions||[];
     attachmentChoice=retainAttachment(selectedAttachment,attachmentRows,account.id,underlying);
     if(!attachmentChoice){
      try{localStorage.removeItem(storage()+':attachment');}catch{}
      panel.querySelector('[data-ai-attachment]').replaceChildren(new Option('No external position selected',''));
      panel.querySelector('[data-ai-attachment-status]').textContent='Previous attachment is no longer open with the same quantity and product. Selection cleared; no runner started.';
      show();throw Error('Previous holding is closed or changed. Attachment cleared. Press Start to run the strategy without that attachment.');
     }
     payload.ai_attach_position={symbol:attachmentChoice.symbol,quantity:attachmentChoice.quantity,product:attachmentChoice.product};
    }
    payload.start_requested=true;
    snapshot=await request('start',payload);current=snapshot;
   }
   status.textContent=snapshot.phase+' · '+(snapshot.error||snapshot.notice||snapshot.run_id||'stopped');show();
  }catch(error){status.textContent=error.message;if(action==='start')status.dataset.userMessage='1';}
 });
 let automaticRequestAt=0,automaticRequestKey='',statusSequence=0,statusInFlight=false,nativePrepareError=null;
 async function refreshStatus(){
  if(mode.value!==MODE||statusInFlight)return;
  const account=selected(),symbol=values().underlying,sequence=++statusSequence;
  if(!['FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'].includes(account?.broker)){status.textContent='Waiting for the selected broker account…';return;}
  if(!snapshot&&!status.dataset.userMessage)status.textContent='Reading strategy status…';
  statusInFlight=true;
  try{
   const data=await request('status');
   if(sequence!==statusSequence||selected()?.id!==account.id||values().underlying!==symbol||mode.value!==MODE)return;
   snapshot=data;current=snapshot;if(!localStorage.getItem(storage())&&snapshot.settings_owner_username===settingsUser())restore();hydrate(snapshot);if(referenceLoaded||values().sizingMode==='MANUAL_PARENT')nativePrepareError=null;
   const job=(values().sizingMode==='MANUAL_PARENT'?[]:snapshot.native_jobs||[]).filter(j=>j.symbol===symbol).sort((a,b)=>b.updated_at-a.updated_at)[0];
   if(!status.dataset.userMessage)status.textContent=snapshot.phase+' · '+(snapshot.error||(panel.dataset.referenceResult==='MANUAL_FALLBACK'?'Auto unavailable · using your manual parent size':null)||(snapshot.heartbeat?.exit_waiting_for_quote?'Exit confirmed · waiting for a fresh executable option quote':null)||marketWaitLabel(snapshot)||job?.error||(nativePrepareError?.symbol===symbol?nativePrepareError.message:null)||(job?.state==='RUNNING'?'Calculating native Renko size…':snapshot.run_id)||'stopped');
   show();
   const requestKey=account.id+'|'+symbol+'|'+values().category;
   if(values().sizingMode!=='MANUAL_PARENT'&&symbol&&!referenceLoaded&&snapshot.native_acquisition_ready&&(requestKey!==automaticRequestKey||Date.now()-automaticRequestAt>30000)){
    automaticRequestKey=requestKey;automaticRequestAt=Date.now();
    const body=configuration(values(),account,true);body.preview_options=false;
    const prepared=await request('prepare',body);
    if(selected()?.id===account.id&&values().underlying===symbol&&prepared.native_job?.error){nativePrepareError={symbol,message:prepared.native_job.error};status.textContent=prepared.native_job.error;}
   }
  }catch(error){if(selected()?.id===account.id){nativePrepareError={symbol,message:error.message};status.textContent=error.message;}}
  finally{statusInFlight=false;}
 }
 setInterval(refreshStatus,5000);
 root.addEventListener('broker-accounts-ready',()=>{restoreAiView();show();refreshStatus();});
 strategySectionEntry();show();
}
if(typeof module!=='undefined')module.exports={manualRequestLabel,createStrategyVisit,restoredDataAccount,createAiContextLoader,aiRequestOptions,mappedChartOwnership,restoredInstrumentValues,instrumentSettingsKey,readInstrumentSettings,writeInstrumentSettings,capturedStrategyRules,manualSizingValues,chartFramePolicy,expiryDeadline,nativeBrokerReady,positionControlView,positionControlPayload,optionMultiplier,retainAttachment,responseError,selectionFrameUrl,selectionIntentMatches,marketWaitLabel,SelectionSync,manualEntryPayload,configuration,sizingContext,chartContracts,chartView,verifiedReference};
if(typeof document!=='undefined'){
 const observer=new MutationObserver(()=>mount());observer.observe(document.documentElement,{childList:true,subtree:true});
 root.addEventListener('broker-accounts-ready',mount);if(document.readyState!=='loading')mount();else document.addEventListener('DOMContentLoaded',mount);
}
})(typeof window==='undefined'?globalThis:window);
