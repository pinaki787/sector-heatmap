const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const start=source.indexOf('  const dhanPineInstruments = new Map();'),end=source.indexOf('  function pineCandleWindowForEvaluation',start);
assert.ok(start>=0&&end>start);
function setup(){const ctx=vm.createContext({dhanSymbolSelection:true,deltaSymbolSelection:false,motilalSymbolSelection:false,
settings:{},broker:{nse:true},commoditySession:()=>false,currencySession:()=>false,fyersRegularSession:undefined,
fyersSymbolSelection:false,motilalNcdex:()=>false,calendarZone:()=> 'Asia/Kolkata',catalogTickSize:()=>.05});
vm.runInContext(source.slice(start,end)+';this.meta=dhanPineInstruments;this.info=workerPineSymbolInfo;this.resolve=dhanPineHostTicker',ctx);return ctx;}
for(const [id,symbol,exchange,instrument,type] of [
['NSE_EQ:1333','HDFCBANK','NSE','EQUITY','stock'],
['IDX_I:13','NIFTY','NSE','INDEX','index'],
['NSE_FNO:123','NIFTY26NOV25000PE','NSE','OPTIDX','option'],
['BSE_FNO:124','SENSEX26NOVCE','BSE','OPTIDX','option'],
['MCX_COMM:125','GOLD26NOVFUT','MCX','FUTCOM','futures'],
['NSE_CURRENCY:126','USDINR26NOVFUT','NSE','FUTCUR','futures']]){
test(symbol+' catalog metadata preserves native routing',()=>{const c=setup();c.meta.set(id,{symbol,exchange,instrument});const info=c.info(id);
assert.equal(info.tickerid,id);assert.equal(info.ticker,symbol);assert.equal(info.prefix,exchange);assert.equal(info.type,type);
assert.equal(c.resolve(symbol,id),id);assert.equal(c.resolve(exchange+':'+symbol,id),id);
assert.equal(c.resolve('BSE:OTHER',id),'BSE:OTHER');assert.equal(c.resolve(id,id),id);assert.equal(c.resolve(id.split(':')[1],id),id);});}
test('missing catalog falls back without inventing an identity',()=>{const c=setup();assert.equal(c.info('NSE_EQ:1333').ticker,'1333');assert.equal(c.resolve('NSE:HDFCBANK','NSE_EQ:1333'),'NSE:HDFCBANK');});
test('non-Dhan aliases are untouched',()=>{const c=setup();c.dhanSymbolSelection=false;assert.equal(c.resolve('NSE:HDFCBANK','NSE_EQ:1333'),'NSE:HDFCBANK');});
test('known tick cannot suppress catalog hydration',()=>{assert.match(source,/catalogTickSize\(\) !== undefined && dhanPineInstruments\.has\(symbol\)/);});
