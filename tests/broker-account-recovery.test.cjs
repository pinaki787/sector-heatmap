const test=require('node:test');
const assert=require('node:assert/strict');
const {retryInventory}=require('../broker-account-options.js');
test('transient inventory failure retries and releases initialization on success',async()=>{
 let calls=0,ready=false;const queued=[],errors=[];
 await retryInventory(async()=>{if(++calls<3)throw Error('temporary');ready=true;},e=>errors.push(e.message),(fn,delay)=>queued.push({fn,delay}));
 assert.equal(ready,false);assert.equal(queued[0].delay,1000);
 await queued.shift().fn();assert.equal(queued[0].delay,2000);
 await queued.shift().fn();assert.equal(ready,true);assert.equal(calls,3);assert.equal(queued.length,0);assert.equal(errors.length,2);
});
test('repeated failures use capped backoff and never retry mutations',async()=>{
 const queued=[];let calls=0;
 await retryInventory(async()=>{calls++;throw Error('offline');},()=>{},(fn,delay)=>queued.push({fn,delay}));
 for(let i=0;i<9;i++){const task=queued.shift();assert.ok(task.delay<=30000);await task.fn();}
 assert.equal(calls,10);assert.equal(queued[0].delay,30000);
});
