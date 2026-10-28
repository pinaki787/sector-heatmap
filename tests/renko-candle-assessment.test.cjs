const {test}=require('node:test'),assert=require('node:assert/strict');
const {candleInspection}=require('../renko-supertrend.js');
const config={underlying:'NSE:NIFTY50-INDEX',timeframe:'5 minutes',mode:'LIVE',calibrated_enabled:true,calibrated_overlap_max:.4,calibrated_overlap_pairs:6,retest_enabled:true,ema_fast_enabled:true,ema_slow_enabled:true,ema_third_enabled:true,ema_momentum_enabled:true,ema_proximity_enabled:true,higher_timeframe_enabled:true,supertrend_timeframe:'15 minutes'};
const record={timestamp:100,run_id:'run',underlying:config.underlying,timeframe:config.timeframe,eligible:false,code:'WAITING_CALIBRATED_OVERLAP',reason:'Overlap exceeds maximum',signal:{timestamp:100,close:22781.3,open:22772.05,high:22784.15,low:22766.8,direction:'BULLISH',ema10:22756.289349,ema30:22731.132702,ema100:22660.97783,ema_widening:true,retest_signal:false,retest_touched:false,calibrated_filter:{allowed:false,average_overlap:.436092736},mtf_supertrend:{allowed:false,reason:'Incomplete recent Supertrend history.'}}};
const input={time:100,symbol:config.underlying,timeframe:config.timeframe,state:{config,run_id:'run',entry_assessments:[record],latest_entry_assessment:{...record,timestamp:200,signal:{direction:'BEARISH'}}},rows:[{timestamp:100,direction:'BEARISH'}]};
test('exact candle uses actual run record and recorded Start settings',()=>{
 const m=candleInspection(input);assert.equal(m.source,'Recorded runner assessment');assert.equal(m.mode,'LIVE');
 assert.equal(m.checks.find(r=>r.name==='Calibrated overlap').status,'FAIL');
 assert.equal(m.checks.find(r=>r.name==='Calibrated overlap').observed,'Observed 43.61%');
 assert.equal(m.checks.find(r=>r.name==='EMA alignment').status,'PASS');
 assert.equal(m.checks.find(r=>r.name==='Retest / EMA touch').status,'WAIT');
 assert.equal(m.checks.find(r=>r.name==='Higher-timeframe Supertrend').status,'UNAVAILABLE');
 assert.equal(m.checks.find(r=>r.name==='ADX'),undefined);
 assert.equal(m.checks.find(r=>r.name==='Momentum chase').status,'WAIT');
 assert.ok(!JSON.stringify(m).includes('22756.289349'));
});
test('older candle never inherits latest or different-run assessment',()=>{
 for(const changed of [{time:50},{state:{...input.state,run_id:'different'}}]){
  const m=candleInspection({...input,...changed});assert.equal(m.source,'Historical chart reconstruction');assert.match(m.reason,/do not establish a live rejection/);
 }
});
test('forming candle cannot consume completed record or imply confirmed pass',()=>{
 const m=candleInspection({...input,forming:true,rows:[]});assert.equal(m.source,'Forming chart preview');assert.match(m.reason,/Forming display only/);
 assert.equal(m.checks.find(r=>r.name==='EMA alignment').status,'UNAVAILABLE');
});
test('unmatched chart settings do not borrow active runner values',()=>{
 const m=candleInspection({...input,symbol:'OTHER',settings:{ema_fast_enabled:false,ema_slow_enabled:false}});
 assert.equal(m.configSource,'Chart settings');assert.equal(m.mode,null);assert.equal(m.checks.find(r=>r.name==='EMA alignment'),undefined);
});

