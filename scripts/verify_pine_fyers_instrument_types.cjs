const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
(async()=>{
 const frontend=fs.readFileSync('chart-workspace.js','utf8'),start=frontend.indexOf('  function workerPineSymbolInfo('),end=frontend.indexOf('  function pineCandleWindowForEvaluation(',start);
 const worker=fs.readFileSync('.private/chart-pine-worker.js','utf8'),results=[];
 for(const [symbol,expected] of [['MCX:GOLDM26DECFUT','futures'],['NSE:NIFTY26NOV25000PE','option'],['NSE:NIFTY50-INDEX','index'],['NSE:HDFCBANK-EQ','stock']]){
  const meta=vm.createContext({dhanSymbolSelection:false,motilalSymbolSelection:false,deltaSymbolSelection:false,fyersSymbolSelection:true,broker:{nse:true},
   motilalNcdex:()=>false,commoditySession:()=>symbol.startsWith('MCX:'),currencySession:()=>false,fyersRegularSession:undefined,calendarZone:()=> 'Asia/Kolkata',catalogTickSize:()=>.05});
  const info=vm.runInContext(frontend.slice(start,end)+';workerPineSymbolInfo',meta)(symbol);
  const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;
  const bars=Array.from({length:40},(_,i)=>({openTime:1794894300000+i*1800000,closeTime:1794894300000+(i+1)*1800000,open:100+i,high:102+i,low:99+i,close:101+i,volume:100}));
  const source='//@version=6\nindicator("Instrument type check")\nplot(syminfo.type=="'+expected+'"?1:0,"Type matches")\nplot(close,"Source close")';
  const result=await new Promise((resolve,reject)=>{ctx.postMessage=d=>d.ok===false?reject(Error(d.error)):resolve(d);vm.runInContext(worker,ctx);ctx.onmessage({data:{source,symbolInfo:info,frames:{'30':bars},timeframe:'30',count:bars.length}}).catch(reject)});
  assert.ok(result.plots['Type matches'].data.every(p=>p.value===1));assert.equal(result.plots['Source close'].data.at(-1).value,140);
  results.push({symbol,expected,bars:40,status:'PASS'});
 }
 console.log(JSON.stringify({status:'PASS',scope:'Current frontend metadata passed through actual Pine worker on synthetic replay candles; not hosted FYERS data validation.',results},null,2));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
