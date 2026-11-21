const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
function block(start){let level=0,end=source.indexOf('{',start);for(let i=end;i<source.length;i++){if(source[i]==='{')level++;if(source[i]==='}'&&!--level)return source.slice(start,i+1);}throw Error('block');}
function render(width=500,edge=220){
 const labels=[],bounds=[],ys=[],drawing={kind:'fib',width:2,color:'#8757d7'};
 const ctx={drawing,mediaSize:{width,height:400},left:50,edge,from:50,to:width,previousY:undefined,levelYs:ys,labelBounds:bounds,retracementRatios:()=>[0,.44,.5,.56,1],fibLevelPrice:(_,r)=>100+r*200,fibLevelColor:()=>undefined,mainSeries:{priceToCoordinate:price=>400-price},price:{format:n=>String(Math.round(n*100)/100)},context:{measureText:s=>({width:s.length*6}),setLineDash(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){},fillText:(text,x,y)=>labels.push({text,x,y})}};
 vm.createContext(ctx);
 const h=source.indexOf('  function fibLabelHorizontalPosition(');if(h>=0)vm.runInContext(block(h),ctx);
 const a=source.indexOf('                  const levelYs = []'),b=source.indexOf('                  for (const ratio of retracementRatios(drawing)) {',a);
 vm.runInContext(block(b),ctx);return {labels,bounds,ys};
}
test('actual Fib renderer retains all selected percentages including dense44/50/56 labels',()=>{
 const r=render();assert.equal(r.labels.length,5);assert.ok(r.labels.some(l=>l.text.startsWith('50%')));
 assert.deepEqual(r.labels.map(l=>l.y),[300,212,200,188,100]);
 for(let i=0;i<r.bounds.length;i++)for(let j=0;j<i;j++){const a=r.bounds[i],b=r.bounds[j];if(Math.abs(a.y-b.y)<15)assert.ok(a.x>=b.x+b.width+3||b.x>=a.x+a.width+3);}
});
test('dense right-edge Fibonacci labels remain inside the plot without changing their prices',()=>{
 const r=render(320,318);assert.equal(r.labels.length,5);
 assert.ok(r.bounds.every(l=>l.x>=0&&l.x+l.width<=320));
 assert.deepEqual(r.labels.map(l=>l.y),[300,212,200,188,100]);
});

