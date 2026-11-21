const {test}=require('node:test'),assert=require('node:assert/strict'),m=require('../renko-supertrend.js');
test('new and reset defaults select SMA entry and exit on completed bricks',()=>{
 const f=m.universalStrategyDefaults({symbol:'BTCUSD','market-structure-enabled':true,'swing-breakout-enabled':true,'supertrend-enabled':true});
 assert.equal(f['sma-entry-enabled'],true);assert.equal(f['sma-exit-enabled'],true);assert.equal(f['sma-length'],5);
 assert.equal(f['strategy-mode'],'SIMPLE_BRICK');assert.equal(f['renko-brick-exit-enabled'],false);
 for(const k of ['swing-breakout-enabled','swing-levels-visible','supertrend-enabled','ema-fast-enabled','ema-slow-enabled','ema-third-enabled','rsi-slope-enabled','market-structure-enabled'])assert.equal(f[k],false,k);
 const c=m.chartEntrySettings(f);assert.equal(c.strategy_mode,'SIMPLE_BRICK');assert.equal(c.swing_breakout_enabled,false);assert.equal(c.renko_brick_exit_enabled,false);
});
test('old drafts retain mode and breakout behavior; display and mode travel to embedded chart',()=>{
 const f=m.migrateDestinations({'swing-breakout-bricks':2});assert.equal(f['strategy-mode'],'SUPERTREND');assert.equal(f['swing-breakout-enabled'],true);
 const current={'strategy-mode':'SIMPLE_BRICK','swing-breakout-enabled':false,'swing-levels-visible':true};
 assert.equal(m.migrateDestinations(current)['sma-entry-enabled'],true);
 assert.equal(m.migrateDestinations({...current,'sma-entry-enabled':false})['sma-entry-enabled'],false);
 assert.equal(f['sma-entry-enabled'],false);
 assert.equal(m.chartEditorSelection(current)['strategy-mode'],'SIMPLE_BRICK');assert.equal(m.chartDisplaySelection(current)['swing-levels-visible'],true);
});
test('disabled Supertrend slope parameters cannot block Simple Brick or family-off requests',()=>{
 for(const fields of [
  {'strategy-mode':'SIMPLE_BRICK','supertrend-slope-enabled':true,'supertrend-family-enabled':true},
  {'strategy-mode':'SUPERTREND','supertrend-slope-enabled':false,'supertrend-family-enabled':true},
  {'strategy-mode':'SUPERTREND','supertrend-slope-enabled':true,'supertrend-family-enabled':false}
 ]){
  const original={...fields,'supertrend-slope-bars':0,'supertrend-slope-min-atr':-1};
  const c=m.signalSettings(original);assert.equal(c.supertrend_slope_bars,1);assert.equal(c.supertrend_slope_min_atr,0);assert.equal(original['supertrend-slope-bars'],0);
 }
 const active=m.signalSettings({'strategy-mode':'SUPERTREND','supertrend-family-enabled':true,'supertrend-slope-enabled':true,'supertrend-slope-bars':0});
 assert.equal(active.supertrend_slope_bars,0,'Selected invalid rule must reach validation, not be silently relaxed');
});
test('selected slope validation errors are settings failures, not retryable feed outages',()=>{
 assert.equal(m.chartSettingsFailure({status:400,message:'Supertrend slope lookback must be 1 to 100 completed observations.'}),true);
 assert.equal(m.chartSettingsFailure({status:503,message:'History unavailable'}),false);
});

test('disabled Third EMA never requires calculations in a Simple Brick chart',()=>{
 const c={strategy_mode:'SIMPLE_BRICK',ema_family_enabled:true,ema_third_enabled:true,indicator_family_choices:{ema_third_enabled:true}};
 assert.equal(m.effectiveFamilySettings(c).ema_third_enabled,false);
 assert.equal(m.effectiveFamilySettings({...c,strategy_mode:'SUPERTREND',ema_family_enabled:false}).ema_third_enabled,false);
 assert.equal(m.effectiveFamilySettings({...c,strategy_mode:'SUPERTREND'}).ema_third_enabled,true);
});

test('live chart deltas retain every new brick and bound browser display history',()=>{
 const previous=Array.from({length:5000},(_,timestamp)=>({timestamp,close:timestamp}));
 const out=m.mergeChartRows({incremental:true,live_price_confirmed:true,rows:[{timestamp:5000,close:5000},{timestamp:5001,close:5001}]},previous);
 assert.equal(out.rows.length,5000);assert.equal(out.rows[0].timestamp,2);assert.equal(out.rows.at(-1).timestamp,5001);
 const historical=m.mergeChartRows({incremental:true,rows:[{timestamp:5000,close:5000}]},previous);
 assert.equal(historical.rows.length,5001);
});
