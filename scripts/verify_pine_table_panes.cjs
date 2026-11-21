const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const worker=process.argv[2]||'.private/chart-pine-worker.js';
(async()=>{let cases=0;for(const [overlay,expected] of [[false,2],[true,1]]){
const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;vm.runInContext(fs.readFileSync(worker,'utf8'),ctx);
const source='//@version=6\nindicator("Table ownership",overlay=false)\nvar table a=table.new(position.top_right,1,1,force_overlay=true)\nvar table b=table.new(position.top_right,1,1,force_overlay='+overlay+')\nif barstate.islast\n    table.cell(a,0,0,"PRICE")\n    table.cell(b,0,0,"SECOND")';
const bars=Array.from({length:3},(_,i)=>({openTime:1700000000000+i*1800000,closeTime:1700000000000+(i+1)*1800000,open:100,high:101,low:99,close:100,volume:1}));
const plots=await new Promise((resolve,reject)=>{ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else if(d.plots)resolve(d.plots)};Promise.resolve(ctx.onmessage({data:{source,symbolInfo:{tickerid:'DELTAIN:TEST',ticker:'TEST',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.01},frames:{'30':bars},timeframe:'30',count:bars.length}})).catch(reject)});
const tables=plots.__tables__.data.at(-1).value;assert.equal(tables.length,expected,'separate pane table ownership');assert.equal(tables.at(-1).cells[0][0].text,'SECOND');if(!overlay){assert.equal(tables[0].cells[0][0].text,'PRICE');assert.equal(tables[0].force_overlay,true);assert.equal(tables[1].force_overlay,false)}cases++;
}console.log(JSON.stringify({status:'PASS',cases}));})().catch(e=>{console.error(e.message);process.exitCode=1});
