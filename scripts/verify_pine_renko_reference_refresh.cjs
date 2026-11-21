/* Same Renko geometry, advancing native reference candles; no network. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=process.argv[2]||'.private/chart-pine-worker.js',start=Date.UTC(2026,10,19,5);
const host=Array.from({length:8},(_,i)=>({openTime:start,closeTime:i===7?NaN:start+1800000,chartTime:start+i*1000,open:100+i,high:102+i,low:99+i,close:101+i,volume:NaN,provisional:i===7}));
let native=Array.from({length:3},(_,i)=>({openTime:start+i*300000,closeTime:start+(i+1)*300000,open:200+i,high:203+i,low:199+i,close:201+i,volume:10}));
let source='//@version=6\nindicator("Renko reference update",overlay=true)\nvar array<float> values=array.new<float>()\narray.push(values,close)\nx=request.security(ticker.standard(syminfo.tickerid),"5",close)\nplot(close,"host")\nplot(bar_index,"index")\nplot(array.sum(values),"persistent")\nplot(x,"reference")\nvar table t=table.new(position.top_right,1,1)\nif barstate.islast\n    table.cell(t,0,0,str.tostring(x))';
if(process.env.PINE_REFERENCE_PROBE_RSI==='1'){
 native=[...Array.from({length:500},(_,i)=>({openTime:start-(500-i)*300000,closeTime:start-(499-i)*300000,open:200,high:220,low:190,close:200+Math.sin(i*1.7)*7+i*.02,volume:10})),...native];
 source=source.replace("x=request.security(ticker.standard(syminfo.tickerid),\"5\",close)","f() =>\n    float r=ta.rsi(close,14)\n    [r,ta.sma(r,14)]\n[x,y]=request.security(ticker.standard(syminfo.tickerid),\"5\",f())").replace("plot(x,\"reference\")","plot(x,\"reference\")\nplot(y,\"reference_sma\")");
}
function runtime(){
 const c=vm.createContext({console,setTimeout,clearTimeout,structuredClone});c.self=c;
 let yes,no;
 c.postMessage=d=>{
  if(d.type==='candles'){
   const rows=d.ticker.includes(';renko')?host:native;
   c.onmessage({data:{type:'candles-result',id:d.id,rows:rows.filter(b=>(d.start==null||b.openTime>=d.start)&&(d.end==null||b.openTime<=d.end)).slice(-(d.limit||10000))}}).catch(no);
  }else if(d.ok===false)no(Error(d.error));else yes(d);
 };
 vm.runInContext(fs.readFileSync(worker,'utf8'),c);
 return {send:data=>new Promise((resolve,reject)=>{yes=resolve;no=reject;c.onmessage({data}).catch(reject)})};
}
const initial=clock=>({source,symbolInfo:{tickerid:'NSE:TEST',ticker:'TEST',prefix:'NSE',type:'index',timezone:'UTC',session:'24x7',mintick:.01},timeframe:'30',chartType:'Renko',count:host.length,replayTime:clock});
(async()=>{
 const live=runtime();const original=await live.send(initial(start+16*60000));
 native.push({openTime:start+15*60000,closeTime:start+20*60000,open:210,high:212,low:209,close:211,volume:10});
 const actual=await live.send({type:'refresh',reset:false,count:host.length,replayTime:start+21*60000});
 const expected=await runtime().send(initial(start+21*60000));
 for(const key of ['host','index','persistent']){
  assert.deepEqual(JSON.parse(JSON.stringify(actual.plots[key])),JSON.parse(JSON.stringify(expected.plots[key])),key+' retains all duplicate-source bricks and fresh reference values');
 }
 if(process.env.PINE_REFERENCE_PROBE_RSI!=='1')assert.equal(actual.plots.reference.data.at(-1).value,211);
 assert.equal(actual.plots.reference.data.at(-1).value,expected.plots.reference.data.at(-1).value);
 assert.deepEqual(JSON.parse(JSON.stringify(actual.plots.reference.data.slice(0,-1))),JSON.parse(JSON.stringify(original.plots.reference.data.slice(0,-1))),'confirmed historical reference points remain as originally published');
 console.log(JSON.stringify({status:'PASS',unchanged_bricks:host.length,native_reference:actual.plots.reference.data.at(-1).value,reference_kind:process.env.PINE_REFERENCE_PROBE_RSI==='1'?'RSI':'close',host_state_plots_match_full:true,tail_reference_matches_full:true,historical_reference_prefix_preserved:true,plots:['host','index','persistent','reference']}));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
