const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('chart-workspace.js','utf8');
const start=source.indexOf("      if(!updated && settings.type==='Renko' && window.RenkoAiChartSource?.context(location.href)");
const end=source.indexOf('      if (!updated && !pendingViewportRedraw',start);
const block=source.slice(start,end);
function run(owned,fail=false,type='Renko'){
 const previous=[{time:1,close:100}],merged=[...previous,{time:2,close:101},{time:3,close:102}];
 const calls=[],ctx={settings:{type},window:{RenkoAiChartSource:{context:()=>owned}},location:{href:'https://example.invalid'},updated:false,referenceChanged:false,pendingViewportRedraw:false,previous,merged,rows:merged,sameCandle:(a,b)=>a.time===b.time&&a.close===b.close};
 ctx.updateLastPrice=bar=>{calls.push([bar.time,ctx.rows.length]);return !fail;};
 vm.runInNewContext(block,ctx);return {ctx,calls};
}
test('owned chart applies every appended observation in order without a full replay',()=>{
 const {ctx,calls}=run(true);assert.equal(ctx.updated,true);assert.deepEqual(calls,[[2,2],[3,3]]);assert.equal(ctx.rows,ctx.merged);
});
test('standalone chart remains outside owned runtime append handling',()=>{assert.deepEqual(run(false).calls,[]);});
test('failed incremental update restores full rows for normal reconciliation',()=>{const {ctx,calls}=run(true,true);assert.equal(ctx.updated,false);assert.equal(ctx.rows,ctx.merged);assert.equal(calls.length,1);});

test('owned alternate views stay outside runtime-close append handling',()=>{assert.deepEqual(run(true,false,'Candles').calls,[]);assert.deepEqual(run(true,false,'Line').calls,[]);});
