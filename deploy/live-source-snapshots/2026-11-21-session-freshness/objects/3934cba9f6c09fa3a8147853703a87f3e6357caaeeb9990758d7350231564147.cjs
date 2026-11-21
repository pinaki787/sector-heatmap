const test=require('node:test'),assert=require('node:assert/strict');
const {activeRunnerFields,scopedFormFields,universalStrategyDefaults}=require('../renko-supertrend.js');
test('index premium is optional and reset clears it',()=>{
 assert.equal(universalStrategyDefaults({'target-premium':'150'})['target-premium'],'');
});
test('premium stays scoped to FYERS index option setup',()=>{
 const fields={symbol:'NSE:NIFTY50-INDEX','target-premium':'150'};
 assert.equal(scopedFormFields(fields,'FYERS')['target-premium'],'150');
 for(const [broker,symbol] of [['FYERS','NSE:TEST-EQ'],['FYERS','MCX:GOLD26DECFUT'],['DELTA_INDIA','BTCUSD'],['DHAN','NSE:NIFTY50-INDEX']]){
  assert.equal(Object.hasOwn(scopedFormFields(fields,broker,symbol),'target-premium'),false);
 }
});
test('active runner uses captured target and older runs show blank',()=>{
 const fields={symbol:'NSE:NIFTY50-INDEX','target-premium':'200'};
 assert.equal(activeRunnerFields(fields,{running:true,config:{underlying:fields.symbol,broker:'FYERS',target_option_premium:100}})['target-premium'],100);
 assert.equal(activeRunnerFields(fields,{running:true,config:{underlying:fields.symbol,broker:'FYERS'}})['target-premium'],'');
});
