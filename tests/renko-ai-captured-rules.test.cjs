
const test=require('node:test'),assert=require('node:assert/strict');
const {capturedStrategyRules}=require('../renko-ai-options.js');
const snapshot={run_id:'fixture',underlying:'MCX:TEST',running:true,mode:'LIVE',source_timeframe:1,supertrend_enabled:true,signal_source:'UNDERLYING',sma_retest_required:false,sizing_mode:'MANUAL_PARENT',manual_parent_value:200,heartbeat:{moving_bands:{bands:[{kind:'EMA',period:30,entry:true,exit:true}]}}};
test('current captured rules explain fresh flip, EMA and independent exits',()=>{
 const rules=capturedStrategyRules(snapshot,'MCX:TEST').lines.join(' ');
 assert.match(rules,/NEW confirmed Supertrend flip/);assert.match(rules,/EMA 30 entry/);
 assert.match(rules,/Any enabled exit can trigger independently/);assert.match(rules,/SMA entry is off/);
 assert.match(rules,/user supplied, not independently verified/);
 assert.doesNotMatch(rules,/retest: ON/);
});
test('different account instrument selection never inherits old run rules',()=>{
 assert.equal(capturedStrategyRules(snapshot,'OTHER'),null);assert.equal(capturedStrategyRules({},'MCX:TEST'),null);
});
test('SMA-only and manual positions are described without inventing a Supertrend gate',()=>{
 const s={...snapshot,supertrend_enabled:false,heartbeat:{position:{manual_override:true},moving_bands:{bands:[{kind:'SMA',period:10,entry:true,exit:true}]}}};
 const text=capturedStrategyRules(s,'MCX:TEST').lines.join(' ');
 assert.match(text,/no Supertrend gate/);assert.match(text,/OFF — not required/);assert.match(text,/manual override/);
 assert.doesNotMatch(text,/NEW confirmed/);
});

test('rules reject another account and name direct Long/Short correctly',()=>{
 assert.equal(capturedStrategyRules({...snapshot,manual_entry_context:{account_id:'one'}},'MCX:TEST','two'),null);
 const text=capturedStrategyRules({...snapshot,execution_route:'DIRECT'},'MCX:TEST').lines.join(' ');
 assert.match(text,/opens Long; bearish opens Short/);assert.doesNotMatch(text,/buys Put/);
});
