const test=require('node:test');
const assert=require('node:assert/strict');
const {signalSettings,universalStrategyDefaults,activeRunnerFields}=require('../renko-supertrend.js');
test('Renko confirmation defaults to two and transmits explicit one/two/larger counts',()=>{
 assert.equal(universalStrategyDefaults({})['swing-breakout-bricks'],2);
 for(const n of [1,2,5])assert.equal(signalSettings({'swing-breakout-bricks':String(n)}).swing_breakout_bricks,n);
});
test('Captured runner confirmation is displayed without replacing the draft',()=>{
 const draft={symbol:'BTCUSD','swing-breakout-bricks':1};
 const fields=activeRunnerFields(draft,{running:true,config:{underlying:'BTCUSD',swing_breakout_bricks:3}});
 assert.equal(fields['swing-breakout-bricks'],3);assert.equal(draft['swing-breakout-bricks'],1);
});
