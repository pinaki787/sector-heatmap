const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=process.argv[2]||'.private/chart-pine-worker.js',M=60000,start=Date.UTC(2026,10,1,6);
const source='//@version=6\nindicator("Metadata history")\nf() =>\n    [time,time_close,hour]\n[o,c,h]=f()\nint assigned=time_close\nvar int firstOpen=time\nvar int firstClose=time_close\nvar int firstHour=hour\nvarip int firstCloseIp=time_close\nplot(time_close,"current")\nplot(time_close[1],"direct")\nplot(assigned[1],"assigned")\nplot(c[1],"tuple")\nplot(h[1],"previous_hour")\nplot(firstOpen,"first_open")\nplot(firstClose,"first_close")\nplot(firstHour,"first_hour")\nplot(firstCloseIp,"first_close_ip")';
async function run(frame){
 const step=Number(frame)*M,bars=Array.from({length:40},(_,i)=>({openTime:start+i*step,closeTime:start+(i+1)*step,open:100,high:110,low:90,close:105+i%3,volume:10}));
 const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;let resolve,reject,last;
 ctx.postMessage=d=>{if(d.ok===false)return reject(Error(d.error));if(d.plots){last=d.plots;resolve(last)}else if(d.type==='updated')resolve(last)};
 vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
 const send=data=>new Promise((yes,no)=>{resolve=yes;reject=no;ctx.onmessage({data}).catch(no)});
 let plots=await send({source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.5},frames:{[frame]:bars},timeframe:frame,count:40});
 const values=name=>Array.from(plots[name].data,p=>p.value);
 const check=()=>{const closes=bars.map(b=>b.closeTime),previous=[null,...closes.slice(0,-1)];
  assert.deepEqual(values('current'),closes);
  for(const name of ['direct','assigned','tuple'])assert.deepEqual(values(name),previous,frame+' '+name);
  assert.deepEqual(values('previous_hour'),[null,...bars.slice(0,-1).map(b=>new Date(b.openTime).getUTCHours())]);
  for(const [name,value] of [['first_open',start],['first_close',start+step],['first_close_ip',start+step],['first_hour',6]])assert.ok(values(name).every(v=>v===value),frame+' '+name);
 };
 check();
 bars.at(-1).closeTime+=M;plots=await send({type:'refresh'});check();
 plots=await send({type:'refresh',reset:true});check();
 bars.push({openTime:start+40*step,closeTime:start+41*step,open:105,high:112,low:100,close:109,volume:12});
 plots=await send({type:'refresh',count:41});check();
 return {frame,bars:41,steps:['initial','same_bar_metadata_revision','reset','new_bar'],status:'PASS'};
}
(async()=>{const results=[];for(const frame of ['5','15','30'])results.push(await run(frame));console.log(JSON.stringify({status:'PASS',scope:'Synthetic metadata assignment/history, persistent var/varip and worker refresh; no broker requests',results},null,2))})().catch(e=>{console.error(e.message);process.exitCode=1});
