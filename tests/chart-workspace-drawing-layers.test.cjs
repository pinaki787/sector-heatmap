
const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
function renderDrawing(kind) {
const source=fs.readFileSync(require.resolve('../chart-workspace.js'),'utf8');
const from=source.indexOf("      attachDrawingPrimitive = () => mainSeries.attachPrimitive({\n        attached({requestUpdate}) { repaintAnchors");
const to=source.indexOf("\n    }\n    const drawingTime",from);
const helpers=source.slice(source.indexOf("  const extendableTrendKinds"),source.indexOf("  const drawingUndo"));
const drawing={kind,start:{time:100,price:100},end:{time:200,price:110},color:'#2962ff',width:2};
let primitive,layer;const strokes=[],fills=[];
const context=new Proxy({save(){},restore(){},stroke(){strokes.push(layer)},fill(){fills.push(layer)},measureText(){return {width:20}},globalAlpha:1},{get:(o,k)=>k in o?o[k]:(()=>{})});
const scope={price:{format:String},console,Math,Number,Map,Set,window:{},mainSeries:{attachPrimitive(p){primitive=p},priceToCoordinate:p=>300-p},shapes:[drawing],drawings:[drawing],
timeLabels:[],priceLabels:[],drawingHits:new Map(),drawingLabelBounds:new Map(),measurementLabelHits:new Map(),chartTableBounds:new Map(),
anchorPreview:x=>x,isRenko:false,drawingAnchorDrag:undefined,drawingAnchorHover:undefined,selectedLine:undefined,selectedDrawings:new Set(),
projectsSubBarAnchors:()=>true,subBarLogical:a=>(a.time-100)/100,drawingLogical:a=>(a.time-100)/100,forecastLogical:()=>undefined,
horizontalRayBounds:(_drawing,x,width)=>({left:x,right:width}),scale:{logicalToCoordinate:i=>50+i*100},bars:[{time:100},{time:200}],timeOf:b=>b.time,
interpolatedBarCoordinate:(s,i)=>s.logicalToCoordinate(i),pointSequenceDrawing:()=>false,annotationKinds:{},pitchforkKinds:[],
repeatingTimeDrawing:()=>false,arrowMarker:()=>false,paintLineLabel:()=>{},positionDrawing:()=>false,isVolumeProfile:()=>false,isFibArcDrawing:()=>false,priceFib:()=>false,canvasColor:()=> '#fff',selectedTrendDrawing:undefined,tableResizeHover:undefined};
vm.createContext(scope);
vm.runInContext('let attachDrawingPrimitive;\n'+helpers+'\n'+source.slice(from,to),scope);
assert.equal(primitive,undefined,'manual drawings wait until Pine overlays are registered');
vm.runInContext('attachDrawingPrimitive();',scope);
for(const view of primitive.paneViews()) {
  layer=view.zOrder();
  view.renderer().draw({useMediaCoordinateSpace:fn=>fn({context,mediaSize:{width:800,height:500}})});
}
return {strokes,paints:[...strokes,...fills],hits:scope.drawingHits.size};
}
test('manual line strokes stay above filled indicators and remain selectable',()=>{
  for(const kind of ['trend','extended-line','ray','info-line','arrow','arrow-marker','double-arrow','horizontal-ray','vertical','cross']) {
    const result=renderDrawing(kind);
    assert.ok(result.paints.length>0,kind+' paints a stroke');
    assert.ok(result.paints.every(layer=>layer==='top'),kind+' must paint above fills');
    assert.equal(result.hits,1,kind+' retains selection geometry');
  }
});
test('shaded circle and ellipse shapes retain their background layer',()=>{
  for(const kind of ['circle','ellipse']) {
    assert.deepEqual(renderDrawing(kind).strokes,['bottom']);
  }
});

