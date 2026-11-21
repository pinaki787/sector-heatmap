const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {chartHistoryBehind}=require('../renko-supertrend.js');
test('completed broker candle catches up stopped research, without treating quiet live bricks as stale',()=>{
 assert.equal(chartHistoryBehind({candles:{latest_completed:600}},[{timestamp:300}],'draft'),true);
 for(const basis of ['active','recorded'])assert.equal(chartHistoryBehind({candles:{latest_completed:600}},[{timestamp:300}],basis),false);
 assert.equal(chartHistoryBehind({candles:{latest_completed:300}},[{timestamp:300}]),false);
 assert.equal(chartHistoryBehind({candles:{latest_completed:600}},[]),false);
 assert.equal(chartHistoryBehind({},[{timestamp:300}]),false);
});
test('real load entry and finally preserve one boundary refresh received while busy',async()=>{
 const source=fs.readFileSync('renko-supertrend.js','utf8');
 const start=source.indexOf('    async function load(){'),body=source.indexOf('      try{',start);
 const prefix=source.slice(start,body);
 const final=source.match(/finally\{busy=false;if\(seq!==version\|\|historyRefreshPending\)\{historyRefreshPending=false;load\(\);\}\}/)[0];
 const releases=[],ctx={restoreChartStyle(){},paintChartBasis(){},isBatchChartView:true,batchChartFrames:new Map(),busy:false,el:()=>({value:'GOLDM'}),historyRefreshPending:false,historyRetry:null,clearTimeout(){},connectStream(){},version:1,fetchChart:()=>new Promise(resolve=>releases.push(resolve))};
 vm.createContext(ctx);vm.runInContext(prefix+'try{await fetchChart();}'+final+'}',ctx);
 const initial=ctx.load();assert.equal(releases.length,1);
 await ctx.load();await ctx.load();assert.equal(releases.length,1);assert.equal(ctx.historyRefreshPending,true);
 releases[0]();await initial;await new Promise(r=>setImmediate(r));
 assert.equal(releases.length,2,'one queued fresh request after the old response finishes');
 releases[1]();await new Promise(r=>setImmediate(r));assert.equal(ctx.busy,false);assert.equal(releases.length,2);
});
