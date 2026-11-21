const test=require('node:test'),assert=require('node:assert/strict');
const {universalStrategyDefaults,signalSettings,chartSettings,activeRunnerFields,candleInspection}=require('../renko-supertrend.js');
test('reset enables adjustable one-observation slope without optional chop gates',()=>{
 const d=universalStrategyDefaults({});
 assert.equal(d['supertrend-slope-enabled'],true);assert.equal(d['supertrend-slope-bars'],1);assert.equal(d['supertrend-slope-min-atr'],0);assert.equal(d['anti-chop-enabled'],false);
 const c=signalSettings(d);assert.equal(c.supertrend_slope_enabled,true);assert.equal(c.supertrend_slope_bars,1);
 assert.equal(chartSettings({...d,'supertrend-family-enabled':false}).supertrend_slope_enabled,false);
});
test('old saved settings stay off and numeric controls reach engine',()=>{
 assert.equal(signalSettings({}).supertrend_slope_enabled,false);
 const c=signalSettings({'supertrend-slope-enabled':true,'supertrend-slope-bars':'3','supertrend-slope-min-atr':'0.05'});
 assert.equal(c.supertrend_slope_bars,3);assert.equal(c.supertrend_slope_min_atr,.05);
});

test('legacy named configuration does not inherit enabled reset filter',()=>{
 const {restoredConfigurationFields}=require('../renko-supertrend.js');
 const f=restoredConfigurationFields(universalStrategyDefaults({}),{settings:{},symbol:'BTCUSD'});
 assert.equal(f['supertrend-slope-enabled'],false);
});

test('reset disables EMA 30 entry across symbols while retaining its chart display',()=>{
 for(const symbol of ['NSE:NIFTY50-INDEX','MCX:CRUDEOILM26NOVFUT','BTCUSD']){
 const d=universalStrategyDefaults({symbol,'ema-family-enabled':true,'ema-fast-enabled':true,'ema-exit-enabled':true,'ema-fast-enabled-indicator':true,'ema-exit-enabled-indicator':true,'anti-chop-enabled':true,'higher-timeframe-enabled':true});
 assert.equal(d.symbol,symbol);assert.equal(d['ema-family-enabled'],true);assert.equal(d['ema-slow-enabled'],false);assert.equal(d['ema-slow-enabled-indicator'],true);assert.equal(signalSettings(d).ema_slow_enabled,false);assert.equal(chartSettings(d).ema_slow_enabled,true);
 for(const key of ['ema-fast-enabled','ema-fast-enabled-indicator','ema-widening-enabled','rsi-family-enabled','adx-family-enabled','structure-family-enabled','zones-family-enabled','anti-chop-enabled','higher-timeframe-enabled'])assert.equal(d[key],false,key);
 const c=signalSettings(d);assert.equal(c.supertrend_slope_enabled,true);assert.equal(c.supertrend_enabled,true);assert.equal(c.ema_exit_enabled,true);assert.equal(c.ema_fast_enabled,false);
 const chart=chartSettings(d);assert.equal(chart.ema_fast_enabled,false);assert.equal(chart.ema_exit_enabled,true);
 }
});

test('default adds EMA100 entry and exit alongside Supertrend, leaving EMA30 entry off',()=>{
 for(const symbol of ['NSE:NIFTY50-INDEX','MCX:CRUDEOILM26NOVFUT','BTCUSD']){
  const d=universalStrategyDefaults({symbol});
  const c=signalSettings(d), chart=chartSettings(d);
  assert.equal(c.ema_third_enabled,true);assert.equal(c.ema_third_length,100);
  assert.equal(c.ema_exit_enabled,true);assert.equal(c.ema_exit_length,100);
  assert.equal(c.ema_slow_enabled,false);assert.equal(c.supertrend_enabled,true);assert.equal(c.supertrend_exit_enabled,true);
  assert.equal(chart.ema_third_enabled,true);assert.equal(chart.ema_exit_length,100);
 }
});
