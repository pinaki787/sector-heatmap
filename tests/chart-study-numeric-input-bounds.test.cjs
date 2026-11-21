const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
require(path.resolve('chart-workspace-studies.js'));
const definitions=globalThis.SectorPulseChartStudies.indicators;
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const a=source.indexOf('  function studyInputs('),b=source.indexOf('  function targetControls(',a);assert.ok(a>=0&&b>a);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function render(inputs,saved,id='value'){
 const fn=vm.runInNewContext(source.slice(a,b)+';studyInputs',{indicators:{Fixture:{inputs}},pineInputDefinitions:new Map(),calculationTimeframeStudies:new Set(),esc});
 const dom=new JSDOM(fn({kind:'Fixture',inputs:{[id]:saved}},0,inputs.find(input=>input.id===id)?.section??'Inputs'));
 const el=Array.from(dom.window.document.querySelectorAll('[data-pine-input]')).find(el=>el.dataset.pineInput===id);
 const value=el.value;dom.window.close();return value;
}
for(const type of ['float','int']){
 for(const bounds of [{},{min:1},{max:10},{min:1,max:10}]){
  test(type+' retains valid saved number with bounds '+JSON.stringify(bounds),()=>{
   assert.equal(Number(render([{id:'value',title:'Value',value:3,type,...bounds}],4)),4);
  });
 }
 test(type+' rejects nonfinite and out-of-range values',()=>{
  const defs=[{id:'value',title:'Value',value:3,type,min:1,max:10}];
  for(const invalid of [NaN,Infinity,-Infinity,0,11])assert.equal(Number(render(defs,invalid)),3);
 });
}
test('ASI native Limit move without maximum retains edited value',()=>{
 assert.equal(Number(render(definitions.ASI.inputs,3.01,'limitMove')),3.01);
});
test('all ordinary built-in numeric controls retain an in-range edit',()=>{
 let cases=0;
 for(const [kind,indicator] of Object.entries(definitions)){
  if(['TWAP','TechnicalRatings'].includes(kind)||indicator.deltaCandles)continue;
  for(const input of indicator.inputs??[]){
   if(typeof input.value!=='number'||input.options)continue;
   const step=input.type==='float'?(input.step??0.1):1,min=input.min??-Infinity,max=input.max??Infinity;
   const saved=input.value+step<=max?input.value+step:input.value-step>=min?input.value-step:input.value;
   assert.equal(Number(render(indicator.inputs,saved,input.id)),saved,kind+'.'+input.id);cases++;
  }
 }
 assert.equal(cases,202);
});
