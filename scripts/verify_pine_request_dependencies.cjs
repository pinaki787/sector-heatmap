const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [baseline,candidate]=process.argv.slice(2),start=Date.UTC(2026,10,18,4);
const bars=Array.from({length:100},(_,i)=>({openTime:start+i*60000,closeTime:start+(i+1)*60000,open:100+i,high:103+i,low:99+i,close:101+i,volume:10}));
async function run(worker,body){
 const c=vm.createContext({console,setTimeout,clearTimeout,structuredClone});c.self=c;
 return new Promise((resolve,reject)=>{
  c.postMessage=d=>d.ok===false?reject(Error(d.error)):d.plots&&resolve(JSON.parse(JSON.stringify(d.plots)));
  vm.runInContext(fs.readFileSync(worker,'utf8'),c);
  c.onmessage({data:{source:'//@version=6\nindicator("Dependencies")\n'+body,
   symbolInfo:{tickerid:'NSE:TEST',ticker:'TEST',prefix:'NSE',type:'stock',timezone:'UTC',session:'24x7',mintick:.01},
   frames:{'1':bars,'5':bars.filter((_,i)=>i%5===0).map(b=>({...b,closeTime:b.openTime+300000}))},timeframe:'5',count:20,replayTime:start+100*60000}}).catch(reject);
 });
}
const cases=[
 ['array instance method mutation','var array<float> a=array.new<float>()\na.push(close)\nif a.size()>5\n    a.shift()\nx=request.security(syminfo.tickerid,"1",a.sum())\nplot(x,"x")'],
 ['global array mutation from no-argument function','var array<float> a=array.new<float>()\nf() =>\n    array.push(a,close)\n    if array.size(a)>5\n        array.shift(a)\nf()\nx=request.security(syminfo.tickerid,"1",array.sum(a))\nplot(x,"x")'],
 ['tuple function histories','f() =>\n    [ta.sma(close,3),ta.ema(close,5)]\n[a,b]=request.security(syminfo.tickerid,"1",f())\nplot(a,"a")\nplot(b,"b")'],

 ['conditional persistent scalar','var float s=0\nif close>open\n    s+=close\nf() => s\nx=request.security(syminfo.tickerid,"1",f())\nplot(x,"x")'],
 ['array mutations through generated params','var array<float> a=array.new<float>()\narray.push(a,close)\nif array.size(a)>5\n    array.shift(a)\nx=request.security(syminfo.tickerid,"1",array.avg(a))\nplot(x,"x")'],
 ['function argument mutates shared array','var array<float> a=array.new<float>()\nf(array<float> v) =>\n    array.push(v,close)\n    if array.size(v)>5\n        array.shift(v)\nf(a)\nx=request.security(syminfo.tickerid,"1",array.sum(a))\nplot(x,"x")'],
 ['transitive functions and inputs','n=input.int(4)\nf() => ta.sma(close,n)\ng() => f()*2\nx=request.security(syminfo.tickerid,"1",g())\nplot(x,"x")'],
 ['two independent request histories','x=request.security(syminfo.tickerid,"1",ta.sma(close,3))\ny=request.security(syminfo.tickerid,"1",ta.ema(close,5))\nplot(x,"x")\nplot(y,"y")'],
 ['object field mutation','type Rec\n    float v\nvar array<Rec> a=array.new<Rec>()\nif array.size(a)==0\n    array.push(a,Rec.new(0))\nRec r=array.last(a)\nr.v:=close\nx=request.security(syminfo.tickerid,"1",r.v)\nplot(x,"x")']
];
(async()=>{
 const report=[];
 for(const [name,body]of cases){
  let before,after;
  try{before=await run(baseline,body)}catch(e){throw Error(name+' baseline: '+e.message)}
  try{after=await run(candidate,body)}catch(e){throw Error(name+' candidate: '+e.message)}
  assert.deepEqual(after,before,name);report.push({name,passed:true});
 }
 console.log(JSON.stringify(report));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
