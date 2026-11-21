const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),test=require('node:test');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const start=source.indexOf('    if (restoredViewAnchor && settings.range) {');
const end=source.indexOf('    if (isRenko && renkoReturnView',start);
assert.ok(start>0&&end>start);
const code=source.slice(start,end);
function render(state){
 const bars=Array.from({length:state.count||616},(_,i)=>({time:i,sourceTime:100000+i*1800,open:100,close:105}));
 const ctx={...state,bars,isRenko:true,firstBrickBySource:new Map(),byTime:new Map(),indexes:new Map(),chartRangeToLatest:(n,from)=>({from,to:n+6}),latestChartBar:n=>n-1,Math};
 ctx.chart={timeScale:()=>({setVisibleLogicalRange:range=>{ctx.visible=range}})};
 vm.runInNewContext(code,ctx);return ctx;
}
test('queued anchor without its range is consumed during the initial rebuild',()=>{
 const state=render({settings:{},restoredViewAnchor:{index:998,latest:true}});
 assert.equal(state.restoredViewAnchor,undefined);
 assert.equal(state.settings.range,undefined);
});
test('later Go-to range cannot inherit a stale candle-axis anchor',()=>{
 const initial=render({settings:{},restoredViewAnchor:{index:998,latest:true}});
 initial.settings.range={from:516,to:622};
 const next=render({settings:initial.settings,restoredViewAnchor:initial.restoredViewAnchor});
 assert.equal(next.visible.from,516);assert.equal(next.visible.to,622);
});
test('valid paired latest anchor follows an appended Renko brick exactly once',()=>{
 const state=render({count:617,settings:{range:{from:516,to:622}},restoredViewAnchor:{index:615,latest:true}});
 assert.equal(state.visible.from,517);assert.equal(state.visible.to,623);
 assert.equal(state.restoredViewAnchor,undefined);
});
