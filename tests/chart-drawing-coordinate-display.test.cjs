const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8'),start=s.indexOf('  function drawingNumberEditor('),end=s.indexOf('  function editDrawing(',start);assert.ok(start>=0&&end>start);
const create=vm.runInNewContext(s.slice(start,end)+';drawingCoordinateEditors');
for(const labels of [['Start'],['Start','End'],['Start','End','Third'],['Start','Control1','Control2','End'],Array.from({length:6},(_,i)=>'Vertex'+i)])
test(labels.join('/')+' formats all prices without changing unedited anchors',()=>{
const anchors={},inputs={},events={};
for(let i=0;i<labels.length;i++){const label=labels[i];anchors[label]={price:100.123456789+i,time:1700000000+i*300,brick:3+i};events[label]={};inputs[label]={addEventListener:(name,fn)=>events[label][name]=fn};Object.defineProperty(inputs[label],'valueAsNumber',{get:()=>Number(inputs[label].value)});}
const form={querySelectorAll:()=>labels.map(label=>({dataset:{anchorOffset:label}})),elements:{namedItem:name=>inputs[name.slice(0,-5)]}};
const readers=create(form,label=>anchors[label]);
for(const label of labels){assert.equal(inputs[label].value,Number(anchors[label].price.toFixed(2)).toString());assert.equal(readers.get(label)(),anchors[label].price);}
const label=labels.at(-1);inputs[label].value='150.25';events[label].input();assert.equal(readers.get(label)(),150.25);
assert.equal(anchors[label].time,1700000000+(labels.length-1)*300);assert.equal(anchors[label].brick,3+labels.length-1);
});
test('Coordinate read uses the precision-preserving editors',()=>{assert.match(s,/const price = coordinatePrices\.get\(label\)\(\);/);});
