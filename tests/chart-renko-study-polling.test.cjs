const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('.private/chart-order-rollouts/renko-study-pipeline-candidate-20261119/candidate.js','utf8');
function section(a,b){const x=source.indexOf(a),y=source.indexOf(b,x);assert.ok(x>=0&&y>x);return source.slice(x,y);}
function fixture(type='Renko'){
 const calls={loads:0,updates:0,draws:0},scope={aborted:false},study={kind:'SMA'},frame={connected:true,latest_tick:7999,rows:[[7200,10,12,9,11,2]]};
 const c={barReplay:null,settings:{type,studies:[study]},broker:{yahoo:false},studyVisible:()=>true,calculationInterval:()=> '60',studyUsesFormingBar:()=>false,studyCanUseFormingBar:()=>true,twapReferenceInterval:()=>undefined,indicators:{SMA:{}},ratingTableUsesForming:()=>false,chartSymbol:()=> 'ETHUSD',generation:1,panel:{open:true},Date:{now:()=>8000000},history:new Map([['60',[{time:3600}]]]),calendarInterval:()=>false,calendarPrefixes:new Map(),chartTickTimestamp:t=>t,candleEnd:(t,i)=>t+Number(i)*60,motilalSymbolSelection:false,deltaSymbolSelection:false,fyersSymbolSelection:false,liveStudyBars:new Map(),requestScope:{signal:scope},rows:[{time:7200,provisional:true}],pendingViewportRedraw:false,updateLastPrice:()=>{calls.updates++;return true;},redrawKeepingViewport:()=>calls.draws++,sameCandle:(a,b)=>['time','open','high','low','close','volume'].every(k=>a[k]===b[k]),loadPineLiveFrame:async()=>{calls.loads++;return frame;}};
 vm.createContext(c);vm.runInContext(section('  async function refreshLiveStudyBars(','  async function pollLive(')+'\nthis.refresh=refreshLiveStudyBars;',c);
 return{c,calls,scope,frame};
}
test('closed Renko study requests its own reference and retains native feed timestamp',async()=>{
 const f=fixture();await f.c.refresh(1,'30',f.scope);assert.equal(f.calls.loads,1);assert.equal(f.c.liveStudyBars.get('60').updatedAt,7999);assert.equal(f.calls.updates,1);assert.equal(f.calls.draws,0);
});
test('unchanged candle geometry still refreshes the Renko reference tick without forcing a full redraw',async()=>{
 const f=fixture();await f.c.refresh(1,'30',f.scope);const candle=f.c.liveStudyBars.get('60').candle;
 f.frame.latest_tick=8000;await f.c.refresh(1,'30',f.scope);
 assert.equal(f.c.liveStudyBars.get('60').updatedAt,8000);assert.equal(f.c.liveStudyBars.get('60').candle,candle);assert.equal(f.calls.updates,2);assert.equal(f.calls.draws,0);
});
test('stale, disconnected, and future feed frames clear reference freshness',async()=>{
 for(const patch of [{connected:false},{latest_tick:7940},{latest_tick:8003}]){
  const f=fixture();await f.c.refresh(1,'30',f.scope);Object.assign(f.frame,patch);await f.c.refresh(1,'30',f.scope);
  assert.equal(f.c.liveStudyBars.get('60').updatedAt,undefined);assert.equal(f.c.liveStudyBars.get('60').candle,undefined);
 }
});
test('aborted scopes and replay do not request live reference frames',async()=>{
 for(const mode of ['abort','replay']){
  const f=fixture();if(mode==='abort')f.scope.aborted=true;else f.c.barReplay={};
  await f.c.refresh(1,'30',f.scope);assert.equal(f.calls.loads,0);
 }
});
test('closed standard chart calculations retain existing polling behavior',async()=>{
 const f=fixture('Candles');await f.c.refresh(1,'30',f.scope);assert.equal(f.calls.loads,0);
});
test('existing completed-history scheduler includes calculation interval and redraws changed references',async()=>{
 const calls=[],c={settings:{studies:[{kind:'SMA'}]},studyVisible:()=>true,calculationInterval:()=> '60',twapReferenceInterval:()=>undefined,indicators:{SMA:{}},ratingTableIntervals:()=>[],broker:{nse:false},sourceInterval:()=>true,historyRefresh:undefined,reconcileHistory:async(r,i)=>{calls.push(i);return i==='60';},generation:1,panel:{open:true,querySelector:()=>({textContent:'',hidden:false})},historyErrors:new Map(),nextHistoryCheck:new Map(),history:new Map([['30',[]],['60',[]]]),renderLiveRows:(...args)=>calls.push(args),Date};
 vm.createContext(c);vm.runInContext(section('  function historyIntervals(','  let barReplay;')+'\n'+section('  function refreshCompletedHistory(','  function chartTickTimestamp(')+'\nthis.refresh=refreshCompletedHistory;',c);
 assert.equal(c.refresh(1,'30',8000),true);await new Promise(setImmediate);
 assert.deepEqual(calls.slice(0,2),['30','60']);assert.equal(calls[2][4],true);assert.equal(c.historyRefresh,undefined);
});
