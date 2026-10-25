const test=require('node:test'),assert=require('node:assert/strict');
const {rsiHtfSettings,rsiHtfSummary,signalSettings,chartSettings,requireRsiHtfSupport,configurationText}=require('../renko-supertrend.js');
test('three slots default off and retain independent periods and shared levels in start/chart/export',()=>{
 const defaults=rsiHtfSettings({});assert.equal(defaults.rsi_htf_1_enabled,false);assert.equal(defaults.rsi_htf_2_enabled,false);assert.equal(defaults.rsi_htf_3_enabled,false);
 const fields={'rsi-htf-1-enabled':true,'rsi-htf-1-timeframe':'5 minutes','rsi-htf-2-enabled':false,'rsi-htf-2-timeframe':'30 minutes','rsi-htf-3-enabled':true,'rsi-htf-3-timeframe':'1 hour','rsi-level-mode':'BETWEEN','rsi-bullish-min':61,'rsi-bullish-max':79,'rsi-bearish-min':31,'rsi-bearish-max':39,'rsi-length':10};
 const start=signalSettings(fields),chart=chartSettings(fields);
 for(const config of [start,chart]){assert.equal(config.rsi_htf_1_enabled,true);assert.equal(config.rsi_htf_2_enabled,false);assert.equal(config.rsi_htf_2_timeframe,'30 minutes');assert.equal(config.rsi_htf_3_enabled,true);assert.equal(config.rsi_bullish_min,61);assert.equal(config.rsi_bearish_max,39);assert.equal(config.rsi_slope_length,10);}
 const exported=configurationText({broker:'FYERS',instance:'default',fields:Object.entries(fields).map(([id,value])=>({id,label:id,value})),requested:start,active:start,now:'2026-10-18T00:00:00Z'});
 assert.match(exported.text,/rsi_htf_1_enabled/);assert.match(exported.text,/rsi_htf_3_timeframe/);
 const disabled=rsiHtfSettings({...fields,'rsi-family-enabled':false});assert.equal(disabled.rsi_htf_1_enabled,false);assert.equal(disabled.rsi_htf_3_enabled,false);assert.equal(fields['rsi-htf-1-enabled'],true);
});
test('new enabled gate cannot be silently ignored by an older backend',()=>{
 const config={rsi_htf_2_enabled:true};assert.throws(()=>requireRsiHtfSupport(config,{}),/backend update required/);
 assert.equal(requireRsiHtfSupport(config,{mtf_rsi_revision:'optional-three-htf-rsi-v2'}),config);
 assert.doesNotThrow(()=>requireRsiHtfSupport({},{}));
});
test('status distinguishes stale and unavailable from confirmed as-of evidence',()=>{
 const summary=rsiHtfSummary({enabled:true,observed_at:10000,slots:[{slot:1,timeframe:'15 minutes',rsi:66.5,reason:'PASS',closed_at:9900,fresh:true},{slot:2,timeframe:'30 minutes',rsi:null,reason:'MISSING_OR_STALE',closed_at:null,fresh:false}]});
 assert.match(summary,/66.50/);assert.match(summary,/fresh at assessment/);assert.match(summary,/Unavailable/);assert.match(summary,/missing or stale/);
});

test('slot levels inherit once, persist separately, and export independently',()=>{
 const {inheritRsiHtfFields,restoredConfigurationFields}=require('../renko-supertrend.js');
 const fields={'rsi-level-mode':'BETWEEN','rsi-bullish-min':60,'rsi-bullish-max':80,'rsi-bearish-min':35,'rsi-bearish-max':40};
 const inherited=inheritRsiHtfFields(fields);assert.equal(inherited['rsi-htf-1-bullish-min'],60);
 inherited['rsi-htf-2-bullish-min']=65;inherited['rsi-bullish-min']=55;
 const c=rsiHtfSettings(inherited);assert.equal(c.rsi_htf_1_bullish_min,60);assert.equal(c.rsi_htf_2_bullish_min,65);assert.equal(c.rsi_htf_3_bullish_min,60);
 const restored=restoredConfigurationFields(inherited,{symbol:'X',settings:fields});assert.equal(restored['rsi-htf-2-bullish-min'],60);
 const output=configurationText({broker:'FYERS',instance:'default',fields:[],requested:c,active:c,now:'2026-10-18T00:00:00Z'});
 assert.match(output.text,/rsi_htf_2_bullish_min/);
});

test('configuration rejection is distinct from transient feed failures',()=>{
 const {chartSettingsFailure}=require('../renko-supertrend.js');
 assert.equal(chartSettingsFailure({status:400,message:'RSI ranges need minimum below maximum'}),true);
 assert.equal(chartSettingsFailure({status:400,message:'RSI HTF 1 must be higher than the host timeframe.'}),true);
 assert.equal(chartSettingsFailure({status:503,message:'History temporarily unavailable'}),false);
 assert.equal(chartSettingsFailure(new Error('Network disconnected')),false);
});

test('hover bursts use one frame and render only the newest loaded candle',()=>{
 const {coalescedHover}=require('../renko-supertrend.js'),frames=[],rendered=[];
 const update=coalescedHover(value=>rendered.push(value),callback=>frames.push(callback));
 for(let i=0;i<100;i++)update(i);
 assert.equal(frames.length,1);assert.equal(rendered.length,0);frames.shift()();assert.deepEqual(rendered,[99]);
 update(100);assert.equal(frames.length,1);frames.shift()();assert.deepEqual(rendered,[99,100]);
});
