const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const a=source.indexOf('  function validDrawings(drawings) {'),b=source.indexOf('  const chartTypes =',a);
assert.ok(a>=0&&b>a);
const context={drawingLimit:100,patternAnchors:{},annotationKinds:{},pitchforkKinds:['pitchfork','schiff-pitchfork','modified-schiff-pitchfork','inside-pitchfork'],
pointSequenceDrawing:()=>false,positionDrawing:()=>false,distinctDrawingBricks:()=>false,allowsSameBar:()=>false};
const restore=vm.runInNewContext(source.slice(a,b)+';validDrawings',context);
const base={start:{time:100,price:100},end:{time:200,price:110},third:{time:300,price:90},
color:'#123456',width:4,style:'dashed',fillColor:'#aa2233',fillOpacity:37,name:'Saved drawing',locked:true};
const cases=[
['rectangle',{rectangleMidline:true,rectangleExtendLeft:true,rectangleExtendRight:false}],
['channel',{offset:5,channelMidline:false,channelExtendLeft:true,channelExtendRight:false}],
['disjoint-channel',{offset:5,channelPrices:true,channelPriceBackground:true,channelPriceColor:'#aa2233',channelPriceBold:true,channelPriceItalic:true,channelPriceSize:16}],
['pitchfork',{pitchforkLevels:[{ratio:.5,color:'#aa2233',width:4,style:'dashed'},{ratio:2,color:'#123456',width:1,style:'dotted'}]}],
['horizontal-ray',{horizontalExtension:'both',showRayPrice:true}],
['trend',{extendLeft:true,extendRight:true}],
['sector',{fillOpacity:0}]
];
for(const [kind,attributes] of cases)test(kind+' saved JSON retains edited attributes and geometry through restoration',()=>{
const drawing={...base,kind,...attributes};
const persisted=JSON.parse(JSON.stringify([drawing]));
const result=restore(persisted);
assert.equal(result.length,1);
assert.equal(JSON.stringify(result),JSON.stringify([drawing]));
assert.equal(JSON.stringify(persisted),JSON.stringify([drawing]));
});
test('invalid geometry is rejected without stripping valid styled neighbor',()=>{
const good={...base,kind:'rectangle',rectangleMidline:true};
const result=restore(JSON.parse(JSON.stringify([{...good,start:{time:100,price:-1}},good])));
assert.equal(result.length,1);assert.equal(JSON.stringify(result[0]),JSON.stringify(good));
});

