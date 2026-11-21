const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),test=require('node:test');
require(path.resolve(process.env.CHART_STUDIES_SOURCE||'chart-workspace-studies.js'));
const run=(values,n)=>globalThis.SectorPulseChartStudies.indicators.CCI.run([],values,n)[0];
test('one-bar CCI stays unavailable after changing decimal prices',()=>assert.deepEqual(run([100,103.7,101.1,101.1],1),[null,null,null,null]));
test('expired price changes cannot leave CCI readings on a flat window',()=>{
 const values=[100,103.7,...Array(40).fill(101.1)];
 for(const n of [14,20])assert.ok(run(values,n).slice(n+1).every(x=>x===null));
});
test('nonflat CCI preserves real small price movements',()=>{
 const actual=run([1000000,1000000.00000001,1000000.00000002],3);
 assert.equal(actual[0],null);assert.equal(actual[1],null);assert.ok(Math.abs(actual[2]-100)<1e-8);
});
