const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {chartSimulationMarkers,executionMarkers}=require(path.resolve(process.env.RENKO_SOURCE||'renko-supertrend.js'));
test('hiding simulation retains confirmed fill and swing annotations without altering input',()=>{
 const markers=[{text:'SIM BUY',time:1},{text:'SIM SELL',time:2},{text:'SIM EXIT',time:3},{text:'FILL BUY',time:4},{text:'Swing high · confirmed',time:5}];
 const before=structuredClone(markers);
 assert.deepEqual(chartSimulationMarkers(markers,false).map(m=>m.text),['FILL BUY','Swing high · confirmed']);
 assert.deepEqual(markers,before);
 assert.deepEqual(chartSimulationMarkers(markers,true),before);
});
test('execution fills remain visible with simulations hidden and deduplicate by lifecycle',()=>{
 const order={status:'FILLED',is_entry:true,underlying_symbol:'INDEX',run_id:'RUN',lifecycle_id:'LIFE',filled_at:125,indicator_snapshot:{settings:{timeframe:'1 minute'},indicators:{direction:'BULLISH'}}};
 const s={config:{underlying:'INDEX',timeframe:'1 minute'},run_id:'RUN',order_history:[order,order]};
 const hidden=chartSimulationMarkers([{text:'SIM BUY',time:120,position:'belowBar',shape:'arrowUp'}],false);
 const output=executionMarkers(hidden,s,'INDEX','1 minute');
 assert.equal(output.length,1);assert.equal(output[0].text,'FILL BUY');assert.equal(output[0].time,120);
});
