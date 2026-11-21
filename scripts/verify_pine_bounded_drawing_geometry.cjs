const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=process.argv[2]||'.private/chart-pine-worker.js',start=Date.UTC(2026,10,18),step=300000;
const source='//@version=6\nindicator("Bounded geometry",overlay=false,calc_bars_count=100)\nplot(bar_index,"index")\nif barstate.islast\n    line a=line.new(0,close,bar_index,close)\n    line b=line.new(0,close+1,bar_index,close+1)\n    linefill.new(a,b,color.red)\n    line c=line.new(0,close,bar_index,close,force_overlay=true)\n    line d=line.new(0,close+1,bar_index,close+1,force_overlay=true)\n    linefill.new(c,d,color.red)\n    line e=line.new(time[5],close,time,close,xloc=xloc.bar_time)\n    line f=line.new(time[5],close+1,time,close+1,xloc=xloc.bar_time)\n    linefill.new(e,f,color.red)\n    box.new(bar_index-5,close+1,bar_index,close)\n    box.new(bar_index-5,close+1,bar_index,close,force_overlay=true)\n    box.new(time[5],close+1,time,close,xloc=xloc.bar_time)\n    label.new(bar_index,close,"index")\n    label.new(bar_index,close,"forced",force_overlay=true)\n    label.new(time,close,"time",xloc=xloc.bar_time)\n    array<chart.point> points=array.from(chart.point.from_index(0,close),chart.point.from_index(bar_index,close+1))\n    polyline.new(points)\n    polyline.new(points,force_overlay=true)\n    array<chart.point> timed=array.from(chart.point.from_time(time[5],close),chart.point.from_time(time,close+1))\n    polyline.new(timed,xloc=xloc.bar_time)';
async function run(chartType){
 const renko=chartType==='Renko',make=i=>({openTime:start+(renko?Math.floor(i/2):i)*step,closeTime:start+((renko?Math.floor(i/2):i)+1)*step,chartTime:start+i*step,open:100+i,high:102+i,low:99+i,close:101+i,volume:10}),bars=Array.from({length:250},(_,i)=>make(i));
 const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;let resolve,reject;ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else resolve(d)};vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
 const send=data=>new Promise((yes,no)=>{resolve=yes;reject=no;ctx.onmessage({data}).catch(no)});
 const check=(d,offset)=>{const objects=kind=>[...(d.plots['__'+kind+'__']?.data.at(-1)?.value||[]),...(d.plots['__'+kind+'_overlay__']?.data.at(-1)?.value||[])];
  assert.equal(d.plots.index.data.length,100);assert.equal(d.plots.index.data[0].value,0);assert.equal(d.plots.index.data.at(-1).value,99);
  const from=bars.at(-6).openTime,to=bars.at(-1).openTime;
  for(const kind of ['lines','boxes','labels','linefills','polylines']){
   const values=objects(kind);assert.equal(values.length,kind==='lines'?6:3,kind+' count');
   for(const object of values){const timed=(kind==='linefills'?object.line1:object).xloc==='bt';
    if(kind==='lines'){assert.equal(object.x1,timed?from:offset);assert.equal(object.x2,timed?to:offset+99)}
    if(kind==='boxes'){assert.equal(object.left,timed?from:offset+94);assert.equal(object.right,timed?to:offset+99)}
    if(kind==='labels')assert.equal(object.x,timed?to:offset+99);
    if(kind==='linefills')for(const line of [object.line1,object.line2]){assert.equal(line.x1,timed?from:offset);assert.equal(line.x2,timed?to:offset+99)}
    if(kind==='polylines'){assert.equal(object.points[0][timed?'time':'index'],timed?from:offset);assert.equal(object.points[1][timed?'time':'index'],timed?to:offset+99)}
   }
  }
 };
 let d=await send({source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'5':bars},timeframe:'5',chartType,count:250});check(d,150);
 bars.unshift(...Array.from({length:50},(_,i)=>make(i-50)));d=await send({type:'refresh',reset:true,count:300});check(d,200);
 return {chartType,phases:['initial','older history prepend'],families:5,bar_index_and_time_coordinates:true,forced_and_pane_objects:true,status:'PASS'};
}
(async()=>{const results=[];for(const type of ['Candles','Heikin Ashi','Renko'])results.push(await run(type));console.log(JSON.stringify({status:'PASS',results},null,2))})().catch(e=>{console.error(e.stack);process.exitCode=1});
