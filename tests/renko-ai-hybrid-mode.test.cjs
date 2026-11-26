
const test=require('node:test'),assert=require('node:assert/strict');
const {configuration,capturedStrategyRules}=require('../renko-ai-options.js');
const f={underlying:'NSE:NIFTY50-INDEX',timeframe:'1 minute',lots:1,execution:'PAPER',product:'MARGIN'};
test('new launches use hybrid while explicitly captured old decisions remain candle-only',()=>{
 assert.equal(configuration(f,{id:'owner',broker:'FYERS'}).ai_calculation_mode,'HYBRID');
 assert.equal(configuration({...f,decisionMode:'CANDLES'},{id:'owner',broker:'FYERS'}).ai_calculation_mode,'CANDLES');
});
test('rules never label an old candle worker as hybrid',()=>{
 const s={run_id:'test',underlying:f.underlying,running:true,supertrend_enabled:true,heartbeat:{moving_bands:{bands:[]}}};
 assert.match(capturedStrategyRules({...s,calculation_mode:'HYBRID'},f.underlying).lines.join(' '),/Partial units never qualify/);
 assert.match(capturedStrategyRules({...s,calculation_mode:'CANDLES'},f.underlying).lines.join(' '),/candle-only captured run/);
});
