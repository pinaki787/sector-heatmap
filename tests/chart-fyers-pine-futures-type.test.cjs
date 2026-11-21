const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8'),start=s.indexOf('  function workerPineSymbolInfo('),end=s.indexOf('  function pineCandleWindowForEvaluation(',start);assert.ok(start>=0&&end>start);
for(const [symbol,type] of [['MCX:GOLDM26DECFUT','futures'],['NSE:NIFTY26NOVFUT','futures'],['BSE:SENSEX26NOVFUT','futures'],['NSE:USDINR26NOVFUT','futures'],['NSE:NIFTY26NOV25000CE','option'],['NSE:NIFTY26NOV25000PE','option'],['NSE:NIFTY50-INDEX','index'],['NSE:HDFCBANK-EQ','stock']])
test(symbol+' passes native instrument type without changing identity',()=>{
const c=vm.createContext({dhanSymbolSelection:false,motilalSymbolSelection:false,deltaSymbolSelection:false,fyersSymbolSelection:true,
broker:{nse:true},motilalNcdex:()=>false,commoditySession:()=>symbol.startsWith('MCX:'),currencySession:()=>symbol.includes('USDINR'),fyersRegularSession:undefined,calendarZone:()=> 'Asia/Kolkata',catalogTickSize:()=>.05});
const info=vm.runInContext(s.slice(start,end)+';workerPineSymbolInfo',c)(symbol);assert.equal(info.type,type);assert.equal(info.tickerid,symbol);assert.equal(info.timezone,'Asia/Kolkata');assert.equal(info.preserveNativeExchange,true);
});
