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
 assert.equal(toggleState({running:false,position:{},accepting_entries:false}).label,'Stop Runner');
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

const {chartAnalysisAvailable,chartStreamStatus}=require('../renko-supertrend.js');
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
