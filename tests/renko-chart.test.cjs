const {test}=require('node:test');
const assert=require('node:assert/strict');
const {chartCandles}=require('../renko-supertrend.js');
const bar={timestamp:1791194100,open:22535.45,high:22555.75,low:22535.45,close:22555.75,synthetic_open:22524.562886,synthetic_close:22551.852324};
test('host candles preserve exact broker wicks, prices and opening timestamp',()=>{
 const d={rows:[{...bar,high:22570.125,low:22520.075}],forming:[{...bar,timestamp:bar.timestamp+300}]};
 assert.deepEqual(chartCandles(d,'host'),d.rows.concat(d.forming).map(c=>({time:c.timestamp,open:c.open,high:c.high,low:c.low,close:c.close})));
});
test('synthetic bodies remain separate and exclude forming host bars',()=>{
 const bars=chartCandles({rows:[bar],forming:[{...bar,timestamp:bar.timestamp+300}]},'synthetic');
 assert.equal(bars.length,1);assert.equal(bars[0].open,bar.synthetic_open);assert.equal(bars[0].close,bar.synthetic_close);assert.equal(bars[0].high,bar.synthetic_close);assert.equal(bars[0].low,bar.synthetic_open);
});
const {toggleState}=require('../renko-supertrend.js');
const {pnlValues}=require('../renko-supertrend.js');
const {executionMarkers}=require('../renko-supertrend.js');
test('research BUY and actual runner BUY have distinct evidence and status',()=>{
 const historical=[{time:1,text:'BUY',position:'belowBar',shape:'arrowUp',color:'green'}];
 const state={config:{underlying:'BSE:SENSEX-INDEX',timeframe:'1 minute'},execution_signals:[{timestamp:2,direction:'BULLISH',mode:'PAPER',status:'BLOCKED'}]};
 const markers=executionMarkers(historical,state,'BSE:SENSEX-INDEX','1 minute');
 assert.equal(markers[0].text,'');assert.equal(markers.length,1);
 state.execution_signals.push({timestamp:3,direction:'BULLISH',mode:'PAPER',status:'FILLED'});
 assert.equal(executionMarkers(historical,state,'BSE:SENSEX-INDEX','1 minute')[1].text,'BUY · PAPER · FILLED');
 assert.equal(executionMarkers(historical,state,'NSE:NIFTY50-INDEX','1 minute').length,1);
});
test('P&L never reports stale or disconnected option marks as live profit',()=>{
 const s={config:{mode:'LIVE'},position:{symbol:'NSE:TESTCE'},pnl:{available:true,unrealized:-40,realized:60}};
 assert.equal(pnlValues(s).total,20);
 assert.equal(pnlValues(s).unrealized,-40);
 assert.equal(pnlValues(s,false).unrealized,null);
 assert.equal(pnlValues(s,false).total,null);
 assert.equal(pnlValues({...s,pnl:{...s.pnl,available:false}}).total,null);
 assert.equal(pnlValues({...s,position:null,pnl:{available:true,unrealized:0,realized:60}}).total,60);
});
test('one toggle waits during requests and draining, restart only once flat',()=>{
 assert.deepEqual(toggleState({running:false,position:null,pending:null}),{label:'Start Runner',disabled:false});
 assert.deepEqual(toggleState({running:true,accepting_entries:true}),{label:'Stop Runner',disabled:false});
 assert.deepEqual(toggleState({running:true,accepting_entries:false,pending:{}}),{label:'Stopping…',disabled:true});
 assert.equal(toggleState({running:false,position:{},accepting_entries:false}).label,'Resume position monitoring');
 assert.equal(toggleState({running:false,shutdown_pending:true}).disabled,true);
 assert.equal(toggleState({},true).disabled,true);
});