test('shifted price brick resolves exact event, true indicators and recorded Paper fills',()=>{
 const {chartCandles}=require('../renko-supertrend.js'),t=1793215985.850288;
 const sig={timestamp:t,source_timestamp:t,source_event_index:0,source_sequence:3764,source_generation:3,open:81190.5,high:81247,low:81190.5,close:81247,supertrend:80983.28664661174,direction:'BULLISH',entry_qualified:true,entry_direction:'BULLISH'};
 const row={...sig,brick_events:[sig]},config={underlying:'BTCUSD',timeframe:'5 minutes',mode:'PAPER',supertrend_enabled:true,ema_fast_enabled:false,ema_slow_enabled:false};
 const record={timestamp:t,event_at:t,run_id:'price-run',underlying:'BTCUSD',timeframe:'5 minutes',eligible:true,code:'ELIGIBLE',reason:'Fresh event',signal:sig};
 const state={config,run_id:'price-run',running:true,entry_assessments:[record],order_history:[{run_id:'price-run',underlying_symbol:'BTCUSD',entry_event_at:t,is_entry:true,side:'BUY',mode:'PAPER',status:'FILLED',filled:1,average_price:482,filled_at:1793215990.714252},{run_id:'price-run',underlying_symbol:'BTCUSD',entry_event_at:t,is_entry:false,side:'SELL',mode:'PAPER',status:'FILLED',filled:1,average_price:420,filled_at:1793216249.694735}]};
 const brick=chartCandles({settings:{strategy_basis:'RENKO'},rows:[row]},'synthetic')[0];
 const model=candleInspection({time:brick.time,brick,symbol:'BTCUSD',timeframe:'5 minutes',state,rows:[row]});
 assert.notEqual(brick.time,t);assert.equal(model.time,t);assert.equal(model.displayTime,brick.time);
 assert.equal(model.source,'Recorded runner assessment');assert.equal(model.execution.length,2);
 assert.equal(model.execution[0].filled_at,1793215990.714252);
 assert.match(model.checks.find(c=>c.name==='Renko / ST direction').observed,/80983.29/);
 for(const changed of [{...brick,indicator_timestamp:t+.001,source_timestamp:t+.001},{...brick,source_sequence:3765},{...brick,source_event_index:1}]){
  assert.equal(candleInspection({time:changed.time,brick:changed,symbol:'BTCUSD',timeframe:'5 minutes',state,rows:[row]}).source,'Historical chart reconstruction');
 }
 assert.equal(candleInspection({time:brick.time,brick,symbol:'BTCUSD',timeframe:'5 minutes',state:{...state,order_history:[]},rows:[row]}).execution.length,0);
});
test('same-source multi-bricks cannot borrow the final sibling assessment',()=>{
 const {chartCandles}=require('../renko-supertrend.js'),t=100;
 const first={timestamp:t,source_timestamp:t,source_event_index:0,open:100,close:110,supertrend:95,direction:'BULLISH'};
 const last={timestamp:t,source_timestamp:t,source_event_index:1,open:110,close:120,supertrend:101,direction:'BULLISH',entry_qualified:true};
 const rows=[{...last,brick_events:[first,last]}],bricks=chartCandles({settings:{strategy_basis:'RENKO'},rows},'synthetic');
 const state={config:{underlying:'BTCUSD',timeframe:'5 minutes',mode:'PAPER',ema_fast_enabled:false,ema_slow_enabled:false},run_id:'r',entry_assessments:[{timestamp:t,run_id:'r',underlying:'BTCUSD',timeframe:'5 minutes',code:'ELIGIBLE',signal:last}]};
 const inspect=brick=>candleInspection({time:brick.time,brick,symbol:'BTCUSD',timeframe:'5 minutes',state,rows});
 assert.equal(inspect(bricks[0]).source,'Historical chart reconstruction');
 assert.match(inspect(bricks[0]).checks.find(c=>c.name==='Renko / ST direction').observed,/Supertrend 95/);
 assert.equal(inspect(bricks[1]).source,'Recorded runner assessment');
 assert.notEqual(bricks[0].time,bricks[1].time);
});

test('stopped price run uses immutable recorded history while explicit draft remains editable',()=>{
 const {runnerChartContext}=require('../renko-supertrend.js');
 const state={running:false,run_id:'old',confirmed_feed_revision:'shared-confirmed-live-v1',config:{underlying:'BTCUSD',timeframe:'5 minutes',mode:'PAPER',strategy_basis:'RENKO',renko_confirmation:'PRICE',lots:1},last_signal:{confirmation_basis:'ORDERED_LIVE_PRICE',box:56.5}};
 const fields={symbol:'BTCUSD',timeframe:'5 minutes',lots:10,mode:'PAPER'};
 const before=JSON.stringify(state),c=runnerChartContext(fields,state);
 assert.equal(c.basis,'recorded');assert.equal(c.settings.confirmed_run_id,'old');assert.deepEqual(c.history,{});assert.match(c.label,/LAST RECORDED RUN.*STOPPED.*PAPER/);
 assert.equal(runnerChartContext(fields,state,true).basis,'draft');
 assert.equal(runnerChartContext({...fields,symbol:'ETHUSD'},state).basis,'draft');
 assert.equal(runnerChartContext(fields,{...state,last_signal:{}}).basis,'draft');
 assert.equal(JSON.stringify(state),before);assert.equal(fields.lots,10);
});
