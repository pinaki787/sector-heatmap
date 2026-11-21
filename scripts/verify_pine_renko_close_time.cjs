const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const a=source.indexOf('  function pineSyntheticHostBar('),b=source.indexOf('  function pinePlotEntries(',a);
assert.ok(a>=0&&b>a,'candidate helper must exist');
const ctx={candleEnd:(time,interval)=>time+Number(interval)*60};vm.createContext(ctx);vm.runInContext(source.slice(a,b),ctx);
const bar={time:200,sourceTime:100,open:1,high:2,low:1,close:2,volume:10};
test('an open Renko projection never acquires a scheduled close',()=>{
 const input={...bar,provisional:true},before=structuredClone(input),actual=ctx.pineSyntheticHostBar(input,'30','renko');
 assert.ok(Number.isNaN(actual.closeTime));assert.equal(actual.openTime,100000);assert.equal(actual.chartTime,200000);
 assert.equal(actual.provisional,true);assert.deepEqual(input,before);
});
test('historical Renko source windows retain existing known bounds and prices',()=>{
 const actual=ctx.pineSyntheticHostBar(bar,'30','renko');
 assert.equal(actual.closeTime,1900000);assert.equal(actual.provisional,false);assert.equal(actual.close,2);
});
test('Heikin Ashi retains scheduled close and broker volume on its forming bar',()=>{
 const actual=ctx.pineSyntheticHostBar({...bar,provisional:true},'30','heikinashi');
 assert.equal(actual.closeTime,1900000);assert.equal(actual.volume,10);
});
test('display-time fallback retains millisecond precision for source-less bars',()=>{
 const actual=ctx.pineSyntheticHostBar({...bar,sourceTime:undefined,time:200.25,provisional:true},'1','renko');
 assert.equal(actual.openTime,200250);assert.equal(actual.chartTime,200250);assert.ok(Number.isNaN(actual.closeTime));
});
