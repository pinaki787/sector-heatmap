const test=require('node:test'),assert=require('node:assert/strict');
const {manualRequestLabel,manualRequestNotice}=require('../renko-ai-options.js');
test('one identifiable fill confirmation, not a duplicate FILLED notice',()=>{
 const s={manual_entry:{phase:'FILLED',order_id:'26112700080610',symbol:'NSE:LAURUSLABS-EQ',direction:'LONG',quantity:30,fill_price:2514.2,confirmed_at:1795753352,strategy_exits_active:true}};
 const label=manualRequestLabel(s);
 for(const expected of ['26112700080610','NSE:LAURUSLABS-EQ','Buy / LONG','30 units','2,514.2','Confirmed','Opened position'])assert.ok(label.includes(expected),expected);
 assert.equal(manualRequestNotice(s),'Manual order confirmed · details below.');
 assert.ok(!manualRequestNotice(s).includes('FILLED'));
});
test('unknown IDs and rejected errors stay explicit',()=>{
 assert.ok(manualRequestLabel({manual_entry:{phase:'FILLED',direction:'SHORT'}}).includes('ID unavailable'));
 assert.ok(manualRequestNotice({manual_entry:{phase:'REJECTED',error:'No depth'}}).includes('No depth'));
});
test('only selected sizing mode supplies configuration quantity',()=>{
 const {configuration}=require('../renko-ai-options.js'),account={id:'owner',broker:'FYERS'};
 const f={underlying:'NSE:LAURUSLABS-EQ',route:'DIRECT',timeframe:'1 minute',execution:'PAPER',product:'INTRADAY',lots:'30',reference:'100',session:'2026-11-27',evidence:'fixture'};
 const q=configuration({...f,allocationAmount:'20000'},account);assert.equal(q.lots,30);assert.equal(q.entry_amount_inr,null);
 const a=configuration({...f,lots:'999',quantityMode:'AMOUNT_INR',allocationAmount:'20000'},account);assert.equal(a.lots,null);assert.equal(a.entry_amount_inr,20000);
 assert.throws(()=>configuration({...f,quantityMode:'AMOUNT_INR',allocationAmount:'0'},account),/positive/);
});
