const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
require('../chart-workspace-studies.js');
const worker=process.argv[2]||'.private/chart-pine-worker.js';
const original=JSON.parse(fs.readFileSync(process.argv[3]||'/tmp/paxg-supertrend-worker-bars.json','utf8'));
const make=values=>values.map((close,i)=>({openTime:1700000000000+i*1800000,closeTime:1700000000000+(i+1)*1800000,open:close,high:close+1,low:close-1,close,volume:10}));
const datasets={broker:original,flat:make(Array(50).fill(100)),impulse_then_flat:make([100,103.7,...Array(48).fill(101.1)])};
(async()=>{const results=[];for(const [name,bars] of Object.entries(datasets))for(const length of [1,14,20]){
 const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
 const source='//@version=6\nindicator("CCI worker parity")\nplot(ta.cci(close,'+length+'),"CCI")';
 const plots=await new Promise((resolve,reject)=>{ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else if(d.plots)resolve(d.plots)};Promise.resolve(ctx.onmessage({data:{source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'30':bars},timeframe:'30',count:bars.length}})).catch(reject)});
 const want=globalThis.SectorPulseChartStudies.indicators.CCI.run(bars,bars.map(x=>x.close),length)[0];let max=0,count=0;
 assert.equal(plots.CCI.data.length,want.length);
 for(let i=0;i<want.length;i++){const got=plots.CCI.data[i].value;assert.equal(got==null,want[i]==null,name+'/'+length+' null at'+i);if(want[i]!=null){const error=Math.abs(got-want[i]);assert.ok(error<1e-8,name+'/'+length+' value at'+i);max=Math.max(max,error);count++}}
 results.push({dataset:name,length,numeric_points:count,max_error:max,null_masks_exact:true});
}console.log(JSON.stringify({status:'PASS',results,scope:'Actual worker versus independently Decimal-validated built-in CCI; external feed/seed separate.'},null,2))})().catch(e=>{console.error(e.message);process.exitCode=1});