const {volumePoints}=require('../renko-supertrend.js');
test('volume preserves host timestamps, zero volume and missing-volume gaps',()=>{
 const data={rows:[{...bar,volume:123},{...bar,timestamp:bar.timestamp+300,close:bar.open-1,volume:0},{...bar,timestamp:bar.timestamp+600,volume:null}],forming:[{...bar,timestamp:bar.timestamp+900,volume:17}]};
 const v=volumePoints(data);assert.deepEqual(v.map(p=>p.time),data.rows.concat(data.forming).map(p=>p.timestamp));
 assert.equal(v[0].value,123);assert.equal(v[1].value,0);assert.notEqual(v[0].color,v[1].color);assert.deepEqual(v[2],{time:bar.timestamp+600});assert.equal(v[3].value,17);
 assert.equal(volumePoints(data,'synthetic').length,3);
});

const {chartAnalysisAvailable,chartStreamStatus,chartStreamHealth}=require('../renko-supertrend.js');
test('invalid history shows exact valid OHLC plus whitespace gaps and suppresses synthetic bodies',()=>{
 const d={rows:[bar,{...bar,timestamp:bar.timestamp+120}],forming:[],data_quality:{analysis_available:false,gaps:[{timestamp:bar.timestamp+60,reason:'invalid OHLC'}]}};
 assert.equal(chartAnalysisAvailable(d),false);
 assert.deepEqual(chartCandles(d,'host'),[{time:bar.timestamp,open:bar.open,high:bar.high,low:bar.low,close:bar.close},{time:bar.timestamp+60},{time:bar.timestamp+120,open:bar.open,high:bar.high,low:bar.low,close:bar.close}]);
 assert.deepEqual(chartCandles(d,'synthetic'),[]);
});
test('chart status reports forming-candle failure separately from broker and runner state',()=>{
 const frame={market:{connected:true,fresh:false,error:'Verified current host candle open unavailable.'},orders:{connected:true},runner:{message:'Underlying stream timestamp is fresh.'}};
 assert.equal(chartStreamStatus(frame),'Chart feed stale / unavailable · Order stream connected · Tick age unknown · Verified current host candle open unavailable.');
 frame.market.fresh=true;frame.market.error=null;frame.server_at=100;frame.market.tick_exchange_at=99;assert.equal(chartStreamStatus(frame),'Chart feed is live · Order stream connected · Tick age 1s');
});

test('actual EMA exit markers use local fill candle and recorded applied period, not current chart lines',()=>{
 const s={config:{underlying:'MCX:TEST',timeframe:'1 minute',mode:'PAPER'},order_history:[{tag:'EXIT1',is_entry:false,filled_at:901,underlying_symbol:'MCX:TEST',status:'FILLED',mode:'PAPER',reason:'EMA10_CONFIRMED_BREACH',submitted_at:900,indicator_snapshot:{settings:{ema_exit_length:10},indicators:{timestamp:600,direction:'BEARISH',ema10:100,ema30:200}}}]};
 const marker=executionMarkers([],s,'MCX:TEST','1 minute')[0];assert.equal(marker.time,900);assert.equal(marker.position,'belowBar');assert.equal(marker.text,'EXIT · PAPER · EMA10 · FILLED');
 s.order_history[0].status='PENDING';assert.deepEqual(executionMarkers([],s,'MCX:TEST','1 minute'),[]);
});

const {overrideState}=require('../renko-supertrend.js');
test('override requires explicit direction and active matching mode, broker, chart and flat run',()=>{
 const context={symbol:'BTCUSD',timeframe:'1 minute',broker:'DELTA_INDIA',mode:'PAPER'};
 const state={manual_override_revision:'explicit-entry-v1',running:true,accepting_entries:true,trades_used:0,config:{underlying:'BTCUSD',timeframe:'1 minute',broker:'DELTA_INDIA',mode:'PAPER',max_trades:3}};
 assert.equal(overrideState(state,context,'').disabled,true);assert.equal(overrideState(state,context,'BULLISH').disabled,false);
 assert.equal(overrideState(state,context,'BEARISH').label,'Override Entry · PAPER');
 for(const changes of [{position:{}},{pending:{}},{running:false},{accepting_entries:false},{manual_override_revision:null},{trades_used:3},{shutdown_pending:true}])assert.equal(overrideState({...state,...changes},context,'BEARISH').disabled,true);
 for(const changes of [{symbol:'ETHUSD'},{timeframe:'5 minutes'},{mode:'LIVE'},{broker:'FYERS'}])assert.equal(overrideState(state,{...context,...changes},'BULLISH').disabled,true);
 assert.equal(overrideState(state,context,'BULLISH',true).disabled,true);
});

