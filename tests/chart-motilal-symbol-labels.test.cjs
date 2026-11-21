
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.env.CHART_SOURCE||'.private/chart-order-rollouts/motilal-symbol-labels-20261120/ticker-display/root/chart-workspace.js','utf8');
const description=source.slice(source.indexOf('  function syncInstrumentDescription('),source.indexOf('  function syncInstrumentTitle('));
const remember=source.slice(source.indexOf('  function rememberMotilalPineInstrument('),source.indexOf('  function motilalPineInstrumentType('));
const metadata=source.slice(source.indexOf('  async function loadMotilalInstrumentMetadata('),source.indexOf('  async function loadDhanInstrumentMetadata('));
function fixture(){const label={},active={},scope={aborted:false},symbols=new Map(),id='MO:INDEX:NSE:26000';
 const c={settings:{motilalSymbolLabel:id},panel:{querySelector:s=>s.includes('active-instrument')?active:label},deltaSymbolSelection:false,dhanSymbolSelection:false,motilalSymbolSelection:true,fyersSymbolSelection:false,motilalPineInstruments:symbols,syncInstrumentTitle:()=>{},chartSymbol:()=>id,chartPrefix:'/owner',URLSearchParams,AbortSignal,fetch:async()=>({ok:true,json:async()=>({symbols:[{id,symbol:'Nifty 50',exchange:'NSE',instrument:'INDEX',tick_size:.05}]})}),rememberMotilalPineInstrument:r=>{if(r)symbols.set(r.id,{symbol:r.symbol,tickSize:r.tick_size});}};
 vm.createContext(c);vm.runInContext(remember+description+metadata,c);return {c,label,active,scope,symbols,id};}
test('exact broker symbol remains the lookup key while native human label populates header and selector',async()=>{
 const f=fixture();await f.c.loadMotilalInstrumentMetadata(f.scope);assert.equal(f.active.textContent,'Nifty 50');assert.equal(f.label.textContent,'Nifty 50');assert.equal(f.c.chartSymbol(),f.id);assert.equal(f.symbols.get(f.id).tickSize,.05);assert.equal(f.c.settings.motilalSymbolLabel,f.id);
});
test('cached instrument name is preferred without rewriting saved preferences',()=>{
 const f=fixture();f.symbols.set(f.id,{symbol:'Nifty 50'});f.c.syncInstrumentDescription(f.id);assert.equal(f.label.textContent,'Nifty 50');assert.equal(f.c.settings.motilalSymbolLabel,f.id);
});
test('aborted or changed-symbol metadata cannot relabel the new chart',async()=>{
 for(const mode of ['abort','switch']){const f=fixture();f.c.fetch=async()=>{if(mode==='abort')f.scope.aborted=true;else f.c.chartSymbol=()=> 'MO:INDEX:BSE:999901';return{ok:true,json:async()=>({symbols:[{id:f.id,symbol:'Nifty 50'}]})};};await f.c.loadMotilalInstrumentMetadata(f.scope);assert.equal(f.active.textContent,undefined);assert.equal(f.symbols.size,0);}
});
test('unavailable metadata keeps existing label rather than inventing an instrument',async()=>{
 const f=fixture();f.c.settings.motilalSymbolLabel='Saved native label';f.c.fetch=async()=>({ok:false});await f.c.loadMotilalInstrumentMetadata(f.scope);f.c.syncInstrumentDescription(f.id);assert.equal(f.label.textContent,'Saved native label');
});
test('selector reconstruction uses the same cached native label',()=>{
 const f=fixture();f.symbols.set(f.id,{symbol:'Nifty 50'});const start=source.indexOf("      instruments.querySelector('[data-chart-active-instrument]').textContent =");const end=source.indexOf('\n      if (!instruments.open',start);assert.ok(start>0&&end>start);f.c.instruments={querySelector:()=>f.active};vm.runInContext(source.slice(start,end),f.c);assert.equal(f.active.textContent,'Nifty 50');
});

test('native display ticker replaces opaque broker ID without duplicating description and keeps exact ID in tooltip',()=>{
 const f=fixture();f.symbols.set(f.id,{symbol:'Nifty 50'});const legend={},description={textContent:'Nifty 50'},choice={};
 f.c.panel={querySelector:q=>q.includes('legend-symbol')?legend:q.includes('legend-description')?description:choice};
 const a=source.indexOf('  function chartDisplayTicker()'),b=source.indexOf('  function compactDeltaInstrumentDescription',a);
 const c=source.indexOf('  function syncInstrumentTitle()'),d=source.indexOf('  function syncStatusLine()',c);
 vm.runInContext(source.slice(a,b)+source.slice(c,d),f.c);
 for(const mode of ['ticker','description','both']){f.c.settings.instrumentTitleMode=mode;f.c.syncInstrumentTitle();assert.equal(legend.textContent,'Nifty 50');assert.equal(description.hidden,true);assert.match(legend.title,/MO:INDEX:NSE:26000/);}
 assert.equal(f.c.chartSymbol(),f.id);
});
test('missing native metadata retains broker ID rather than fabricating a ticker',()=>{
 const f=fixture();const a=source.indexOf('  function chartDisplayTicker()'),b=source.indexOf('  function compactDeltaInstrumentDescription',a);vm.runInContext(source.slice(a,b),f.c);assert.equal(f.c.chartDisplayTicker(),f.id);
});
