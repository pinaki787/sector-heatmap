const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const [library,stateFile,engineFile,output]=process.argv.slice(2);
const {executionMarkers,mapExecutionMarkers}=require(path.resolve(library));
const state=JSON.parse(fs.readFileSync(stateFile)),engine=JSON.parse(fs.readFileSync(engineFile)).renko_engine;
const bricks=engine.rows.map((r,i)=>({...r,time:r.timestamp,indicator_timestamp:r.timestamp}));
const markers=executionMarkers([],state,state.config.underlying,state.config.timeframe),mapped=mapExecutionMarkers(markers,bricks);
const report={run_id:state.run_id,source_bricks:bricks.length,ledger_fill_markers:markers.length,mapped_markers:mapped.length,markers:markers.map(m=>({time:m.time,text:m.text,reference_time:m.brickReference?.timestamp})),status:mapped.length===markers.length&&mapped.length===4?'PASS':'FAIL',scope:'Replay recorded FYERS run and its saved exact reference bricks. No broker/order calls.'};
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
if(process.env.EXPECT_MARKER_PASS==='1')assert.equal(report.status,'PASS');
