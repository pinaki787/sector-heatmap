
const test=require('node:test'),assert=require('node:assert/strict');
const {configuration}=require('../renko-ai-options.js');
const f={underlying:'NSE:NIFTY50-INDEX',timeframe:'1 minute',lots:1,execution:'PAPER',product:'MARGIN'};
test('SMA retest defaults off and is explicitly selectable',()=>{
 assert.equal(configuration(f,{id:'owner',broker:'FYERS'}).ai_sma_retest_required,false);
 assert.equal(configuration({...f,smaRetest:true},{id:'owner',broker:'FYERS'}).ai_sma_retest_required,true);
});
