const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {renkoPercentageSize}=require('../chart-renko-sizing.js');
const cases=JSON.parse(fs.readFileSync('.private/chart-order-rollouts/renko-percentage-reference-20261120/native-cases.json','utf8'));
const ticks={'DELTAIN:BTCUSD.P':.5,'DELTAIN:PAXGUSD.P':.01,'DELTAIN:ETHUSD.P':.05};
test('tick-aware candidate matches36 completed native percentage calculations across three symbols',()=>{
 assert.equal(cases.length,36);
 for(const c of cases){
  assert.equal(c.complete,true);assert.ok(c.generation);assert.ok(c.rows>0);
  assert.ok(c.boxSizes.every(n=>Math.abs(n-c.boxSize)<1e-8));
  assert.equal(renkoPercentageSize(c.price,c.percent,ticks[c.symbol]),c.boxSize,c.symbol+' '+c.percent+'%');
 }
});
test('same raw percentage range needs native tick-aware rounding rather than a universal price adjustment',()=>{
 const btc=cases.find(c=>c.symbol==='DELTAIN:BTCUSD.P'&&c.percent===1);
 const paxg=cases.find(c=>c.symbol==='DELTAIN:PAXGUSD.P'&&c.percent===17);
 assert.equal(btc.boxSize,500);assert.equal(paxg.boxSize,600);
 assert.ok(Math.abs(btc.price*btc.percent/100-paxg.price*paxg.percent/100)<5);
});
test('invalid, overflowing and sub-tick inputs are handled explicitly',()=>{
 for(const value of [0,-1,NaN,Infinity])assert.throws(()=>renkoPercentageSize(value,1,.01),/Positive finite/);
 assert.throws(()=>renkoPercentageSize(1,0,.01),/Positive finite/);
 assert.throws(()=>renkoPercentageSize(1,1,0),/Positive finite/);
 assert.throws(()=>renkoPercentageSize(Number.MAX_VALUE,1000,.01),/numeric range/);
 assert.equal(renkoPercentageSize(.001,.01,.01),.01);
});

