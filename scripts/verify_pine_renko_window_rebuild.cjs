const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=process.argv[2]||'.private/chart-pine-worker.js',start=Date.UTC(2026,10,18),step=300000;
const make=i=>({openTime:start+Math.floor(i/2)*step,closeTime:start+(Math.floor(i/2)+1)*step,chartTime:start+i*step,open:100+i,high:102+i,low:99+i,close:101+i,volume:10});
(async()=>{
 const bars=Array.from({length:250},(_,i)=>make(i)),ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;let resolve,reject;
 ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else resolve(d)};vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
 const send=data=>new Promise((yes,no)=>{resolve=yes;reject=no;ctx.onmessage({data}).catch(no)});
 const source='//@version=6\nindicator("Renko window",calc_bars_count=100)\nvar float total=0\ntotal+=close\nplot(close,"close")\nplot(bar_index,"index")\nplot(total,"total")\nif barstate.islast\n    line.new(0,close,bar_index,close)';
 const results=[];const check=(name,d,n,offset)=>{
  const p=d.plots,want=bars.slice(-n);assert.equal(p.close.data.length,n,name);assert.equal(p.index.data[0].value,0);assert.equal(p.index.data.at(-1).value,n-1);assert.equal(p.close.data[0].barIndex,offset);assert.equal(p.close.data.at(-1).barIndex,offset+n-1);assert.equal(p.close.data[0].value,want[0].close);assert.ok(Math.abs(p.total.data.at(-1).value-want.reduce((s,b)=>s+b.close,0))<1e-8);
  const line=p.__lines__.data.at(-1).value.at(-1);assert.equal(line.x1,offset);assert.equal(line.x2,offset+n-1);results.push({name,bars:n,chart_offset:offset,status:'PASS'});
 };
 let d=await send({source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'5':bars},timeframe:'5',chartType:'Renko',count:250});check('initial',d,100,150);
 bars.push(make(250));d=await send({type:'refresh',reset:true,count:251});check('ordinary append retains original start',d,101,150);
 for(const bar of bars)for(const key of ['open','high','low','close'])bar[key]+=.5;
 d=await send({type:'refresh',reset:true,restartCalculation:true,count:251});check('confirmed geometry rebuild starts fresh bounded calculation',d,100,151);
 for(const bar of bars)bar.chartTime+=1;
 d=await send({type:'refresh',reset:true,count:251});check('removed Renko anchor recovers automatically',d,100,151);
 console.log(JSON.stringify({status:'PASS',duplicate_source_times:true,results},null,2));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
