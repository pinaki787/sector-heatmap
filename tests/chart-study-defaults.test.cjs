const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
require(path.resolve(process.env.CHART_STUDIES_SOURCE||'chart-workspace-studies.js'));
const {indicators}=globalThis.SectorPulseChartStudies;
test('every built-in length default is accepted by the indicator settings field',()=>{
 for(const [kind,d]of Object.entries(indicators)){
  if(!d.length)continue;
  assert.ok(Number.isInteger(d.length),kind+' requires an integer default');
  assert.ok(d.length>=(d.minLength??1),kind+' default is below its input minimum');
  assert.ok(d.length<=(d.maxLength??250),kind+' default exceeds its input maximum');
 }
});
test('NVI and PVI accept their 255-period EMA defaults',()=>{
 for(const kind of ['NVI','PVI']){
  assert.equal(indicators[kind].length,255);
  assert.ok(indicators[kind].maxLength>=255);
 }
});
