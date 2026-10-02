const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const c={};vm.createContext(c);vm.runInContext(fs.readFileSync('delta-india.js','utf8').split('/* Independent Delta India')[0],c);const view=c.DeltaPositionView;
const position={symbol:'BTCUSD',side:'LONG',contracts:7,entry_price:100,entry_time:990,contract_value:'0.001',quote_currency:'USD'};
const args={workflow:'PAPER',state:{running:true,paper:{position}},quotes:{BTCUSD:{symbol:'BTCUSD',bid:110,ask:111,exchange_at:1000}},statusAt:1000,now:1001};
test('Paper current position uses remaining filled contracts and executable bid; closed watching runner is flat',()=>{
 const v=view(args);assert.equal(v.rows.length,1);assert.equal(v.rows[0].contracts,7);assert.equal(v.rows[0].pnl,.07);assert.match(v.summary,/1 open position/);assert.match(v.summary,/0.07000000 USD/);
 const flat=view({...args,state:{running:true,paper:{position:null}}});assert.equal(flat.rows.length,0);assert.match(flat.summary,/0 open positions · Awaiting entry/);
});
test('stale quote or stale position suppresses valuation without hiding last known quantity',()=>{
 for(const update of [{now:1020},{statusAt:980}]){const v=view({...args,...update});assert.equal(v.rows[0].contracts,7);assert.equal(v.rows[0].pnl,null);assert.match(v.summary,/Unavailable/);assert.doesNotMatch(v.summary,/0.00000000/);}
});
test('short Paper values executable ask and never includes live broker positions',()=>{
 const v=view({...args,state:{paper:{position:{...position,side:'SHORT'}}},account:{positions:[{size:3,product_symbol:'ETHUSD'}]}});assert.equal(v.rows[0].side,'SHORT');assert.equal(v.rows[0].pnl,-.077);assert.equal(v.rows.length,1);assert.match(v.rows[0].valuation,/ask 111/);
});
test('Live current positions use broker P&L and keep settlement currencies separate',()=>{
 const account={as_of:1000,positions:[{product_symbol:'BTCUSD',size:-3,entry_price:100,mark_price:99,unrealized_pnl:'1.5',settlement_currency:'USD',pnl_basis:'Broker supplied'},{product_symbol:'ETHUSD',size:2,entry_price:20,mark_price:21,unrealized_pnl:'2',settlement_currency:'USDT'}]};
 const v=view({...args,workflow:'LIVE',account});assert.equal(v.rows.length,2);assert.equal(v.rows[0].contracts,3);assert.equal(v.rows[0].side,'SHORT');assert.match(v.summary,/1.50000000 USD \/ 2.00000000 USDT/);
 const stale=view({...args,workflow:'LIVE',account,now:1040});assert.ok(stale.rows.every(r=>r.pnl===null));assert.match(stale.summary,/stale/);
});
