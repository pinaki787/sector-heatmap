const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
const a=source.indexOf('  function mergeSavedDrawings('),b=source.indexOf('  function preserveCopiedPineStudies(',a);
const merge=new Function(source.slice(a,b)+'return mergeSavedDrawings;')();
const A={kind:'trend',start:{time:1,price:10},end:{time:2,price:20}};
const B={...A,kind:'ray'},C={...A,kind:'rectangle'};
test('concurrent same-symbol appends retain drawings from both tabs',()=>{
 const previous={symbol:'A',drawings:[A],levels:[10]};
 const current={symbol:'A',drawings:[A,B],levels:[10,20]};
 const stored={symbol:'A',drawings:[A,C],levels:[10,30]};
 merge(current,previous,stored,'A');
 assert.deepEqual(current.drawings,[A,B,C]);assert.deepEqual(current.levels,[10,20,30]);
});
test('independent appends for inactive instruments are also retained',()=>{
 const previous={symbol:'X',drawings:[],levels:[],instrumentDrawings:{A:[A]}};
 const current={...previous,instrumentDrawings:{A:[A,B]}};
 const stored={...previous,instrumentDrawings:{A:[A,C]}};
 merge(current,previous,stored,'X');assert.deepEqual(current.instrumentDrawings.A,[A,B,C]);
});
test('already received appended drawing is not duplicated',()=>{
 const previous={symbol:'A',drawings:[A]},current={symbol:'A',drawings:[A,B]},stored={symbol:'A',drawings:[A,B,C]};
 merge(current,previous,stored,'A');assert.deepEqual(current.drawings,[A,B,C]);
});
test('editing, removing or reordering existing objects keeps the current conflict policy',()=>{
 for(const next of [[B],[],[B,A]]){
 const previous={symbol:'A',drawings:[A,B]},current={symbol:'A',drawings:next},stored={symbol:'A',drawings:[A,B,C]};
 merge(current,previous,stored,'A');assert.deepEqual(current.drawings,next);
 }
});
test('deletion in another tab is not silently resurrected by an ambiguous merge',()=>{
 const previous={symbol:'A',drawings:[A]},current={symbol:'A',drawings:[A,B]},stored={symbol:'A',drawings:[C]};
 merge(current,previous,stored,'A');assert.deepEqual(current.drawings,[A,B]);
});
test('merge never mutates baseline, stored snapshot, or current input arrays',()=>{
 const previous={symbol:'A',drawings:[A]},current={symbol:'A',drawings:[A,B]},stored={symbol:'A',drawings:[A,C]};
 const before=JSON.stringify({previous,stored}),original=current.drawings;
 merge(current,previous,stored,'A');assert.equal(JSON.stringify({previous,stored}),before);assert.deepEqual(original,[A,B]);
});

test('duplicate multiplicities use the greatest observed count rather than multiplying synced copies',()=>{
 const previous={symbol:'A',drawings:[A]},current={symbol:'A',drawings:[A,B,B]},stored={symbol:'A',drawings:[A,B,B,C]};
 merge(current,previous,stored,'A');assert.deepEqual(current.drawings,[A,B,B,C]);
});
test('conflicting styles of existing drawings remain local',()=>{
 const previous={symbol:'A',drawings:[A]},edited={...A,color:'#7b1fa2'},current={symbol:'A',drawings:[edited]},stored={symbol:'A',drawings:[{...A,width:4},C]};
 merge(current,previous,stored,'A');assert.deepEqual(current.drawings,[edited]);
});
test('combined drawing limit fails explicitly rather than producing a silently truncated saved chart',()=>{
 const item=n=>({...A,name:String(n)});
 const previous={symbol:'A',drawings:[]},current={symbol:'A',drawings:Array.from({length:60},(_,i)=>item(i))},stored={symbol:'A',drawings:Array.from({length:60},(_,i)=>item(i+60))};
 assert.throws(()=>merge(current,previous,stored,'A'),/drawing limit/);
});
test('drawing visibility objects retain existing conflict behavior',()=>{
 const previous={symbol:'A',drawings:[],horizontalVisibilityBySymbol:{A:{10:{hidden:false}}}};
 const current={...previous,horizontalVisibilityBySymbol:{A:{10:{hidden:true}}}};
 const stored={...previous,horizontalVisibilityBySymbol:{A:{10:{locked:true}}}};
 merge(current,previous,stored,'A');assert.deepEqual(current.horizontalVisibilityBySymbol.A,{10:{hidden:true}});
});
