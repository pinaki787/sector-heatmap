const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
require('../chart-workspace-studies.js');const lib=globalThis.SectorPulseChartStudies,engine=require('../chart-renko-study-alignment.js');
const source=fs.readFileSync('.private/chart-order-rollouts/renko-study-pipeline-candidate-20261119/candidate.js','utf8');
const raw=JSON.parse(fs.readFileSync('.private/chart-order-rollouts/woodies-cci-20261119/woodies-hourly-history.json','utf8')).rows.map(r=>Object.fromEntries(['time','open','high','low','close','volume'].map((k,i)=>[k,r[i]])));
const fresh=JSON.parse(fs.readFileSync('.private/chart-order-rollouts/native-renko-study-timeframe-20261119/fresh-broker-tail.json','utf8')).results['1h'];
function fixture(){
 let now=1795103936;const scope={aborted:false},base=raw.map(b=>({...b})),history=new Map([['60',base]]),calls=[];
 const c={pendingHistory:new WeakMap(),requestScope:{signal:scope},history,calendarInterval:()=>false,Date:{now:()=>now*1000},nextCandleStart:(t,i)=>t+Number(i)*60,candleEnd:(t,i)=>t+Number(i)*60,motilalSymbolSelection:false,settings:{interval:'30'},motilalNcdex:()=>false,ncdexPeriodClose:undefined,mcxPendingClose:undefined,intradayPrefixes:new Map(),nativeLiveRows:new Map(),fyersFormingSeeds:new Map(),fyersMinuteFrames:new Map(),nextHistoryCheck:new Map(),generation:1,panel:{open:true},historyErrors:new Map(),rememberNcdexSessions:()=>{},chartQuery:x=>new URLSearchParams(x).toString(),brokerJson:async path=>{calls.push(path);return {rows:fresh.filter(r=>r.time>=1795096800&&r.time+3600<=now).map(r=>['time','open','high','low','close','volume'].map(k=>Number(r[k])))};}};
 vm.createContext(c);const a=source.indexOf('  async function reconcileHistory('),b=source.indexOf('  const motilalMcx',a);vm.runInContext(source.slice(a,b)+'\nthis.reconcile=reconcileHistory;',c);
 const tail=()=>engine.calculateRenkoTimeframeStudy({sourceBars:history.get('60'),hostBars:[{sourceTime:1795100400}],renko:lib.renko,run:bars=>lib.indicators.SMA.run(bars,bars.map(b=>b.close),5,undefined,{}),size:10,liveState:{live:true,confirmedThrough:history.get('60').at(-1).time+3600,now,updatedAt:now-1}}).plots[0][0];
 return{c,base,history,calls,tail,setNow:v=>now=v};
}
test('actual completed-reference reconciliation crosses hourly boundary and updates SMA1790to1794 while host brick is unchanged',async()=>{
 const f=fixture(),prefix=JSON.stringify(f.base);
 assert.equal(await f.c.reconcile(1,'60',1795103936,true),true);assert.equal(f.history.get('60').at(-1).time,1795096800);assert.equal(f.tail(),1790);
 assert.equal(JSON.stringify(f.history.get('60').slice(0,f.base.length)),prefix);
 f.setNow(1795105200);assert.equal(await f.c.reconcile(1,'60',1795105200,true),true);
 assert.equal(f.history.get('60').at(-1).time,1795100400);assert.equal(f.tail(),1794);assert.equal(f.calls.length,2);
 assert.equal(JSON.stringify(f.history.get('60').slice(0,f.base.length)),prefix);
});
test('older history arriving during reference refresh is retained',async()=>{
 const f=fixture(),older={...f.base[0],time:f.base[0].time-3600},original=f.c.brokerJson;
 f.c.brokerJson=async path=>{f.history.set('60',[older,...f.history.get('60')]);return original(path);};
 await f.c.reconcile(1,'60',1795103936,true);assert.equal(f.history.get('60')[0],older);assert.equal(f.history.get('60').length,f.base.length+2);
});
test('generation change while reference fetch is in flight cannot replace current history',async()=>{
 const f=fixture(),original=f.c.brokerJson;
 f.c.brokerJson=async path=>{const result=await original(path);f.c.generation=2;return result;};
 assert.equal(await f.c.reconcile(1,'60',1795103936,true),false);assert.equal(f.history.get('60'),f.base);
});
test('failed reference fetch retains prior confirmed history',async()=>{
 const f=fixture();f.c.brokerJson=async()=>{throw Error('Provider unavailable');};
 await assert.rejects(f.c.reconcile(1,'60',1795103936,true),/Provider unavailable/);assert.equal(f.history.get('60'),f.base);
});
