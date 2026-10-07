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
