const test=require('node:test'),assert=require('node:assert/strict');
require(process.env.CHART_STUDIES_SOURCE||'../chart-workspace-studies.js');
const trix=globalThis.SectorPulseChartStudies.indicators.TRIX;
test('length1 log-price change uses native TRIX basis-point scale',()=>{
 const values=[1,Math.E],bars=values.map(close=>({open:close,high:close,low:close,close}));
 assert.deepEqual(trix.run(bars,values,1)[0],[null,10000]);
});
test('unit price has a valid zero logarithm rather than an unavailable denominator',()=>{
 const values=Array(20).fill(1),bars=values.map(close=>({open:close,high:close,low:close,close}));
 assert.deepEqual(trix.run(bars,values,18)[0],[null,...Array(19).fill(0)]);
});
test('invalid price source cannot emit an infinite or NaN chart point',()=>{
 const values=[0,-1,NaN,Infinity],bars=values.map(close=>({open:close,high:close,low:close,close}));
 assert.deepEqual(trix.run(bars,values,18)[0],[null,null,null,null]);
});
