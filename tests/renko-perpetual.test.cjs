const {test}=require('node:test'),assert=require('node:assert/strict');
const {ownedEntryPrice,restoredConfigurationFields,configurationText}=require('../renko-supertrend.js');
test('perpetual chart entry line uses the actual signed-position fill',()=>{
  const s={config:{underlying:'PAXGUSD',execution_route:'DELTA_PERPETUAL'},position:{quantity:100,entry_price:4100,direction:'BEARISH'}};
  assert.deepEqual(ownedEntryPrice(s,'PAXGUSD'),{price:4100,title:'SELL entry',basis:'Confirmed fill'});
  assert.equal(ownedEntryPrice({...s,position:null},'PAXGUSD'),null);
  assert.equal(ownedEntryPrice(s,'BTCUSD'),null);
});
test('loading a legacy options configuration never retains a futures selection',()=>{
  const current={mode:'PAPER','delta-execution-route':'DELTA_PERPETUAL'};
  assert.equal(restoredConfigurationFields(current,{symbol:'BTCUSD',settings:{mode:'LIVE'}})['delta-execution-route'],'OPTIONS');
  const result=restoredConfigurationFields(current,{symbol:'PAXGUSD',settings:{mode:'LIVE','delta-execution-route':'DELTA_PERPETUAL'}});
  assert.equal(result['delta-execution-route'],'DELTA_PERPETUAL');assert.equal(result.mode,'PAPER');
});
test('export preserves distinct draft and active trade products',()=>{
  const result=configurationText({broker:'DELTA_INDIA',instance:'default',fields:[],requested:{execution_route:'DELTA_PERPETUAL',underlying:'PAXGUSD'},active:{execution_route:'OPTIONS',underlying:'BTCUSD'},now:'2026-10-09T00:00:00Z'});
  const data=JSON.parse(result.text.split('Serialized configuration (text JSON):\n')[1]);
  assert.equal(data.requested_start_configuration.execution_route,'DELTA_PERPETUAL');
  assert.equal(data.active_runner_configuration.execution_route,'OPTIONS');
});
