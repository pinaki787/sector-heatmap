const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path=process.env.CHART_SOURCE||'chart-workspace.js',main=fs.readFileSync(path,'utf8');
const a=main.indexOf('  function pineBoundedCalendarPrefix('),b=main.indexOf('  async function loadPineCandles(',a),c=main.indexOf('  function yahooPineReferenceClose(',b);
assert.ok(a>=0&&b>a&&c>b);
const period=1000,cutoff=1300,end=cutoff*1000;
const prefix={through:1400,bar:[period,10,999,1,999,99999]};
const raw=[{time:900,open:8,high:10,low:7,close:10,volume:2},{time:1000,open:10,high:12,low:9,close:11,volume:3},{time:1100,open:11,high:14,low:10,close:13,volume:5},{time:1200,open:13,high:15,low:12,close:14,volume:7},{time:1300,open:14,high:999,low:1,close:999,volume:10000}];
const ctx={calendarInterval:i=>/[DWM]$/.test(i),tradeInterval:i=>/T$/.test(i),candleEnd:(t,i)=>i==='1W'?2000:i==='1D'?1500:t+100};
vm.createContext(ctx);
const prefixFrom=main.indexOf('  function calendarHistoryPrefix('),prefixTo=main.indexOf('  function calendarLiveWithPrefix(',prefixFrom);
if(prefixFrom>=0&&prefixTo>prefixFrom)vm.runInContext(main.slice(prefixFrom,prefixTo),ctx);
vm.runInContext(main.slice(a,c),ctx);
const run=(rows=raw,e=end,src='15')=>ctx.pineBoundedCalendarPrefix(prefix,'1W',e,rows,src,ctx.candleEnd);
test('bounded context includes only fully closed selected-broker candles',()=>{const x=run();assert.equal(x.high,15);assert.equal(x.low,9);assert.equal(x.close,14);assert.equal(x.volume,15);assert.equal(x.time,1000);assert.equal(x.provisional,true);assert.equal(raw.at(-1).high,999)});
test('missing beginning, mismatched opening and unresolved final boundary are refused',()=>{assert.equal(run(raw.slice(2)),undefined);assert.equal(run(raw.map((x,i)=>i===1?{...x,open:9}:x)),undefined);assert.equal(run(raw,end-1),undefined)});
test('forming source candles are never committed as historical context',()=>{assert.equal(run(raw.map(x=>x.time===1200?{...x,provisional:true}:x)),undefined)});
test('invalid OHLC fails closed; missing volume remains missing',()=>{assert.equal(run(raw.map(x=>x.time===1100?{...x,high:NaN}:x)),undefined);assert.equal(run(raw.map(x=>x.time===1100?{...x,volume:null}:x)).volume,null)});
test('calendar or trade-count source and unbounded requests are refused',()=>{assert.equal(run(raw,end,'1D'),undefined);assert.equal(run(raw,end,'10T'),undefined);assert.equal(run(raw,null),undefined);assert.equal(run(raw,2000000),undefined)});
test('actual loader retains bounded current period for previous-week expressions',async()=>{
 Object.assign(ctx,{chartSymbol:()=> 'NSE:NIFTY50-INDEX',validInterval:()=>true,sourceInterval:()=>true,
 history:new Map([['1W',[{time:-1000,high:30,low:20},{time:0,high:40,low:25}]]]),settings:{interval:'15'},rows:raw,Date,Map,
 broker:{yahoo:false},deltaSymbolSelection:false,fyersSymbolSelection:true,pineHistoryChecks:new Map(),calendarPrefixes:new Map([['1W',prefix]]),
 pineCandleRowsForWindow:bars=>bars});
 const before=JSON.stringify(raw),loaded=await ctx.loadPineCandles({ticker:'NSE:NIFTY50-INDEX',interval:'1W',end},{throwIfAborted(){}});
 assert.equal(loaded.length,3);assert.equal(loaded.at(-1).high,15);assert.equal(loaded.at(-2).high,40);assert.equal(ctx.history.get('1W').length,2);assert.equal(JSON.stringify(raw),before);
 const full=await ctx.loadPineCandles({ticker:'NSE:NIFTY50-INDEX',interval:'1W',end:1500000},{throwIfAborted(){}});
 assert.equal(full.at(-1).high,999);
});
