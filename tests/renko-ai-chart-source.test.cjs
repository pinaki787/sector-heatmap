const fs=require('node:fs'),vm=require('node:vm');
const test=require('node:test'),assert=require('node:assert/strict');
const {context,request,verify,quote}=require('../renko-ai-chart-source.js');
const href='https://example.test/?chartContext=renko&aiRenko=1&aiRun=verification-seed&chartSource='+('a'.repeat(32))+'&interval=1&brick=2';
const payload={account:'a'.repeat(32),run_id:'verification-seed',symbol:'EXACT',frame:1,brick:2,source_basis:'PROVIDER_CONFIRMED_CLOSE_ONLY',ohlc_available:false,rows:[[120,null,null,null,4,null]]};
test('standalone and draft charts retain ordinary broker requests',()=>{
 assert.equal(context('https://example.test/?chartContext=renko&aiRenko=1'),null);
 assert.equal(request('/api/chart-workspace/history?interval=1','https://example.test/','EXACT'),null);
});
test('owned run uses exact captured history and excludes independently reconstructed live candles',()=>{
 assert.equal(request('/api/chart-workspace/history?interval=1&after=60',href,'EXACT').path,'/api/renko-supertrend/ai-options/chart-source?run_id=verification-seed&symbol=EXACT&frame=1&after=60');
 assert.equal(request('/api/chart-workspace/live?interval=1',href,'EXACT').path,'/api/chart-workspace/live?interval=1&price_only=1');
 const frame={symbol:'EXACT',connected:true,latest_tick:120,latest_price:4.5,rows:[[120,4,5,3,4.5,20]],private_unused:'omit'};
 const result=quote(frame,href,'EXACT');assert.deepEqual(result.rows,[]);assert.equal(result.latest_price,4.5);assert.equal(result.private_unused,undefined);assert.equal(frame.rows.length,1);
 assert.throws(()=>quote({...frame,symbol:'OTHER'},href,'EXACT'),/different/);
 assert.throws(()=>request('/api/chart-workspace/history?interval=5',href,'EXACT'),/retain/);
});
test('runtime chart rejects a different account, contract, frame, brick or fabricated OHLC',()=>{
 assert.equal(verify(payload,href,'EXACT'),payload);
 for(const changed of [{account:'b'.repeat(32)},{symbol:'OTHER'},{frame:5},{brick:3},{rows:[[120,4,4,4,4,null]]}])assert.throws(()=>verify({...payload,...changed},href,'EXACT'));
});


test('consumed link retains only its original exact run/account frozen source inputs',()=>{
 const fs=require('node:fs'),vm=require('node:vm');
 const browser={location:{href},URL,module:{exports:{}}};browser.globalThis=browser;
 vm.runInNewContext(fs.readFileSync('renko-ai-chart-source.js','utf8'),browser);
 const shortened='https://example.test/?chartContext=renko&aiRun=verification-seed&chartSource='+('a'.repeat(32));
 assert.equal(browser.module.exports.context(shortened).brick,2);
 assert.equal(browser.module.exports.context(shortened).frame,1);
 assert.equal(browser.module.exports.context(shortened.replace('verification-seed','other-run')),null);
});


test('runtime link retains frozen source parameters through chart address cleanup',()=>{
 const fs=require('node:fs'),vm=require('node:vm');
 const source=fs.readFileSync('chart-workspace.js','utf8'),start=source.indexOf('      const runtimeSourceLink='),end=source.indexOf('url.searchParams.delete(param);',start)+'url.searchParams.delete(param);'.length;
 const code=source.slice(start,end);
 const url=new URL(href+'&symbol=EXACT&type=Renko&chartInstance=fixture');
 vm.runInNewContext(code,{url,embeddedScope:'owned',sharedChartParameters:['aiRenko','brick','interval','symbol','type','chartContext','chartInstance']});
 assert.equal(url.searchParams.get('brick'),'2');assert.equal(url.searchParams.get('interval'),'1');assert.equal(url.searchParams.get('aiRenko'),'1');
});

