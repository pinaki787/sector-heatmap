const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),test=require('node:test');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
function toolbar(drawing) {
 const dom=new JSDOM('<div class="sp-drawing-style-toolbar"><button data-line-lock></button><input type="color" data-line-property="color"><select data-line-property="width"><option>1</option><option>2</option><option>3</option></select><select data-line-property="style"><option>solid</option></select><select data-line-property="extension"><option value="none"></option></select><button data-line-settings></button><button data-line-remove></button></div>');
 const start=source.indexOf('  function drawingStrokeColor('),end=source.indexOf('  function removeSelectedLines()',start);assert.ok(start>=0&&end>start);
 const context={panel:dom.window.document,selectedLevel:undefined,lineStyleTargets:()=>[drawing],positionDrawingStyleToolbar:()=>{},lineExtension:()=>undefined,pointSequenceDrawing:()=>false,linkedAnnotation:()=>false,priceFib:kind=>kind==='fib'||kind==='fib-extension'};
 vm.runInNewContext(source.slice(start,end)+';syncSelectedLineStyle();',context);
 const value=dom.window.document.querySelector('input').value;dom.window.close();return value;
}
test('new Fib quick toolbar shows the actual purple default instead of blue',()=>assert.equal(toolbar({kind:'fib'}),'#8757d7'));
test('explicit Fib color overrides the default and normalizes case',()=>assert.equal(toolbar({kind:'fib',color:'#AA2233'}),'#aa2233'));
test('ordinary trend and pitchfan keep their own default colors',()=>{assert.equal(toolbar({kind:'trend'}),'#2962ff');assert.equal(toolbar({kind:'pitchfan'}),'#f23645')});