test('fresh market feed can disclose delayed runner snapshot without faking tick age',()=>{
 const {chartStreamHealth}=require('../renko-supertrend.js');
 const a=chartStreamHealth({server_at:100,market:{connected:true,fresh:true,tick_exchange_at:98},orders:{connected:true},runner_snapshot_fresh:false},0);
 assert.match(a.text,/Chart feed is live/);assert.match(a.text,/Runner status refresh delayed/);assert.match(a.text,/Tick age 2s/);
 assert.match(chartStreamHealth({server_at:100,market:{connected:true,fresh:true,tick_exchange_at:98},orders:{connected:true}},6).text,/Chart updates stale/);
});

const {readableChartViewport}=require('../renko-supertrend.js');
test('reset viewport keeps candles readable across narrow, wide and tall charts',()=>{
 const small=readableChartViewport(360,360,500),wide=readableChartViewport(1800,620,500),tall=readableChartViewport(1800,1000,500);
 assert.ok(wide.range.to-wide.range.from>small.range.to-small.range.from);
 assert.ok(tall.spacing>wide.spacing);
 assert.ok(small.range.to-small.range.from<35);
 assert.equal(wide.scaleMargins.top+wide.scaleMargins.bottom,.32);
 assert.equal(readableChartViewport(360,360,5).range.from,0);
});

test('live ticks with missing OHLC are distinguished from a disconnected feed',()=>{
 const frame={server_at:100,market:{connected:true,fresh:false,tick_fresh:true,tick_exchange_at:99,error:'Broker forming OHLC unavailable'},orders:{connected:true}};
 assert.match(chartStreamStatus(frame),/Live ticks · current candle OHLC unavailable/);
 assert.equal(chartStreamHealth(frame).live,false);
 assert.equal(chartStreamHealth(frame).tickFresh,true);
 assert.match(chartStreamStatus({...frame,market:{...frame.market,connected:false}}),/disconnected/);
});

test('native REST order checks do not claim a notification connection',()=>{
 for(const basis of ['Delta REST reconciliation; broker order notifications not claimed.','Dhan REST reconciliation; broker order notifications not claimed.','Motilal native orderbook reconciliation; acceptance is not a fill']){
  const frame={server_at:100,market:{connected:true,fresh:true,tick_exchange_at:99},orders:{connected:false,basis},runner:{config:{mode:'LIVE'}}};
  assert.equal(chartStreamHealth(frame).restOrders,true);
  assert.equal(chartStreamHealth(frame).ordersConnected,false);
  assert.doesNotMatch(chartStreamStatus(frame),/unavailable/);
  assert.equal(chartStreamHealth(frame,6).live,false);
 }
 assert.equal(chartStreamHealth({orders:{basis:'Unknown reconciliation'}}).restOrders,false);
});

test('missing chart candle does not claim to block completed-candle decisions',()=>{
 const frame={server_at:100,market:{connected:true,fresh:false,tick_fresh:true,tick_exchange_at:99,error:'Broker forming OHLC unavailable; intrabar entry blocked.'},orders:{connected:true},runner:{config:{intrabar_entries:false}}};
 assert.match(chartStreamStatus(frame),/runner uses confirmed completed candles/);
 assert.doesNotMatch(chartStreamStatus(frame),/intrabar entry blocked/);
 assert.match(chartStreamStatus({...frame,runner:{config:{intrabar_entries:true}}}),/intrabar entry blocked/);
 assert.equal(chartStreamHealth(frame).chartFresh,false);
});


