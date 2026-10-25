const {test}=require('node:test'),assert=require('node:assert/strict');
const {feedHealthSummary,feedPresentation,runnerChartContext,runnerChartAlignment}=require('../renko-supertrend.js');
test('fresh prices remain live while broker candles recover and order health is separate',()=>{
 const data={server_at:100,market:{connected:true,tick_fresh:true,tick_exchange_at:99,fresh:false},candles:{busy:true},runner_snapshot_fresh:true,orders:{connected:false}};
 assert.equal(feedPresentation(data).label,'Live prices · candle recovering');
 assert.match(feedHealthSummary(data),/Prices: live/);assert.match(feedHealthSummary(data),/Candles: refreshing in background/);
 assert.match(feedHealthSummary(data),/Orders: reconciliation/);
 assert.match(feedHealthSummary(data,20),/awaiting fresh ticks/);
});
test('confirmed chart comparison uses committed candle even when last signal is provisional',()=>{
 const signal={timestamp:120,supertrend:100,direction:'BULLISH',ema10:102,ema30:101};
 const context={basis:'active',runId:'run',anchor:0,settings:{timeframe:'1 minute'}};
 const state={run_id:'run',last_signal:{...signal,timestamp:180,supertrend:999},confirmed_indicators:{latest:signal}};
 const data={initialization_anchor:0,rows:[signal],confirmed_source:{run_id:'run',timeframe:'1 minute'}};
 assert.equal(runnerChartAlignment(context,state,data).verified,true);
 assert.equal(runnerChartAlignment(context,state,{...data,confirmed_source:{run_id:'other',timeframe:'1 minute'}}).blocked,true);
 assert.equal(runnerChartAlignment(context,state,{...data,confirmed_source:{run_id:'run',timeframe:'5 minutes'}}).blocked,true);
});
