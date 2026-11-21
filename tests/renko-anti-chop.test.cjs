const {test}=require('node:test'),assert=require('node:assert/strict');
const r=require('../renko-supertrend.js'),{assessment}=require('../renko-assessment.js');
test('anti-chop settings remain optional and retain zero thresholds',()=>{
 assert.equal(r.antiChopSettings({}).anti_chop_enabled,false);
 const c=r.antiChopSettings({'anti-chop-enabled':true,'anti-chop-overlap-percent':0,'anti-chop-gap-atr':0});assert.equal(c.anti_chop_enabled,true);assert.equal(c.anti_chop_overlap_percent,0);assert.equal(c.anti_chop_gap_atr,0);assert.equal(c.anti_chop_slope_bars,3);
});
test('unactivated backend cannot silently accept enabled filter',()=>{
 assert.throws(()=>r.requireRsiHtfSupport({anti_chop_enabled:true},{}),/activation/);
 assert.equal(r.requireRsiHtfSupport({anti_chop_enabled:true},{anti_chop_revision:'host-timeframe-anti-chop-v4-combination'}).anti_chop_enabled,true);
});
test('only selected anti-chop checks appear in entry assessment',()=>{
 const s={running:true,run_id:'x',updated_at:1804,stream:{connected:true},config:{underlying:'BTCUSD',timeframe:'1 minute',mode:'PAPER',anti_chop_enabled:true,ema_fast_enabled:false,ema_slow_enabled:false,ema_third_enabled:false,ema_widening_enabled:false},last_signal:{timestamp:1740,direction:'BULLISH',anti_chop:{allowed:false,checks:[{label:'ATR14 above average',passed:false,observed:10,reference:12}]}}};
 const view={symbol:'BTCUSD',timeframe:'1 minute'};assert.ok(assessment(s,view,1805).checks.some(x=>x.includes('WAIT · Anti-chop')));
 s.config.anti_chop_enabled=false;assert.ok(!assessment(s,view,1805).checks.some(x=>x.includes('Anti-chop')));
});

test('standalone role survives UI serialization',()=>{assert.equal(r.antiChopSettings({'anti-chop-role':'Entry'}).anti_chop_role,'Entry');assert.equal(r.antiChopSettings({}).anti_chop_role,'Filter');});

test('confirmation rule persists and defaults to all four',()=>{assert.equal(r.antiChopSettings({}).anti_chop_combination,'All');assert.equal(r.antiChopSettings({'anti-chop-combination':'Trend'}).anti_chop_combination,'Trend');});

test('alternative supports are informational while combined confirmation gates',()=>{
 const s={running:true,run_id:'x',updated_at:1804,stream:{connected:true},config:{underlying:'BTCUSD',timeframe:'1 minute',mode:'PAPER',anti_chop_enabled:true,anti_chop_combination:'Trend',ema_fast_enabled:false,ema_slow_enabled:false,ema_third_enabled:false,ema_widening_enabled:false},last_signal:{timestamp:1740,direction:'BULLISH',anti_chop:{allowed:true,checks:[{label:'ATR',passed:false,mandatory:false},{label:'Either ATR or candle structure',passed:true,mandatory:true}]}}};
 const checks=assessment(s,{symbol:'BTCUSD',timeframe:'1 minute'},1805).checks;
 assert.ok(checks.some(x=>x.startsWith('INFO · Anti-chop: ATR')));
 assert.ok(checks.some(x=>x.startsWith('PASS · Anti-chop: Either')));
 assert.ok(!checks.some(x=>x.startsWith('WAIT · Anti-chop: ATR')));
});
