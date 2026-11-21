const {test}=require('node:test'),assert=require('node:assert/strict');
const {chartDisplaySelection,chartSettings}=require('../renko-supertrend.js');
test('parent OFF replaces stale embedded HTF selection without changing execution settings',()=>{
 const child={'higher-timeframe-enabled':true,'higher-timeframe-enabled-indicator':true,mode:'PAPER',lots:100};
 const selection=chartDisplaySelection({'higher-timeframe-enabled':false,'higher-timeframe-enabled-indicator':false,mode:'LIVE',lots:1});
 const next={...child,...selection};
 assert.equal(next['higher-timeframe-enabled-indicator'],false);
 assert.equal(next['higher-timeframe-enabled'],true);
 assert.equal(next.mode,'PAPER');assert.equal(next.lots,100);
 assert.equal(chartSettings(next).higher_timeframe_enabled,false);
});
test('chart-only HTF may remain ON independently of strategy checkbox',()=>{
 const selected=chartDisplaySelection({'higher-timeframe-enabled':false,'higher-timeframe-enabled-indicator':true});
 assert.deepEqual(selected,{'higher-timeframe-enabled-indicator':true});
});
test('visual sync retains family OFF and rejects nonboolean or unrelated settings',()=>{
 assert.deepEqual(chartDisplaySelection({'supertrend-family-enabled':false,'volume-enabled':false,'rsi-sma-enabled':true,'supertrend-enabled-indicator':'false',mode:'LIVE',symbol:'BTCUSD','calibrated-enabled':true}),{'volume-enabled':false,'rsi-sma-enabled':true,'supertrend-family-enabled':false});
});
