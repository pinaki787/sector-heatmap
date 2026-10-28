const {test}=require('node:test'),assert=require('node:assert/strict');
const {refreshChartViewport,runnerStartContext}=require('../renko-supertrend.js');
const rows=Array.from({length:100},(_,i)=>({time:i}));
test('live edge advances on append without resetting zoom',()=>{
 const r=refreshChartViewport(rows,[...rows,{time:100}],{from:70,to:102},true);
 assert.equal(r.follow,true);assert.deepEqual(r.range,{from:71,to:103});
});
test('manual history is anchored to time across rolling-window trimming',()=>{
 const r=refreshChartViewport(rows,[...rows.slice(5),{time:100}],{from:20.5,to:40.5},true);
 assert.equal(r.follow,false);assert.deepEqual(r.range,{from:15.5,to:35.5});
});
test('recorded eligible event is not retroactively excluded by later errors',()=>{
 const c=runnerStartContext(rows,{started_at:10,eligible_since:50,run_id:'r',config:{mode:'PAPER'},execution_signals:[{run_id:'r',event_at:30,eligible:true,status:'BLOCKED',reason:'Quote unavailable'}]},300);
 assert.equal(c.eventTiming,'AFTER_START');assert.equal(c.event.status,'BLOCKED');
});
