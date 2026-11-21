const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
require(path.join(root,'chart-workspace-studies.js'));
const input=JSON.parse(fs.readFileSync(path.join(__dirname,'evidence/chart-fixture.json')));
const chart=globalThis.SectorPulseChartStudies.renko(input.bars,input.size,undefined,'close',false);
assert.equal(chart.length,input.bricks.length);
let maximum=0;
chart.forEach((bar,i)=>{for(const k of ['open','high','low','close','sourceTime'])assert.equal(bar[k],input.bricks[i][k],k+' brick '+i)});
(async()=>{
 const ctx=vm.createContext({console,setTimeout,clearTimeout,structuredClone});ctx.self=ctx;
 vm.runInContext(fs.readFileSync(path.join(root,'.private/chart-pine-worker.js'),'utf8'),ctx);
 const workspace=fs.readFileSync(path.join(root,'chart-workspace.js'),'utf8');
 const functionText=workspace.slice(workspace.indexOf('  function aiRenkoPineSource() {'),workspace.indexOf('  function openAiRenkoSupertrend()'));
 const source=vm.runInNewContext(functionText+';aiRenkoPineSource()');
 const disk=fs.readFileSync(path.join(root,'ai-renko-supertrend.pine'),'utf8');
 assert.equal(source.replace(/\r/g,'').trim(),disk.replace(/\r/g,'').trim(),'embedded chart Pine source must match authoritative Pine');

 const plots=await new Promise((resolve,reject)=>{
  ctx.postMessage=d=>{if(d.ok===false)reject(Error(d.error));else if(d.plots)resolve(d.plots)};
  ctx.onmessage({data:{source,symbolInfo:{tickerid:'NSE:NIFTY50-INDEX',ticker:'NIFTY50-INDEX',prefix:'NSE',type:'index',timezone:'Asia/Kolkata',session:'0915-1530',mintick:.05},frames:{'15':chart},timeframe:'15',count:chart.length,inputs:{in_0:5,in_1:3,in_2:'Manual',in_3:input.size,in_4:false},chart:{is_renko:true,is_standard:false}}}).catch(reject);
 });
 const names=Object.keys(plots);
 const get=(name,i)=>{const p=plots[name];if(!p)throw Error('Missing plot '+name+'; available '+names);return p.data[i]?.value};
 for(let i=0;i<chart.length;i++){
  for(const [plot,key] of [['Synthetic close','synthetic_close'],['Synthetic open','synthetic_open'],['Host-updated synthetic ATR','synthetic_atr'],['Connected Supertrend','st'],['Effective factor hypothesis','effective_factor']]){
   const actual=get(plot,i),expected=input.expected[i][key],error=Math.abs(actual-expected);
   maximum=Math.max(maximum,error);assert.ok(error<1e-8,plot+' brick '+i+': '+actual+' vs '+expected+' box='+get('Active brick size',i)+' expectedbox='+input.size+' previousActual='+get('Synthetic close',i-1)+' hostClose='+chart[i].close);
  }
  assert.equal(get('Direction (-1 bullish)',i),input.expected[i].direction,'direction '+i);
 }
 const report={status:'PASS',source_rows:input.bars.length,bricks:chart.length,max_error:maximum,scope:'FYERS recorded time-close fixture -> new chart close/no-wick fixed Renko -> actual Pine worker with strategy-only fixed brick override versus Python; standalone Auto defaults unchanged. Not native TradingView history/tick parity or hosted chart acceptance.'};
 fs.writeFileSync(path.join(__dirname,'evidence/chart-parity.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e.message);process.exitCode=1});
