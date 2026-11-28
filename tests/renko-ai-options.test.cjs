const test=require('node:test'),assert=require('node:assert/strict');
const {configuration}=require('../renko-ai-options.js');
const fields={underlying:'NSE:NIFTY50-INDEX',reference:'400',lots:'1',expiry:'1795428600',session:'2026-11-19',evidence:'fixture',timeframe:'30 minutes',execution:'PAPER',product:'MARGIN',premium:'40'};
test('AI UI configuration selects the actual dedicated options runtime',()=>{
 const p=configuration(fields,{id:'owner',broker:'FYERS'});assert.equal(p.strategy_mode,'AI_RENKO_OPTIONS');assert.equal(p.ai_sma_exit_enabled,false);assert.equal(p.ai_reference_value,400);assert.equal(p.timeframe,'30 minutes');assert.equal(p.target_premium,40);assert.equal(p.underlying,'NSE:NIFTY50-INDEX');
});
test('AI mode cannot redirect another broker or invent quantity/reference',()=>{
 assert.throws(()=>configuration(fields,{id:'owner',broker:'DELTA_INDIA'}),/supported/);
 assert.throws(()=>configuration({...fields,lots:''},{id:'owner',broker:'FYERS'}),/whole lots/);
 const pending=configuration({...fields,reference:'',session:'',evidence:''},{id:'owner',broker:'FYERS'});assert.equal(pending.ai_reference_value,null);assert.equal(pending.ai_reference_symbol,fields.underlying);assert.equal(pending.ai_accept_chart_basis,true);
});

const fs=require('node:fs'),vm=require('node:vm');
const chartSource=fs.readFileSync('chart-workspace.js','utf8');
const blockStart=chartSource.indexOf("    if (embeddedRenko && linkedChart.aiRenko === '1'");
const scopedBlock=chartSource.slice(blockStart,chartSource.indexOf('    if (restoreView)',blockStart));
test('managed Auto binding is isolated to the AI strategy embedded context',()=>{
 const contractStart=chartSource.indexOf('  // BEGIN APPROVED AI RENKO AUTO CONTRACT');
 const contractEnd=chartSource.indexOf('\n  function openAiRenkoSupertrend()',contractStart);
 const contract={completedBrickSignalView:()=>false};vm.createContext(contract);vm.runInContext(chartSource.slice(contractStart,contractEnd),contract);
 for(const [embeddedRenko,aiRenko] of [[false,'1'],[true,'0']]){
  const study={kind:'Pine',name:'AI Renko Supertrend',inputs:{in_2:'Auto'}};const settings={studies:[study]};
  vm.runInNewContext(chartSource.slice(chartSource.indexOf('  function aiIndicatorInputsMatch('),chartSource.indexOf('  function aiIndicatorSourceMatches('))+scopedBlock,{completedBrickSignalView:()=>false,window:{},document:{documentElement:{dataset:{}}},aiRuntimeParams:new URLSearchParams(),embeddedRenko,linkedChart:{aiRenko,method:'fixed',brick:'20.833333333333332'},settings,managedAiRenkoPineSource:contract.managedAiRenkoPineSource,aiIndicatorSourceMatches:contract.aiIndicatorSourceMatches,Number});
  assert.equal(settings.studies[0],study);assert.equal(study.inputs.in_2,'Auto');
 }
 const settings={studies:[]};vm.runInNewContext(chartSource.slice(chartSource.indexOf('  function aiIndicatorInputsMatch('),chartSource.indexOf('  function aiIndicatorSourceMatches('))+scopedBlock,{completedBrickSignalView:()=>false,window:{},document:{documentElement:{dataset:{}}},aiRuntimeParams:new URLSearchParams(),embeddedRenko:true,linkedChart:{aiRenko:'1',method:'fixed',brick:'20.833333333333332'},settings,managedAiRenkoPineSource:contract.managedAiRenkoPineSource,aiIndicatorSourceMatches:contract.aiIndicatorSourceMatches,Number});
 assert.equal(settings.studies[0].inputs.in_2,'Auto');assert.equal(settings.studies[0].inputs.in_3,250/12);
 assert.ok(settings.studies[0].source.includes('Verified strategy Auto result'));
});

