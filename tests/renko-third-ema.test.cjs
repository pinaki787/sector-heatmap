const {test}=require('node:test');const assert=require('node:assert/strict');
const api=require('../renko-supertrend.js');
test('third EMA defaults, explicit false and independent chart choices',()=>{
 const d=api.signalSettings({});assert.equal(d.ema_third_enabled,true);assert.equal(d.ema_third_length,100);
 const x=api.signalSettings({'ema-third-enabled':false,'ema-third-length':77});assert.equal(x.ema_third_enabled,false);assert.equal(x.ema_third_length,77);
 assert.equal(api.chartSettings({'ema-third-enabled':true,'ema-third-enabled-indicator':false}).ema_third_enabled,false);
 assert.equal(api.chartSettings({'ema-family-enabled':false,'ema-third-enabled':true}).ema_third_enabled,false);
});
test('legacy named config gets new default without inheriting another draft or changing existing choices',()=>{
 const current={'ema-third-enabled':false,'ema-third-length':77,mode:'PAPER'};
 const legacy={symbol:'NSE:NIFTY50-INDEX',settings:{'ema-fast-enabled':false,'ema-slow-length':45,mode:'LIVE'}};
 const restored=api.restoredConfigurationFields(current,legacy);
 assert.equal(restored['ema-third-enabled'],true);assert.equal(restored['ema-third-length'],100);assert.equal(restored['ema-fast-enabled'],false);assert.equal(restored['ema-slow-length'],45);assert.equal(restored.mode,'PAPER');assert.equal(legacy.settings['ema-third-enabled'],undefined);
});
test('old runtime cannot silently accept enabled third EMA',()=>{
 assert.throws(()=>api.requireRsiHtfSupport({ema_third_enabled:true},{}),/Third EMA activation/);
 assert.doesNotThrow(()=>api.requireRsiHtfSupport({ema_third_enabled:false},{}));
 assert.doesNotThrow(()=>api.requireRsiHtfSupport({ema_third_enabled:true},{ema_third_revision:'third-ema-entry-v1'}));
});
