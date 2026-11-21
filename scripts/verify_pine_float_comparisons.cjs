const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=process.argv[2]||'.private/chart-pine-worker.js';
const cases=[
 ['same rounded bucket',1.0000000001,1.0000000004],
 ['adjacent rounded buckets',1.00000000049,1.00000000051],
 ['negative same bucket',-1.0000000001,-1.0000000004],
 ['negative adjacent buckets',-1.00000000049,-1.00000000051],
 ['price equality artifact',3931.3,3931.2999999999993],
 ['different values',2,3],['equal integers',4,4],['zero signs',0,-0],
 ['small positive',0.0000000004,0],['small negative',-0.0000000004,0]
];
const operations=[['eq','==',(a,b)=>a===b],['neq','!=',(a,b)=>a!==b],['gt','>',(a,b)=>a>b],['ge','>=',(a,b)=>a>=b],['lt','<',(a,b)=>a<b],['le','<=',(a,b)=>a<=b]];
(async()=>{
 let checked=0;
 for(const [name,a,b] of cases){
  const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;
  vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
  const source='//@version=6\nindicator("Float comparison verification")\nfloat a=close*0+'+a+'\nfloat b=close*0+'+b+'\n'+operations.map(([key,op])=>'plot(a '+op+' b ? 1 : 0,"'+key+'")').join('\n');
  const bars=[0,1,2].map(i=>({time:1700000000+i*1800,open:100,high:101,low:99,close:100,volume:1}));
  const plots=await new Promise((resolve,reject)=>{ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else if(d.plots)resolve(d.plots)};Promise.resolve(ctx.onmessage({data:{source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'30':bars},timeframe:'30',count:bars.length}})).catch(reject)});
  const x=Number(a.toFixed(9)),y=Number(b.toFixed(9));
  for(const [key,,compare] of operations)for(const point of plots[key].data){assert.equal(point.value,compare(x,y)?1:0,name+' '+key);checked++}
 }
 console.log(JSON.stringify({status:'PASS',cases:cases.length,comparisons:checked,rule:'Float operands rounded to nine fractional digits before comparison; arithmetic unchanged.'},null,2));
})().catch(e=>{console.error(e.message);process.exitCode=1});
