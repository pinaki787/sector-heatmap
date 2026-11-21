const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {universalStrategyDefaults,signalSettings,provisionalRenkoBricks,chartCandles}=require('../renko-supertrend.js');
test('universal reset clears optional gates, chooses Simple Brick Only with indicator gates off, and defaults to Live',()=>{
 for(const symbol of ['NSE:NIFTY50-INDEX','MCX:CRUDEOIL26OCTFUT','BTCUSD']){
 const original={symbol,timeframe:'1 minute','anti-chop-enabled':true,'calibrated-enabled':true,'manual-trend-enabled':true,'higher-timeframe-enabled':true,'ema-third-enabled':true,'rsi-slope-enabled':true,'use-adx':true,mode:'LIVE'};
 const d=universalStrategyDefaults(original);assert.equal(original.mode,'LIVE');assert.equal(d.symbol,symbol);assert.equal(d.timeframe,'1 minute');assert.equal(d.mode,'LIVE');assert.equal(d['max-trades'],5);assert.equal(d['strategy-basis'],'RENKO');assert.equal(d['ema-exit-length'],100);
 for(const k of ['anti-chop-enabled','calibrated-enabled','manual-trend-enabled','higher-timeframe-enabled','rsi-slope-enabled','use-adx'])assert.equal(d[k],false,k);
 assert.equal(d['strategy-mode'],'SIMPLE_BRICK');assert.equal(d['supertrend-enabled'],false);assert.equal(d['ema-fast-enabled'],false);assert.equal(d['renko-brick-exit-enabled'],true);assert.equal(d['brick-mode'],'Auto');assert.equal(d['ema-family-enabled'],false);assert.equal(d['ema-slow-enabled'],false);assert.equal(d['ema-slow-length'],30);
 }});
test('basis and brick exit flow through settings; EMA10/30 both selectable',()=>{
 for(const basis of ['RENKO','CANDLESTICK'])for(const period of [10,30]){const s=signalSettings({...universalStrategyDefaults(),'strategy-basis':basis,'ema-exit-length':period});assert.equal(s.strategy_basis,basis);assert.equal(s.ema_exit_length,period);assert.equal(s.higher_timeframe_enabled,false);}
});
test('forming previews show both directions, never mutate confirmed bricks, and are explicitly provisional',()=>{
 const bricks=[{source_timestamp:100,time:100.5,open:100,close:110,box:10}],copy=JSON.stringify(bricks);
 for(const close of [115,95]){const p=provisionalRenkoBricks(bricks,{timestamp:160,close},10);assert.ok(p.length);assert.ok(p.every(b=>b.provisional));assert.equal(Math.sign(p[0].close-p[0].open),Math.sign(close-110));}
 assert.equal(JSON.stringify(bricks),copy);assert.deepEqual(provisionalRenkoBricks(bricks,{timestamp:100,close:200},10),[]);
});
test('Renko chart uses the actual engine bricks; candles preserve real host OHLC',()=>{
 const row={timestamp:100,host_open:99,host_high:138,host_low:95,host_close:135,open:120,high:130,low:120,close:130,brick_events:[{open:100,high:110,low:100,close:110,box:10},{open:110,high:120,low:110,close:120,box:10}]};
 const data={rows:[row],settings:{strategy_basis:'RENKO'},data_quality:{valid:true}};
 assert.equal(chartCandles(data,'synthetic').length,2);assert.equal(chartCandles(data,'host')[0].high,138);
});
test('reset refuses active exposure and does not start a runner',()=>{
 const s=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8'),a=s.indexOf('    resetSettingsButton.onclick='),b=s.indexOf("    el('strategy-basis').addEventListener",a),body=s.slice(a,b);
 assert.match(body,/lastRunner\?\.running\|\|lastRunner\?\.position\|\|lastRunner\?\.pending/);assert.match(body,/persistDraft/);assert.doesNotMatch(body,/request\(['"](?:start|resume|stop)/);
});

test('forming brick fill follows live price and accounts for two-box reversals',()=>{
 const bricks=[{source_timestamp:100,open:100,close:110,box:10}];
 const a=provisionalRenkoBricks(bricks,{timestamp:160,close:112.5},10)[0],b=provisionalRenkoBricks(bricks,{timestamp:160,close:117.5},10)[0];
 assert.equal(a.progress,.25);assert.equal(b.progress,.75);assert.equal(a.close,b.close);assert.equal(a.fillClose,112.5);assert.equal(b.fillClose,117.5);
 const reverse=provisionalRenkoBricks(bricks,{timestamp:160,close:105},10)[0];assert.equal(reverse.progress,.25);
 const multi=provisionalRenkoBricks(bricks,{timestamp:160,close:135},10);assert.equal(multi.length,3);assert.deepEqual(multi.map(b=>b.progress),[1,1,.5]);
});

test('saved server/local drafts are not overwritten by an older named configuration on reload',()=>{
 const s=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 assert.match(s,/if\(!remote.saved_at&&!local&&JSON.stringify\(values\(\)\)===initialConfigurationSignature\)matchInstrumentConfiguration\(\)/);
 assert.match(s,/if\(!record.settings\['strategy-basis'\]\)fields\['strategy-basis'\]='LEGACY'/);
});

test('confirmed brick inspection uses current draft settings when an old runner is stopped',()=>{
 const {candleInspection}=require('../renko-supertrend.js');
 const current={underlying:'MCX:TEST',timeframe:'5 minutes',strategy_basis:'RENKO',brick_mode:'Auto',atr_length:5,factor:3,supertrend_enabled:true,ema_fast_enabled:true,ema_slow_enabled:false,ema_third_enabled:false,ema_widening_enabled:false,rsi_slope_enabled:false};
 const state={running:false,config:{...current,brick_mode:'Manual',manual_brick:11.71,ema_third_enabled:true}};
 const result=candleInspection({time:100.25,symbol:'MCX:TEST',timeframe:'5 minutes',settings:current,state,rows:[{timestamp:100,brick_events:[{timestamp:100.25,close:9673,box:17,supertrend:9711.5,direction:'BEARISH',ema10:9675.63}]}]});
 assert.equal(result.configSource,'Chart settings');assert.equal(result.checks.find(c=>c.name==='Renko / ST direction').status,'PASS');assert.ok(!result.checks.some(c=>c.name==='Third EMA'));
});
