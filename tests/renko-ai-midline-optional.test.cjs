const test=require('node:test'),assert=require('node:assert/strict');
const {configuration,capturedStrategyRules,writeInstrumentSettings,readInstrumentSettings}=require('../renko-ai-options.js');
const fields={underlying:'BTCUSD',timeframe:'5 minutes',lots:100,execution:'PAPER',route:'DIRECT',calculationMode:'RENKO'};
const account={id:'a'.repeat(32),broker:'DELTA_INDIA'};
test('Midline entry filter defaults off and can be disabled independently of Supertrend',()=>{
 assert.equal(configuration(fields,account).ai_midline_filter_enabled,false);
 assert.equal(configuration({...fields,calculationMode:'CANDLES',chartView:'Candles',midlineEnabled:true},account).ai_midline_filter_enabled,true);
 assert.equal(configuration({...fields,midlineFilter:true},account).ai_midline_filter_enabled,false);
 const off=configuration({...fields,midlineEnabled:false},account);
 assert.equal(off.ai_midline_filter_enabled,false);assert.equal(off.ai_supertrend_enabled,true);
 assert.deepEqual(off.ai_indicator_inputs,{length:1,factor:2.1,adx_enabled:false});
 assert.equal(configuration({...fields,midlineEnabled:true,supertrend:false},account).ai_midline_filter_enabled,false);
});
test('Midline preference persists with the exact account and instrument',()=>{
 const values=new Map(),storage={getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)};
 writeInstrumentSettings(storage,'owner',account,{...fields,midlineEnabled:false});
 assert.equal(readInstrumentSettings(storage,'owner',account,'BTCUSD').midlineEnabled,false);
 assert.equal(readInstrumentSettings(storage,'owner',account,'PAXGUSD'),null);
});
test('captured rule summary explicitly distinguishes filter on and off',()=>{
 const base={running:true,run_id:'run',underlying:'BTCUSD',supertrend_enabled:true,heartbeat:{moving_bands:{bands:[]}}};
 assert.match(capturedStrategyRules({...base,midline_filter_enabled:false},'BTCUSD').lines.join(' '),/Midline entry filter: Off/);
 assert.match(capturedStrategyRules({...base,midline_filter_enabled:true},'BTCUSD').lines.join(' '),/latest buy signal/);
});

test('Midline entry filter is available only for actual candlestick selection',()=>{
 const {midlineFilterAvailable}=require('../renko-ai-options.js');
 for(const chartView of ['Candles','Renko','Heikin Ashi','Line']){
 const selected={...fields,calculationMode:chartView==='Renko'?'RENKO':'CANDLES',chartView,midlineEnabled:true};
 assert.equal(midlineFilterAvailable(selected),chartView==='Candles');
 assert.equal(configuration(selected,account).ai_midline_filter_enabled,chartView==='Candles');
 }
});

test('candlestick filter defaults on, respects explicit off, Renko always off',()=>{
 const {midlineFilterDefault}=require('../renko-ai-options.js');
 assert.equal(midlineFilterDefault({chartView:'Candles'}),true);
 assert.equal(midlineFilterDefault({chartView:'Candles'},false),false);
 assert.equal(midlineFilterDefault({chartView:'Candles'},true),true);
 assert.equal(midlineFilterDefault({chartView:'Renko'},true),false);
 assert.equal(midlineFilterDefault({chartView:'Renko'}),false);
 // Switching away does not erase the saved explicit candlestick preference.
 const saved=false;
 assert.equal(midlineFilterDefault({chartView:'Renko'},saved),false);
 assert.equal(midlineFilterDefault({chartView:'Candles'},saved),false);
});
