const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const from=source.indexOf('  const dhanPineInstruments = new Map();'),to=source.indexOf('  function pineCandleWindowForEvaluation',from);
function setup(){
 const c=vm.createContext({motilalSymbolSelection:true,dhanSymbolSelection:false,deltaSymbolSelection:false,fyersSymbolSelection:false,
 settings:{},broker:{nse:true,venue:'NSE'},commoditySession:()=>false,currencySession:()=>false,fyersRegularSession:undefined,
 motilalNcdex:()=>false,calendarZone:()=> 'Asia/Kolkata',catalogTickSize:()=>.05,AbortSignal,URLSearchParams});
 vm.runInContext(source.slice(from,to)+';this.remember=rememberMotilalPineInstrument;this.info=workerPineSymbolInfo;this.resolve=motilalPineHostTicker;this.meta=motilalPineInstruments',c);
 return c;
}
for(const [id,symbol,exchange,instrument,type,prefix] of [
 ['MO:NSE:1333','HDFCBANK','NSE','','stock','NSE'],
 ['MO:INDEX:BSE:1','SENSEX','BSE','INDEX','index','BSE'],
 ['MO:NSEFO:123','NIFTY 26-NOV-2026 PE','NSEFO','OPTIDX','option','NSE'],
 ['MO:BSEFO:124','SENSEX 26-NOV-2026 CE','BSEFO','OPTIDX','option','BSE'],
 ['MO:MCX:125','GOLD 05-DEC-2026','MCX','FUTCOM','futures','MCX'],
 ['MO:NCDEX:126','JEERA 20-DEC-2026','NCDEX','OPTFUT','option','NCDEX'],
 ['MO:NSECD:127','USDINR 26-NOV-2026','NSECD','FUTCUR','futures','NSE']
]){
 test(id+' uses native catalog identity and instrument class',()=>{
 const c=setup();c.motilalNcdex=()=>exchange==='NCDEX';c.remember({id,symbol,exchange,instrument});
 const info=c.info(id);assert.equal(info.tickerid,id);assert.equal(info.ticker,symbol);assert.equal(info.type,type);assert.equal(info.prefix,prefix);
 assert.equal(c.resolve(prefix+':'+symbol,id),id);assert.equal(c.resolve(symbol,id),id);assert.equal(c.resolve(exchange+':'+symbol,id),id);
 assert.equal(c.resolve(id.split(':').at(-1),id),id);assert.equal(c.resolve(id,id),id);
 assert.equal(c.resolve('NSE:UNRELATED',id),'NSE:UNRELATED');
 });
}
test('mismatched exchange and non-native IDs cannot publish aliases',()=>{
 const c=setup();c.remember({id:'MO:MCX:125',symbol:'GOLD',exchange:'NSE',instrument:'FUTCOM'});
 c.remember({id:'NSE:125',symbol:'GOLD',exchange:'NSE',instrument:'FUTCOM'});assert.equal(c.meta.size,0);
});
test('another broker cannot inherit Motilal aliases',()=>{
 const c=setup();c.remember({id:'MO:NSE:1333',symbol:'HDFCBANK',exchange:'NSE',instrument:''});c.motilalSymbolSelection=false;
 assert.equal(c.resolve('NSE:HDFCBANK','MO:NSE:1333'),'NSE:HDFCBANK');
});
function hydrate(c){
 const a=source.indexOf('  async function loadMotilalInstrumentMetadata('),b=source.indexOf('  async function loadDhanInstrumentMetadata(',a);
 assert.ok(a>=0&&b>a);vm.runInContext(source.slice(a,b)+';this.hydrate=loadMotilalInstrumentMetadata',c);
}
test('saved chart hydrates exact native symbol from its own segment',async()=>{
 const c=setup();c.chartSymbol=()=> 'MO:MCX:125';c.chartPrefix='/broker-workspace/test';let url;
 c.fetch=async u=>{url=u;return {ok:true,json:async()=>({symbols:[{id:'MO:MCX:125',symbol:'GOLD',exchange:'MCX',instrument:'FUTCOM'}]})}};
 hydrate(c);await c.hydrate(new AbortController().signal);
 assert.equal(new URL('https://test'+url).searchParams.get('segment'),'MCX');
 assert.equal(new URL('https://test'+url).searchParams.get('q'),'MO:MCX:125');assert.equal(c.info('MO:MCX:125').type,'futures');
});
test('late metadata cannot attach after the selected symbol changes',async()=>{
 const c=setup();let current='MO:MCX:125';c.chartSymbol=()=>current;c.chartPrefix='';c.fetch=async()=>({ok:true,json:async()=>{current='MO:NSE:1333';return {symbols:[{id:'MO:MCX:125',symbol:'GOLD',exchange:'MCX',instrument:'FUTCOM'}]}}});
 hydrate(c);await c.hydrate(new AbortController().signal);assert.equal(c.meta.size,0);
});

