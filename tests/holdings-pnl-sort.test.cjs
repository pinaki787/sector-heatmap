const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('holdings-review.js','utf8'),start=source.indexOf('  function holdingPnlValue'),end=source.indexOf('  const labels =');
const context={};vm.runInNewContext(source.slice(start,end)+';this.compare=compareHoldingsPnl;this.filter=filterHoldings;',context);
test('signed P&L descending preserves precision and puts unavailable last',()=>{
 const rows=[{symbol:'loss-large',gross_pnl:-100},{symbol:'missing',gross_pnl:null},{symbol:'zero',gross_pnl:0},{symbol:'profit',gross_pnl:5},{symbol:'loss-small',gross_pnl:-1},{symbol:'broker-profit',broker_unrealized_pnl:8},{symbol:'precise',gross_pnl:5.001},{symbol:'invalid',gross_pnl:NaN}].map(r=>({...r,currency:'INR',action:'REVIEW_NEEDED'}));
 const expected=['broker-profit','precise','profit','zero','loss-small','loss-large','invalid','missing'];
 assert.deepEqual(rows.slice().sort(context.compare).map(r=>r.symbol),expected);
 assert.deepEqual(rows.filter(r=>r.action==='REVIEW_NEEDED').sort(context.compare).map(r=>r.symbol),expected);
 assert.equal(rows.find(r=>r.symbol==='precise').gross_pnl,5.001);
});

test('profit and loss selections compose with action filters and exclude zero/missing',()=>{
 const rows=[{symbol:'big-loss',gross_pnl:-100,action:'REVIEW_NEEDED'},{symbol:'small-loss',gross_pnl:-1,action:'REVIEW_NEEDED'},{symbol:'big-gain',gross_pnl:100,action:'BOOK_PROFIT'},{symbol:'small-gain',gross_pnl:2,action:'BOOK_PROFIT'},{symbol:'zero',gross_pnl:0,action:'HOLD'},{symbol:'missing',gross_pnl:null,action:'REVIEW_NEEDED'}].map(r=>({...r,currency:'INR'}));
 assert.deepEqual(Array.from(context.filter(rows,'ALL','LOSS'),r=>r.symbol),['big-loss','small-loss']);
 assert.deepEqual(Array.from(context.filter(rows,'REVIEW_NEEDED','LOSS'),r=>r.symbol),['big-loss','small-loss']);
 assert.deepEqual(Array.from(context.filter(rows,'BOOK_PROFIT','PROFIT'),r=>r.symbol),['big-gain','small-gain']);
 assert.equal(context.filter(rows,'HOLD','PROFIT').length,0);
 assert.equal(context.filter(rows).length,6);
});
