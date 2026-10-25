const {test}=require('node:test');
const assert=require('node:assert/strict');
const {signalSettings,requireRsiHtfSupport,entryDecisionText}=require('../renko-supertrend.js');
test('explicit opt in and runtime capability required before Start',()=>{
  assert.equal(signalSettings({}).ema_momentum_enabled,false);
  const config=signalSettings({'ema-momentum-enabled':true});
  assert.equal(config.ema_momentum_enabled,true);
  assert.throws(()=>requireRsiHtfSupport(config,{ema_third_revision:'third-ema-entry-v1'}),/activation required/);
  assert.equal(requireRsiHtfSupport(config,{entry_momentum_revision:'split-proximity-momentum-v1',entry_atr_policy_revision:'all-broker-flexible-atr-v1',ema_third_revision:'third-ema-entry-v1'}),config);
});
test('blocked execution label is scoped to matching run candle and symbol',()=>{
  const sig={timestamp:100,entry_qualified:true,entry_diagnostic:'QUALIFIED'};
  const state={run_id:'run',config:{underlying:'NIFTY'},execution_signals:[{run_id:'run',timestamp:100,underlying:'NIFTY',status:'BLOCKED',reason:'EMA distance'}]};
  assert.match(entryDecisionText(sig,state,'NIFTY'),/execution blocked: EMA distance/);
  assert.equal(entryDecisionText({...sig,timestamp:101},state,'NIFTY'),'QUALIFIED');
  assert.equal(entryDecisionText(sig,state,'CRUDE'),'QUALIFIED');
  assert.equal(entryDecisionText(sig,{...state,run_id:'other'},'NIFTY'),'QUALIFIED');
});
