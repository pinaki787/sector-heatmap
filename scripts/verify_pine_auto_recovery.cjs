const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE,'utf8');
const between=(start,end)=>{const a=source.indexOf(start),b=source.indexOf(end,a);assert.ok(a>=0&&b>a);return source.slice(a,b);};
const helpers=between('  function chartHistoryRetryAfter(','  async function requestChartHistory(');
const restore=between('  function restoreWorkerPine(','  function prefetchPineHistory(');
const cancel=between('  function cancelPendingPineStudy(','  function pineChartRestriction(');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(outcomes=[]){
 const timers=new Map();let id=0,calls=0;
 const scope=new AbortController(),study={kind:'Pine',workerRuntime:true,source:'SCRIPT',inputs:{period:14}},settings={interval:'5',studies:[study]},old={lastGood:true};
 const c={settings,rows:[{time:1}],displayedBars:[],barReplay:null,panel:{open:true},chartPrefix:'/broker/A',
 pineRestoreRetries:new WeakMap(),pineRestoreRequests:new WeakMap(),pineRestoreStatus:new WeakMap(),pineRestoreProgress:new WeakMap(),workerPineResults:new WeakMap([[study,old]]),pineInputDefinitions:new WeakMap(),
 chartSymbol:()=>c.symbol,pineChartType:()=>c.chartType,symbol:'SYMBOL',chartType:'Candles',studyVisible:()=>!c.hidden,pineChartRestriction:()=>false,
 AbortController,AbortSignal,clearTimeout:n=>timers.delete(n),setTimeout:(fn,delay)=>{const n=++id;timers.set(n,{fn,delay});return n},
 drawLegend(){},save(){},pinePlotMetadata:()=>[],pineStylePlotEntries:()=>[],workerInputControls:()=>[],
 publishWorkerPineResult:(s,r)=>c.workerPineResults.set(s,r),
 runChartPine:()=>{const next=outcomes[Math.min(calls++,outcomes.length-1)];return next instanceof Error?Promise.reject(next):Promise.resolve({plots:next||{newResult:true}})}};
 vm.createContext(c);vm.runInContext(helpers+cancel+restore,c);
 return {c,study,scope,timers,old,calls:()=>calls,start:()=>c.restoreWorkerPine(scope.signal),async next(){const n=timers.keys().next().value;assert.ok(n);const task=timers.get(n);timers.delete(n);task.fn();await settle();return task.delay;}};
}
function transient(status=503,extra={}){return Object.assign(new Error('Temporary broker failure'),{status,...extra});}
test('retry classification excludes permanent, auth, abort and script errors',()=>{
 const f=fixture();
 for(const error of [new Error('Syntax error'),{status:400},{status:401},{status:403},{status:404},transient(503,{authRequired:true}),{name:'AbortError',historyTransient:true}]){
  assert.equal(f.c.pineReferenceRetryDelay(error,0),null);
 }
 assert.equal(f.c.pineReferenceRetryDelay(transient(),4),null);
 assert.equal(f.c.pineReferenceRetryDelay({historyTransient:true},0),5000);
});
test('broker retry deadlines honor seconds, HTTP date and long cooldown',()=>{
 const f=fixture(),now=Date.UTC(2026,10,19);
 const response={status:429,headers:{get:()=> '120'}};
 assert.equal(f.c.chartHistoryRetryAfter(response,{},now),120000);
 assert.equal(f.c.pineReferenceRetryDelay(transient(429,{retryAfterMs:120000}),0),120000);
 assert.equal(f.c.chartHistoryRetryAfter({status:503,headers:{get:()=>new Date(now+90000).toUTCString()}},{retry_after:120},now),120000);
 assert.equal(f.c.chartHistoryRetryAfter({status:429},{},now),60000);
 assert.equal(f.c.pineReferenceRetryDelay(transient(429,{retryAfterMs:3e9}),0),null);
});
test('transient failure automatically recovers and retains last good plots while waiting',async()=>{
 const f=fixture([transient(),{ready:true}]);f.start();await settle();
 assert.equal(f.calls(),1);assert.equal(f.c.workerPineResults.get(f.study),f.old);
 assert.match(f.c.pineRestoreStatus.get(f.study),/Retrying automatically in 5s/);
 assert.equal(await f.next(),5000);assert.equal(f.calls(),2);
 assert.equal(f.c.workerPineResults.get(f.study).plots.ready,true);
 assert.equal(f.c.pineRestoreStatus.has(f.study),false);assert.equal(f.timers.size,0);
 assert.equal(f.study.source,'SCRIPT');assert.deepEqual(f.study.inputs,{period:14});
});
test('one outage gets at most four automatic retries with bounded backoff',async()=>{
 const f=fixture([transient()]);f.start();await settle();
 const delays=[];while(f.timers.size)delays.push(await f.next());
 assert.deepEqual(delays,[5000,15000,30000,60000]);assert.equal(f.calls(),5);
 assert.doesNotMatch(f.c.pineRestoreStatus.get(f.study),/Retrying automatically/);
});
test('authentication failure does not schedule any automatic retry',async()=>{
 const f=fixture([transient(401,{authRequired:true})]);f.start();await settle();
 assert.equal(f.calls(),1);assert.equal(f.timers.size,0);
});
for(const change of ['symbol','broker','interval','type','source','inputs','close','remove','hide']){
 test('pending retry cannot run after chart context changes: '+change,async()=>{
  const f=fixture([transient()]);f.start();await settle();
  if(change==='symbol')f.c.symbol='OTHER';
  if(change==='broker')f.c.chartPrefix='/broker/B';
  if(change==='inputs')f.study.inputs={period:28};
  if(change==='interval')f.c.settings.interval='15';
  if(change==='type')f.c.chartType='Renko';
  if(change==='source')f.study.source='NEW SCRIPT';
  if(change==='close')f.c.panel.open=false;
  if(change==='remove')f.c.settings.studies=[];
  if(change==='hide')f.c.hidden=true;
  await f.next();assert.equal(f.calls(),1);
 });
}
test('scope cancellation and explicit study cancellation clear pending timers',async()=>{
 for(const type of ['scope','study']){
  const f=fixture([transient()]);f.start();await settle();
  if(type==='scope')f.scope.abort();else f.c.cancelPendingPineStudy(f.study);
  assert.equal(f.timers.size,0);assert.equal(f.c.pineRestoreRetries.has(f.study),false);assert.equal(f.calls(),1);
 }
});
test('a broker cooldown is respected by the study scheduler',async()=>{
 const f=fixture([transient(429,{retryAfterMs:120000}),{ready:true}]);f.start();await settle();
 assert.equal(await f.next(),120000);assert.equal(f.calls(),2);
});
const runPine=between('  async function runChartPine(','  function validatePine(');
for(const detail of [{status:503,retryAfterMs:25000},{status:429,retryAfterMs:120000},{status:503,authRequired:true},{historyTransient:true}]){
 test('reference failure properties survive worker message wrapping: '+JSON.stringify(detail),async()=>{
  const original=Object.assign(new Error('Reference temporarily unavailable'),detail),abort=new AbortController();
  class FakeWorker{
   postMessage(data){
    if(data.source)queueMicrotask(()=>Promise.resolve(this.onmessage({data:{type:'candles',id:1,ticker:'SYM',interval:'5'}})).catch(()=>this.onerror()));
    else if(data.type==='candles-result')queueMicrotask(()=>this.onmessage({data:{ok:false,error:'Runtime wrapper: '+data.error}}));
   }
   terminate(){}
  }
  const c={barReplay:null,settings:{interval:'5'},rows:[{time:1}],displayedBars:[],deltaSymbolSelection:false,fyersSymbolSelection:false,
   chartSymbol:()=> 'SYM',workerPineSymbolInfo:()=>({ticker:'SYM'}),pineChartType:()=> 'Candles',
   AbortController,AbortSignal,Worker:FakeWorker,performance,setTimeout,clearTimeout,setInterval,clearInterval,
   broker:{name:'Selected broker'},pineRefreshListeners:new Set(),intervalLabel:x=>x,
   motilalPineHostTicker:x=>x,dhanPineHostTicker:x=>x,
   pineCandleWindowForEvaluation:async(map,request,load)=>load(),loadPineCandles:async()=>{throw original;}};
  vm.createContext(c);vm.runInContext(runPine,c);
  await assert.rejects(c.runChartPineOnce('SOURCE',abort.signal,undefined,()=>true),error=>{
   for(const [key,value] of Object.entries(detail))assert.equal(error[key],value,key);
   return true;
  });
 });
}
const historyRequest=between('  async function requestChartHistory(','  function aggregateYahooMonths(');
test('HTTP history retry remains bounded and abortable',async()=>{
 const f=fixture(),abort=new AbortController();let calls=0;
 f.c.brokerJson=async()=>{calls++;throw transient();};vm.runInContext(historyRequest,f.c);
 const request=f.c.requestChartHistory('/history',abort.signal);
 const rejected=assert.rejects(request,error=>error.name==='AbortError');await settle();
 assert.equal(calls,1);assert.equal(f.timers.size,1);abort.abort();await rejected;
 assert.equal(f.timers.size,0);assert.equal(calls,1);
});
test('long broker cooldown is delegated rather than holding the worker request open',async()=>{
 const f=fixture(),abort=new AbortController();let calls=0;
 f.c.brokerJson=async()=>{calls++;throw transient(429,{retryAfterMs:120000});};vm.runInContext(historyRequest,f.c);
 await assert.rejects(f.c.requestChartHistory('/history',abort.signal),error=>error.status===429);
 assert.equal(calls,1);assert.equal(f.timers.size,0);
});
const recoveryWrapper=between('  async function runChartPine(','  async function runChartPineOnce(');
function coreFixture(outcomes){
 const f=fixture();let calls=0,liveFailure;const progress=[],updates=[],terminal=[];
 f.c.runChartPineOnce=async(_source,_signal,_update,_current,onError)=>{
  liveFailure=onError;const item=outcomes[Math.min(calls++,outcomes.length-1)];
  if(item instanceof Error)throw Object.assign(new Error(item.message),item);
  return item;
 };
 vm.runInContext(recoveryWrapper,f.c);
 return {...f,coreCalls:()=>calls,progress,updates,terminal,fail:error=>liveFailure(error),
 begin:()=>f.c.runChartPine('SCRIPT',f.scope.signal,(...args)=>updates.push(args),
 ()=>f.c.symbol==='SYMBOL'&&f.c.panel.open,error=>terminal.push(error),(message,recovering)=>progress.push({message,recovering}))};
}
test('initial Add-to-chart path recovers without a second user apply',async()=>{
 const f=coreFixture([transient(),{plots:{ready:true}}]);const pending=f.begin();await settle();
 assert.equal(f.coreCalls(),1);assert.equal(f.progress[0].recovering,true);
 await f.next();assert.equal((await pending).plots.ready,true);assert.equal(f.coreCalls(),2);assert.equal(f.updates.length,0);
});
test('already-applied live study recovers and republishes the replacement result',async()=>{
 const f=coreFixture([{plots:{version:1}},{plots:{version:2}}]);await f.begin();
 f.fail(transient());await settle();assert.equal(f.timers.size,1);assert.equal(f.updates.length,0);
 await f.next();assert.equal(f.coreCalls(),2);assert.equal(f.updates.length,1);assert.equal(f.updates[0][0].version,2);assert.equal(f.terminal.length,0);
});
test('initial recovery has one four-retry budget and marks exhaustion',async()=>{
 const f=coreFixture([transient()]);const pending=f.begin();const rejection=assert.rejects(pending,error=>error.recoveryExhausted===true);
 await settle();while(f.timers.size)await f.next();await rejection;
 assert.equal(f.coreCalls(),5);assert.equal(f.c.pineReferenceRetryDelay({status:503,recoveryExhausted:true},0),null);
});
test('recovery in the initial application path cancels when the draft scope aborts',async()=>{
 const f=coreFixture([transient()]);const pending=f.begin();const rejection=assert.rejects(pending,error=>error.name==='AbortError');
 await settle();f.scope.abort();await rejection;assert.equal(f.timers.size,0);assert.equal(f.coreCalls(),1);
});
test('live recovery cannot restart after the selected chart changes',async()=>{
 const f=coreFixture([{plots:{version:1}}]);await f.begin();f.fail(transient());await settle();
 f.c.symbol='OTHER';await f.next();assert.equal(f.coreCalls(),1);assert.equal(f.updates.length,0);
});
test('initial permanent script or authentication errors never retry',async()=>{
 for(const error of [new Error('Syntax error'),transient(401,{authRequired:true})]){
  const f=coreFixture([error]);await assert.rejects(f.begin());assert.equal(f.timers.size,0);assert.equal(f.coreCalls(),1);
 }
});
test('an unchanged pending study is reused without duplicate worker starts',()=>{
 const f=fixture();let calls=0;f.c.runChartPine=()=>{calls++;return new Promise(()=>{});};
 f.start();f.start();assert.equal(calls,1);f.scope.abort();
});
for(const change of ['inputs','broker','settings']){
 test('changed pending context replaces the old request: '+change,()=>{
  const f=fixture();let calls=0;f.c.runChartPine=()=>{calls++;return new Promise(()=>{});};
  f.start();const original=f.c.pineRestoreRequests.get(f.study);
  if(change==='inputs')f.study.inputs={period:28};
  if(change==='broker')f.c.chartPrefix='/broker/B';
  if(change==='settings')f.c.settings={...f.c.settings};
  f.start();assert.equal(calls,2);assert.equal(original.controller.signal.aborted,true);
  f.scope.abort();
 });
}