test('expiry is automatic without a required user field in both execution modes',()=>{
 for(const execution of ['PAPER','LIVE']){
 const p=configuration({...fields,expiry:undefined,execution},{id:'owner',broker:'FYERS'});
 assert.equal(p.ai_expiry_policy,'nearest_tradable');assert.equal(p.mode,execution);assert.equal(p.ai_expiry,undefined);
 }
});

test('read-only sizing preview does not require lots or product',()=>{
 const p=configuration({...fields,lots:'',product:'',expiry:undefined},{id:'owner',broker:'FYERS'},true);
 assert.equal(p.preview_options,true);assert.equal(p.lots,null);assert.equal(p.ai_expiry_policy,'nearest_tradable');
});

const {sizingContext}=require('../renko-ai-options.js');
test('selected instrument drives configuration and market divisor without a Nifty default',()=>{
 for(const [underlying,broker,divisor] of [['NSE:CUPID-EQ','FYERS',12],['BSE:SENSEX-INDEX','FYERS',12],['BTCUSD','DELTA_INDIA',46],['MCX:GOLD26DECFUT','FYERS',28],['MCX:SILVER26DECFUT','FYERS',28]]){
  const p=configuration({...fields,underlying},{id:'owner',broker},true);
  assert.equal(p.underlying,underlying);assert.equal(sizingContext(underlying,broker).divisor,divisor);
 }
 assert.throws(()=>configuration({...fields,underlying:''},{id:'owner',broker:'FYERS'},true),/Select an underlying/);
});

const {chartContracts}=require('../renko-ai-options.js');
test('held exact option and locked brick override new near-premium previews',()=>{
 const old={symbol:'NSE:CUPID-HELD-CE',underlying:'NSE:CUPID-EQ',option_type:'CE',option_brick:4,selection_delta:.4};
 const preview={underlying:'NSE:CUPID-EQ',contracts:{CE:{symbol:'NEW-CE',option_brick:5},PE:{symbol:'NEW-PE',option_brick:6}}};
 const c=chartContracts(preview,{position:old,selected_contract:{...old,symbol:'OTHER-CE',option_brick:8}},'NSE:CUPID-EQ');
 assert.equal(c.CE,old);assert.equal(c.PE.symbol,'NEW-PE');
 assert.deepEqual(chartContracts(preview,{position:old},'BSE:SENSEX-INDEX'),{});
});

const {chartView}=require('../renko-ai-options.js');
test('requested chart follows the new selection while retaining exact owned geometry separately',()=>{
 const held={underlying:'NSE:NIFTY50-INDEX',symbol:'HELD-CE',option_type:'CE',spot_brick:400/12};
 const view=chartView({underlying:'NSE:RELIANCE-EQ',reference:120,route:'DIRECT'},{position:held},true,'FYERS');
 assert.equal(view.underlying,'NSE:RELIANCE-EQ');assert.equal(view.base,10);assert.equal(view.route,'DIRECT');assert.equal(view.owned,held);
 const direct=chartView({underlying:'ETHUSD',reference:1,route:'OPTIONS'},{position:{underlying:'BTCUSD',spot_brick:100,execution_route:'DIRECT'}},true,'DELTA_INDIA');
 assert.equal(direct.base,1/46);assert.equal(direct.route,'OPTIONS');assert.equal(direct.owned.spot_brick,100);
});


