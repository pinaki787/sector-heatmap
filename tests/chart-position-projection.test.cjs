const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const src=fs.readFileSync('chart-workspace.js','utf8');
const helper=src.slice(src.indexOf('  const lineCanProject ='),src.indexOf('  function arrowMarkerDimensions'));
const anchor=src.slice(src.indexOf('    function forecastAnchor('),src.indexOf('    function drawingEndpoint('));
function fixture(kind,interval='30'){
 const scope={drawingTool:kind,drawingStart:undefined,isRenko:false,settings:{interval},
 bars:[{time:1000},{time:2800}],styledTrendLine:k=>k==='trend',
 positionDrawing:k=>['long-position','short-position'].includes(k),pitchforkKinds:['pitchfork'],
 tickInterval:i=>i==='100T',nextCandleStart:t=>t+1800,drawingPrice:e=>e.point.y,
 chart:{timeScale:()=>({coordinateToLogical:x=>x,logicalToCoordinate:x=>x})}};
 vm.createContext(scope);vm.runInContext(helper+anchor+';this.canProject=lineCanProject;',scope);
 return scope;
}
test('position and channel tools can begin and finish in future chart space',()=>{
 for(const kind of ['long-position','short-position','channel','disjoint-channel','flat-channel','rectangle','fib','pitchfork']){
  const s=fixture(kind);assert.equal(s.canProject(kind),true,kind);
  let p=s.forecastEndpoint({point:{x:5,y:100}});
  assert.equal(p.forecastOffset,4,kind);assert.equal(p.time,10000);assert.equal(p.price,100);
  s.drawingStart=p;p=s.forecastEndpoint({point:{x:8,y:110}});
  assert.equal(p.forecastOffset,7);assert.equal(p.price,110);
 }
});
test('future placement keeps tick-chart and loaded-bar boundaries',()=>{
 assert.equal(fixture('channel','100T').forecastEndpoint({point:{x:5,y:100}}),undefined);
 assert.equal(fixture('channel').forecastEndpoint({point:{x:1,y:100}}),undefined);
 assert.equal(fixture('fixed-volume-profile').canProject('fixed-volume-profile'),false);
});
