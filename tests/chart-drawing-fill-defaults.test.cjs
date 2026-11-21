const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const from=source.indexOf("      if (field('saveDrawingStyle').checked) {"),to=source.indexOf("      if (nextKind === drawing.kind",from);
const a=source.indexOf('  function drawingStyleDefaults(kind) {'),b=source.indexOf('  function duplicateDrawings(',a);
assert.ok(from>=0&&to>from&&a>=0&&b>a);
function roundtrip(kind,fill,hasFill=true,extra={}){
 const settings={drawingStyleDefaults:{}};
 const context={settings,field:name=>name==='saveDrawingStyle'?{checked:true}:null,drawingExtensionFields:['rectangleExtendLeft','rectangleExtendRight'],
 nextKind:kind,drawing:{kind},nextColor:'#7b1fa2',nextWidth:4,nextStyle:'dashed',nextProfile:{},image:false,nextArcs:{},hasFill,nextFill:fill,
 rectangleStyle:{},channelPriceStyle:{},channelMidline:undefined,lineLabelDrawing:()=>false,rectangleTextStyle:{},pitchforkLevels:null,fibLevels:false,fibExtensionTrend:undefined,horizontalExtension:undefined,
 setDrawingStyleDefaults:value=>settings.drawingStyleDefaults=value,
 isPitchfork:()=>false,priceFib:()=>false,isFibArcDrawing:()=>false,styledTrendLine:()=>false,linkedAnnotation:()=>false,patternAnchors:{},
 styledCurveDrawing:()=>false,isVolumeProfile:()=>false,freehandDrawing:()=>false,pointSequenceDrawing:()=>false,
 profileColor:(color,fallback)=>/^#[0-9a-f]{6}$/i.test(color)?color:fallback,...extra};
 vm.runInNewContext(source.slice(from,to),context);
 const fn=vm.runInNewContext(source.slice(a,b)+';drawingStyleDefaults',context);
 return {saved:settings.drawingStyleDefaults[kind],loaded:fn(kind)};
}
for(const kind of ['rectangle','circle','ellipse','triangle','channel','regression','sector','callout','polyline','curve','head-shoulders']){
 test(kind+' new style retains explicit fill and stroke',()=>{
  const {saved,loaded}=roundtrip(kind,{fillColor:'#aa2233',fillOpacity:37});
  for(const value of [saved,loaded]){assert.equal(value.fillColor,'#aa2233');assert.equal(value.fillOpacity,37);assert.equal(value.color,'#7b1fa2');assert.equal(value.width,4);assert.equal(value.style,'dashed');}
 });
}
test('no-fill tools do not acquire fill defaults',()=>{
 const {saved,loaded}=roundtrip('trend',{fillColor:'#aa2233',fillOpacity:37},false);
 for(const value of [saved,loaded]){assert.equal(value.fillColor,undefined);assert.equal(value.fillOpacity,undefined);}
});
test('automatic color, transparent and opaque fills survive',()=>{
 for(const opacity of [0,100]){
  const {loaded}=roundtrip('rectangle',{fillColor:'',fillOpacity:opacity});
  assert.equal(loaded.fillColor,'');assert.equal(loaded.fillOpacity,opacity);
 }
});
test('invalid persisted opacity is discarded and invalid color uses automatic color',()=>{
 for(const opacity of [-1,101,NaN,Infinity]){
  const {loaded}=roundtrip('rectangle',{fillColor:'bad',fillOpacity:opacity});
  assert.equal(loaded.fillColor,'');assert.equal(loaded.fillOpacity,undefined);
 }
});

test('rectangle centerline and extensions persist in new rectangle defaults',()=>{
 const fields={rectangleMidline:true,rectangleExtendLeft:true,rectangleExtendRight:false};
 const result=roundtrip('rectangle',{},true,{rectangleStyle:fields});
 for(const value of [result.saved,result.loaded])for(const [key,wanted] of Object.entries(fields))assert.equal(value[key],wanted,key);
});
test('channel hidden centerline persists without copying channel geometry',()=>{
 const result=roundtrip('channel',{},true,{channelMidline:false});
 for(const value of [result.saved,result.loaded]){assert.equal(value.channelMidline,false);assert.equal(value.offset,undefined);}
});
test('disjoint channel boundary price styles persist in new drawing defaults',()=>{
 const fields={channelPrices:true,channelPriceBackground:false,channelPriceBold:true,channelPriceItalic:true,channelPriceColor:'#aa2233',channelPriceSize:16};
 const result=roundtrip('disjoint-channel',{},true,{channelPriceStyle:fields});
 for(const value of [result.saved,result.loaded])for(const [key,wanted] of Object.entries(fields))assert.equal(value[key],wanted,key);
});
