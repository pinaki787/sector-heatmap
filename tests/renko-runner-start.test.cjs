const test=require('node:test'),assert=require('node:assert/strict');
const {runnerStartContext}=require('../renko-supertrend.js');
const rows=[{time:1,source_timestamp:100},{time:2,source_timestamp:400},{time:3,source_timestamp:1000}];
const state={started_at:750,eligible_since:750,running:true,run_id:'current',config:{mode:'PAPER'},execution_signals:[{run_id:'older',event_at:900},{run_id:'current',event_at:700,direction:'BULLISH',status:'NOT ELIGIBLE'}]};
test('recorded confirmation before start remains excluded and pointer interpolates source availability',()=>{
 const c=runnerStartContext(rows,state,300);assert.equal(c.eventTiming,'BEFORE_START');assert.equal(c.event.event_at,700);assert.ok(c.logical>1&&c.logical<2);
});
test('later activation boundary is distinguished from initial start',()=>{
 const c=runnerStartContext(rows,{...state,eligible_since:950,execution_signals:[{run_id:'current',event_at:800}]},300);assert.equal(c.eventTiming,'BEFORE_ELIGIBLE');
});
test('new post-start recorded signal and no-signal states are explicit',()=>{
 assert.equal(runnerStartContext(rows,{...state,execution_signals:[{run_id:'current',event_at:800}]},300).eventTiming,'AFTER_START');
 assert.equal(runnerStartContext(rows,{...state,execution_signals:[]},300).eventTiming,'NO_SIGNAL');
 assert.equal(runnerStartContext(rows,{},300),null);
 assert.equal(runnerStartContext(rows,{...state,started_at:2000},300).logical,2.5);
});
