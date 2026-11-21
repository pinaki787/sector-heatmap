const {test}=require('node:test'),assert=require('node:assert/strict');
const {chartSourceContext}=require('../renko-supertrend.js');
for(const broker of ['DELTA_INDIA','FYERS','DHAN','MOTILAL'])for(const mode of ['LIVE','PAPER']){
test(broker+' '+mode+' active chart uses executable recurrence',()=>{
 const fields={symbol:'TEST',timeframe:'5 minutes','manual-brick':10};
 const state={run_id:'run',running:true,confirmed_feed_revision:'shared-confirmed-live-v1',config:{broker,mode,underlying:'TEST',timeframe:'5 minutes',manual_brick:20,renko_confirmation:'PRICE'}};
 const active=chartSourceContext(fields,state,'live');
 assert.equal(active.basis,'active');assert.equal(active.settings.confirmed_run_id,'run');assert.equal(active.live,false);
 assert.equal(active.settings.manual_brick,20);
 const draft=chartSourceContext(fields,state,'draft');
 assert.equal(draft.basis,'draft');assert.equal(draft.settings.confirmed_run_id,undefined);
 const stopped=chartSourceContext(fields,{...state,running:false},'live');
 assert.equal(stopped.live,true);
});}
