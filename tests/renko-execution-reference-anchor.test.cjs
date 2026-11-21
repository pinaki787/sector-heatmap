const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {executionMarkers,mapExecutionMarkers}=require(path.resolve(process.env.RENKO_SOURCE||'renko-supertrend.js'));
const ref={confirmation_basis:'ORDERED_LIVE_PRICE',timestamp:105,open:101,close:102,source_generation:0,source_sequence:2,source_event_index:0};
const order={status:'FILLED',is_entry:true,underlying_symbol:'INDEX',run_id:'RUN',lifecycle_id:'LIFE',filled_at:110,entry_event_at:100,indicator_snapshot:{settings:{timeframe:'1 minute'},confirmed_indicator_reference:ref,indicators:{direction:'BULLISH'}}};
function state(row=order){return {config:{underlying:'INDEX',timeframe:'1 minute'},run_id:'RUN',order_history:[row]};}
test('fill mapping uses the captured reference brick when preflight advanced past initial signal',()=>{
 const markers=executionMarkers([],state(),'INDEX','1 minute');
 const bricks=[{time:1,source_timestamp:100,open:100,close:101,source_sequence:1,source_generation:0,source_event_index:0},{time:2,source_timestamp:105,open:101,close:102,source_sequence:2,source_generation:0,source_event_index:0}];
 const mapped=mapExecutionMarkers(markers,bricks);assert.equal(mapped.length,1);assert.equal(mapped[0].time,2);assert.equal(mapped[0].text,'FILL BUY');
 assert.equal(order.entry_event_at,100);assert.equal(order.filled_at,110);
});
test('missing matching reference never borrows a nearby brick',()=>{
 const markers=executionMarkers([],state(),'INDEX','1 minute');
 assert.equal(mapExecutionMarkers(markers,[{time:104,source_timestamp:104,open:101,close:102}]).length,0);
});
test('legacy candle fills remain aligned by filled host interval and isolate another run',()=>{
 const legacy={...order,filled_at:125,indicator_snapshot:{settings:{timeframe:'1 minute'},indicators:{direction:'BULLISH'}}};
 assert.equal(executionMarkers([],state(legacy),'INDEX','1 minute')[0].time,120);
 assert.equal(executionMarkers([],state({...order,run_id:'OTHER'}),'INDEX','1 minute').length,0);
});
