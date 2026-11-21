const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
const first=source.indexOf('  function drawGannFan('),last=source.indexOf('  function drawFibSpiral(',first);
assert.ok(first>=0&&last>first);
const ratios=[1/8,1/4,1/3,1/2,1,2,3,4,8];
const ratioDeclaration=source.match(/const gannFanRatios = (\[[^;]+\]);/);
assert.ok(ratioDeclaration);
const actualRatios=new Function('return '+ratioDeclaration[1])();
const draw=new Function('gannFanRatios','fibArcLevelStyle','gannRayLabel',
 source.slice(first,last)+';return drawGannFan;')(actualRatios,
 (drawing,ratio)=>({visible:drawing.hiddenRatio!==ratio,color:'#2962ff',width:2,stroke:'solid'}),
 ratio=>String(ratio));
function recorder(){
 const paths=[],labels=[];let path=[];
 return {paths,labels,lineWidth:2,save(){},restore(){},getLineDash(){return[]},setLineDash(){},
 beginPath(){path=[]},moveTo(x,y){path.push([x,y])},lineTo(x,y){path.push([x,y])},
 closePath(){},fill(){},stroke(){paths.push(path)},fillText(text,x,y){labels.push({text,x,y})}};
}
for(const [dx,dy]of [[100,60],[-100,60],[100,-60],[-100,-60]]){
 test('Gann fan preserves all nine angular ratios and selectable forward rays: '+dx+','+dy,()=>{
  const c=recorder(),origin=[400,300],hit=draw(c,{width:800,height:600},...origin,400+dx,300+dy,{kind:'gann-fan',fibArcFill:false});
  assert.equal(c.paths.length,9);
  const actual=c.paths.map(p=>{
   assert.deepEqual(p[0],origin);assert.ok(p.flat().every(Number.isFinite));
   const [x,y]=p[1];assert.ok((x-400)*dx>0);return (y-300)/(x-400)/(dy/dx);
  }).sort((a,b)=>a-b);
  ratios.forEach((r,i)=>assert.ok(Math.abs(actual[i]-r)<1e-12));
  assert.equal(hit({x:400+dx,y:300+dy}),true);
  assert.equal(hit({x:400-dx,y:300-dy}),false);
  assert.equal(c.labels.length,9);
  for(const p of c.labels)assert.ok(p.x>=10&&p.x<=790&&p.y>=10&&p.y<=590);
 });
}
test('hidden ratios remove both painted and labeled levels',()=>{
 const c=recorder();draw(c,{width:800,height:600},400,300,500,360,{kind:'gann-fan',hiddenRatio:1,fibArcFill:false});
 assert.equal(c.paths.length,8);assert.equal(c.labels.length,8);assert.ok(!c.labels.some(p=>p.text==='1'));
});
test('degenerate and nonfinite anchors produce no canvas geometry',()=>{
 for(const anchors of [[1,2,1,4],[1,2,3,2],[NaN,2,3,4],[1,2,Infinity,4]]){
  const c=recorder();assert.equal(draw(c,{width:800,height:600},...anchors,{kind:'gann-fan'}),undefined);
  assert.equal(c.paths.length,0);assert.equal(c.labels.length,0);
 }
});
