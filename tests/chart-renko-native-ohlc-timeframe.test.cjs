const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
require('../chart-workspace-studies.js');const lib=globalThis.SectorPulseChartStudies,engine=require('../chart-renko-study-alignment.js');
const folder='.private/chart-order-rollouts/renko-ohlc-reference-20261120/';
function csv(name){const[h,...ls]=fs.readFileSync(folder+name,'utf8').trim().split(/\r?\n/),keys=h.split(',');return ls.map(l=>Object.fromEntries(l.split(',').map((v,i)=>[keys[i],v===''?null:Number(v)])));}
function raw(name){return JSON.parse(fs.readFileSync(folder+name,'utf8')).result.sort((a,b)=>a.time-b.time);}
const upper=csv('native-5m-ohlc10.csv'),lower=csv('native-1m-ref5m-ohlc10.csv');
const ref=lib.renko(raw('broker-5m.json').filter(b=>b.time<1795115700),10,undefined,'ohlc',false);
const plots=lib.indicators.SMA.run(ref,ref.map(b=>b.close),5,undefined,{});
function checkBodies(native,bars,minutes,cutoff){
 const start=Math.floor(native[0].time/(minutes*60))*minutes*60+minutes*60;
 const selected=native.filter(b=>b.time>=start&&b.time<cutoff);
 const actual=lib.renko(bars.filter(b=>b.time<cutoff),10,undefined,'ohlc',false).filter(b=>b.sourceTime>=start);
 assert.equal(actual.length,selected.length);
 const duplicates=new Map();
 for(let i=0;i<actual.length;i++){
  for(const key of ['open','high','low','close'])assert.equal(actual[i][key],selected[i][key],key+' row '+i);
  const count=duplicates.get(actual[i].sourceTime)??0;
  assert.ok(Math.abs(selected[i].time-(actual[i].sourceTime+count/1000))<1e-6);
  duplicates.set(actual[i].sourceTime,count+1);
 }
 return {selected,actual};
}
test('native Traditional10 OHLC five-minute bodies, clocks and SMA match broker-derived reference',()=>{
 const {selected}=checkBodies(upper,raw('broker-5m.json'),5,1795115700);assert.equal(selected.length,276);
 const start=ref.findIndex(b=>b.sourceTime===Math.floor(selected[0].time/300)*300);
 for(let i=0;i<selected.length;i++)assert.equal(plots[0][start+i],selected[i].MA,'SMA '+i);
 console.log(JSON.stringify({nativeOhlc5mBricks:selected.length,ohlcFields:selected.length*4,smaValues:selected.length}));
});
test('native Traditional10 OHLC one-minute bodies and clocks match broker-derived host',()=>{
 const {selected}=checkBodies(lower,raw('broker-1m.json'),1,1795116000);
 assert.ok(selected.length>250);
 console.log(JSON.stringify({nativeOhlc1mBricks:selected.length,ohlcFields:selected.length*4}));
});
test('native OHLC lower-chart five-minute calculation matches confirmed historical alignment',()=>{
 const host=lower.map(b=>({sourceTime:Math.floor(b.time/60)*60}));
 const out=engine.alignRenkoStudyPlots(plots,ref,host,{gaps:false})[0],clock=engine.renkoStudyClock(ref);let checked=0;
 for(let i=0;i<lower.length-2;i++){
  if(lower[i].time<clock[0]||lower[i+1].time>=clock.at(-1))continue;
  assert.equal(out[i],lower[i].MA,'native lower row '+i);checked++;
 }
 assert.equal(checked,246);console.log(JSON.stringify({nativeOhlcMtfRows:checked}));
});

