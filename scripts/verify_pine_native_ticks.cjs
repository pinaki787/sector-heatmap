const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [library,worker,output]=process.argv.slice(2),source=fs.readFileSync(library,'utf8');
const a=source.indexOf('  const dhanPineInstruments = new Map();'),b=source.indexOf('  function pineCandleWindowForEvaluation',a);
const c=vm.createContext({motilalSymbolSelection:true,dhanSymbolSelection:false,deltaSymbolSelection:false,fyersSymbolSelection:false,settings:{},broker:{nse:true,venue:'NSE'},
commoditySession:()=>false,currencySession:()=>false,fyersRegularSession:undefined,motilalNcdex:()=>false,calendarZone:()=> 'Asia/Kolkata'});
vm.runInContext(source.slice(a,b)+';this.remember=rememberMotilalPineInstrument;this.info=workerPineSymbolInfo',c);
const ta=source.indexOf('  function catalogTickSize() {'),tb=source.indexOf('  function chartQuery(',ta);
vm.runInContext(source.slice(ta,tb),c);
(async()=>{
const results=[];
for(const tick of [1,5,.05,.0025,.0001]){
 const id='MO:MCX:125';c.chartSymbol=()=>id;c.remember({id,symbol:'Native tick fixture',exchange:'MCX',instrument:'FUTCOM',tick_size:tick});
 const symbolInfo=c.info(id),ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;
 vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
 const bars=[0,1,2].map(i=>({openTime:1700000000000+i*1800000,closeTime:1700000000000+(i+1)*1800000,open:100,high:101,low:99,close:100,volume:1}));
 const plots=await new Promise((resolve,reject)=>{
 ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else if(d.plots)resolve(d.plots)};
 Promise.resolve(ctx.onmessage({data:{source:'//@version=6\nindicator("Native tick fixture")\nvar array<float> sample=array.new<float>()\nplot(syminfo.mintick,"Native tick")',symbolInfo,frames:{'30':bars},timeframe:'30',count:bars.length}})).catch(reject);
 });
 assert.equal(plots['Native tick'].data.length,3);
 for(const p of plots['Native tick'].data)assert.equal(p.value,tick);
 results.push({tick,points:3,raw_worker_values_exact:true});
}
const report={status:'PASS',results,scope:'Full Pine worker with frontend-generated Motilal metadata and synthetic candles; no authenticated broker/live or order verification.'};
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
})().catch(e=>{console.error(e.message);process.exitCode=1});
