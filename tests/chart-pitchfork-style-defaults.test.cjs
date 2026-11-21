const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const a=s.indexOf('  function drawingStyleDefaults(kind) {'),b=s.indexOf('  function duplicateDrawings(',a);
const p=s.indexOf('  const pitchforkNames = {'),q=s.indexOf('  const defaultPitchforkLevels',p);assert.ok(a>=0&&b>a&&p>=0&&q>p);
function fixture(kind,levels){
 const settings={drawingStyleDefaults:{[kind]:{pitchforkLevels:levels}}};
 const context={settings,drawingExtensionFields:[],priceFib:()=>false,isFibArcDrawing:()=>false,styledTrendLine:()=>false,lineLabelDrawing:()=>false,linkedAnnotation:()=>false,patternAnchors:{},styledCurveDrawing:()=>false,isVolumeProfile:()=>false,freehandDrawing:()=>false,pointSequenceDrawing:()=>false};
 const fn=vm.runInNewContext(s.slice(p,q)+s.slice(a,b)+';drawingStyleDefaults',context);
 return {load:()=>fn(kind),settings};
}
for(const kind of ['pitchfork','schiff-pitchfork','modified-schiff-pitchfork','inside-pitchfork']){
 test(kind+' preserves ratios and individual colors widths strokes without sharing mutable levels',()=>{
  const levels=[{ratio:0.5,color:'#aa2233',width:4,style:'dashed'},{ratio:1},{ratio:2,color:'#123456',width:2,style:'dotted'}];
  const f=fixture(kind,levels),first=f.load();
  assert.deepEqual(JSON.parse(JSON.stringify(first.pitchforkLevels)),levels);
  first.pitchforkLevels[0].color='#ffffff';first.pitchforkLevels.push({ratio:3});
  assert.deepEqual(JSON.parse(JSON.stringify(f.load().pitchforkLevels)),levels);assert.equal(levels.length,3);
 });
}
test('empty levels intentionally retain no parallel lines',()=>assert.deepEqual(JSON.parse(JSON.stringify(fixture('pitchfork',[]).load().pitchforkLevels)),[]));
test('malformed ratios reject the saved level set',()=>{
 for(const levels of [null,{},[null],[{ratio:0}],[{ratio:-1}],[{ratio:101}],[{ratio:NaN}],[{ratio:1},{ratio:1}],Array.from({length:10},(_,i)=>({ratio:i+1}))])
  assert.equal(fixture('pitchfork',levels).load().pitchforkLevels,undefined);
});
test('invalid optional style attributes are omitted',()=>{
 const f=fixture('pitchfork',[{ratio:1,color:'bad',width:9,style:'invalid'}]);
 assert.deepEqual(JSON.parse(JSON.stringify(f.load().pitchforkLevels)),[{ratio:1}]);
});
test('other drawing kinds do not inherit pitchfork levels',()=>assert.equal(fixture('trend',[{ratio:1}]).load().pitchforkLevels,undefined));
