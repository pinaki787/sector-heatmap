const test=require('node:test'),assert=require('node:assert/strict');
require('../chart-workspace-studies.js');
const studies=globalThis.SectorPulseChartStudies.indicators;
test('equal decimal directional moves do not create a directional trend',()=>{
 const bars=[
 {open:100,high:100.1,low:99.8,close:100},
 {open:100,high:100.2,low:99.7,close:100}];
 const result=studies.DMI.run(bars,bars.map(b=>b.close),1,1);
 assert.deepEqual(result.map(plot=>plot[1]),[0,0,0]);
});
test('unequal directional movement retains unrounded magnitude',()=>{
 const bars=[
 {open:100,high:100.1,low:99.8,close:100},
 {open:100,high:100.223456789123,low:99.7,close:100}];
 const result=studies.DMI.run(bars,bars.map(b=>b.close),1,1);
 const expected=(bars[1].high-bars[0].high)/(bars[1].high-bars[1].low)*100;
 assert.equal(result[0][1],expected);
 assert.equal(result[1][1],0);assert.ok(Math.abs(result[2][1]-100)<1e-12);
});
