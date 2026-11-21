const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
require('../chart-workspace-studies.js');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const a=source.indexOf('  async function loadPineCandles('),b=source.indexOf('  function yahooPineReferenceClose(',a);
const x=source.indexOf('  function fyersFormingLiveBar('),y=source.indexOf('  function calendarLiveWithPrefix(',x);
function fixture({fyers=true,provisional=true,seed={bar:[100,100,110,90,104,50],sampled_at:160},frame=null}={}){
 const confirmed=[{time:-800,open:99,high:101,low:98,close:100,volume:10}];let calls=0;
 const scope={throwIfAborted(){}};
 const c={Date:{now:()=>200000},settings:{interval:'30'},fyersSymbolSelection:fyers,deltaSymbolSelection:false,
 rows:[{time:100,provisional}],history:new Map([['15',confirmed]]),fyersFormingSeeds:new Map(seed?[['15',seed]]:[]),
 chartSymbol:()=> 'NSE:NIFTY50-INDEX',validInterval:()=>true,sourceInterval:()=>true,calendarInterval:()=>false,
 candleEnd:(t,i)=>t+Number(i)*60,calendarPrefixes:new Map(),pineHistoryChecks:new Map(),broker:{yahoo:false},
 mergeLiveCandles:globalThis.SectorPulseChartStudies.mergeLiveCandles,
 pineCandleRowsForWindow:bars=>bars,loadPineLiveFrame:async()=>{calls++;return frame}};
 vm.createContext(c);vm.runInContext(source.slice(x,y)+source.slice(a,b),c);
 return {c,confirmed,calls:()=>calls,load:(end)=>c.loadPineCandles({ticker:'NSE:NIFTY50-INDEX',interval:'15',end},scope)};
}
test('FYERS current reference includes native forming seed without confirming it',async()=>{
 const f=fixture(),got=await f.load();assert.equal(got.length,2);assert.equal(got[1].provisional,true);
 assert.equal(got[1].close,104);assert.equal(f.confirmed.length,1);assert.equal(f.calls(),1);
});
test('fresh continuous minute coverage updates the forming seed',async()=>{
 const frame={connected:true,latest_tick:180,fyers_intraday:{coverage_since:150,minutes:[[120,104,111,103,108,1],[180,108,112,105,106,1]]}};
 const f=fixture({frame}),got=await f.load();assert.equal(got[1].close,106);assert.equal(got[1].high,112);assert.equal(got[1].volume,null);assert.equal(got[1].provisional,true);
});
test('historical windows, confirmed host and other providers never request forming FYERS data',async()=>{
 for(const options of [{provisional:false},{fyers:false}]){
  const f=fixture(options);assert.equal((await f.load()).length,1);assert.equal(f.calls(),0);
 }
 const f=fixture();assert.equal((await f.load(99000)).length,1);assert.equal(f.calls(),0);
});
test('missing, expired or future native seeds do not invent a reference candle',async()=>{
 for(const seed of [null,{bar:[-1000,1,2,1,2,1],sampled_at:160},{bar:[100,1,2,1,2,1],sampled_at:203},{bar:[100,1,2,1,2,1]}]){
  const f=fixture({seed});assert.equal((await f.load()).length,1);
 }
});
