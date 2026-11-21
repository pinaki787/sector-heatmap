const test=require('node:test'),assert=require('node:assert/strict');
const {configuration}=require('../renko-ai-options.js');
const fields={underlying:'NSE:NIFTY50-INDEX',reference:'400',lots:'1',expiry:'1795428600',session:'2026-11-19',evidence:'fixture',timeframe:'30 minutes',execution:'PAPER',product:'MARGIN',premium:'40'};
test('AI UI configuration selects the actual dedicated options runtime',()=>{
 const p=configuration(fields,{id:'owner',broker:'FYERS'});assert.equal(p.strategy_mode,'AI_RENKO_OPTIONS');assert.equal(p.ai_sma_exit_enabled,false);assert.equal(p.ai_reference_value,400);assert.equal(p.timeframe,'30 minutes');assert.equal(p.target_premium,40);assert.equal(p.underlying,'NSE:NIFTY50-INDEX');
});
test('AI mode cannot redirect another broker or invent quantity/reference',()=>{
 assert.throws(()=>configuration(fields,{id:'owner',broker:'DELTA_INDIA'}),/supported/);
 assert.throws(()=>configuration({...fields,lots:''},{id:'owner',broker:'FYERS'}),/whole lots/);
 assert.throws(()=>configuration({...fields,reference:''},{id:'owner',broker:'FYERS'}),/verified/);
});

const fs=require('node:fs'),vm=require('node:vm');
const chartSource=fs.readFileSync('chart-workspace.js','utf8');
const blockStart=chartSource.indexOf("    if (embeddedRenko && linkedChart.aiRenko === '1'");
const scopedBlock=chartSource.slice(blockStart,chartSource.indexOf('    if (restoreView)',blockStart));
test('fixed indicator input override is isolated to the AI strategy embedded context',()=>{
 for(const [embeddedRenko,aiRenko] of [[false,'1'],[true,'0']]){
  const study={kind:'Pine',name:'AI Renko Supertrend',inputs:{in_2:'Auto'}};const settings={studies:[study]};
  vm.runInNewContext(scopedBlock,{embeddedRenko,linkedChart:{aiRenko,method:'fixed',brick:'20.833333333333332'},settings,aiRenkoPineSource:()=>'',Number});
  assert.equal(settings.studies[0],study);assert.equal(study.inputs.in_2,'Auto');
 }
 const settings={studies:[]};vm.runInNewContext(scopedBlock,{embeddedRenko:true,linkedChart:{aiRenko:'1',method:'fixed',brick:'20.833333333333332'},settings,aiRenkoPineSource:()=>'',Number});
 assert.equal(settings.studies[0].inputs.in_2,'Manual');assert.equal(settings.studies[0].inputs.in_3,250/12);
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
 for(const [underlying,broker,divisor] of [['NSE:CUPID-EQ','FYERS',12],['BSE:SENSEX-INDEX','FYERS',12],['BTCUSD','DELTA_INDIA',46],['MCX:GOLD26DECFUT','FYERS',44],['MCX:SILVER26DECFUT','FYERS',28]]){
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
test('owned underlying and brick stay pinned when the next-start draft changes',()=>{
 const held={underlying:'NSE:NIFTY50-INDEX',symbol:'HELD-CE',option_type:'CE',spot_brick:400/12};
 const view=chartView({underlying:'NSE:RELIANCE-EQ',reference:120,route:'DIRECT'},{position:held},true,'FYERS');
 assert.equal(view.underlying,'NSE:NIFTY50-INDEX');assert.equal(view.base,400/12);assert.equal(view.route,'OPTIONS');
 const direct=chartView({underlying:'ETHUSD',reference:1,route:'OPTIONS'},{position:{underlying:'BTCUSD',spot_brick:100,execution_route:'DIRECT'}},true,'DELTA_INDIA');
 assert.equal(direct.base,100);assert.equal(direct.route,'DIRECT');
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
 const ref={broker_symbol:symbol,status:'VERIFIED_TEST',native_box:460,parent_hours:23,atr_length:5,completed_parent_at:100000};
 assert.equal(verifiedReference({native_reference:ref},symbol,context,100001),ref);
 assert.equal(verifiedReference({native_reference:ref},symbol,context,99999),null);
 assert.equal(verifiedReference({native_reference:ref},symbol,context,200000),null);
});


test('pending exact intent pins its underlying and premium ahead of draft and new preview',()=>{
 const {chartView,chartContracts}=require('../renko-ai-options.js');
 const position={underlying:'NSE:NIFTY50-INDEX',symbol:'EXACT-PENDING-CE',option_type:'CE',spot_brick:400/12,option_brick:4,execution_route:'OPTIONS'};
 const heartbeat={pending:{intent:{position}}};
 const view=chartView({underlying:'NSE:RELIANCE-EQ',reference:123,route:'DIRECT'},heartbeat,false,'FYERS');
 assert.equal(view.underlying,position.underlying);assert.equal(view.base,position.spot_brick);assert.equal(view.route,'OPTIONS');
 assert.equal(chartContracts({underlying:position.underlying,contracts:{CE:{symbol:'NEW-PREVIEW'}}},heartbeat,position.underlying).CE,position);
});


test('active and retained owned chart timeframe stays captured while draft timeframe changes',()=>{
 const {chartView}=require('../renko-ai-options.js');
 const position={underlying:'NSE:NIFTY50-INDEX',option_type:'CE',spot_brick:400/12};
 const result=chartView({underlying:'NSE:RELIANCE-EQ',reference:50,timeframe:'30 minutes',route:'DIRECT'},{position,timeframe:1},false,'FYERS');
 assert.equal(result.timeframe,'1 minute');assert.equal(result.frozen,true);
});
