const {test}=require("node:test");
const assert=require("node:assert/strict");
const {executionMarkers,mapExecutionMarkers,chartPreviewPolicy}=require("../renko-supertrend.js");
test("ordered Paper fills use original fractional bricks and the order ledger",()=>{
 const ref={timestamp:100.125,confirmation_basis:"ORDERED_LIVE_PRICE",open:100,close:90,source_generation:3,source_sequence:7,source_event_index:0};
 const state={run_id:"R",config:{underlying:"BTCUSD",timeframe:"5 minutes",mode:"PAPER"},execution_signals:[{timestamp:100.125,direction:"BEARISH",status:"ELIGIBLE"}],order_history:[
 {tag:"A",lifecycle_id:"A",run_id:"R",underlying_symbol:"BTCUSD",is_entry:true,status:"FILLED",entry_event_at:100.125,filled_at:110,indicator_snapshot:{confirmed_indicator_reference:ref,indicators:{direction:"BEARISH"}}},
 {tag:"B",lifecycle_id:"A",run_id:"R",underlying_symbol:"BTCUSD",is_entry:false,status:"FILLED",filled_at:122,reason:"OPPOSITE_RENKO_BRICK_CLOSE",indicator_snapshot:{settings:{ema_exit_length:10,ema_exit_enabled:false},confirmed_indicator_reference:{...ref,timestamp:120.75,open:90,close:100}}},
 {tag:"OLD",run_id:"OLD",underlying_symbol:"BTCUSD",is_entry:true,status:"FILLED",filled_at:110,indicator_snapshot:{confirmed_indicator_reference:ref,indicators:{direction:"BEARISH"}}}]};
 const markers=executionMarkers([],state,"BTCUSD","5 minutes");
 assert.deepEqual(markers.map(m=>m.time),[100.125,120.75]);assert.match(markers[0].text,/SELL .* FILLED/);assert.match(markers[1].text,/SELL EXIT .* FILLED/);
 assert.doesNotMatch(markers[1].text,/EMA/);
 const bricks=[{...ref,time:100.458,indicator_timestamp:100.125},{...ref,open:90,close:100,time:121.083,indicator_timestamp:120.75}];
 assert.deepEqual(mapExecutionMarkers(markers,bricks).map(m=>m.time),[100.458,121.083]);
 assert.deepEqual(mapExecutionMarkers(markers,[{...bricks[0],source_sequence:8}]),[]);
 assert.deepEqual(mapExecutionMarkers(markers,[{...bricks[0],indicator_timestamp:100,time:100}]),[]);
});
test("stopped recorded audit and delayed history never grow live provisional bricks",()=>{
 assert.match(chartPreviewPolicy({basis:"recorded"}),/last recorded brick/);
 assert.match(chartPreviewPolicy({basis:"active"},1),/withheld/);
 assert.match(chartPreviewPolicy({basis:"draft"},3),/withheld/);
 assert.equal(chartPreviewPolicy({basis:"active"},0),null);
 assert.equal(chartPreviewPolicy({basis:"draft"},0),null);
});

const {deltaNative,deltaPnl}=require('../renko-supertrend.js');
test('USD price precision and signed dual P&L retain native values and verified policy',()=>{
 const conversion=require('../delta-inr.js');const now=Date.now()/1000;
 conversion.set({source:conversion.source,native_currency:'USD',equivalent_currency:'INR',rate:85,verified_at:now});
 assert.equal(deltaNative(81045.123456),'USD 81,045.12');
 assert.equal(deltaPnl(-8.9,'USD',conversion),'USD -8.90 · INR -756.50');
 assert.equal(deltaPnl(8.9,'USD',conversion),'USD 8.90 · INR 756.50');
 assert.equal(deltaPnl(0,'USD',conversion),'USD 0.00 · INR 0.00');
 conversion.set(null);assert.equal(deltaPnl(-8.9,'USD',conversion),'USD -8.90 · INR unavailable');
 assert.equal(deltaPnl(null,'USD',conversion),'USD unavailable · INR unavailable');
});

test('entry page changes the Renko asset URL from the obsolete cached build',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
 assert.match(html,/renko-supertrend\.js\?[^"']*v=20261029-recorded-price-audit-2/);
 assert.doesNotMatch(html,/renko-supertrend\.js\?[^"']*20261022-chart-indicator-recovery-1/);
});
