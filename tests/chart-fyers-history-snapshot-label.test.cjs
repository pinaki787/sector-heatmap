const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const start=source.indexOf('  function fyersHistorySnapshot('),end=source.indexOf('  function renkoBrickStatus(',start);
assert.ok(start>0&&end>start);
function fixture({interval='1380',fyers=true,seed={bar:[100],sampled_at:160}}={}){
 const context={settings:{interval},fyersSymbolSelection:fyers,fyersFormingSeeds:new Map([[interval,seed]]),calendarPrefixes:new Map(),
 calendarInterval:i=>i==='1M',tradeInterval:()=>false,tickInterval:()=>false,chartTime:t=>'time '+t};
 vm.createContext(context);vm.runInContext(source.slice(start,end),context);return context;
}
const bar={time:100,provisional:true,historyOnly:true};
test('validated forming FYERS seed says history snapshot awaiting live data',()=>{
 const f=fixture();assert.ok(f.fyersHistorySnapshot(bar));
 assert.equal(f.provisionalStatus(bar),' · Forming candle from broker history at time 160; awaiting live updates');
 assert.equal(bar.historyOnly,true);
});
test('gaps and unbound seed do not lose incomplete-history warning',()=>{
 for(const c of [{fyers:false},{seed:{bar:[99],sampled_at:160}},{seed:{bar:[100]}},{seed:{bar:[100],sampled_at:NaN}}]){
  const f=fixture(c);assert.equal(f.fyersHistorySnapshot(bar),undefined);
  assert.equal(f.provisionalStatus(bar),' · Incomplete interval from broker history');
 }
});
test('live/confirmed bars and calendar periods retain their separate semantics',()=>{
 const f=fixture();assert.equal(f.fyersHistorySnapshot({...bar,historyOnly:false}),undefined);
 assert.equal(f.provisionalStatus({...bar,historyOnly:false}),' · WebSocket bar pending broker confirmation');
 assert.equal(f.provisionalStatus({...bar,provisional:false}),'');
 const c=fixture({interval:'1M'});assert.equal(c.fyersHistorySnapshot(bar),undefined);
 c.calendarPrefixes.set('1M',{bar:[100],through:150});
 assert.equal(c.provisionalStatus(bar),' · Broker history through time 150');
});
