const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'../..');require(path.join(root,'chart-workspace-studies.js'));
const fixture=JSON.parse(fs.readFileSync(path.join(__dirname,'evidence/runtime-seed-fixture.json')));
const workspace=fs.readFileSync(path.join(root,'chart-workspace.js'),'utf8');
const sourceFunction=workspace.slice(workspace.indexOf('  function aiRenkoPineSource() {'),workspace.indexOf('  function openAiRenkoSupertrend()'));
const source=vm.runInNewContext(sourceFunction+';aiRenkoPineSource()');
assert.ok(source.replace(/\r/g,'').trim()===fs.readFileSync(path.join(root,'ai-renko-supertrend.pine'),'utf8').replace(/\r/g,'').trim(),'Embedded Pine must match authoritative source');
(async()=>{
 const results=[];
 for(const sample of fixture.cases){
  const input=sample.rows.map(([time,open,high,low,close,volume])=>({time,open,high,low,close,volume}));
  const bricks=globalThis.SectorPulseChartStudies.renko(input,sample.brick,undefined,'close',false);
  assert.equal(bricks.length,sample.bricks.length);
  bricks.forEach((bar,i)=>{for(const key of ['open','high','low','close','sourceTime'])assert.equal(bar[key],sample.bricks[i][key]);});
  const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;
  vm.runInContext(fs.readFileSync(path.join(root,'.private/chart-pine-worker.js'),'utf8'),ctx);
  const plots=await new Promise((resolve,reject)=>{
   ctx.postMessage=data=>{if(data.ok===false)reject(Error(data.error));else if(data.plots)resolve(data.plots);};
   ctx.onmessage({data:{source,symbolInfo:{tickerid:sample.symbol,ticker:sample.symbol,prefix:'NSE',type:'index',timezone:'Asia/Kolkata',session:'0915-1530',mintick:.05},frames:{[sample.frame]:bricks},timeframe:String(sample.frame),count:bricks.length,inputs:{in_0:5,in_1:3,in_2:'Manual',in_3:sample.brick,in_4:false},chart:{is_renko:true,is_standard:false}}}).catch(reject);
  });
  let maximum=0;
  for(let i=0;i<bricks.length;i++){
   for(const [plot,key] of [['Synthetic close','synthetic_close'],['Synthetic open','synthetic_open'],['Host-updated synthetic ATR','synthetic_atr'],['Connected Supertrend','st'],['Effective factor hypothesis','effective_factor']]){
    const actual=plots[plot]?.data[i]?.value,expected=sample.expected[i][key],error=Math.abs(actual-expected);
    assert.ok(error<1e-8,sample.symbol+' '+sample.frame+' '+plot+' '+actual+' vs '+expected);maximum=Math.max(maximum,error);
   }
   assert.equal(plots['Direction (-1 bullish)'].data[i].value,sample.expected[i].direction);
  }
  results.push({symbol:sample.symbol,frame:sample.frame,source_rows:input.length,bricks:bricks.length,max_error:maximum,seed_sha256:sample.seed_sha256});
 }
 const report={status:'PASS',cases:results,scope:'Nine preserved previous-session close-only series captured in verification-only run ledgers -> actual NEW chart Renko -> actual Pine worker versus Python. Same provider source consumed; no stream or order was started. Short CE fixture is not sufficient live warm-up.',orders_submitted:0,stream_started:false};
 fs.writeFileSync(path.join(__dirname,'evidence/runtime-seed-parity.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