test('native reference binds exact symbol, parent and completed regular session',()=>{
 const {verifiedReference,sizingContext}=require('../renko-ai-options.js');
 const symbol='NSE:NIFTY50-INDEX',context=sizingContext(symbol,'FYERS');
 const ref={broker_symbol:symbol,status:'VERIFIED_TEST',native_box:400,parent_hours:6,atr_length:5,chart_session:'Regular trading hours',reference_session:'2026-11-19'};
 const data={native_references:[ref],expected_reference_session:'2026-11-19'};
 assert.equal(verifiedReference(data,symbol,context),ref);
 assert.equal(verifiedReference(data,'NSE:RELIANCE-EQ',context),null);
 assert.equal(verifiedReference({...data,expected_reference_session:'2026-11-20'},symbol,context),null);
 assert.equal(verifiedReference({...data,native_references:[{...ref,chart_session:'Extended trading hours'}]},symbol,context),null);
});
test('continuous native reference rejects future and expired parent observations',()=>{
 const {verifiedReference,sizingContext}=require('../renko-ai-options.js');
 const symbol='BTCUSD',context=sizingContext(symbol,'DELTA_INDIA');
 const ref={broker_symbol:symbol,status:'VERIFIED_TEST',native_box:460,parent_hours:23,atr_length:7,completed_parent_at:100000};
 assert.equal(verifiedReference({native_reference:ref},symbol,context,100001),ref);
 assert.equal(verifiedReference({native_reference:ref},symbol,context,99999),null);
 assert.equal(verifiedReference({native_reference:ref},symbol,context,200000),null);
});


test('pending exact intent remains distinct from the newly requested instrument',()=>{
 const {chartView,chartContracts}=require('../renko-ai-options.js');
 const position={underlying:'NSE:NIFTY50-INDEX',symbol:'EXACT-PENDING-CE',option_type:'CE',spot_brick:400/12,option_brick:4,execution_route:'OPTIONS'};
 const heartbeat={pending:{intent:{position}}};
 const view=chartView({underlying:'NSE:RELIANCE-EQ',reference:123,route:'DIRECT'},heartbeat,false,'FYERS');
 assert.equal(view.underlying,'NSE:RELIANCE-EQ');assert.equal(view.base,123/12);assert.equal(view.owned,position);
 assert.equal(chartContracts({underlying:position.underlying,contracts:{CE:{symbol:'NEW-PREVIEW'}}},heartbeat,position.underlying).CE,position);
});


test('active and retained owned chart timeframe stays captured while draft timeframe changes',()=>{
 const {chartView}=require('../renko-ai-options.js');
 const position={underlying:'NSE:NIFTY50-INDEX',option_type:'CE',spot_brick:400/12};
 const result=chartView({underlying:'NSE:RELIANCE-EQ',reference:50,timeframe:'30 minutes',route:'DIRECT'},{position,timeframe:1},false,'FYERS');
 assert.equal(result.timeframe,'30 minutes');assert.equal(result.frozen,false);assert.equal(result.owned,position);
 const same=chartView({underlying:position.underlying,reference:50,timeframe:'30 minutes',route:'OPTIONS'},{position,timeframe:1},true,'FYERS');assert.equal(same.timeframe,'1 minute');assert.equal(same.base,400/12);
});

test('official native reference cannot outlive its calculation lease',()=>{
 const {verifiedReference,sizingContext}=require('../renko-ai-options.js');
 const r={broker_symbol:'ETHUSD',status:'VERIFIED_OFFICIAL_NATIVE',parent_hours:23,atr_length:7,native_box:100,native_provider:'TRADINGVIEW',chart_session:'Regular trading hours',valid_until:1001,completed_parent_at:900};
 const ctx=sizingContext('ETHUSD','DELTA_INDIA');
 assert.equal(verifiedReference({native_references:[r]},'ETHUSD',ctx,1000),r);
 assert.equal(verifiedReference({native_references:[r]},'ETHUSD',ctx,1002),null);
});

