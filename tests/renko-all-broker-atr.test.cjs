const {test}=require('node:test');const assert=require('node:assert/strict');
const {migrateAtrProfile,signalSettings}=require('../renko-supertrend.js');
test('legacy saved instruments migrate across all market/broker selections without mode change',()=>{
 for(const [broker,symbol] of [['FYERS','NSE:NIFTY50-INDEX'],['DHAN','NSE:SUNTV-EQ'],['MOTILAL_OSWAL','MCX:CRUDEOILM26NOVFUT'],['DELTA_INDIA','BTCUSD']]){
  const old={broker,symbol,mode:'PAPER','intrabar-entries':true,'ema-momentum-enabled':false,'ema-proximity-mode':'POINTS'};
  const next=migrateAtrProfile(old),payload=signalSettings(next);
  assert.equal(payload.ema_momentum_enabled,true);assert.equal(payload.ema_proximity_mode,'ATR');assert.equal(payload.ema_proximity_distance,.5);assert.equal(payload.intrabar_entries,false);
  assert.equal(next.symbol,symbol);assert.equal(next.mode,'PAPER');assert.equal(old['intrabar-entries'],true);
  next['ema-momentum-enabled']=false;assert.equal(migrateAtrProfile(next)['ema-momentum-enabled'],false);
 }
});
