const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const [library,masterFolder,output]=process.argv.slice(2),source=fs.readFileSync(library,'utf8');
const a=source.indexOf('  const dhanPineInstruments = new Map();'),b=source.indexOf('  function pineCandleWindowForEvaluation',a);
const c=vm.createContext({motilalSymbolSelection:true,dhanSymbolSelection:false,deltaSymbolSelection:false,fyersSymbolSelection:false,settings:{},broker:{nse:true},
commoditySession:()=>false,currencySession:()=>false,fyersRegularSession:undefined,motilalNcdex:()=>false,calendarZone:()=> 'Asia/Kolkata',catalogTickSize:()=>.05});
vm.runInContext(source.slice(a,b)+';this.remember=rememberMotilalPineInstrument;this.info=workerPineSymbolInfo;this.resolve=motilalPineHostTicker',c);
const tickStart=source.indexOf('  function catalogTickSize() {'),tickEnd=source.indexOf('  function chartQuery(',tickStart);
vm.runInContext(source.slice(tickStart,tickEnd)+';this.nativeTick=catalogTickSize',c);
c.catalogTickSize=c.nativeTick;
const results=[],unknown={},ticks={},ids=new Set();let checked=0,aliases=0,unambiguous=0;
for(const file of fs.readdirSync(masterFolder).filter(x=>x.endsWith('.json'))){
 const raw=fs.readFileSync(path.join(masterFolder,file)),data=JSON.parse(raw);
 const stats={exchange:data.exchange,rows:data.rows.length,observed_at:data.observed_at,sha256:crypto.createHash('sha256').update(raw).digest('hex'),type_checked:0};
 for(const row of data.rows){
  assert.ok(!ids.has(row.symbol),'duplicate native identity');ids.add(row.symbol);
  c.chartSymbol=()=>row.symbol;
  c.remember({id:row.symbol,symbol:row.name,exchange:row.exchange,instrument:row.instrument,tick_size:row.tick_size});
  c.motilalNcdex=()=>row.exchange==='NCDEX';
  const info=c.info(row.symbol);assert.equal(info.tickerid,row.symbol);
  assert.equal(info.mintick,row.tick_size);assert.equal(c.nativeTick(),row.tick_size);ticks[row.tick_size]=(ticks[row.tick_size]||0)+1;assert.equal(info.ticker,row.name.trim());
  const kind=row.instrument,expected=kind===''?'stock':/^OPT/.test(kind)?'option':/^FUT/.test(kind)?'futures':null;
  if(expected){assert.equal(info.type,expected);stats.type_checked++;unambiguous++;}else unknown[kind]=(unknown[kind]||0)+1;
  assert.equal(c.resolve(info.ticker,row.symbol),row.symbol);
  assert.equal(c.resolve(info.prefix+':'+info.ticker,row.symbol),row.symbol);
  assert.equal(c.resolve('UNRELATED:OTHER',row.symbol),'UNRELATED:OTHER');
  assert.equal(c.resolve(row.exchange+':'+row.token,row.symbol),row.symbol);
  assert.equal(c.resolve(info.prefix+':'+row.token,row.symbol),row.symbol);
  aliases+=4;checked++;
 }
 results.push(stats);
}
const report={status:'PASS',rows_checked:checked,unique_ids:ids.size,unambiguous_types_checked:unambiguous,selected_instrument_alias_checks:aliases,
unresolved_instrument_classes:unknown,native_tick_checks:checked,tick_distribution:ticks,segments:results,scope:'Cached broker master metadata only; snapshot age retained. Index masters not persisted here. No fresh broker catalog, chart/history coverage, live feed, or order behavior claim.'};
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,rows_checked:checked,unambiguous_types_checked:unambiguous,unresolved_instrument_classes:unknown}));
