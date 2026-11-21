
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
require('../chart-workspace-studies.js');const lib=globalThis.SectorPulseChartStudies;
const worker=fs.readFileSync('.private/chart-pine-worker.js','utf8'),main=fs.readFileSync('chart-workspace.js','utf8');
const a=main.indexOf('  function pineSyntheticHostBar('),b=main.indexOf('  function pinePlotEntries(',a),mapper={candleEnd:t=>t+60};vm.createContext(mapper);vm.runInContext(main.slice(a,b),mapper);
async function evaluate(bars){
 const frames=bars.map(b=>mapper.pineSyntheticHostBar(b,'1','renko')),messages=[];
 const scope={console,setTimeout,clearTimeout,setInterval,clearInterval,TextEncoder,TextDecoder,AbortController,URL,performance:require('node:perf_hooks').performance};
 scope.self=scope;scope.postMessage=m=>messages.push(m);vm.createContext(scope);vm.runInContext(worker,scope,{timeout:15000});
 await scope.onmessage({data:{source:'//@version=6\nindicator("Sector Pulse volume check")\nplot(volume,"Brick volume")\nplot(ta.cum(volume),"Cumulative brick volume")',chartType:'Renko',timeframe:'1',count:frames.length,frames:{'1':frames},symbolInfo:{tickerid:'DELTAIN:BTCUSD',ticker:'BTCUSD',prefix:'DELTAIN',type:'crypto',timezone:'Etc/UTC',mintick:.5,pricescale:2,minmove:1,session:'24x7',currency:'USD',basecurrency:'BTC'},inputs:{}}});
 const error=messages.find(m=>m.ok===false);assert.ok(!error,JSON.stringify(error));const ready=messages.find(m=>m.type==='ready');assert.ok(ready);
 return ready.plots;
}
function confirmed(){return lib.renko([{time:0,open:100,high:100,low:100,close:100,volume:10},{time:60,open:100,high:125,low:100,close:125,volume:30}],10);}
test('actual Pine worker plots allocated confirmed brick volume and cumulative volume',async()=>{
 const plots=await evaluate(confirmed());assert.deepEqual(Array.from(plots['Brick volume'].data,p=>p.value),[20,20]);assert.deepEqual(Array.from(plots['Cumulative brick volume'].data,p=>p.value),[20,40]);
});
test('actual Pine worker receives zero for certified projection without consuming future source volume',async()=>{
 const bars=confirmed();bars.push({time:3,sourceTime:120,open:120,high:129,low:120,close:129,volume:0,renkoVolume:true,provisional:true});
 const plots=await evaluate(bars);assert.deepEqual(Array.from(plots['Brick volume'].data,p=>p.value),[20,20,0]);assert.deepEqual(Array.from(plots['Cumulative brick volume'].data,p=>p.value),[20,40,40]);
});