test('fresh native tick price updates even while broker candle OHLC is unavailable',()=>{
 const vm=require('node:vm'),fs=require('node:fs'),source=fs.readFileSync('renko-supertrend.js','utf8');
 const ctx={el:()=>({value:'MCX:TEST'}),lastUnderlyingSymbol:'MCX:TEST',lastUnderlyingPrice:100,underlyingDirection:0,statusFrame:{market:{tick_price:105},forming:null},isDelta:false,underlyingPrice:{style:{}},price:v=>String(v),nativeCashSessionClosed:()=>false};
 vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('    function paintUnderlyingPrice('),source.indexOf('    let statusFrame='))+';globalThis.paint=paintUnderlyingPrice;',ctx);
 ctx.paint({chartFresh:false,tickFresh:true});assert.match(ctx.underlyingPrice.textContent,/105 · Live/);
 ctx.statusFrame.market.tick_price=110;ctx.paint({chartFresh:false,tickFresh:false});assert.match(ctx.underlyingPrice.textContent,/105 · Last known/);
});

test('history refresh follows latest bars and restores price autoscale without moving history review',()=>{
 const source=require('node:fs').readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 const select=source.match(/const previousRange=chart\.timeScale\(\)\.getVisibleLogicalRange\(\);const followLatest=([^;]+);/)[1];
 const apply=source.match(/if\(followLatest\)\{el\('readable-chart'\)\.onclick\(\);\}/)[0];
 const vm=require('node:vm');
 for(const [same,previousRange,expected] of [[false,{from:0,to:65},true],[true,{from:940,to:1002},true],[true,{from:40,to:105},false],[true,null,true]]){
  const calls=[];const context={el:()=>({onclick:()=>calls.push({reset:true})}),same,previousRange,plottedCount:1000,plotted:Array(1100),isMotilal:false,chart:{priceScale:()=>({applyOptions:v=>calls.push(v)}),timeScale:()=>({setVisibleLogicalRange:v=>calls.push(v)})}};
  vm.runInNewContext('const followLatest='+select+';'+apply,context);
  assert.equal(calls.length,expected?1:0);
  if(expected)assert.equal(calls[0].reset,true);
 }
});

test('viewport follows only after overlays and selected indicator series finish updating',()=>{
 const source=require('node:fs').readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 const start=source.indexOf('const previousRange=chart.timeScale()');
 const end=source.indexOf('allEvents=events.slice()',start);
 const render=source.slice(start,end);
 assert.ok(render.indexOf('if(followLatest)')>render.indexOf('paintSelectedIndicators();'));
 assert.ok(render.indexOf('if(followLatest)')>render.indexOf('fiveMinuteLine.setData(fiveMinutePointerPoints)'));
});

test('chart resize repairs latest view only after a visible size exists',()=>{
 const source=require('node:fs').readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 const body=source.match(/new ResizeObserver\(\(\)=>\{const width=el\('chart'\).*?\}\)\.observe\(el\('chart'\)\);/)[0];
 const vm=require('node:vm');
 for(const [width,to,expected] of [[0,1002,0],[800,1002,1],[1600,1002,1],[800,100,0]]){
  let reset=0;const context={plottedCount:1000,el:id=>id==='chart'?{clientWidth:width,clientHeight:600}:{onclick:()=>reset++},chart:{applyOptions:()=>{},timeScale:()=>({getVisibleLogicalRange:()=>({from:to-60,to})})},ResizeObserver:class{constructor(fn){this.fn=fn;}observe(){this.fn();}}};
  vm.runInNewContext(body,context);assert.equal(reset,expected);
 }
});

