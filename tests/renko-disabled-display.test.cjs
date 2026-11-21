const {test}=require('node:test'),assert=require('node:assert/strict');
const r=require('../renko-supertrend.js');
test('disabled families hide retained chart choices and inspection checks',()=>{
 const fields={'ema-family-enabled':false,'ema-fast-enabled-indicator':true,'rsi-family-enabled':false,'rsi-sma-enabled':true};
 assert.equal(r.effectiveChartChoice(fields,'ema-fast-enabled-indicator'),false);
 assert.equal(r.effectiveChartChoice(fields,'rsi-sma-enabled'),false);
 assert.equal(r.effectiveChartChoice({...fields,'ema-family-enabled':true},'ema-fast-enabled-indicator'),true);
 const config={underlying:'BTCUSD',timeframe:'1 minute',supertrend_enabled:true,ema_family_enabled:false,rsi_family_enabled:false,ema_fast_enabled:true,ema_slow_enabled:true,ema_widening_enabled:true,rsi_level_enabled:true,rsi_slope_enabled:true,calibrated_enabled:false,calibrated_overlap_pairs:6};
 const model=r.candleInspection({time:60,symbol:'BTCUSD',timeframe:'1 minute',state:{config},rows:[{timestamp:60,direction:'BULLISH',supertrend:100}]});
 assert.ok(model.checks.some(x=>x.name==='Renko / ST direction'));
 assert.ok(!model.checks.some(x=>/EMA|RSI|Calibrated/.test(x.name)));
 assert.ok(!model.settings.some(x=>/^(ema|rsi|calibrated) /.test(x.name)));
});