test('manual entry binds the displayed draft to the exact active runtime context',()=>{
 const {manualEntryPayload}=require('../renko-ai-options.js');
 const account={id:'owner',broker:'DELTA_INDIA'},fields={underlying:'BTCUSD',execution:'PAPER',route:'DIRECT',timeframe:'5 minutes'};
 const context={account_id:'owner',broker:'DELTA_INDIA',underlying:'BTCUSD',mode:'PAPER',route:'DIRECT',timeframe:5,run_id:'run',runtime_session:'session'};
 const state={running:true,manual_entry_ready:true,manual_entry_context:context,heartbeat:{position:null,pending:null}};
 assert.deepEqual(manualEntryPayload(state,fields,account,'LONG','a'.repeat(32)),{...context,direction:'LONG',request_id:'a'.repeat(32)});
 for(const change of [{underlying:'ETHUSD'},{execution:'LIVE'},{timeframe:'1 minute'},{route:'OPTIONS'}])assert.throws(()=>manualEntryPayload(state,{...fields,...change},account,'LONG','a'.repeat(32)),/differs/);
 for(const change of [{running:false},{manual_entry_ready:false},{heartbeat:{position:{symbol:'BTCUSD'}}},{heartbeat:{pending:{id:'unknown'}}}])assert.throws(()=>manualEntryPayload({...state,...change},fields,account,'LONG','a'.repeat(32)),/ready/);
 assert.throws(()=>manualEntryPayload(state,fields,{...account,id:'other'},'LONG','a'.repeat(32)),/differs/);
 assert.throws(()=>manualEntryPayload(state,fields,account,'CE','a'.repeat(32)),/direction/);
});

test('selection sync discards late results and leaves both surfaces unchanged on cancellation',async()=>{
 const {SelectionSync}=require('../renko-ai-options.js'),sync=new SelectionSync(),applied=[];
 let resolve;
 const older=sync.change({symbol:'ETHUSD'},()=>new Promise(r=>resolve=r),next=>applied.push(next.symbol));
 await sync.change({symbol:'BTCUSD'},async()=>true,next=>applied.push(next.symbol));
 resolve(true);assert.equal(await older,false);assert.deepEqual(applied,['BTCUSD']);
 assert.equal(await sync.change({symbol:'OTHER'},async()=>false,next=>applied.push(next.symbol)),false);
 assert.deepEqual(applied,['BTCUSD']);
});

test('explicit broker expiry is sent through Paper and Live without changing automatic default',()=>{
 for(const execution of ['PAPER','LIVE']){
  const p=configuration({...fields,execution,expiry:'1999999999'},{id:'owner',broker:'FYERS'});
  assert.equal(p.ai_expiry_policy,'explicit_listed');assert.equal(p.ai_expiry,'1999999999');
  assert.equal(configuration({...fields,execution,expiry:''},{id:'owner',broker:'FYERS'}).ai_expiry_policy,'nearest_tradable');
 }
});
test('A failed worker snapshot still delivers valid sizing while transport and action errors reject',()=>{
 const {responseError}=require('../renko-ai-options.js');
 const failed={running:false,phase:'FAILED',error:'Worker failed before streaming',native_references:[{native_box:400}]};
 assert.equal(responseError(failed,true),null);
 assert.equal(responseError(failed,false),failed.error);
 assert.equal(responseError({error:'Wrong account'},true),'Wrong account');
 assert.equal(responseError({running:false,phase:'STOPPED',error:null},true),null);
});

test('option entry source is explicit in Paper and Live and never inferred from SMA',()=>{
 for(const execution of ['PAPER','LIVE']){
  assert.equal(configuration({...fields,execution,underlyingEntry:true},{id:'owner',broker:'FYERS'}).ai_entry_source,'UNDERLYING');
  assert.equal(configuration({...fields,execution,underlyingEntry:false,smaEntry:true,smaExit:true},{id:'owner',broker:'FYERS'}).ai_entry_source,'PREMIUM');
 }
});

