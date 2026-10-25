
const {test}=require('node:test'),assert=require('node:assert/strict');
const {mergeChartRows,runnerChartAlignment,chartHistoricalEvents,chartAnalysisAvailable}=require('../renko-supertrend.js');
const prior={timestamp:1,direction:'BULLISH',supertrend:10,ema10:11,ema30:12,lifecycle_event:'BUY'};
test('incremental history is merged before runner comparison without changing cached rows',()=>{
 const rows=[prior],data={incremental:true,initialization_anchor:1,rows:[{timestamp:2,supertrend:13}]};
 const merged=mergeChartRows(data,rows);
 assert.equal(runnerChartAlignment({basis:'active',runId:'r',anchor:1},{run_id:'r',last_signal:prior},merged).verified,true);
 assert.equal(rows.length,1);assert.equal(data.rows.length,1);assert.deepEqual(merged.rows.map(r=>r.timestamp),[1,2]);
 const revision=mergeChartRows({...data,rows:[{...prior,supertrend:9}]},rows);assert.equal(revision.rows[0].supertrend,9);
});
test('validated chart indicators survive genuine runner mismatch but trade signals stay withheld',()=>{
 const d={rows:[{...prior,supertrend:20}],initialization_anchor:1,data_quality:{analysis_available:true}};
 const parity=runnerChartAlignment({basis:'active',runId:'r',anchor:1},{run_id:'r',last_signal:prior},d);
 assert.equal(parity.blocked,true);assert.equal(chartAnalysisAvailable(d),true);assert.deepEqual(chartHistoricalEvents(d,parity),[]);
 assert.equal(chartHistoricalEvents(d,{blocked:false}).length,1);
 assert.deepEqual(chartHistoricalEvents({...d,data_quality:{analysis_available:false}},{blocked:false}),[]);
});
