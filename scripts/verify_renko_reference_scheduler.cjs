const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2],'utf8'),a=source.indexOf('  async function runChartPineOnce('),b=source.indexOf('  function validatePine(',a);
const helperA=source.indexOf('  function pineSyntheticHostBar('),helperB=source.indexOf('  function pinePlotEntries(',helperA);
assert.ok(a>=0&&b>a&&helperA>=0);
async function fixture({native=true,chartType='Renko',forming=true}={}){
 const workers=[],bars=Array.from({length:8},(_,i)=>({time:1000+i,sourceTime:1000,open:100+i,high:102+i,low:99+i,close:101+i,volume:1,provisional:i===7&&forming}));
 const controller=new AbortController();
 class Worker{constructor(){this.messages=[];workers.push(this)}postMessage(data){this.messages.push(structuredClone(data))}terminate(){this.terminated=true}}
 const c=vm.createContext({Worker,AbortController,AbortSignal,performance,setTimeout,clearTimeout,setInterval,clearInterval,
 Date:{now:()=>c.now*1000},now:1000,latestLiveTick:1000,settings:{interval:'30'},barReplay:undefined,broker:{yahoo:false,name:'Test'},
 deltaSymbolSelection:false,fyersSymbolSelection:false,rows:bars,displayedBars:bars,pineRefreshListeners:new Set(),
 chartSymbol:()=> 'TEST',workerPineSymbolInfo:()=>({ticker:'TEST',tickerid:'TEST'}),pineChartType:()=>chartType,
 pineCandleWindowForEvaluation:(_w,_r,load)=>load(),candleEnd:t=>t+1800,mergePineOverlayPlots:p=>p,
 dhanPineHostTicker:t=>t,motilalPineHostTicker:t=>t,intervalLabel:t=>t,
 loadPineCandles:async()=>[],sameCandle:(x,y)=>JSON.stringify(x)===JSON.stringify(y),
 renkoCalculationRestartRequired:()=>false,heikinTailUpdateAllowed:()=>true});
 vm.runInContext(source.slice(helperA,helperB),c);
 const run=vm.runInContext(source.slice(a,b)+';runChartPineOnce',c),pending=run('SCRIPT',controller.signal,()=>{},()=>true,()=>{});
 const w=workers[0];
 if(native)await w.onmessage({data:{type:'candles',id:1,ticker:'TEST',interval:'5'}});
 await w.onmessage({data:{ok:true,plots:{}}});await pending;
 return {c,w,controller,refresh:[...c.pineRefreshListeners][0],messages:()=>w.messages.filter(m=>m.type==='refresh')};
}
(async()=>{
 let f=await fixture({native:false});f.refresh(false,true);assert.equal(f.messages().length,0);f.controller.abort();
 f=await fixture();f.refresh(false,true);assert.equal(f.messages().length,1);assert.equal(f.messages()[0].reset,false);assert.equal(f.messages()[0].restartCalculation,false);
 f.refresh(false,true);assert.equal(f.messages().length,1);
 f.c.latestLiveTick=1001;f.c.now=1001;f.refresh(false,true);assert.equal(f.messages().length,1);
 await f.w.onmessage({data:{type:'updated',ok:true,plots:{}}});assert.equal(f.messages().length,2);assert.equal(f.messages()[1].reset,false);
 await f.w.onmessage({data:{type:'updated',ok:true,plots:{}}});
 f.c.now=1100;f.c.latestLiveTick=1002;f.refresh(false,true);assert.equal(f.messages().length,2);
 f.c.latestLiveTick=1104;f.refresh(false,true);assert.equal(f.messages().length,2);
 f.c.latestLiveTick=undefined;f.refresh(false,true);assert.equal(f.messages().length,2);
 f.controller.abort();assert.equal(f.c.pineRefreshListeners.size,0);assert.ok(f.w.terminated);
 f=await fixture({forming:false});f.refresh(false,true);assert.equal(f.messages().length,0);f.refresh(true);assert.equal(f.messages()[0].reset,true);f.controller.abort();
 for(const chartType of ['Heikin Ashi','Candles','Line']){
  f=await fixture({chartType});f.refresh(false,true);assert.equal(f.messages().length,1,chartType);assert.equal(Boolean(f.messages()[0].reset),false,chartType);f.controller.abort();
 }
 console.log(JSON.stringify({passed:true,cases:12,reference_only_is_incremental:true,duplicate_tick_deduplicated:true,inflight_updates_coalesced:true,stale_future_disconnected_ticks_ignored:true,confirmed_bricks_frozen:true,non_reference_studies_ignored:true,four_chart_types_incremental:true,abort_cleans_up:true}));
})().catch(error=>{console.error(error.stack);process.exit(1)});