test('AI embedded reload retains renamed and modified indicators without duplicates',()=>{
 const source=fs.readFileSync('chart-workspace.js','utf8'),start=source.indexOf("    if (embeddedRenko && linkedChart.aiRenko === '1'");
 const block=source.slice(start,source.indexOf('    if (restoreView)',start));
 const managedAiRenkoPineSource=brick=>'generated-'+brick;
 for(const custom of [false,true]){
  const study={kind:'Pine',name:'AR-Supertrend',strategyManaged:true,source:custom?'modified script':'generated-8',inputs:{in_0:7,in_3:8},hidden:true};
  const settings={studies:[study]};
  vm.runInNewContext(source.slice(source.indexOf('  function aiIndicatorInputsMatch('),source.indexOf('  function aiIndicatorSourceMatches('))+block,{completedBrickSignalView:()=>false,window:{},document:{documentElement:{dataset:{}}},aiRuntimeParams:new URLSearchParams(),settings,embeddedRenko:true,linkedChart:{aiRenko:'1',method:'fixed',brick:'10'},Number,managedAiRenkoPineSource,aiIndicatorSourceMatches:(source,brick)=>source===managedAiRenkoPineSource(brick)});
  assert.equal(settings.studies.length,1);assert.equal(settings.studies[0],study);assert.equal(study.name,'AR-Supertrend');assert.equal(study.hidden,true);
  assert.equal(study.inputs.in_0,7);assert.equal(study.source,custom?'modified script':'generated-10');assert.equal(study.inputs.in_3,custom?8:10);
 }
});

test('renamed draft indicator carries into a new run without changing source or account scope',()=>{
 const source=fs.readFileSync('chart-workspace.js','utf8'),start=source.indexOf("    if (embeddedRenko && linkedChart.aiRenko === '1'");
 const block=source.slice(start,source.indexOf('    if (restoreView)',start));
 const custom={kind:'Pine',name:'AR-Supertrend',strategyManaged:true,source:'user modified source',inputs:{in_3:8}};
 const storage=new Map([['sector-pulse:chart-workspace:user:renko:ai-draft-0:workspace',JSON.stringify({symbol:'NIFTY',studies:[custom]})]]);
 const settings={studies:[]};
 vm.runInNewContext(source.slice(source.indexOf('  function aiIndicatorInputsMatch('),source.indexOf('  function aiIndicatorSourceMatches('))+block,{completedBrickSignalView:()=>false,window:{},document:{documentElement:{dataset:{}}},aiRuntimeParams:new URLSearchParams(),settings,embeddedRenko:true,linkedChart:{aiRenko:'1',method:'fixed',brick:'10',chartInstance:'ai-run-0'},Number,structuredClone,managedAiRenkoPineSource:b=>'generated-'+b,aiIndicatorSourceMatches:(source,brick)=>source==='generated-'+brick,chartStoragePrefix:'sector-pulse:chart-workspace:user:renko:ai-run-0:',chartSymbol:()=> 'NIFTY',context:{username:'user',workspace:{id:'workspace'}},aiRuntimeParams:new URLSearchParams({chartSource:'owner',aiRun:'run'}),readChartSnapshot:k=>storage.get(k)||null,durableChartSnapshots:new Map(),localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)}});
 assert.equal(settings.studies.length,1);assert.equal(settings.studies[0].name,'AR-Supertrend');assert.equal(settings.studies[0].source,'user modified source');
 assert.ok(storage.has('sector-pulse:chart-workspace:user:ai-indicator:owner:NIFTY'));
});

test('shared signal choice defaults to underlying and carries through both Paper and Live',()=>{
 for(const execution of ['PAPER','LIVE']){
  assert.equal(configuration({...fields,execution},{id:'owner',broker:'FYERS'}).ai_signal_source,'UNDERLYING');
  assert.equal(configuration({...fields,execution,underlyingSignals:false},{id:'owner',broker:'FYERS'}).ai_signal_source,'PREMIUM');
 }
});

