const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const start=source.indexOf('  function plainTextStyle('),end=source.indexOf('  function drawingStrokeColor(',start);
assert.ok(start>=0&&end>start);
const helper=source.slice(start,end);
function render(style={}){
 const from=source.indexOf("                  if (drawing.kind === 'text') {"),to=source.indexOf('                  let builtInMeasurementBadge;',from);
 const drawing={kind:'text',text:'Annotation check',...style},drawingHits=new Map(),draws=[];
 const context={strokeStyle:'#2962ff',measureText:()=>({width:150}),fillText(text,x,y){draws.push({text,x,y,font:this.font})}};
 const scope={Number,Math,context,drawingHits,drawings:[drawing],layer:'bottom',x1:100,y1:100};
 vm.runInNewContext(helper+'for(const drawing of drawings){'+source.slice(from,to)+'}',scope);
 return {draw:draws[0],hit:drawingHits.get(drawing)};
}
test('old text drawings retain13px semibold rendering',()=>{const r=render();assert.equal(r.draw.font,'600 13px Inter, system-ui, sans-serif');assert.equal(r.draw.text,'Annotation check');assert.ok(r.hit({x:110,y:85}))});
test('large italic text is rendered and selectable over its full height',()=>{const r=render({drawingTextSize:40,drawingTextBold:false,drawingTextItalic:true});assert.equal(r.draw.font,'italic 400 40px Inter, system-ui, sans-serif');assert.ok(r.hit({x:110,y:55}));assert.equal(r.hit({x:110,y:50}),false)});
test('invalid persisted font sizes cannot create oversized canvas text',()=>{assert.equal(render({drawingTextSize:900}).draw.font,'600 200px Inter, system-ui, sans-serif');assert.equal(render({drawingTextSize:NaN}).draw.font,'600 13px Inter, system-ui, sans-serif')});
