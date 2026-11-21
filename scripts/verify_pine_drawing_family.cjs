const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const dir='.private/chart-order-rollouts/pine-drawing-family-audit-20261119';
(async()=>{
 const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;vm.runInContext(fs.readFileSync('.private/chart-pine-worker.js','utf8'),ctx);
 const bars=JSON.parse(fs.readFileSync('/tmp/paxg-supertrend-worker-bars.json','utf8'));
 const plots=await new Promise((resolve,reject)=>{ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else if(d.plots)resolve(d.plots)};Promise.resolve(ctx.onmessage({data:{source:fs.readFileSync(dir+'/fixture.pine','utf8'),symbolInfo:{tickerid:'DELTAIN:PAXGUSD',ticker:'PAXGUSD',prefix:'DELTAIN',type:'crypto',timezone:'UTC',session:'24x7',mintick:.1},frames:{'30':bars},timeframe:'30',count:bars.length}})).catch(reject)});
 const out={};for(const kind of ['boxes','lines','linefills','polylines']){
 const objects=[...(plots['__'+kind+'__']?.data.at(-1)?.value||[]),...(plots['__'+kind+'_overlay__']?.data.at(-1)?.value||[])];
 out[kind]={ordinary:objects.filter(x=>!x.force_overlay).length,forced:objects.filter(x=>x.force_overlay).length};
 assert.equal(out[kind].ordinary,kind==='lines'?2:1,kind+' ordinary');assert.equal(out[kind].forced,kind==='lines'?2:1,kind+' forced');
 }
 fs.writeFileSync(dir+'/worker-objects.json',JSON.stringify(plots,null,2));console.log(JSON.stringify({status:'PASS',counts:out},null,2));
})().catch(e=>{console.error(e.message);process.exitCode=1});
