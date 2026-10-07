const {test}=require('node:test');const assert=require('node:assert/strict');
const {rsiHistory,rsiStep,rsiZone}=require('../renko-supertrend.js');
const rows=prices=>prices.map((close,i)=>({timestamp:i*60,close}));
test('Wilder RSI seeds from fourteen completed changes then smooths',()=>{
 const r=rsiHistory(rows([100,102,101,103,100]),3);
 assert.equal(r.points[2].value,undefined);assert.equal(r.points[3].value,80);
 assert.ok(Math.abs(r.points[4].value-100*8/19)<1e-10);
 const fourteen=rsiHistory(rows(Array.from({length:16},(_,i)=>100+i)));
 assert.equal(fourteen.points[13].value,undefined);assert.equal(fourteen.points[14].value,100);
});
test('forming ticks clone confirmed state instead of accumulating candle changes',()=>{
 const confirmed=rsiHistory(rows([100,102,101,103]),3).state,before=JSON.stringify(confirmed);
 const one=rsiStep(confirmed,100,240,3),two=rsiStep(confirmed,100,240,3);
 assert.deepEqual(one,two);assert.equal(JSON.stringify(confirmed),before);
 const revised=rsiStep(confirmed,104,240,3);
 assert.ok(revised.point.value>one.point.value);assert.equal(JSON.stringify(confirmed),before);
});
test('zone boundaries belong to the next band and one-sided prices remain bounded',()=>{
 assert.deepEqual([0,39.99,40,59.99,60,79.99,80,100].map(rsiZone),['0–40','0–40','40–60','40–60','60–80','60–80','80–100','80–100']);
 assert.equal(rsiHistory(rows([3,2,1]),2).points.at(-1).value,0);
 assert.equal(rsiHistory(rows([1,1,1]),2).points.at(-1).value,50);
 assert.throws(()=>rsiStep({},NaN,0));assert.throws(()=>rsiStep({},1,0,0));
});
