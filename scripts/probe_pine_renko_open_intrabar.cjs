/* Deterministic open-Renko request probe. No network, broker, or workspace writes. */
const fs=require('node:fs'),vm=require('node:vm');
const worker=process.argv[2]||'.private/chart-pine-worker.js',output=process.argv[3];
(async()=>{
 const minute=60000,start=Date.UTC(2026,10,18,12),clock=start+63*minute;
 const results=[];
 for(const unknown of [false,true]){
  const host=Array.from({length:3},(_,i)=>({openTime:start+(i-1)*30*minute,closeTime:i===2&&unknown?NaN:start+i*30*minute,chartTime:start+(i-1)*30*minute,open:100+i,high:101+i,low:100+i,close:101+i,volume:NaN,provisional:i===2}));
  const ref=Array.from({length:22},(_,i)=>({openTime:start+(i-6)*5*minute,closeTime:start+(i-5)*5*minute,open:10+i,high:11+i,low:10+i,close:11+i,volume:1}));
  const context=vm.createContext({console,setTimeout,clearTimeout,structuredClone});context.self=context;
  let source='//@version=6\nindicator("Open Renko intrabars")\na=request.security_lower_tf(ticker.standard(syminfo.tickerid),"5",close)\nplot(array.size(a),"count")\nplot(array.size(a)>0?array.last(a):na,"last")\nplot(time_close,"host_close")';
  source+="\n[priorClose,priorEnd]=request.security(ticker.standard(syminfo.tickerid),\"5\",[close[1],time_close[1]],lookahead=barmerge.lookahead_on)\nplot(priorClose,\"prior_reference_close\")\nplot(priorEnd,\"prior_reference_end\")";
  const response=await new Promise((resolve,reject)=>{
   context.postMessage=data=>data.ok===false?reject(Error(data.error)):resolve(data);
   vm.runInContext(fs.readFileSync(worker,'utf8'),context);
   context.onmessage({data:{source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'30':host,'5':ref},timeframe:'30',chartType:'Renko',count:3,replayTime:clock}}).catch(reject);
  });
  results.push({unknown_close:unknown,expected_completed_intrabar_count:6,plots:Object.fromEntries(Object.entries(response.plots).filter(([k])=>!k.startsWith('__')).map(([name,p])=>[name,p.data.map(x=>x.value)]))});
 }
 if(output)fs.writeFileSync(output,JSON.stringify(results,null,2));
 console.log(JSON.stringify(results,null,2));
})().catch(error=>{console.error(error.stack);process.exitCode=1});
