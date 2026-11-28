const test=require('node:test'),assert=require('node:assert/strict');
const {verifiedManagedStop}=require('../renko-ai-options.js');
const {stopLine}=require('../renko-ai-chart-markers.js');
function sample(){
 const grid={high:59847,low:59744,origin_at:100,available_at:200,source_frame:30,session:1};
 return {running:true,run_id:'run1',underlying:'BTCUSD',heartbeat:{at:new Date(1000000).toISOString(),runtime_session:'session1',position_control:{mode:'MANAGED',entries_paused:false},position:{symbol:'BTCUSD',execution_route:'DIRECT',quantity:20,side:'SHORT',order_id:'123',fill_price:59415.5,target_grid:grid},zone_policy:{revision:'opposing-structure-zone-v1',ladder:{grid,entry:59415.5,direction:'SHORT',achieved:1,stop:59415.5}}}};
}
test('only fresh exact managed active stop is published, with full numeric precision',()=>{
 const s=sample();s.heartbeat.zone_policy.ladder.stop=59332.123456;
 const stop=verifiedManagedStop(s,'BTCUSD',1001);
 assert.equal(stop.price,59332.123456);assert.equal(stop.broker_resting,false);
 const line=stopLine(stop,s.heartbeat.position,'BTCUSD',1001);
 assert.equal(line.title,'Strategy stop 59,332.12');assert.equal(line.price,59332.123456);
});
test('flat, pending, stale, detached, missing grid, wrong entry or symbol suppress stop',()=>{
 for(const change of [s=>s.running=false,s=>s.heartbeat.position=null,s=>s.heartbeat.pending={id:1},s=>s.heartbeat.at=new Date(900000).toISOString(),s=>s.heartbeat.position_control.mode='DETACHED',s=>s.heartbeat.position.target_grid=null,s=>s.heartbeat.zone_policy.ladder.entry=1,s=>s.heartbeat.zone_policy=null,s=>s.heartbeat.source_health={entries_blocked:true}]){
  const s=sample();change(s);assert.equal(verifiedManagedStop(s,'BTCUSD',1001),null);
 }
 assert.equal(verifiedManagedStop(sample(),'PAXGUSD',1001),null);
});
test('chart rejects stale, wrong order, different contract and inferred/native stops',()=>{
 const s=sample(),v=verifiedManagedStop(s,'BTCUSD',1001);
 for(const changes of [{verified_at:900},{order_id:'OTHER'},{symbol:'OTHER'},{kind:'THEORETICAL'},{broker_resting:true}])assert.equal(stopLine({...v,...changes},s.heartbeat.position,'BTCUSD',1001),null);
});
test('provisional Supertrend extension carries confirmed value without altering signal bars',()=>{
 const {mountCompletedRenkoProjection}=require('../chart-renko-study-alignment.js');
 const confirmed=[{index:4,time:4,sourceTime:100,open:110,high:110,low:100,close:100,st:120,direction:1}];
 const before=JSON.stringify(confirmed),lines=[],candles=[];
 const chart={addCandlestickSeries:()=>({setData:x=>candles.push(x),update:x=>candles.push(x)}),addLineSeries:()=>{const s={points:[],applyOptions(){},setData(x){this.points=x;}};lines.push(s);return s;}};
 const p=mountCompletedRenkoProjection({chart,getBars:()=>confirmed,size:10,enabled:()=>true,showSupertrend:()=>true});
 p.update(96,101);assert.equal(lines.length,1);assert.deepEqual(lines[0].points,[{time:4,value:120},{time:5,value:120}]);assert.equal(JSON.stringify(confirmed),before);
 p.update(97,102);assert.equal(lines.length,1);assert.equal(lines[0].points.at(-1).value,120);
 p.update(100,103);assert.deepEqual(lines[0].points,[]);
});
test('draft Supertrend extension reuses newly published matching value at unchanged live price',()=>{
 const {mountCompletedRenkoProjection}=require('../chart-renko-study-alignment.js');
 const bars=[{time:4,sourceTime:100,open:110,high:110,low:100,close:100}];
 const before=JSON.stringify(bars),lines=[];let ref=null,publication;
 const chart={addCandlestickSeries:()=>({setData(){},update(){}}),addLineSeries:()=>{const x={points:[],setData(v){this.points=v;},applyOptions(){}};lines.push(x);return x;}};
 const p=mountCompletedRenkoProjection({chart,getBars:()=>bars,size:10,showSupertrend:()=>true,getSupertrend:()=>ref,onSupertrendExtension:s=>publication=s});
 p.update(96,101);assert.equal(lines.length,0);assert.equal(publication.state,'WAITING_FOR_MATCHING_COMPLETED_SUPERTREND');
 ref={value:120.123456,color:'#e53935',index:4};p.refresh();
 assert.equal(lines.length,1);assert.equal(lines[0].points.at(-1).value,120.123456);
 assert.equal(publication.state,'MATCHED_COMPLETED_VALUE');assert.equal(JSON.stringify(bars),before);
});
test('draft completed-brick cache ignores provisional quote changes and invalidates real completed history revisions',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),s=fs.readFileSync('chart-workspace.js','utf8');
 const start=s.indexOf('  let completedPreviewCache;'),end=s.indexOf('  function completedBrickSignalView()',start);
 const completed=[{time:1,close:100},{time:2,close:101}],history=new Map([['1',completed]]);
 let calls=0;
 const c={history,rows:[...completed,{time:3,close:102,provisional:true}],settings:{interval:'1',size:10},chartPrefix:'broker-account-a',chartSymbol:()=> 'BTCUSD',aiSelectionParams:new URLSearchParams('brick=10'),renko:(source)=>{calls++;return source.map(x=>({...x}));}};
 vm.createContext(c);vm.runInContext(s.slice(start,end),c);
 vm.runInContext('completedPreviewSignalBars()',c);
 for(let i=0;i<100;i++){c.rows.at(-1).close=102+i;vm.runInContext('completedPreviewSignalBars()',c);}
 assert.equal(calls,1);
 history.set('1',[...completed,{time:3,close:103}]);vm.runInContext('completedPreviewSignalBars()',c);assert.equal(calls,2);
 history.set('1',[{time:0,close:99},...history.get('1')]);vm.runInContext('completedPreviewSignalBars()',c);assert.equal(calls,3);
 history.set('1',history.get('1').map(x=>x.time===1?{...x,close:100.5}:x));vm.runInContext('completedPreviewSignalBars()',c);assert.equal(calls,4);
 c.chartPrefix='broker-account-b';vm.runInContext('completedPreviewSignalBars()',c);assert.equal(calls,5);
});
