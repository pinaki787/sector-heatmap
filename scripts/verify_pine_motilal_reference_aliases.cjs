const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [library,worker,output]=process.argv.slice(2),code=fs.readFileSync(library,'utf8');
const a=code.indexOf('  const dhanPineInstruments = new Map();'),b=code.indexOf('  function pineCandleWindowForEvaluation',a);
const fixtures=[
 {id:'NIFTY',symbol:'NIFTY',exchange:'NSE',instrument:'INDEX',tick_size:.05,type:'index'},
 {id:'MO:INDEX:BSE:1',symbol:'SENSEX',exchange:'BSE',instrument:'INDEX',tick_size:.05,type:'index'},
 {id:'MO:MCX:495213',symbol:'GOLD 04-Dec-2026',exchange:'MCX',instrument:'FUTCOM',tick_size:1,type:'futures'},
 {id:'MO:NSEFO:123',symbol:'NIFTY 26-Nov-2026 PE',exchange:'NSEFO',instrument:'OPTIDX',tick_size:.05,type:'option'},
 {id:'MO:NCDEX:126',symbol:'JEERA 20-Dec-2026',exchange:'NCDEX',instrument:'OPTFUT',tick_size:5,type:'option'},
 {id:'MO:NSE:1333',symbol:'HDFCBANK',exchange:'NSE',instrument:'',tick_size:.05,type:'stock'}
];
(async()=>{
const results=[];
for(const row of fixtures)for(const chartType of ['Candles','Line','Heikin Ashi','Renko']){
 const front=vm.createContext({motilalSymbolSelection:true,dhanSymbolSelection:false,deltaSymbolSelection:false,fyersSymbolSelection:false,settings:{},broker:{nse:true,venue:'NSE'},
 commoditySession:()=>['MCX','NCDEX'].includes(row.exchange),currencySession:()=>false,fyersRegularSession:undefined,motilalNcdex:()=>row.exchange==='NCDEX',calendarZone:()=> 'Asia/Kolkata',catalogTickSize:()=>row.tick_size});
 vm.runInContext(code.slice(a,b)+';this.remember=rememberMotilalPineInstrument;this.info=workerPineSymbolInfo;this.resolve=motilalPineHostTicker',front);
 front.remember(row);const symbolInfo=front.info(row.id);
 const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;
 vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
 const start=Date.UTC(2026,10,17,3,45),make=(minutes,n)=>Array.from({length:n},(_,i)=>({openTime:start+i*minutes*60000,closeTime:start+(i+1)*minutes*60000,open:100,high:101,low:99,close:100,volume:10}));
 const frames={'5':make(5,240),'30':make(30,40)},requests=[];let plots;
 const synthetic={Renko:'renko','Heikin Ashi':'heikinashi'}[chartType],syntheticTicker=row.id+';'+synthetic;
 await new Promise((resolve,reject)=>{
 let timer=setTimeout(()=>reject(Error('Worker alias probe timed out')),15000);
 const fail=e=>{clearTimeout(timer);reject(e)};
 ctx.postMessage=d=>{
 if(d.ok===false)return fail(Error(d.error));
 if(d.type==='candles'){
  const syntheticHost=synthetic && d.ticker===syntheticTicker;
  const native=syntheticHost?row.id:front.resolve(d.ticker,row.id);requests.push({ticker:d.ticker,interval:d.interval,resolved:native,synthetic_host:!!syntheticHost});
  let error,rows;
  if(native!==row.id)error='Unexpected native alias '+d.ticker+' resolved '+native;
  else{rows=frames[String(d.interval)];if(!rows)error='Unsupported fixture interval '+d.interval;else rows=rows.filter(r=>(d.start==null||r.openTime>=d.start)&&(d.end==null||r.openTime<=d.end)).slice(-(d.limit||5000));}
  Promise.resolve(ctx.onmessage({data:{type:'candles-result',id:d.id,rows,error}})).catch(fail);return;
 }
 if(d.plots){plots=d.plots;clearTimeout(timer);resolve();}
 };
 const source='//@version=6\nindicator("Motilal reference aliases")\nvar array<float> probe=array.new<float>()\nstring native=ticker.standard(syminfo.tickerid)\nstring named=ticker.new(syminfo.prefix,syminfo.ticker,session.regular)\nplot(request.security(native,"5",close),"native")\nplot(request.security(named,"5",close),"named")\nplot(syminfo.type=="'+row.type+'" ? 1 : 0,"type")\nplot(syminfo.mintick,"tick")';
 Promise.resolve(ctx.onmessage({data:{source,symbolInfo,timeframe:'30',count:40,chartType}})).catch(fail);
 });
 for(const key of ['native','named']){const values=plots[key].data.map(p=>p.value).filter(v=>v!=null);assert.ok(values.length>0,row.id+' '+key+' finite');assert.ok(values.every(v=>v===100),row.id+' '+key+' close');}
 assert.ok(plots.type.data.every(p=>p.value===1));assert.ok(plots.tick.data.every(p=>p.value===row.tick_size));
 results.push({id:row.id,chartType,type:row.type,tick:row.tick_size,requests,native_and_named_reference:true});
}
const report={status:'PASS',results,scope:'Full Pine worker request messages routed through actual selected-instrument alias helper; synthetic candles across4chartType flags; no candle/HA/brick construction parity claim. No fresh authenticated Motilal requests or live/feed/order verification.'};
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
})().catch(e=>{console.error(e.message);process.exitCode=1});