test('AI workspace preserves the explicitly selected display mode and captured geometry',()=>{
 const {selectionFrameUrl}=require('../renko-ai-options.js');
 const base='https://example.test/?chartContext=renko&chartSource=owner&chartInstance=ai-run-0&aiRenko=1&aiRun=run&type=Renko&brick=33.333333333333336&method=fixed';
 const u=new URL(selectionFrameUrl({dataset:{},getAttribute:()=>null},base,()=> 'navigation'));
 assert.equal(u.searchParams.get('type'),'Renko');assert.equal(u.searchParams.get('brick'),'33.333333333333336');assert.equal(u.searchParams.get('aiRun'),'run');assert.equal(u.searchParams.get('method'),'fixed');
});

test('SMA-only selection reaches configuration and does not gate on Supertrend multiplier',()=>{
 const p=configuration({...fields,supertrend:false,factor:0},{id:'owner',broker:'FYERS'});
 assert.equal(p.ai_supertrend_enabled,false);
 assert.equal(configuration(fields,{id:'owner',broker:'FYERS'}).ai_supertrend_enabled,true);
});

test('AI mutations carry the current workspace CSRF token while reads stay GET',()=>{
 const {aiRequestOptions}=require('../renko-ai-options.js');
 const opts=aiRequestOptions({account_id:'account',read_only:true},{csrf:'fixture-token'});
 assert.equal(opts.method,'POST');assert.equal(opts.headers['X-CSRF-Token'],'fixture-token');
 assert.deepEqual(JSON.parse(opts.body),{account_id:'account',read_only:true});
 assert.equal(aiRequestOptions(undefined,{csrf:'fixture-token'}),undefined);
 assert.equal(aiRequestOptions({read_only:true},null).headers['X-CSRF-Token'],'');
});

test('missing workspace CSRF is loaded once from the authenticated portal without retrying an action',async()=>{
 const {createAiContextLoader}=require('../renko-ai-options.js');let calls=0;
 const load=createAiContextLoader(async(url,options)=>{calls++;assert.equal(url,'/api/workspaces/me');assert.equal(options.cache,'no-store');return {ok:true,json:async()=>({username:'alice',csrf:'fixture-token'})};});
 const results=await Promise.all([load({username:'alice'}),load({username:'alice'})]);
 assert.equal(calls,1);assert.equal(results[0].csrf,'fixture-token');
 await assert.rejects(load({username:'bob'}),/user changed/);
 assert.equal((await load({username:'alice',csrf:'current-token'})).csrf,'current-token');assert.equal(calls,1);
});
test('missing or expired authenticated session cannot prepare an AI mutation',async()=>{
 const {createAiContextLoader}=require('../renko-ai-options.js');
 await assert.rejects(createAiContextLoader(async()=>({ok:false}))(null),/Sign in/);
 await assert.rejects(createAiContextLoader(async()=>({ok:true,json:async()=>({username:'alice'})}))(null),/session verification/);
});

test('Dhan direct selection defaults to Intraday and maps native ids to the correct sizing market',()=>{
 const {sizingContext}=require('../renko-ai-options.js');
 const p=configuration({...fields,underlying:'NSE_FNO:123',route:'DIRECT',product:''},{id:'owner',broker:'DHAN'});
 assert.equal(p.ai_product,'INTRADAY');assert.equal(p.ai_market,'NSE');assert.equal(p.ai_execution_route,'DIRECT');
 assert.equal(sizingContext('MCX_COMM:123','DHAN').parentHours,14);
 assert.equal(sizingContext('BSE_EQ:123','DHAN').parentHours,6);
 assert.throws(()=>configuration({...fields,underlying:'NSE_EQ:123',route:'DIRECT',product:'CNC'},{id:'owner',broker:'DHAN'}),/Dhan product/);
});

