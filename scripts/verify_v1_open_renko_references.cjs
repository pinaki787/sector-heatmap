/* Frozen FYERS archive continuation; no broker calls, orders or saved preferences.
   Custom worker provider keeps native and synthetic 30m datasets separate. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
require('../chart-workspace-studies.js');
const worker=process.argv[2],workspace=process.argv[3],output=process.argv[4];
const deadline=setTimeout(()=>{console.error('Isolated V1 replay exceeded 120 seconds.');process.exit(124);},120000);
const replayStarted=Date.now();
const historyMinutes=Number(process.env.PINE_REPLAY_HISTORY_MINUTES||18000);
assert.ok(Number.isInteger(historyMinutes)&&historyMinutes>=6000&&historyMinutes<=18000);
const minute=60000;
const regular=JSON.parse(fs.readFileSync('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json')).rows.filter(row=>{
 const local=((row[0]+19800)%86400+86400)%86400;
 return local>=33300&&local<55800;
});
let archive=regular.slice(-historyMinutes,-10),clock=(archive.at(-1)[0]+60)*1000;
const frames=new Map();
function group(interval){
 const groups=new Map(),width=Number(interval)*60;
 for(const [time,open,high,low,close,volume] of archive){
  const day=Math.floor((time+19800)/86400),session=day*86400-19800+33300,end=session+22500;
  if(time<session||time>=end)continue;
  let key=session;
  if(interval==='1W'||interval==='W')key-=((day+3)%7)*86400;
  else if(interval==='1M'||interval==='M'){const d=new Date(day*86400000);key=Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),1)/1000-19800+33300;}
  else if(width)key+=Math.floor((time-session)/width)*width;
  const closeTime=(width?Math.min(end,key+width):end)*1000;
  const previous=groups.get(key);
  if(previous){previous.high=Math.max(previous.high,high);previous.low=Math.min(previous.low,low);previous.close=close;previous.volume+=volume;previous.closeTime=Math.max(previous.closeTime,closeTime);}
  else groups.set(key,{openTime:key*1000,closeTime,open,high,low,close,volume});
 }
 return [...groups.values()].map(bar=>({...bar,provisional:bar.closeTime>clock}));
}
function native(interval){
 interval=String(interval).replace(/^([DWM])$/,'1$1');
 if(!frames.has(interval))frames.set(interval,group(interval));return frames.get(interval);
}
let host,fixtureCut;
for(const cut of [10,20,30,40,50,60]){
 archive=regular.slice(-historyMinutes,-cut);clock=(archive.at(-1)[0]+60)*1000;frames.clear();
 const candidate=globalThis.SectorPulseChartStudies.renko(native('30').map(b=>({time:b.openTime/1000,open:b.open,high:b.high,low:b.low,close:b.close,volume:b.volume,provisional:b.provisional})),5,undefined,'close',true).slice(-300);
 if(candidate.at(-1)?.provisional){host=candidate;fixtureCut=cut;break;}
}
assert.ok(host,'need a real partial source period that produces projected bricks');
assert.ok(host.length>200);assert.equal(host.at(-1).provisional,true,'fixture must contain actual projected bricks from partial archive source');
const helperText=fs.readFileSync(workspace,'utf8'),a=helperText.indexOf('  function pineSyntheticHostBar('),b=helperText.indexOf('  function pinePlotEntries(',a);
assert.ok(a>=0&&b>a);
const helper=vm.createContext({candleEnd:(time,resolution)=>time+Number(resolution)*60});vm.runInContext(helperText.slice(a,b),helper);
const mapped=host.map(bar=>helper.pineSyntheticHostBar(bar,'30','renko'));
const expectedFrames=native('15').filter(b=>b.closeTime<=clock);
assert.ok(expectedFrames.length>200);
function rsi(closes,length){
 let up=0,down=0,previous=closes[0],count=0;const result=[];
 for(const current of closes.slice(1)){
  const delta=current-previous;previous=current;
  if(count<length){up+=Math.max(delta,0);down+=Math.max(-delta,0);count++;if(count===length){up/=length;down/=length;}else{result.push(null);continue;}}
  else {up=(up*(length-1)+Math.max(delta,0))/length;down=(down*(length-1)+Math.max(-delta,0))/length;}
  result.push(down===0?100:up===0?0:100-100/(1+up/down));
 }
 return result;
}
const oscillator=rsi(expectedFrames.map(b=>b.close),14),last=oscillator.at(-1),average=oscillator.slice(-14).reduce((a,b)=>a+b,0)/14;
const requests=[];
const context=vm.createContext({console,setTimeout,clearTimeout,structuredClone});context.self=context;
const source=fs.readFileSync('sector-pulse-v1.pine','utf8');
(async()=>{
 const send=data=>new Promise((resolve,reject)=>{
  context.postMessage=message=>{
   if(message.type==='candles'){
    const values=message.ticker.includes(';renko')?mapped:native(message.interval);
    const rows=values.filter(b=>(message.start==null||b.openTime>=message.start)&&(message.end==null||b.openTime<=message.end)).slice(-(message.limit||10000));
    requests.push({synthetic:message.ticker.includes(';renko'),interval:message.interval,rows:rows.length});
    globalThis.PineReplayAllocationCheckpoint?.(requests);
    if(output)fs.writeFileSync(output+'.progress.json',JSON.stringify({stage:'reference-candles',requests,last:requests.at(-1),at:Date.now()},null,2));
    void context.onmessage({data:{type:'candles-result',id:message.id,rows}}).catch(reject);
   }else if(message.ok===false)reject(Error(message.error));else resolve(message);
  };
  context.onmessage({data}).catch(reject);
 });
 vm.runInContext(fs.readFileSync(worker,'utf8'),context);
 const response=await send({source,symbolInfo:{tickerid:'NSE:NIFTY50-INDEX',ticker:'NIFTY50-INDEX',prefix:'NSE',type:'index',timezone:'Asia/Kolkata',session:'0915-1530',mintick:.05},timeframe:'30',chartType:'Renko',count:mapped.length,replayTime:clock});
 const tables=response.plots.__tables__?.data.at(-1)?.value||[];
 const panel=tables.find(t=>t.cells.some(row=>row?.[0]?.text==='RSI'));
 assert.ok(panel,'full V1 RSI table must be present');
 const rsiRow=panel.cells.find(row=>row?.[0]?.text==='RSI');
 const smaRow=panel.cells.find(row=>row?.[0]?.text==='RSI SMA');
 assert.ok(Math.abs(Number.parseFloat(rsiRow[3].text)-last)<=0.0051,'15m RSI must match independently completed native candles');
 assert.ok(Math.abs(Number.parseFloat(smaRow[3].text)-average)<=0.0051,'15m RSI SMA must match independent calculation');
 const report={plots_sha256:require('node:crypto').createHash('sha256').update(JSON.stringify(response.plots)).digest('hex'),history_minutes:historyMinutes,elapsed_seconds:(Date.now()-replayStarted)/1000,max_rss_kib:process.resourceUsage().maxRSS,independent15m_display_parity:true,scope:'Full saved V1, frozen FYERS archive, projected Renko with unknown close; no network',clock,archive_cut_minutes:fixtureCut,host_bars:host.length,projected_bricks:host.filter(b=>b.provisional).length,expected15:{end:expectedFrames.at(-1).closeTime,rsi:last,sma:average},tables,requests};
 if(process.env.PINE_REPLAY_WARM_REFERENCE==='1'){
  const before=response.plots,cut=Math.max(1,fixtureCut-5);
  assert.ok(cut<fixtureCut,'warm reference requires additional archived native candles');
  archive=regular.slice(-historyMinutes,-cut);clock=(archive.at(-1)[0]+60)*1000;frames.clear();
  const started=Date.now(),updated=await send({type:'refresh',reset:false,count:mapped.length,replayTime:clock});
  const after=updated.plots;
  let preserved=0;
  for(const [name,plot]of Object.entries(before)){
   if(name.startsWith('__')||!Array.isArray(plot.data))continue;
   assert.equal(after[name].data.length,plot.data.length,name+' retains all brick plot points');
   assert.deepEqual(JSON.parse(JSON.stringify(after[name].data.slice(0,-1))),JSON.parse(JSON.stringify(plot.data.slice(0,-1))),name+' keeps confirmed prefix unchanged');
   preserved++;
  }
  const warmTables=after.__tables__?.data.at(-1)?.value||[];
  const warmPanel=warmTables.find(t=>t.cells.some(row=>row?.[0]?.text==='RSI'));
  assert.ok(warmPanel,'warm RSI panel');
  const warmRsi=warmPanel.cells.find(row=>row?.[0]?.text==='RSI'),warmSma=warmPanel.cells.find(row=>row?.[0]?.text==='RSI SMA');
  const checks=['5','15','30'].map((frame,i)=>{
   const available=native(frame).filter(b=>b.openTime<=clock),completed=available.slice(0,-1),values=rsi(completed.map(b=>b.close),14);
   assert.ok(completed.at(-1).closeTime<=clock,frame+'m previous source is completed');
   const expected=values.at(-1),sma=values.slice(-14).reduce((sum,v)=>sum+v,0)/14;
   const observed=Number.parseFloat(warmRsi[i+2].text),observedSma=Number.parseFloat(warmSma[i+2].text);
   assert.ok(Math.abs(observed-expected)<=0.0051,frame+'m warm RSI matches V1 previous-source guard '+JSON.stringify({observed,expected,observedSma,sma,clock,end:completed.at(-1).closeTime}));
   assert.ok(Math.abs(observedSma-sma)<=0.0051,frame+'m warm RSI SMA matches V1 previous-source guard');
   return {frame,source_end:completed.at(-1).closeTime,expected,expectedSma:sma,observed,observedSma};
  });
  report.warm_reference={selection_rule:'V1 sc_closedOsc selects previous source while open Renko time_close is unknown',seconds:(Date.now()-started)/1000,clock,unchanged_host_bricks:mapped.length,numeric_prefixes_preserved:preserved,checks};
 }
 if(output)fs.writeFileSync(output,JSON.stringify(report,null,2));
 clearTimeout(deadline);
 console.log(JSON.stringify({...report,tables:tables.map(t=>({position:t.position,rows:t.rows,cells:t.cells})),requests:requests.length},null,2));
})().catch(error=>{clearTimeout(deadline);console.error(error.stack);process.exitCode=1});
