const test=require('node:test'),assert=require('node:assert/strict');
const {assessment}=require('../renko-assessment.js');
const now=1805,view={symbol:'BTCUSD',timeframe:'5 minutes'};
const base=()=>({running:true,run_id:'current',status:'WATCHING_NO_ENTRY',updated_at:1804,eligible_since:1200,stream:{connected:true},config:{underlying:'BTCUSD',timeframe:'5 minutes',mode:'PAPER',use_adx:true,adx_threshold:25,widening_window:2,retest_enabled:true,ema_proximity_enabled:true,ema_proximity_mode:'ATR',ema_proximity_distance:.5},last_signal:{timestamp:1500,close:90,ema10:95,ema30:100,direction:'BEARISH',adx:40,signal_allowed:true,ema_widening:false,entry_diagnostic:'WAITING_WIDENING',entry_qualified:false,retest_signal:false}});
test('uses saved runner gate evidence, not passing visible ADX or staged settings',()=>{
 const a=assessment(base(),view,now);assert.match(a.reason,/gap is not strictly widening/);assert.equal(a.link,true);assert.ok(a.checks.includes('PASS · ADX 40.0 > 25'));assert.ok(a.checks.some(x=>x.startsWith('PENDING · Proximity')));assert.doesNotMatch(a.reason,/sideways/i);
});
test('no entry never implies sideways; only a recorded active quick-loss lock is shown',()=>{
 const s=base();s.sideways_status={enabled:true};assert.doesNotMatch(assessment(s,view,now).reason,/sideways/i);s.sideways_status.lock={active:true};const a=assessment(s,view,now);assert.equal(a.title,'Quick-loss range lock');assert.match(a.reason,/does not classify/);assert.equal(a.link,undefined);
});
test('stale, disconnected or older-candle evidence cannot claim a current gate block',()=>{
 for(const mutate of [s=>s.updated_at=1700,s=>s.last_signal.timestamp=1200,s=>s.stream.connected=false]){const s=base();mutate(s);const a=assessment(s,view,now);assert.equal(a.fresh,false);assert.doesNotMatch(a.reason,/gap is not/);assert.equal(a.link,undefined);}
 assert.equal(assessment(base(),view,now,false).fresh,false);
});
test('stopped, pending, held exposure and absent configuration show management state',()=>{
 const s=base();s.running=false;assert.equal(assessment(s,view,now).title,'Runner stopped');s.position={symbol:'PUT'};assert.equal(assessment(s,view,now).title,'Monitoring stopped · position remains');s.running=true;s.pending={};assert.equal(assessment(s,view,now).title,'Order reconciliation');s.pending=null;assert.equal(assessment(s,view,now).title,'Position management');assert.match(assessment({},view,now).reason,/No armed/);
});
test('chart mismatch and pre-arming candles are not executable assessments',()=>{
 assert.match(assessment(base(),{...view,timeframe:'1 minute'},now).reason,/Chart differs/);const s=base();s.eligible_since=1801;assert.match(assessment(s,view,now).reason,/predates entry eligibility/);assert.equal(assessment(s,view,now).link,true);
});
test('forming assessments are provisional and require fresh market-event time',()=>{
 const s=base();Object.assign(s.last_signal,{timestamp:1800,provisional:true,market_event_at:1804});let a=assessment(s,view,now);assert.equal(a.provisional,true);assert.match(a.title,/provisional/);s.last_signal.market_event_at=1780;assert.equal(assessment(s,view,now).fresh,false);
});
test('only same-run same-candle execution evidence supplies execution eligibility reason',()=>{
 const s=base();s.execution_signals=[{run_id:'old',underlying:'BTCUSD',timestamp:1500,eligible:false,reason:'OLD ERROR'}];assert.doesNotMatch(assessment(s,view,now).reason,/OLD ERROR/);s.execution_signals[0].run_id='current';assert.match(assessment(s,view,now).reason,/OLD ERROR/);s.status='BLOCKED';s.message='Entry too far from EMA10: 20 points; maximum 10.';assert.match(assessment(s,view,now).reason,/Blocked at runner preflight: Entry too far/);
});
test('qualifying setup alone does not claim entry, retest waiting is an alternative path',()=>{
 const s=base();Object.assign(s.last_signal,{entry_qualified:true,entry_diagnostic:'QUALIFIED',ema_widening:true});const a=assessment(s,view,now);assert.match(a.reason,/waiting for a fresh entry event/);assert.ok(a.checks.some(x=>x.includes('No confirmed retest entry')));s.config.use_adx=false;assert.ok(assessment(s,view,now).checks.includes('OFF · ADX gate'));
});

