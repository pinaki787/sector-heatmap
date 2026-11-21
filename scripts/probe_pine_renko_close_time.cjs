/* Offline semantic probe; no market/order calls or saved workspace mutations. */
const fs=require('node:fs'),vm=require('node:vm');
const worker=process.argv[2]||'.private/chart-pine-worker.js';
const out=process.argv[3],workspace=process.argv[4];
const assert=require('node:assert/strict');
let mapHostBar;
if(workspace){
 const text=fs.readFileSync(workspace,'utf8'),a=text.indexOf('  function pineSyntheticHostBar('),b=text.indexOf('  function pinePlotEntries(',a);
 assert.ok(a>=0&&b>a);const helper=vm.createContext({candleEnd:(time,interval)=>time+Number(interval)*60});
 vm.runInContext(text.slice(a,b),helper);mapHostBar=helper.pineSyntheticHostBar;
}
(async()=>{
 const result=[];
 for(const mode of ['historical','projected-close','unknown-close',...(workspace?['candidate-mapped-close']:[])]){
  const clock=Date.now(),minute=60000,start=Math.floor(clock/minute)*minute;
  const bars=[
   {openTime:start-2*minute,closeTime:start-minute,chartTime:start-2*minute,open:100,high:101,low:100,close:101,volume:NaN},
   {openTime:start-minute,closeTime:start,chartTime:start-minute,open:101,high:102,low:101,close:102,volume:NaN},
   {openTime:start,closeTime:mode==='historical'?start+1000:mode==='projected-close'?start+minute:NaN,chartTime:start,open:102,high:103,low:102,close:103,volume:NaN,provisional:mode!=='historical'}
  ];
  if(mode==='candidate-mapped-close'){
   const input={time:start/1000,sourceTime:start/1000,open:102,high:103,low:102,close:103,provisional:true};
   bars[2]=mapHostBar(input,'1','renko');
  }
  if(mode==='historical')for(const b of bars){b.openTime-=2*minute;b.closeTime-=2*minute;b.chartTime-=2*minute;}
  const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;
  const d=await new Promise((resolve,reject)=>{
   ctx.postMessage=data=>data.ok===false?reject(Error(data.error)):resolve(data);
   vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
   ctx.onmessage({data:{source:'//@version=6\nindicator("Renko timestamp probe")\nplot(time_close,"close_time")\nplot(na(time_close)?1:0,"unknown_close")\nplot(barstate.isrealtime?1:0,"realtime")\nplot(barstate.isconfirmed?1:0,"confirmed")',symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'1':bars},timeframe:'1',chartType:'Renko',count:bars.length}}).catch(reject);
  });
  if(mode==='candidate-mapped-close')assert.equal(d.plots.unknown_close.data.at(-1).value,1);
  result.push({mode,expected_unknown_close:mode!=='historical',last:Object.fromEntries(Object.entries(d.plots).map(([name,plot])=>[name,plot.data.at(-1)?.value]))});
 }
 if(out)fs.writeFileSync(out,JSON.stringify(result,null,2));
 console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
