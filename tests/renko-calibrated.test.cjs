const test=require('node:test'),assert=require('node:assert/strict');
const {signalSettings,chartSettings,requireRsiHtfSupport,configurationText}=require('../renko-supertrend.js');
const fields={symbol:'NSE:NIFTY50-INDEX',timeframe:'5 minutes','calibrated-enabled':true,'calibrated-overlap-pairs':6,'calibrated-overlap-max':.4,'calibrated-stop-atr':3,'calibrated-target-atr':1.5};
test('calibrated settings reach chart and strategy payload without changing core indicators',()=>{
 for(const c of [signalSettings(fields),chartSettings(fields)]){
  assert.equal(c.calibrated_enabled,true);assert.equal(c.calibrated_overlap_pairs,6);assert.equal(c.calibrated_overlap_max,.4);assert.equal(c.calibrated_stop_atr,3);assert.equal(c.calibrated_target_atr,1.5);
 }
 assert.equal(signalSettings({...fields,'calibrated-enabled':false}).calibrated_enabled,false);
});
test('unsupported chart scopes retain baseline rather than enabling a research gate',()=>{
 assert.equal(signalSettings({...fields,symbol:'NSE:TEST-EQ'}).calibrated_enabled,false);
 assert.equal(signalSettings({...fields,timeframe:'1 minute'}).calibrated_enabled,false);
});
test('old backend cannot silently ignore an enabled calibrated setup',()=>{
 assert.throws(()=>requireRsiHtfSupport({calibrated_enabled:true},{}),/activation required/);
 assert.doesNotThrow(()=>requireRsiHtfSupport({calibrated_enabled:true},{calibrated_profile_revision:'overlap-atr-profile-v1'}));
 assert.doesNotThrow(()=>requireRsiHtfSupport({calibrated_enabled:false},{}));
});
test('configuration export preserves calibrated levels as ATR multiples rather than absolute prices',()=>{
 const c=signalSettings(fields);
 const out=configurationText({broker:'FYERS',instance:'test',fields:Object.entries(fields).map(([id,value])=>({id,label:id,value})),requested:c,active:c,now:'2026-10-26T00:00:00Z'});
 assert.match(out.text,/calibrated_stop_atr/);assert.match(out.text,/calibrated_target_atr/);
});