test('routine history revision explanation retains completed rule evidence',()=>{
 const s=base();s.eligible_since=1801;s.history_recoveries=[{at:1801}];
 const a=assessment(s,view,now);assert.match(a.reason,/excluded from entry eligibility/);assert.equal(a.fresh,true);assert.equal(a.link,true);assert.ok(a.checks.some(x=>x.includes('EMA gap widening')));
});
test('recorded actual evaluation is not replaced by subsequently revised indicator output',()=>{
 const s=base();const signal={...s.last_signal,entry_diagnostic:'WAITING_RSI_DIRECTION',rsi14_slope:2,rsi_slope_pass:false};
 s.config.rsi_slope_enabled=true;s.eligible_since=1801;
 s.latest_entry_assessment={run_id:'current',underlying:'BTCUSD',timeframe:'5 minutes',timestamp:1500,observed_at:1802,code:'WAITING_RSI_DIRECTION',eligible:false,signal};
 s.last_signal={...s.last_signal,entry_diagnostic:'QUALIFIED',entry_qualified:true};
 const a=assessment(s,view,now);assert.match(a.reason,/RSI14 slope opposes/);assert.ok(a.checks.some(x=>x.includes('RSI14 slope 2.000')));assert.equal(a.assessed_at,1802);
});
test('confirmed retest assessment remains visible and eligible through historical rebuild',()=>{
 const s=base();const signal={...s.last_signal,retest_signal:true,entry_qualified:true,entry_direction:'BEARISH',entry_diagnostic:'EMA10_RETEST_BOUNCE'};
 s.latest_entry_assessment={run_id:'current',underlying:'BTCUSD',timeframe:'5 minutes',timestamp:1500,observed_at:1802,eligible:true,code:'ELIGIBLE',signal};
 const a=assessment(s,view,now);assert.match(a.reason,/Entry signal eligible/);assert.ok(a.checks.includes('PASS · Confirmed retest pattern'));assert.equal(a.link,true);
});
test('unmatched prior-run assessment cannot explain the current decision',()=>{
 const s=base();s.latest_entry_assessment={run_id:'old',underlying:'BTCUSD',timeframe:'5 minutes',timestamp:1500,code:'BLOCKED',reason:'WRONG RUN',signal:s.last_signal};
 assert.doesNotMatch(assessment(s,view,now).reason,/WRONG RUN/);
});
test('invalid runner history reports the exact error instead of a current gate decision',()=>{
 const s=base();s.last_signal.timestamp=1200;s.status='BLOCKED';s.message='Invalid Renko host candle OHLC.';
 const a=assessment(s,view,now);assert.equal(a.fresh,false);assert.match(a.reason,/Entry data unavailable: Invalid Renko host candle OHLC/);
});

test('saved same-candle execution blocker survives WATCHING status and replaces pending proximity',()=>{
 const s=base();Object.assign(s.last_signal,{entry_qualified:true,entry_diagnostic:'QUALIFIED',cross_direction:'BEARISH',ema_widening:true});
 s.latest_entry_assessment={run_id:'current',underlying:'BTCUSD',timeframe:'5 minutes',timestamp:1500,observed_at:1802,eligible:true,code:'ELIGIBLE',signal:s.last_signal};
 s.execution_signals=[{run_id:'current',underlying:'BTCUSD',timestamp:1500,eligible:true,status:'BLOCKED',reason:'Entry too far from EMA10: 52.88 underlying points; maximum 19.02.'}];
 const a=assessment(s,view,now);assert.match(a.reason,/Blocked at runner preflight: Entry too far/);assert.equal(a.tone,'blocked');assert.ok(a.checks.some(x=>x.startsWith('BLOCKED · Entry too far')));assert.ok(!a.checks.some(x=>x.startsWith('PENDING · Proximity')));
 s.execution_signals[0].timestamp=1200;assert.match(assessment(s,view,now).reason,/Entry signal eligible/);
});
