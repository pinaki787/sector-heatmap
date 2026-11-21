const {test}=require('node:test'),assert=require('node:assert/strict');
const {chartSourceContext,runnerChartAlignment}=require('../renko-supertrend.js');
for(const symbol of ['MCX:GOLDM26NOVFUT','BTCUSD','NSE:NIFTY50-INDEX'])for(const timeframe of ['1 minute','5 minutes','1 hour']){
 const fields={symbol,timeframe,'session-run-id':'run','history-preset':'custom','manual-brick':10};
 const state={run_id:'run',running:false,confirmed_feed_revision:'shared-confirmed-live-v1',config:{underlying:symbol,timeframe,mode:'PAPER',manual_brick:20}};
 test(symbol+' '+timeframe+' live and stopped audit remain independent',()=>{
  const before=JSON.stringify(state),live=chartSourceContext(fields,state,'live'),audit=chartSourceContext(fields,state,'runner');
  assert.equal(live.live,true);assert.equal(live.settings.confirmed_run_id,undefined);assert.equal(live.settings.manual_brick,10);
  assert.equal(live.history.history_preset,'45');assert.equal(runnerChartAlignment(live,state,{}).blocked,false);
  assert.equal(audit.basis,'recorded');assert.equal(audit.settings.confirmed_run_id,'run');assert.equal(audit.settings.manual_brick,20);
  assert.equal(chartSourceContext(fields,{...state,running:true},'runner').basis,'active');
  assert.equal(chartSourceContext(fields,{...state,run_id:'new'},'live').error,undefined);
  assert.equal(chartSourceContext(fields,{...state,run_id:'new'},'runner').basis,'recorded');
  assert.equal(JSON.stringify(state),before);
 });
}