test('Line remains independent while owned Candles and Renko request captured source',()=>{
 for(const type of ['Line']){
  assert.equal(request('/api/chart-workspace/history?interval=1',href,'EXACT',type),null);
  assert.equal(request('/api/chart-workspace/live?interval=1',href,'EXACT',type),null);
 }
 assert.match(request('/api/chart-workspace/history?interval=1',href,'EXACT','Renko').path,/chart-source/);
});

test('Renko and Candles display reuse the identical captured OHLC without source reload',()=>{
 const source=fs.readFileSync('chart-workspace.js','utf8'),begin=source.indexOf('  const aiDisplayHistories=new Map();'),end=source.indexOf('  async function brokerJson(',begin);
 const rows=[{time:1,open:10,high:14,low:8,close:12}],history=new Map([['1',rows]]);
 let clears=0;
 const context=vm.createContext({window:{RenkoAiChartSource:{context:()=>({account:'owner',run:'run'})}},location:{href},history,panel:{querySelector:()=>null},clearInstrumentData:()=>clears++});
 vm.runInContext(source.slice(begin,end),context);
 for(const [a,b] of [['Candles','Renko'],['Renko','Candles'],['Candles','Line']]){
  assert.equal(context.switchAiDisplayBasis(a,b),false);assert.equal(history.get('1'),rows);
 }
 assert.equal(clears,0);assert.equal(rows[0].high,14);
});

test('deferred chart bootstraps survive dashboard body replacement',()=>{
 const html=fs.readFileSync('index.html','utf8'),head=html.slice(0,html.indexOf('</head>'));
 for(const asset of ['chart-workspace.js','chart-workspace-studies.js','renko-ai-options.js']){
  assert.ok(head.includes('/'+asset+'?'),asset+' must be loaded from the retained head');
 }
});
test('AI view restores only after matching account context is ready and never starts a runner',()=>{
 const src=fs.readFileSync('renko-ai-options.js','utf8'),start=src.indexOf(' function restoreAiView(){'),end=src.indexOf(' function strategySectionEntry(){',start);
 const block=src.slice(start,end)+';restoreAiView();';
 function check(ready,account,saved){
  const calls=[],mode={value:'SUPERTREND',dispatchEvent:e=>calls.push(e.type)};
  vm.runInNewContext(block,{section:{dataset:{aiContextReady:ready}},strategySectionVisible:()=>true,strategyVisit:{selected:()=>'AI_RENKO_OPTIONS'},applyingViewDefault:false,selected:()=>account,localStorage:{getItem:()=>saved},MODE:'AI_RENKO_OPTIONS',mode,restoredDraftAccount:null,restore:()=>calls.push('restore'),show:()=>{},refreshStatus:()=>{},Event:class{constructor(type){this.type=type;}}});
  return {mode:mode.value,calls};
 }
 assert.equal(check('0',{id:'a'},'AI_RENKO_OPTIONS').mode,'SUPERTREND');
 assert.equal(check('1',null,'AI_RENKO_OPTIONS').mode,'SUPERTREND');
 assert.deepEqual(check('1',{id:'a'},'AI_RENKO_OPTIONS'),{mode:'AI_RENKO_OPTIONS',calls:['change']});
 assert.equal(check('1',{id:'a'},'SUPERTREND').mode,'AI_RENKO_OPTIONS');
});

