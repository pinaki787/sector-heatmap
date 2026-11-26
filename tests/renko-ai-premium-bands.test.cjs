const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('chart-workspace.js','utf8');
const start=source.indexOf('  async function refreshAiPremiumBands(){'),end=source.indexOf('  function applyAiRuntimeMarkers(series,bars){',start);
const block=source.slice(start,end);
test('premium cloud seeds real OHLC once, then requests only an incremental tail after close',async()=>{
 let now=4000,calls=[],refreshes=0;
 const rows=Array.from({length:30},(_,i)=>[2200+i*60,100,110,90,101,1]);
 const context={aiRuntimeEmbedded:true,aiBandBasis:'PREMIUM',aiBandSpecs:[{kind:'SMA',period:30}],settings:{type:'Renko',interval:1},window:{RenkoAiChartSource:{context:()=>({account:'owner',run:'run'})}},location:{href:'https://example.test'},requestScope:{signal:{aborted:false}},embeddedChartHidden:()=>false,chartSymbol:()=> 'PUT',chartPrefix:'/broker-workspace/owner',aiPremiumBandCache:new Map(),aiPremiumBandRequest:null,Date:{now:()=>now*1000},Number,Map,chartQuery:p=>new URLSearchParams({...p,symbol:'PUT'}),candleEnd:(t)=>t+60,nextCandleStart:t=>t+60,aiBandCloud:{refresh:()=>refreshes++},brokerJson:async p=>{calls.push(p);return {rows:calls.length===1?[...rows,[4000,100,110,90,101,1],[3990,null,null,null,100,null]]:[...rows.slice(-3),[4000,100,120,95,105,1]]};}};
 vm.createContext(context);vm.runInContext(block,context);
 await context.refreshAiPremiumBands();await context.refreshAiPremiumBands();
 assert.equal(calls.length,1);assert.equal(context.aiPremiumBandCache.get('/broker-workspace/owner|PUT|1').rows.length,30);
 now=4063;await context.refreshAiPremiumBands();assert.equal(calls.length,2);assert.match(calls[1],/after=/);assert.equal(refreshes,2);
 assert.equal(context.aiPremiumBandCache.get('/broker-workspace/owner|PUT|1').rows.at(-1).close,105);
 context.aiBandBasis='UNDERLYING';now=5000;await context.refreshAiPremiumBands();assert.equal(calls.length,3);
});
test('parent sends each option its own band basis without changing strategy configuration',()=>{
 const js=fs.readFileSync('renko-ai-options.js','utf8');
 assert.ok(js.includes("band_basis:i===0?"));assert.ok(js.includes("'CHART':'UNDERLYING'"));
 assert.ok(js.includes("runtime_bands:sourceRun&&i===0?"));
});
