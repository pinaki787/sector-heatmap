const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
require('../chart-workspace-studies.js');
const worker=process.argv[2]||'.private/chart-pine-worker.js',bars=JSON.parse(fs.readFileSync(process.argv[3]||'/tmp/paxg-supertrend-worker-bars.json','utf8'));
const results=[];
(async()=>{for(const length of [1,7,10,14])for(const factor of [1.5,3]){
 const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
 const source='//@version=6\nindicator("Pine Supertrend parity")\n[s,d]=ta.supertrend('+factor+','+length+')\nplot(s,"line")\nplot(d,"direction")';
 const plots=await new Promise((resolve,reject)=>{ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else if(d.plots)resolve(d.plots)};ctx.onmessage({data:{source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'30':bars},timeframe:'30',count:bars.length}}).catch(reject)});
 const [up,down]=globalThis.SectorPulseChartStudies.indicators.Supertrend.run(bars,bars.map(b=>b.close),length,factor);
 assert.equal(plots.line.data.length,bars.length);let max=0,compared=0;
 for(let i=0;i<bars.length;i++){const expected=up[i]??down[i],direction=up[i]!=null?-1:down[i]!=null?1:null,actual=plots.line.data[i].value;assert.equal(plots.direction.data[i].value,direction,'direction '+length+'/'+factor+' bar'+i);assert.equal(actual==null,expected==null,'warmup');if(expected!=null){const error=Math.abs(actual-expected);max=Math.max(max,error);assert.ok(error<1e-8,'line '+length+'/'+factor+' bar'+i);compared++}}
 results.push({length,factor,compared,max_error:max});
}console.log(JSON.stringify({status:'PASS',rows:bars.length,results,scope:'Pine runtime ta.supertrend versus separately Decimal-validated built-in chart calculation; no external feed or seeding parity claim.'},null,2))})().catch(e=>{console.error(e.message);process.exitCode=1});
