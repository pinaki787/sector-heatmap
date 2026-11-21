const {test}=require('node:test'),assert=require('node:assert/strict');
const {testedNiftyDefaults,signalSettings,chartSettings,requireRsiHtfSupport}=require('../renko-supertrend.js');
test('tested defaults preserve execution choice, quantity, budgets and capital',()=>{
 const old={symbol:'NSE:NIFTY50-INDEX',timeframe:'5 minutes',mode:'LIVE',lots:'3','max-trades':'2','paper-capital':'250000','daily-budget':'800','max-premium':'3000'};
 const next=testedNiftyDefaults(old);
 for(const id of ['mode','lots','max-trades','paper-capital','daily-budget','max-premium'])assert.equal(next[id],old[id]);
 const c=signalSettings(next);assert.equal(c.zone_entry_enabled,true);assert.equal(c.zone_entry_min_atr,1);assert.equal(c.zone_entry_rearm,true);assert.equal(c.zone_target_enabled,true);
 assert.equal(c.calibrated_stop_atr,3);assert.equal(c.calibrated_target_atr,1.5);
});
test('irrelevant gates and HTF chart overlay are off, core entry rules retained',()=>{
 const f=testedNiftyDefaults({symbol:'NSE:NIFTY50-INDEX',timeframe:'5 minutes','higher-timeframe-enabled-indicator':true});
 for(const id of ['use-adx','adx-family-enabled','higher-timeframe-enabled','higher-timeframe-enabled-indicator','manual-trend-enabled','trailing-enabled','market-structure-enabled','rsi-level-enabled','rsi-htf-1-enabled','rsi-htf-2-enabled','rsi-htf-3-enabled'])assert.equal(f[id],false,id);
 for(const id of ['supertrend-enabled','ema-fast-enabled','ema-slow-enabled','ema-third-enabled','ema-widening-enabled','rsi-slope-enabled','retest-enabled','ema-exit-enabled','zone-target-enabled'])assert.equal(f[id],true,id);
 assert.equal(chartSettings(f).higher_timeframe_enabled,false);
});
test('scope and capability guard cannot silently use an old backend',()=>{
 assert.throws(()=>testedNiftyDefaults({symbol:'BTCUSD',timeframe:'1 minute'}),/NIFTY/);
 assert.throws(()=>requireRsiHtfSupport({zone_entry_enabled:true},{}),/activation required/);
 assert.doesNotThrow(()=>requireRsiHtfSupport({zone_entry_enabled:true},{zone_entry_revision:'opposing-zone-entry-v1'}));
 const f=testedNiftyDefaults({symbol:'NSE:NIFTY50-INDEX',timeframe:'5 minutes'});
 assert.equal(signalSettings({...f,symbol:'BTCUSD'}).zone_entry_enabled,false);
 assert.equal(signalSettings({...f,'calibrated-enabled':false}).zone_entry_enabled,false);
});

test('tested fixed brick replaces a stale automatic reference at Start',()=>{
 const f=testedNiftyDefaults({symbol:'NSE:NIFTY50-INDEX',timeframe:'5 minutes','manual-brick-reference':JSON.stringify({symbol:'NSE:NIFTY50-INDEX',manual_brick:27.66,rule:{atr_length:5}})});
 const reference=JSON.parse(f['manual-brick-reference']);
 assert.equal(reference.manual_brick,27.71);assert.equal(reference.user_override,true);assert.equal(f['manual-brick'],27.71);
});
