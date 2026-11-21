const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const start=source.indexOf('  async function runChartPine('),end=source.indexOf('  function validatePine(',start);
assert.ok(start>=0&&end>start);
for(const chartType of ['Heikin Ashi','Renko'])for(const change of ['append','trim']){
test(chartType+' startup retains initial cohort through '+change,async()=>{
 const workers=[],bar=i=>({time:1700000000+i*300,sourceTime:1700000000+i*300,open:100+i,high:102+i,low:99+i,close:101+i,volume:10,provisional:i===1});
 const initial=[bar(0),bar(1)],controller=new AbortController();
 class Worker{constructor(){this.messages=[];workers.push(this)}postMessage(d){this.messages.push(structuredClone(d))}terminate(){}}
 const ctx=vm.createContext({Worker,AbortController,AbortSignal,performance,setTimeout,clearTimeout,setInterval,clearInterval,barReplay:undefined,deltaSymbolSelection:false,fyersSymbolSelection:false,
 settings:{interval:'5'},broker:{yahoo:false,name:'Test'},rows:initial,displayedBars:initial,pineRefreshListeners:new Set(),chartSymbol:()=> 'TEST',workerPineSymbolInfo:()=>({ticker:'TEST',tickerid:'TEST'}),pineChartType:()=>chartType,
 pineCandleWindowForEvaluation:(_windows,_request,load)=>load(),candleEnd:t=>t+300,mergePineOverlayPlots:p=>p,dhanPineHostTicker:t=>t,motilalPineHostTicker:t=>t,intervalLabel:t=>t});
 const helperStart=source.indexOf('  function pineSyntheticHostBar(');
 if(helperStart>=0){
  const helperEnd=source.indexOf('  function pinePlotEntries(',helperStart);
  assert.ok(helperEnd>helperStart);
  vm.runInContext(source.slice(helperStart,helperEnd),ctx);
 }
 const run=vm.runInContext(source.slice(start,end)+';runChartPine',ctx);
 try{
 const pending=run('//@version=6\nindicator("Test")',controller.signal,()=>{},()=>true,()=>{});
 const w=workers[0],message=w.messages[0];assert.equal(message.count,2);
 ctx.displayedBars=change==='append'?[...initial,bar(2)]:initial.slice(1);
 const ticker='TEST;'+(chartType==='Renko'?'renko':'heikinashi');
 await w.onmessage({data:{type:'candles',id:1,ticker,interval:'5',limit:message.count}});
 const reply=w.messages.at(-1);assert.equal(reply.type,'candles-result');
 assert.deepEqual(reply.rows.map(b=>b.openTime),initial.map(b=>b.sourceTime*1000));
 await w.onmessage({data:{ok:true,plots:{}}});
 const result=await pending;assert.equal(result.bricks.length,message.count);
 assert.equal(result.bricks[0].time,initial[0].time);
 }finally{controller.abort()}
});
}
