
const test=require('node:test'),assert=require('node:assert/strict');
const {chartFramePolicy}=require('../renko-ai-options.js');
test('pending sizing preserves chart choice without inventing Renko geometry',()=>{
 for(const brick of [null,undefined,0,-1,NaN]){
  const p=chartFramePolicy({symbol:'MCX:CRUDEOIL26DECFUT',brick});
  assert.equal(p.hidden,false);assert.equal(p.pending,true);assert.equal(p.type,null);
  assert.equal(p.instanceSuffix,'-pending-size');
 }
});
test('verified geometry retains original chart context',()=>{
 assert.deepEqual(chartFramePolicy({symbol:'ETHUSD',brick:2.17}),{hidden:false,pending:false,type:null,instanceSuffix:''});
 assert.equal(chartFramePolicy({brick:2.17}).hidden,true);
});

test('embedded defaults are Renko and pending Renko has an explicit sizing message',()=>{
 const fs=require('node:fs'),ui=fs.readFileSync('renko-ai-options.js','utf8'),chart=fs.readFileSync('chart-workspace.js','utf8');
 assert.match(ui,/displayInput.value='RENKO'/);assert.match(ui,/chartViewInput.value='Renko'/);
 assert.match(chart,/settings.type=linkedChart.type\|\|'Renko'/);
 assert.match(chart,/Waiting for brick size/);
 assert.doesNotMatch(chart,/settings.type='Candles';\s*settings.studies=settings.studies.filter/);
});
