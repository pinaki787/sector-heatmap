const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8'),start=s.indexOf('  function studyInputs('),end=s.indexOf('  function targetControls(',start);assert.ok(start>=0&&end>start);
const esc=v=>String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
function render(saved,value='default',kind='Pine'){
 const study={kind,workerRuntime:true,inputs:{text:saved}},defs=[{id:'text',type:'string',title:'Custom text',value,min:0,max:Infinity}];
 const fn=vm.runInNewContext(s.slice(start,end)+';studyInputs',{indicators:{Pine:{},Builtin:{inputs:defs}},pineInputDefinitions:new Map([[study,defs]]),calculationTimeframeStudies:new Set(),esc});
 return fn(study,0);
}
test('Pine long saved string remains in input',()=>{const text='a'.repeat(1000),html=render(text);assert.ok(html.includes('value="'+text+'"'));assert.ok(!html.includes('maxlength='))});
test('Pine long default remains editable',()=>{const text='b'.repeat(500),html=render(undefined,text);assert.ok(html.includes(text));assert.ok(!html.includes('maxlength='))});
test('Pine attribute escaping is retained',()=>{const text='"<>&'.repeat(50),html=render(text);assert.ok(html.includes(esc(text)));assert.ok(!html.includes('value="'+text+'"'))});
test('other input contracts retain existing bound',()=>{const html=render('x'.repeat(100),'default','Builtin');assert.ok(html.includes('maxlength="80"'));assert.ok(html.includes('value="default"'))});
