const test=require('node:test'),assert=require('node:assert/strict');
const {activeRunnerFields,scopedFormFields,universalStrategyDefaults}=require('../renko-supertrend.js');
test('index premium is optional and reset clears it',()=>{
 assert.equal(universalStrategyDefaults({'target-premium':'150'})['target-premium'],'');
});
test('premium stays scoped to supported option setups',()=>{
 const fields={symbol:'NSE:NIFTY50-INDEX','target-premium':'150'};
 assert.equal(scopedFormFields(fields,'FYERS')['target-premium'],'150');
 for(const [broker,symbol] of [['FYERS','NSE:TEST-EQ'],['FYERS','MCX:GOLD26DECFUT'],['DELTA_INDIA','BTCUSD']]){
  assert.equal(Object.hasOwn(scopedFormFields(fields,broker,symbol),'target-premium'),false);
 }
});
test('active runner uses captured target and older runs show blank',()=>{
 const fields={symbol:'NSE:NIFTY50-INDEX','target-premium':'200'};
 assert.equal(activeRunnerFields(fields,{running:true,config:{underlying:fields.symbol,broker:'FYERS',target_option_premium:100}})['target-premium'],100);
 assert.equal(activeRunnerFields(fields,{running:true,config:{underlying:fields.symbol,broker:'FYERS'}})['target-premium'],'');
});

test('native option premium survives instrument-scoped settings',()=>{
 for(const broker of ['DHAN','MOTILAL_OSWAL'])for(const symbol of ['NSE:NIFTY','BSE:SENSEX','MCX:GOLD26DECFUT'])assert.equal(scopedFormFields({'target-premium':'40'},broker,symbol)['target-premium'],'40');
 for(const broker of ['DHAN','MOTILAL_OSWAL'])assert.equal(Object.hasOwn(scopedFormFields({'target-premium':'40',market:'NSE_EQUITY'},broker,'NSE:TEST-EQ'),'target-premium'),false);
});
