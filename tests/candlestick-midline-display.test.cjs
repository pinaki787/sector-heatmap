const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('chart-workspace.js','utf8');
const init=source.match(/integrated.inputs.nativeMidlineVisible=([^;]+);/)[1];
test('candlestick Midline display is independent of off filter and Supertrend',()=>{
 for(const type of ['Candles','Renko','Heikin Ashi'])for(const filter of ['0','1']){
 const inputs={nativeMidlineVisible:false};
 vm.runInNewContext('integrated.inputs.nativeMidlineVisible='+init,{integrated:{inputs},settings:{type},aiRuntimeParams:new URLSearchParams({aiMidline:filter})});
 assert.equal(inputs.nativeMidlineVisible,type==='Candles'||filter==='1');
 }
});
test('type switch reapplies display rule and does not change trading filter',()=>{
 const line=source.split('\n').find(x=>x.includes('if(embeddedRenko)for(const study')&&x.includes('nativeMidlineVisible'));
 assert.ok(line);
 for(const type of ['Candles','Renko']){
 const study={strategyManaged:true,inputs:{}},filter=new URLSearchParams({aiMidline:'0'});
 vm.runInNewContext(line,{embeddedRenko:true,settings:{type,studies:[study]},aiRuntimeParams:filter});
 assert.equal(study.inputs.nativeMidlineVisible,type==='Candles');assert.equal(filter.get('aiMidline'),'0');
 }
});