test('family master locks EMA controls and restores saved choices on re-enable',()=>{
 const source=require('node:fs').readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 const body=source.slice(source.indexOf('    function familyControls(){'),source.indexOf('    const manualReferenceInput='));
 const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,{checked:true,disabled:false,dataset:{},closest(){return {querySelectorAll:()=>[this]};}});return nodes.get(id);};
 const ids=['ema-fast-enabled','ema-slow-enabled','ema-exit-enabled','ema-fast-length'];
 get('ema-slow-enabled').checked=false;get('ema-fast-length').value='10';
 const context={el:get,section:{querySelectorAll:()=>[...nodes.values()].filter(x=>Object.hasOwn(x.dataset,'familyDisabled'))},paintTradingSessionHours:()=>{},lastRunner:{indicator_family_revision:'indicator-family-masters-v1',config:{},running:true},continuationHelp:{},FAMILY_RULES:{ema:ids},familyRows:{ema:ids},exitSectionSync:[],familySettings:()=>({ema_family_enabled:get('ema-family-enabled').checked}),values:()=>({})};
 require('node:vm').runInNewContext(body+';globalThis.run=familyControls;',context);
 get('ema-family-enabled').checked=false;context.run();
 for(const id of ids)assert.equal(get(id).disabled,true);
 assert.equal(get('ema-slow-enabled').checked,false);assert.equal(get('ema-fast-length').value,'10');
 get('ema-family-enabled').checked=true;context.run();
 for(const id of ids)assert.equal(get(id).disabled,false);
 assert.equal(get('ema-slow-enabled').checked,false);
 assert.ok(source.includes('familyControls();'));
});

test('actual Start handler awaits current displayed settings instead of stale child payload',async()=>{
 const source=require('node:fs').readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 const start=source.indexOf('    async function toggleRunner()');const end=source.indexOf("    el('toggle').onclick",start);
 const nodes=new Map();const el=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,textContent:''});return nodes.get(id);};
 const submitted=[];const latest={underlying:'BTCUSD',ema_fast_enabled:false,rsi_level_enabled:false,ema_family_enabled:false};let handoffs=0;
 const context={el,toggleBusy:false,overrideBusy:false,lastRunner:{running:false,indicator_selection_revision:'independent-indicators-v1'},running:false,owned:false,syncChartControl:()=>{},payload:()=>({ema_fast_enabled:true,rsi_level_enabled:true}),selectedStartPayload:async()=>{handoffs++;await Promise.resolve();return latest;},request:async(path,body)=>submitted.push({path,body}),status:async()=>true};
 require('node:vm').runInNewContext(source.slice(start,end)+';globalThis.run=toggleRunner;',context);
 await context.run();assert.equal(handoffs,1);assert.equal(submitted.length,1);assert.equal(submitted[0].path,'start');assert.equal(submitted[0].body,latest);assert.equal(submitted[0].body.ema_fast_enabled,false);assert.equal(submitted[0].body.rsi_level_enabled,false);
 context.lastRunner.running=true;await context.run();assert.equal(handoffs,1);assert.equal(submitted[1].path,'stop');
});

test('restore never forces deselected higher-timeframe or saved strategy switches on',()=>{
 const source=require('node:fs').readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 const restore=source.slice(source.indexOf('    async function restore(){'),source.indexOf('if(isBatchChartView){const compact=',source.indexOf('    async function restore(){')));
 for(const id of ['higher-timeframe-enabled','higher-timeframe-enabled-indicator','sideways-enabled','supertrend-exit-enabled'])assert.ok(!restore.includes("el('"+id+"').checked=true"));
 const {signalSettings,chartSettings}=require('../renko-supertrend.js');
 const fields={'higher-timeframe-enabled':false,'higher-timeframe-enabled-indicator':false,'supertrend-timeframe':'15 minutes'};
 assert.equal(signalSettings(fields).higher_timeframe_enabled,false);assert.equal(chartSettings(fields).higher_timeframe_enabled,false);
});