test('Dhan cash markets are enabled only in the AI direct route',()=>{
 const source=fs.readFileSync('renko-ai-options.js','utf8');
 const begin=source.indexOf(' function directMarketChoices(){'),end=source.indexOf('\n function show(){',begin);
 const options=[{value:'NSE_EQUITY',disabled:true},{value:'BSE_EQUITY',disabled:true},{value:'MCX',disabled:false}];
 let route='DIRECT',mode={value:'AI'},broker='DHAN';
 const sandbox={selected:()=>({broker}),mode,MODE:'AI',values:()=>({route}),document:{getElementById:()=>({options})}};
 vm.createContext(sandbox);vm.runInContext(source.slice(begin,end),sandbox);
 sandbox.directMarketChoices();assert.equal(options[0].disabled,false);assert.equal(options[1].disabled,false);assert.equal(options[2].disabled,false);
 route='OPTIONS';sandbox.directMarketChoices();assert.equal(options[0].disabled,true);
 route='DIRECT';mode.value='SIMPLE_BRICK';sandbox.directMarketChoices();assert.equal(options[1].disabled,true);
 assert.match(source,/event.target.value==='DIRECT'&&\['FYERS','DHAN','MOTILAL_OSWAL'\].includes\(selected\(\)\?\.broker\)&&!snapshot\?\.running/);
});

test('AI search preserves route and market parameters while scoping runner identity',()=>{
 const {aiActionUrl}=require('../renko-ai-options.js');
 const u=new URL(aiActionUrl('search?'+new URLSearchParams({q:'PI Industries',market:'NSE_STOCK',route:'OPTIONS'}),'NSE:PIIND'),'https://example.test');
 assert.equal(u.searchParams.get('q'),'PI Industries');
 assert.equal(u.searchParams.get('market'),'NSE_STOCK');
 assert.equal(u.searchParams.get('route'),'OPTIONS');
 assert.equal(u.searchParams.get('runner_symbol'),'NSE:PIIND');
 assert.equal(new URL(aiActionUrl('status','NSE:NIFTY'),'https://example.test').searchParams.get('runner_symbol'),'NSE:NIFTY');
});

test('explicit market selection survives instrument settings restoration',()=>{
 const {restoredInstrumentValues}=require('../renko-ai-options.js');
 assert.equal(restoredInstrumentValues({}, {instrument_market:'ALL'}, 'NSE:NIFTY','NSE_INDEX').instrument_market,'NSE_INDEX');
});

test('optional Bull Bear and daily loss fields default off and retain precision',()=>{
 const account={id:'owner',broker:'FYERS'};
 const disabled=configuration(fields,account);
 for(const k of ['ai_bull_entry_level','ai_bear_entry_level','ai_daily_max_loss'])assert.equal(disabled[k],null);
 const configured=configuration({...fields,bullEntryLevel:'100.123456789',bearEntryLevel:'90.987654321',dailyMaxLoss:'123.45'},account);
 assert.equal(configured.ai_bull_entry_level,100.123456789);assert.equal(configured.ai_bear_entry_level,90.987654321);assert.equal(configured.ai_daily_max_loss,123.45);
});

test('Midline display follows effective strategy filter, including captured active settings',()=>{
 const {midlineDisplayEnabled}=require('../renko-ai-options.js');
 assert.equal(midlineDisplayEnabled(null,{}),false);
 assert.equal(midlineDisplayEnabled(null,{midlineEnabled:true}),true);
 assert.equal(midlineDisplayEnabled(null,{midlineEnabled:true,supertrend:false}),false);
 assert.equal(midlineDisplayEnabled({running:true,midline_filter_enabled:false},{midlineEnabled:true}),false);
 assert.equal(midlineDisplayEnabled({running:true,midline_filter_enabled:true},{midlineEnabled:false}),true);
 assert.equal(midlineDisplayEnabled({running:true,midline_filter_enabled:true,supertrend_enabled:false}),false);
});
