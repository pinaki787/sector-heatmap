const test=require('node:test'),assert=require('node:assert/strict'),{project}=require('../position-history.js');
const row=(tag,side,filled,price,at,mode='LIVE')=>({tag,order_id:tag,symbol:'MCX:TESTCE',mode,side,filled,requested:filled,average_price:price,submitted_at:at,updated_at:at+.01,reason:side==='BUY'?'EMA_CLOSE_ENTRY':'EMA_CLOSE_EXIT',product:'MARGIN',lot_size:1,quantity_multiplier:10});
const event=(r,status)=>({at:r.updated_at+.001,status,message:`${r.reason}: confirmed ${r.filled} filled at ${r.average_price}; quantities reconciled.`});
test('retained ownership events pair distinct lifecycles of same contract and mode',()=>{
 const a=row('a','BUY',1,100,10),b=row('b','SELL',1,110,20),c=row('c','BUY',1,120,30),d=row('d','SELL',1,115,40);
 const s={order_history:[a,b,c,d],events:[event(a,'POSITION_OPEN'),event(b,'FLAT'),event(c,'POSITION_OPEN'),event(d,'FLAT')]};
 const p=project(s);assert.equal(p.length,2);assert.equal(p[0].realized_pnl,-50);assert.equal(p[1].realized_pnl,100);assert.equal(p[0].strategy,'EMA Cloud (historical)');assert.deepEqual(p[1].entry_order_ids,['a']);assert.deepEqual(p[1].exit_order_ids,['b']);
});
test('absence of ownership events never pairs adjacent legacy orders',()=>{const p=project({order_history:[row('a','BUY',1,100,10),row('b','SELL',1,110,20)]});assert.equal(p.length,2);assert.equal(p[0].status,'PAIRING UNAVAILABLE');assert.equal(p[0].realized_pnl,null);});
test('mode mismatch cannot become an owned exit',()=>{const a=row('a','BUY',1,100,10),b=row('b','SELL',1,110,20,'PAPER');const p=project({order_history:[a,b],events:[event(a,'POSITION_OPEN'),event(b,'FLAT')]});assert.equal(p.length,2);assert.equal(p[1].status,'OPEN');});
test('decimal rendering differences do not lose confirmed ownership linkage',()=>{const a=row('a','BUY',1,404,10),b=row('b','SELL',1,377.55,20);const e=event(a,'POSITION_OPEN');e.message=e.message.replace('at 404;','at 404.0;');const p=project({order_history:[a,b],events:[e,event(b,'FLAT')]});assert.equal(p.length,1);assert.equal(p[0].status,'CLOSED');assert.ok(Math.abs(p[0].realized_pnl+264.5)<1e-9);});
