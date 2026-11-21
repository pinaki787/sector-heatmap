const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8'),start=s.indexOf('  function drawingNumberEditor('),end=s.indexOf('  function editDrawing(',start);
assert.ok(start>=0&&end>start);const create=vm.runInNewContext(s.slice(start,end)+';drawingNumberEditor');
for(const [value,display] of [[18.73172073364276,'18.73'],[-12.56789,'-12.57'],[2,'2'],[.05,'0.05']])test('Unedited displayed '+display+' preserves exact geometry',()=>{
const events={},input={addEventListener:(n,fn)=>events[n]=fn};Object.defineProperty(input,'valueAsNumber',{get:()=>Number(input.value)});
const read=create(input,value);assert.equal(input.value,display);assert.equal(read(),value);
input.value='30.25';events.input();assert.equal(read(),30.25);
});
test('Explicit editing to displayed rounded value commits that edit',()=>{const events={},input={addEventListener:(n,f)=>events[n]=f};Object.defineProperty(input,'valueAsNumber',{get:()=>Number(input.value)});
const read=create(input,18.73172073364276);events.input();assert.equal(read(),18.73);});
test('Empty edit remains invalid instead of restoring prior number',()=>{const events={},input={valueAsNumber:NaN,addEventListener:(n,f)=>events[n]=f};const read=create(input,18.73172);input.value='';events.input();assert.ok(Number.isNaN(read()));});
