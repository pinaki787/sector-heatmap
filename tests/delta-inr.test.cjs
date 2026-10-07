const test=require('node:test'),assert=require('node:assert/strict');
const inr=require('../delta-inr.js');
const p={source:inr.source,native_currency:'USD',equivalent_currency:'INR',rate:85,verified_at:100000};
test('verified fixed conversion handles losses, zero and INR without double conversion',()=>{
 assert.equal(inr.value(10,'USD',p,100001),850);assert.equal(inr.value(-10,'USD',p,100001),-850);
 assert.equal(inr.value(0,'USD',p,100001),0);assert.equal(inr.value(850,'INR',null,100001),850);
 assert.match(inr.format(100,'USD',p,100001),/8,500/);
});
test('missing, stale, unsupported and invalid evidence never shows fabricated rupees',()=>{
 for(const n of [null,'',NaN,Infinity])assert.equal(inr.value(n,'USD',p,100001),null);
 assert.equal(inr.value(1,'USD',p,200000),null);assert.equal(inr.value(1,'USD',null,100001),null);
 assert.equal(inr.value(1,'EUR',p,100001),null);assert.equal(inr.value(1,'USD',{...p,source:'https://example.com'},100001),null);
 assert.equal(inr.format(1,'USD',null,100001),'INR unavailable');
});
