const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const manifest='.private/changes/execution-release-20261126/distribution.json';
const owners=fs.existsSync(manifest)?Object.keys(JSON.parse(fs.readFileSync(manifest,'utf8'))):[];
test('every maintained chart processes fresh owned forming OHLC and refuses stale or wrong-frame data',()=>{
 for(const base of ['.',...owners.map(o=>'.private/dashboard-login/accounts/'+o+'/source')]){
  const source=fs.readFileSync(path.join(base,'chart-workspace.js'),'utf8'),a=source.indexOf("      const ownedQuote=frame.source_basis==='AI_RUNTIME_QUOTE_ONLY';"),b=source.indexOf('      updateActiveWatchlistQuote(frame);',a);assert.ok(a>=0,base);
  for(const variant of ['fresh','stale','wrong-frame']){
   let rendered=0,ltp=0;const output={textContent:''},now=1800000005;
   const frame={source_basis:'AI_RUNTIME_QUOTE_ONLY',connected:true,latest_price:102,forming_row:[1800000000,100,103,99,102,null],forming_frame:variant==='wrong-frame'?5:1,forming_at:variant==='stale'?now-65:now};
   const c={frame,latestLiveTick:now,Date:{now:()=>now*1000},Number,panel:{querySelector:()=>output},formatChartPrice:String,interval:1,candleEnd:(t,m)=>t+m*60,updateRuntimeQuotePrice:()=>ltp++,renderLiveRows:()=>rendered++};
   vm.createContext(c);vm.runInContext(source.slice(a,b),c);assert.equal(rendered,variant==='fresh'?1:0,base+' '+variant);assert.equal(ltp,1);
  }
  assert.match(source,/if \(!ownedQuote && \(revision !== liveRevision/);assert.match(source,/if \(!ownedQuote && Number.isFinite\(latestLiveTick\)\)/);
 }
});
