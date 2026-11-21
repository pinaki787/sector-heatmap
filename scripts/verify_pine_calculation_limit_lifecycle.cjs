const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=process.argv[2]||'.private/chart-pine-worker.js',start=Date.UTC(2026,10,18),step=300000;
const chartType=process.env.PINE_LIMIT_CHART_TYPE,renko=chartType==='Renko';
const make=i=>({openTime:start+(renko?Math.floor(i/2):i)*step,closeTime:start+((renko?Math.floor(i/2):i)+1)*step,chartTime:start+i*step,open:100+i,high:102+i,low:99+i,close:101+i,volume:10});
const bars=Array.from({length:250},(_,i)=>make(i));
(async()=>{
const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;let resolve,reject;
ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else resolve(d)};vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
const send=data=>new Promise((yes,no)=>{resolve=yes;reject=no;ctx.onmessage({data}).catch(no)});
const source='//@version=6\nindicator("Limited lifecycle",calc_bars_count=100)\nvar float sum=0\nsum+=close\nplot(close,"close")\nplot(bar_index,"index")\nplot(sum,"sum")\nif barstate.islast\n    line.new(0,close,bar_index,close)\n    label.new(bar_index,close,"latest")';
const results=[];const check=(name,d,n,offset)=>{
const p=d.plots;assert.equal(p.close.data.length,n,name+' count');assert.equal(p.index.data[0].value,0);assert.equal(p.index.data.at(-1).value,n-1);assert.equal(p.close.data[0].barIndex,offset);assert.equal(p.close.data.at(-1).barIndex,offset+n-1);assert.equal(p.close.data[0].time,make(150).openTime);
const expected=Array.from({length:n},(_,i)=>101+150+i).reduce((s,x)=>s+x,0);assert.equal(p.sum.data.at(-1).value,expected);
const line=p.__lines__.data.at(-1).value.at(-1),label=p.__labels__.data.at(-1).value.at(-1);assert.equal(line.x1,offset);assert.equal(line.x2,offset+n-1);assert.equal(label.x,offset+n-1);
results.push({name,bars:n,chart_offset:offset,status:'PASS'});
};
let d=await send({source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'5':bars},timeframe:'5',chartType,count:250});check('initial',d,100,150);assert.equal(d.inputDefinitions.find(x=>x.id==='__sp_calculated_bars').defval,100);
bars.push(make(250));d=await send({type:'refresh',reset:renko,count:251});check('realtime append grows dataset',d,101,150);
d=await send({type:'refresh',reset:true,count:251});check('reset retains original calculation anchor',d,101,150);
bars.unshift(...Array.from({length:50},(_,i)=>make(i-50)));d=await send({type:'refresh',reset:true,count:301});check('older history preserves anchor and shifts chart geometry',d,101,200);
console.log(JSON.stringify({status:'PASS',chartType:chartType||'Candles',duplicate_source_times:renko,results},null,2));
})().catch(e=>{console.error(e.stack);process.exitCode=1});
