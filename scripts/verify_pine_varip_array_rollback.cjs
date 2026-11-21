const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=process.argv[2]||'.private/chart-pine-worker.js';
(async()=>{
const bars=[1,2,3].map((close,i)=>({openTime:1700000000000+i*300000,closeTime:1700000000000+(i+1)*300000,open:close,high:close+1,low:close-1,close,volume:1}));
const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;let resolve,reject;
ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else resolve(d)};
vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
const send=data=>new Promise((yes,no)=>{resolve=yes;reject=no;ctx.onmessage({data}).catch(no)});
const source='//@version=6\nindicator("Array rollback")\nvar array<float> regular=array.new<float>()\nvarip array<float> sticky=array.new<float>()\narray.push(regular,close)\narray.push(sticky,close)\nplot(array.sum(regular),"regular sum")\nplot(array.size(sticky),"sticky size")';
const check=(d,sum,size)=>{assert.equal(d.plots['regular sum'].data.at(-1).value,sum);assert.equal(d.plots['sticky size'].data.at(-1).value,size)};
check(await send({source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'5':bars},timeframe:'5',count:3}),6,3);
bars[2].close=4;check(await send({type:'refresh'}),7,4);
bars[2].close=5;check(await send({type:'refresh'}),8,5);
check(await send({type:'refresh',reset:true}),8,3);
console.log(JSON.stringify({status:'PASS',steps:['initial','two same-bar revisions','reset'],var_rollback:true,varip_tick_persistence:true}));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