test('AI Heikin Ashi keeps broker OHLC indicator source without false synthetic-bar invalidation',()=>{
 const source=fs.readFileSync('chart-workspace.js','utf8'),start=source.indexOf('  function pineChartType('),end=source.indexOf('  function pineSyntheticHostBar(',start);
 const code=source.slice(start,end)+';result=pineChartType(type);';
 for(const type of ['Candles','Line','Heikin Ashi']){
  const context={completedBrickSignalView:()=>false,settings:{type},type,aiSelectionParams:new URLSearchParams('aiRenko=1')};vm.runInNewContext(code,context);assert.equal(context.result,'Candles');
 }
 const ordinary={completedBrickSignalView:()=>false,settings:{type:'Heikin Ashi'},type:'Heikin Ashi',aiSelectionParams:new URLSearchParams()};vm.runInNewContext(code,ordinary);assert.equal(ordinary.result,'Heikin Ashi');
 assert.ok(source.includes("(isHeikinAshi && result.chartType === 'Heikin Ashi')"));
});

test('refresh retains only an exact unchanged account-bound attachment',()=>{
 const {retainAttachment}=require('../renko-ai-options.js'),previous={account:'a',underlying:'NIFTY',symbol:'EXACT',product:'MARGIN',quantity:65};
 const rows=[{symbol:'EXACT',product:'MARGIN',quantity:65,average_price:44}];
 assert.equal(retainAttachment(previous,rows,'a','NIFTY').average_price,44);
 assert.equal(retainAttachment(previous,rows,'b','NIFTY'),null);
 assert.equal(retainAttachment(previous,rows,'a','OTHER'),null);
 assert.equal(retainAttachment(previous,[{...rows[0],quantity:130}],'a','NIFTY'),null);
 assert.equal(retainAttachment(previous,[],'a','NIFTY'),null);
});

test('option multiplier is selected by classification and never premium price',()=>{
 const {optionMultiplier,configuration}=require('../renko-ai-options.js');
 assert.equal(optionMultiplier('OTM'),.25);assert.equal(optionMultiplier('ATM'),.5);
 assert.throws(()=>optionMultiplier('UNKNOWN'));
 for(const premium of ['5','40','100','500'])for(const moneyness of ['OTM','ATM']){
  const payload=configuration({underlying:'NSE:NIFTY50-INDEX',route:'OPTIONS',execution:'LIVE',timeframe:'5 minutes',premium,moneyness,lots:'1',product:'MARGIN'}, {id:'owner',broker:'FYERS'});
  assert.equal(payload.ai_option_moneyness,moneyness);
 }
});

test('Candles and Renko share exact captured real OHLC initialization',()=>{
 const candles={...payload,source_basis:'PROVIDER_CONFIRMED_OHLC',ohlc_available:true,rows:[[120,4,5,3,4.5,12]]};
 assert.equal(request('/api/chart-workspace/history?interval=1',href,'EXACT','Candles').kind,'history');
 assert.equal(verify(candles,href,'EXACT'),candles);
 assert.throws(()=>verify({...candles,rows:[[120,4,3,5,4.5,12]]},href,'EXACT'));
 assert.equal(request('/api/chart-workspace/history?interval=1',href,'EXACT','Renko').kind,'history');
});

test('study compatibility permits a display rename but rejects a changed formula or sizing literal',()=>{
 const vm=require('node:vm'),fs=require('node:fs');
 const text=fs.readFileSync('chart-workspace.js','utf8');
 const fn=text.match(/  function aiIndicatorSourceMatches\(source,brick\)\{[\s\S]*?\n  \}/)[0];
 const expected='//@version=6\nindicator("AI Renko Supertrend", shorttitle="AI Renko", overlay=true)\nfloat autoBox = 7.142857142857143\nvalue = source + 1';
 const scope={managedAiRenkoPineSource:()=>expected};vm.runInNewContext(fn+';this.matches=aiIndicatorSourceMatches',scope);
 assert.equal(scope.matches(expected,7.14),true);
 assert.equal(scope.matches(expected.replace('AI Renko Supertrend','AR-Supertrend').replace('shorttitle="AI Renko"','shorttitle="AR-Supertrend"'),7.14),true);
 assert.equal(scope.matches(expected.replace('source + 1','source + 2'),7.14),false);
 assert.equal(scope.matches(expected.replace('7.142857142857143','7.14'),7.14),false);
});