test('legacy Motilal NIFTY chart remains an index without a catalog token',()=>{const c=setup();assert.equal(c.info('NIFTY').type,'index');});
function nativeTick(c){
 const a=source.indexOf('  function catalogTickSize() {'),b=source.indexOf('  function chartQuery(',a);
 vm.runInContext(source.slice(a,b)+';this.nativeTick=catalogTickSize',c);
 c.chartSymbol=()=> 'MO:MCX:125';c.catalogTickSize=c.nativeTick;
}
test('native tick replaces generic fallback without rounding',()=>{
 const c=setup();nativeTick(c);
 for(const tick of [1,5,.05,.0025]){
 c.remember({id:'MO:MCX:125',symbol:'GOLD',exchange:'MCX',instrument:'FUTCOM',tick_size:tick});
 assert.equal(c.nativeTick(),tick);assert.equal(c.info('MO:MCX:125').mintick,tick);
 }
});
test('another selected instrument cannot inherit the previous tick',()=>{
 const c=setup();nativeTick(c);c.remember({id:'MO:MCX:125',symbol:'GOLD',exchange:'MCX',instrument:'FUTCOM',tick_size:1});
 c.chartSymbol=()=> 'MO:NCDEX:126';assert.equal(c.nativeTick(),undefined);
});
test('invalid or absent native ticks are not coerced into a price increment',()=>{
 const c=setup();nativeTick(c);
 for(const tick of [undefined,null,0,-1,Infinity,NaN,'0.05']){
 c.remember({id:'MO:MCX:125',symbol:'GOLD',exchange:'MCX',instrument:'FUTCOM',tick_size:tick});
 assert.equal(c.nativeTick(),undefined);
 }
});
test('Renko ATR and percentage sizing use the selected native tick',()=>{
 const c=setup();nativeTick(c);
 c.remember({id:'MO:MCX:125',symbol:'GOLD',exchange:'MCX',instrument:'FUTCOM',tick_size:1});
 require('../chart-workspace-studies.js');
 c.renkoAtrSize=globalThis.SectorPulseChartStudies.renkoAtrSize;c.barReplay=undefined;c.generation=0;
 c.window={SectorPulseRenkoSizing:require('../chart-renko-sizing.js')};
 const a=source.indexOf('  let renkoPercentReference;'),b=source.indexOf('  function visiblePlotColor(',a);
 vm.runInContext(source.slice(a,b)+';this.box=renkoBoxSize',c);
 const bars=Array.from({length:4},()=>({open:237,high:238.185,low:235.815,close:237}));
 assert.equal(c.box({brickMethod:'atr',brickAtrLength:2},bars,c.nativeTick()),2);
 assert.equal(c.box({brickMethod:'percent',brickPercent:1},bars,c.nativeTick()),3);
 assert.equal(c.box({brickMethod:'fixed',size:2.37},bars,c.nativeTick()),2.37);
 assert.equal(bars[0].close,237);
});

test('runtime exchange-qualified native token resolves only to selected instrument',()=>{
 const c=setup();
 for(const [id,exchange,prefix] of [['MO:MCX:495213','MCX','MCX'],['MO:NSEFO:123','NSEFO','NSE'],['MO:INDEX:BSE:1','BSE','BSE']]){
 const token=id.split(':').at(-1);assert.equal(c.resolve(id.slice(3),id),id);
 assert.equal(c.resolve(exchange+':'+token,id),id);assert.equal(c.resolve(prefix+':'+token,id),id);
 assert.equal(c.resolve(exchange+':99999999',id),exchange+':99999999');
 assert.equal(c.resolve('OTHER:'+token,id),'OTHER:'+token);
 }
});

test('legacy NIFTY accepts only its known NSE ticker alias',()=>{
 const c=setup();assert.equal(c.resolve('NSE:NIFTY','NIFTY'),'NIFTY');
 assert.equal(c.resolve('BSE:NIFTY','NIFTY'),'BSE:NIFTY');
 assert.equal(c.resolve('NSE:OTHER','NIFTY'),'NSE:OTHER');
});
