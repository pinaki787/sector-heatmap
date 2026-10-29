const {test}=require('node:test'),assert=require('node:assert/strict');
const {assessment}=require('../renko-assessment.js');
const {chartCandles,mapExecutionMarkers}=require('../renko-supertrend.js');
function live(){
 const q={timestamp:1013,confirmation_basis:'ORDERED_LIVE_PRICE',market_event_at:1013,close:100,direction:'BULLISH',entry_diagnostic:'WAITING_SUPERTREND_SLOPE',supertrend_slope_filter:{allowed:false,reason:'Flat'}};
 return {running:true,run_id:'run',updated_at:1804,eligible_since:1000,status:'WATCHING_NO_ENTRY',stream:{connected:true},config:{underlying:'S',timeframe:'5 minutes',mode:'PAPER',renko_confirmation:'PRICE',supertrend_enabled:true,supertrend_slope_enabled:true,ema_fast_enabled:false,ema_slow_enabled:false,ema_third_enabled:false,ema_widening_enabled:false},last_signal:q,confirmed_indicators:{latest:q},latest_entry_assessment:{run_id:'run',underlying:'S',timeframe:'5 minutes',timestamp:1013,observed_at:1014,signal:q,code:'WAITING_SUPERTREND_SLOPE',reason:'Supertrend slope did not pass'},price_confirmation_health:{error:null,source:{run_id:'run',last_exchange_at:1804}}};
}
test('older arbitrary-second completed brick remains latest recorded assessment with a fresh live stream',()=>{
 const s=live(),a=assessment(s,{symbol:'S',timeframe:'5 minutes'},1805);
 assert.equal(a.fresh,true);assert.equal(a.assessed_at,1014);assert.equal(a.price_confirmed,true);assert.match(a.reason,/Supertrend/);assert.match(a.title,/brick/);assert.equal(a.event_age,792);
});
test('price assessment cannot borrow stale snapshots, old-run records or stale underlying ticks',()=>{
 for(const mutate of [s=>s.updated_at=1700,s=>s.latest_entry_assessment.run_id='old',s=>s.price_confirmation_health.source.last_exchange_at=1700,s=>s.price_confirmation_health.source.run_id='old',s=>s.price_confirmation_health.error='Feed unavailable',s=>s.confirmed_indicators.latest={...s.last_signal,timestamp:1050}]){
  const s=live();mutate(s);assert.equal(assessment(s,{symbol:'S',timeframe:'5 minutes'},1805).fresh,false);
 }
});
test('handoff collapses only adjacent identical historical/live drawing and preserves live identity plus marker aliases',()=>{
 const b={open:90,close:100,high:100,low:90,box:10,supertrend:80};
 const data={settings:{strategy_basis:'RENKO'},rows:[{timestamp:100,brick_events:[b]},{timestamp:150,confirmation_basis:'ORDERED_LIVE_PRICE',source_sequence:7,brick_events:[{...b,source_timestamp:150}]}]};
 const plotted=chartCandles(data,'synthetic');assert.equal(plotted.length,1);assert.equal(plotted[0].source_timestamp,150);assert.equal(plotted[0].source_sequence,7);assert.equal(plotted[0].history_handoff_compacted,true);
 assert.equal(mapExecutionMarkers([{time:100,text:'BUY'}],plotted)[0].time,plotted[0].time);
 assert.equal(mapExecutionMarkers([{time:100+1/3,text:'BUY'}],plotted)[0].time,plotted[0].time);
 assert.equal(mapExecutionMarkers([{time:150,text:'BUY'}],plotted)[0].time,plotted[0].time);
 data.rows.push({timestamp:170,confirmation_basis:'ORDERED_LIVE_PRICE',brick_events:[b]});assert.equal(chartCandles(data,'synthetic').length,2);
 data.rows[1].brick_events[0]={...b,open:100,close:110,high:110,low:100};assert.equal(chartCandles(data,'synthetic').length,3);
});

test('prior-run history revision is not displayed as a current price-run revision',()=>{const s=live();s.started_at=1000;s.history_revised_at=500;assert.equal(assessment(s,{symbol:'S',timeframe:'5 minutes'},1805).history_revised_at,null);});
