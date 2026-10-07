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
 assert.match(assessment(base(),{...view,timeframe:'1 minute'},now).reason,/Chart differs/);const s=base();s.eligible_since=1801;assert.match(assessment(s,view,now).reason,/predates entry eligibility/);assert.equal(assessment(s,view,now).link,undefined);
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
