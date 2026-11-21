const test=require('node:test'),assert=require('node:assert/strict');
const {strategyEntryCheck,chartReplayAudit,chartHistoricalEvents,chartEntrySettings,replayQuerySettings,executionMarkers}=require('../renko-supertrend.js');
const config={strategy_basis:'RENKO',swing_breakout_bricks:2,supertrend_enabled:true,supertrend_slope_enabled:true,supertrend_slope_bars:1,supertrend_slope_min_atr:0,ema_third_enabled:true};
const sig=(side='BULLISH',extra={})=>({timestamp:1,open:side==='BULLISH'?100:120,close:110,entry_qualified:true,has_completed_brick:true,brick_direction:side,pine_direction:side==='BULLISH'?-1:1,ema100:side==='BULLISH'?90:130,supertrend_slope_filter:{allowed:true,lookback:1,slope_atr:side==='BULLISH'?1:-1},swing_breakout:{sides:{[side]:{allowed:true,required:2,count:2,reference:{price:side==='BULLISH'?100:120}}}},...extra});
const row=(event,side='BULLISH',extra={})=>({timestamp:1,strategy_basis:'RENKO',brick_events:[{...sig(side,extra),lifecycle_event:event}]});
test('every selected core rule must pass at the entry brick; equality/forming/missing evidence fail',()=>{
 for(const side of ['BULLISH','BEARISH']){
  assert.equal(strategyEntryCheck(config,sig(side),side).allowed,true);
  for(const extra of [{entry_qualified:false},{provisional:true},{has_completed_brick:false},{ema100:110},{pine_direction:side==='BULLISH'?1:-1},{supertrend_slope_filter:{allowed:true,lookback:1,slope_atr:0}},{swing_breakout:{sides:{[side]:{allowed:true,required:2,count:1}}}},{swing_breakout:null},{swing_breakout:{sides:{[side]:{allowed:true,required:2,count:2,reference:{price:110}}}}}])assert.equal(strategyEntryCheck(config,sig(side,extra),side).allowed,false,JSON.stringify(extra));
 }
});
test('filtered entries cannot create exits; exits are paired to accepted side and forming bars never enter',()=>{
 const rows=[row('SELL','BEARISH',{entry_qualified:false}),row('SELL EXIT','BEARISH'),row('BUY'),row('SELL EXIT','BEARISH'),row('BUY EXIT','BULLISH',{entry_qualified:false})];
 const audit=chartReplayAudit({settings:config,rows},{blocked:false});
 assert.deepEqual(audit.events.map(e=>e.lifecycle_event),['BUY','BUY EXIT']);
 assert.equal(audit.rejected.length,1);assert.equal(audit.unpairedExits,2);
 assert.ok(audit.events.every(e=>e.event_scope==='SIMULATION'));
 assert.deepEqual(chartHistoricalEvents({settings:config,rows},{blocked:true}),[]);
});
test('an exit can pass when its entry checks are now false, provided an eligible simulated entry exists',()=>{
 const rows=[row('SELL','BEARISH'),row('SELL EXIT','BEARISH',{entry_qualified:false,swing_breakout:null})];
 assert.deepEqual(chartHistoricalEvents({settings:config,rows},{blocked:false}).map(e=>e.lifecycle_event),['SELL','SELL EXIT']);
});
test('all optional selected gates require their own evidence',()=>{
 for(const [flag,key] of [['market_structure_enabled','market_structure'],['higher_timeframe_enabled','mtf_supertrend'],['anti_chop_enabled','anti_chop'],['zone_entry_enabled','zone_entry_filter'],['ema_proximity_enabled','ema_proximity']]){
  assert.equal(strategyEntryCheck({...config,[flag]:true},sig(),'BULLISH').allowed,false,flag);
  assert.equal(strategyEntryCheck({...config,[flag]:true},sig('BULLISH',{[key]:{allowed:true}}),'BULLISH').allowed,true,flag);
 }
});
test('strategy marker settings do not inherit chart-only checkboxes or mutate runner capture',()=>{
 const fields={symbol:'BTCUSD',timeframe:'5 minutes','strategy-basis':'RENKO','ema-third-enabled':true,'ema-third-enabled-indicator':false,'swing-breakout-bricks':2,'ema-family-enabled':true};
 assert.equal(chartEntrySettings(fields,null,'live').ema_third_enabled,true);
 const state={config:{...config,ema_third_enabled:false}},before=JSON.stringify(state);
 assert.equal(chartEntrySettings(fields,state,'runner').ema_third_enabled,false);assert.equal(JSON.stringify(state),before);
 const query=replayQuerySettings({...config,ema_family_enabled:false,line_entry_enabled:true,line_entry_definition:'x',trend_reentry_enabled:false});
 assert.equal(query.ema_family_enabled,undefined);assert.equal(query.line_entry_enabled,undefined);assert.equal(query.trend_reentry_enabled,undefined);
});
test('current failing assessment does not rewrite an earlier qualified signal',()=>{
 const data={settings:config,rows:[row('SELL','BEARISH'),row('SELL EXIT','BEARISH',{entry_qualified:false})],latest:{entry_qualified:false}};
 assert.equal(chartHistoricalEvents(data,{blocked:false}).length,2);
});

test('forming parent observations cannot establish completed strategy entries',()=>{assert.deepEqual(chartHistoricalEvents({settings:config,rows:[{...row('BUY'),is_forming:true}]},{blocked:false}),[]);});

test('ordered live brick simulation confirms at the observed price time without adding a host interval',()=>{
 const data={settings:config,timeframe:'5 minutes',rows:[{...row('BUY'),timestamp:100,confirmation_basis:'ORDERED_LIVE_PRICE',market_event_at:100,brick_events:[{...sig('BULLISH'),timestamp:100,market_event_at:100,lifecycle_event:'BUY',lifecycle_event_at:400}]}]};
 assert.equal(chartHistoricalEvents(data,{blocked:false})[0].lifecycle_event_at,100);
});

test('disabled re-entry requires a real strategy entry event and never promotes an aligned continuation',()=>{
 const c={...config,trend_reentry_enabled:false};
 assert.equal(chartHistoricalEvents({settings:c,rows:[row('BUY')]},{blocked:false}).length,0);
 assert.equal(chartHistoricalEvents({settings:c,rows:[row('BUY','BULLISH',{entry_direction:'BULLISH'})]},{blocked:false}).length,1);
});
test('actual exits need a filled owned entry or confirmed owned trade history',()=>{
 const exit={is_entry:false,status:'FILLED',lifecycle_id:'t',symbol:'OPTION',underlying_symbol:'BTCUSD',filled_at:901,indicator_snapshot:{indicators:{direction:'BEARISH'}}};
 const s={config:{underlying:'BTCUSD',timeframe:'5 minutes'},order_history:[exit]};
 assert.equal(executionMarkers([],s,'BTCUSD','5 minutes').length,0);
 s.trade_history=[{lifecycle_id:'t',entry_filled:1,contract:'OPTION',direction:'BEARISH'}];
 assert.equal(executionMarkers([],s,'BTCUSD','5 minutes')[0].text,'FILL SELL EXIT');
 s.trade_history[0].entry_filled=0;assert.equal(executionMarkers([],s,'BTCUSD','5 minutes').length,0);
});
