const test=require('node:test'),assert=require('node:assert/strict');
const {marketWaitLabel}=require('../renko-ai-options.js');
test('active closed market displays waiting without suggesting Start again',()=>{
 assert.equal(marketWaitLabel({running:true,heartbeat:{market_state:'WAITING_FOR_MARKET'}}),'Waiting for market open · runner active');
 assert.equal(marketWaitLabel({running:false,heartbeat:{market_state:'WAITING_FOR_MARKET'}}),null);
 assert.equal(marketWaitLabel({running:true,heartbeat:{market_state:'READY'}}),null);
 assert.match(marketWaitLabel({running:true,heartbeat:{market_state:'WAITING_FOR_MARKET_STATUS'}}),/orders paused/);
});
