const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
const first=source.indexOf('  function twapAnchor(study) {'),last=source.indexOf('  function historyIntervals(interval) {',first);
assert.ok(first>=0&&last>first);
function fixture(){
 const scope={aborted:false},history=new Map(),liveStudyBars=new Map();
 const context={settings:{interval:'30',studies:[],hideStudies:false},validInterval:x=>/^[1-9]\d*(?:S|D|W|M)?$/.test(x),
 tickInterval:x=>/T$/.test(x),sourceInterval:()=>true,tradeInterval:x=>/[ST]$/.test(x),
 projectionIntervalSeconds:x=>/S$/.test(x)?parseInt(x):/D$/.test(x)?parseInt(x)*86400:Number(x)*60,
 history,liveStudyBars,requestScope:{signal:scope},barReplay:null,
 candleEnd:(t)=>new Map([[1000,19000],[19000,37000],[37000,55000],[33300,55800],[119700,142200]]).get(t)};
 vm.createContext(context);vm.runInContext(source.slice(first,last),context);
 return{c:context,scope,history,liveStudyBars,key:study=>context.twapBrokerAnchorKey(study)};
}
test('custom anchors use actual broker windows, including shortened sessions and gaps',()=>{
 const f=fixture();f.history.set('840',[{time:33300},{time:119700}]);
 const key=f.key({inputs:{anchor:'840'}});
 assert.equal(key({time:40000}),33300);assert.equal(key({time:60000}),undefined);
 assert.equal(key({time:120000}),119700);assert.equal(key({time:150000}),undefined);
});
test('custom higher-hour anchor includes only the current workspace live frame',()=>{
 const f=fixture();f.history.set('360',[{time:1000},{time:19000}]);
 f.liveStudyBars.set('360',{scope:{},candle:{time:37000,provisional:true}});
 assert.equal(f.key({inputs:{anchor:'360'}})({time:40000}),undefined);
 f.liveStudyBars.set('360',{scope:f.scope,candle:{time:37000,provisional:true}});
 assert.equal(f.key({inputs:{anchor:'360'}})({time:40000}),37000);
 assert.equal(f.key({inputs:{anchor:'360'}})({time:56000}),undefined);
});
test('synthetic chart coordinates resolve through the original source time',()=>{
 const f=fixture();f.history.set('360',[{time:1000},{time:19000}]);
 assert.equal(f.key({inputs:{anchor:'360'}})({time:7,sourceTime:20000}),19000);
});
test('same or shorter anchor resets at each source chart bar without unavailable lower-history dependencies',()=>{
 const f=fixture();const s={inputs:{anchor:'5'}};
 assert.equal(f.c.twapReferenceInterval(s),undefined);assert.equal(f.key(s)({time:1000}),1000);
 assert.equal(f.key(s)({time:4,sourceTime:1000}),1000);
});
test('calendar anchors use exchange metadata and all four requested custom hours request broker boundaries',()=>{
 const f=fixture();assert.equal(f.key({inputs:{anchor:'1D'}}),undefined);
 for(const anchor of ['360','840','1320','1380'])assert.equal(f.c.twapReferenceInterval({inputs:{anchor}}),anchor);
 assert.equal(f.c.twapAnchor({inputs:{anchor:'100T'}}),undefined);
});
test('TWAP anchor history is part of initial dependency loading',()=>{
 const f=fixture();f.c.settings.studies=[{kind:'TWAP',inputs:{anchor:'840'}}];
 Object.assign(f.c,{studyVisible:()=>true,calculationInterval:()=>undefined,indicators:{TWAP:{}},ratingTableIntervals:()=>[]});
 const body=source.match(/^  function historyIntervals\([\s\S]*?^  }/m)?.[0];assert.ok(body);
 vm.runInContext(body,f.c);assert.deepEqual([...f.c.historyIntervals('30')],['30','840']);
});
test('older chart pagination requests matching older TWAP anchor history',async()=>{
 const f=fixture();f.c.settings.studies=[{kind:'TWAP',inputs:{anchor:'840'}}];const calls=[];
 Object.assign(f.c,{studyVisible:()=>true,indicators:{TWAP:{}},olderHistory:new Set(['840']),generation:1,panel:{open:true},
 loadReferencedHistoryThrough:async(...args)=>{calls.push(args);return true},redrawKeepingViewport:()=>{},usesTickDelta:()=>false});
 const body=source.match(/^  async function loadOlderVolumeDeltaHistory\([\s\S]*?^  }/m)?.[0];assert.ok(body);
 vm.runInContext(body,f.c);await f.c.loadOlderVolumeDeltaHistory(1000,'30',1,f.scope);
 assert.equal(calls.length,1);assert.equal(calls[0][0],'840');assert.equal(calls[0][1],1000000);
});

test('first and rolled TWAP reference openings rebuild captured anchor keys; price updates stay incremental',async()=>{
 const f=fixture();let now=40000,frame,redraws=0,updates=0;
 Object.assign(f.c,{Date:{now:()=>now*1000},barReplay:null,settings:{interval:'30',studies:[{kind:'TWAP',inputs:{anchor:'360'}}]},
 studyVisible:()=>true,calculationInterval:()=>undefined,studyUsesFormingBar:()=>false,studyCanUseFormingBar:()=>true,
 ratingTableUsesForming:()=>false,indicators:{TWAP:{}},usesTickDelta:()=>false,generation:1,panel:{open:true},
 chartSymbol:()=>'ETHUSD',loadPineLiveFrame:async()=>frame,calendarInterval:()=>false,
 chartTickTimestamp:x=>x,deltaSymbolSelection:false,fyersSymbolSelection:false,motilalSymbolSelection:false,
 rows:[{time:39000,provisional:true}],pendingViewportRedraw:false,
 sameCandle:(a,b)=>JSON.stringify(a)===JSON.stringify(b),
 redrawKeepingViewport:()=>redraws++,updateLastPrice:()=>{updates++;return true}});
 const body=source.match(/^  async function refreshLiveStudyBars\([\s\S]*?^  }/m)?.[0];assert.ok(body);vm.runInContext(body,f.c);
 frame={connected:true,latest_tick:now,rows:[[37000,100,110,90,105,5]]};
 await f.c.refreshLiveStudyBars(1,'30',f.scope);assert.equal(redraws,1);assert.equal(updates,0);
 frame.rows[0][4]=106;await f.c.refreshLiveStudyBars(1,'30',f.scope);assert.equal(redraws,1);assert.equal(updates,1);
 now=56000;f.c.candleEnd=t=>t+18000;frame={connected:true,latest_tick:now,rows:[[55000,106,112,100,108,4]]};
 await f.c.refreshLiveStudyBars(1,'30',f.scope);assert.equal(redraws,2);assert.equal(updates,1);
 frame.connected=false;await f.c.refreshLiveStudyBars(1,'30',f.scope);assert.equal(redraws,3);
});
