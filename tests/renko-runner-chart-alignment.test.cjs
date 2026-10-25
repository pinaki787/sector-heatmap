const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const path=process.env.RENKO_CANDIDATE||require('node:path').resolve('renko-supertrend.js');
const {runnerChartContext,runnerChartAlignment}=require(path);
const fields={symbol:'MCX:NATGASMINI26OCTFUT',timeframe:'5 minutes','brick-mode':'Manual','manual-brick':'0.48','atr-length':'5',factor:'3','ema-fast-length':'10','ema-slow-length':'30','rsi-length':'14','supertrend-enabled':true,'rsi-level-enabled':true,'higher-timeframe-enabled':true,'supertrend-timeframe':'15 minutes'};
const anchor=Date.parse('2026-09-04T03:30:00Z')/1000,now=Date.parse('2026-10-19T13:00:00Z');
const signal={timestamp:1792415400,direction:'BULLISH',supertrend:289.5,ema10:299.2289627056509,ema30:299.4828591570019};
const state={run_id:'fixture',running:true,config:{underlying:fields.symbol,timeframe:'5 minutes',brick_mode:'Manual',manual_brick:11.62,atr_length:5,factor:3,ema_fast_length:10,ema_slow_length:30,rsi_slope_length:14,supertrend_enabled:true,rsi_level_enabled:true,higher_timeframe_enabled:true,supertrend_timeframe:'15 minutes'},initialization_anchor:anchor,last_signal:signal};
test('active chart binds actual Start parameters and anchor without changing state or draft',()=>{
 const original=JSON.stringify([fields,state]),c=runnerChartContext(fields,state,false,now);
 assert.equal(c.basis,'active');assert.equal(c.settings.manual_brick,11.62);assert.equal(c.settings.rsi_level_enabled,true);
 assert.equal(c.history.history_from,'2026-09-11');assert.equal(c.history.history_to,'2026-10-19');assert.equal(c.history.history_preset,'custom');assert.ok(c.differences.includes('manual_brick'));assert.equal(JSON.stringify([fields,state]),original);
});
test('draft preview is explicit and never claims runner parity',()=>{
 const c=runnerChartContext(fields,state,true,now);assert.equal(c.basis,'draft');assert.equal(c.settings.manual_brick,.48);assert.deepEqual(c.history,{});
 assert.equal(runnerChartAlignment(c,state,{}).verified,false);
});
test('stopped runner and foreign selection use independent live form chart',()=>{
 assert.equal(runnerChartContext(fields,{...state,running:false},false,now).basis,'draft');
 assert.equal(runnerChartContext({...fields,symbol:'NSE:NIFTY50-INDEX'},state,false,now).basis,'draft');
});
test('same settings are not sufficient: anchor, direction and indicator values must agree',()=>{
 const c=runnerChartContext(fields,state,false,now),data={initialization_anchor:anchor,rows:[{...signal}]};
 assert.equal(runnerChartAlignment(c,state,data).verified,true);
 assert.equal(runnerChartAlignment(c,state,{...data,initialization_anchor:anchor-300}).blocked,true);
 for(const key of ['supertrend','ema10','ema30'])assert.equal(runnerChartAlignment(c,state,{...data,rows:[{...signal,[key]:signal[key]+.5}]}).blocked,true);
 assert.equal(runnerChartAlignment(c,state,{...data,rows:[{...signal,direction:'BEARISH'}]}).blocked,true);
 assert.equal(runnerChartAlignment(c,{...state,run_id:'different'},data).blocked,true);
 assert.equal(runnerChartAlignment(c,state,{...data,rows:[]}).blocked,true);
});


test('selected timeframe and new instrument render without runner ownership',()=>{
 assert.equal(runnerChartContext({...fields,timeframe:'15 minutes'},state,false,now).basis,'draft');
 assert.equal(runnerChartContext(fields,null,false,now).basis,'draft');
 const stopped=runnerChartContext(fields,{...state,running:false},false,now);
 assert.equal(stopped.settings.manual_brick,.48);assert.equal(stopped.settings.confirmed_run_id,undefined);
 const active=runnerChartContext(fields,{...state,initialization_anchor:null,confirmed_feed_revision:'shared-confirmed-live-v1'},false,now);
 assert.equal(active.error,null);assert.deepEqual(active.history,{});
});
