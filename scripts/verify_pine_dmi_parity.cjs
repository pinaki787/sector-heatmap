const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
require('../chart-workspace-studies.js');
const worker=process.argv[2]||'.private/chart-pine-worker.js';
const broker=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const make=(count,kind)=>Array.from({length:count},(_,i)=>({
 openTime:1700000000000+i*1800000,closeTime:1700000000000+(i+1)*1800000,
 open:100,close:100,high:kind==='flat'?100:100.1+i/10,low:kind==='flat'?100:99.8-i/10,volume:10
}));
const datasets={equal_moves:make(100,'tie'),flat:make(80,'flat'),broker,one:make(1,'tie'),short:make(5,'tie')};
(async()=>{
const results=[];
for(const [name,bars] of Object.entries(datasets))for(const [length,smoothing] of [[1,1],[2,3],[7,14],[14,14],[20,7]]){
 const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;
 vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
 const source='//@version=6\nindicator("DMI worker parity")\n[p,m,a]=ta.dmi('+length+','+smoothing+')\nplot(p,"plus")\nplot(m,"minus")\nplot(a,"adx")';
 const plots=await new Promise((resolve,reject)=>{
 ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else if(d.plots)resolve(d.plots)};
 Promise.resolve(ctx.onmessage({data:{source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'30':bars},timeframe:'30',count:bars.length}})).catch(reject);
 });
 const want=globalThis.SectorPulseChartStudies.indicators.DMI.run(bars,bars.map(x=>x.close),length,smoothing);
 let numeric=0,missing=0,max=0;
 ['plus','minus','adx'].forEach((key,p)=>{
 assert.equal(plots[key].data.length,want[p].length);
 want[p].forEach((expected,i)=>{
 const got=plots[key].data[i].value;
 assert.equal(got==null,expected==null,name+'/'+length+'/'+smoothing+'/'+key+' missing '+i);
 if(expected==null){missing++;return}
 const error=Math.abs(got-expected);assert.ok(error<1e-8,name+'/'+length+'/'+smoothing+'/'+key+' bar '+i+' got '+got+' expected '+expected);
 max=Math.max(max,error);numeric++;
 });
 });
 results.push({dataset:name,length,smoothing,numeric,missing,max_error:max});
}
console.log(JSON.stringify({status:'PASS',cases:results.length,results,scope:'Actual full Pine worker compared with separately Decimal50-validated built-in DMI; external TradingView seed/feed parity not claimed.'},null,2));
})().catch(e=>{console.error(e.message);process.exitCode=1});
