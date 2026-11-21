const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
require('../chart-workspace-studies.js');const engine=require('../chart-renko-study-alignment.js'),lib=globalThis.SectorPulseChartStudies;
const source=fs.readFileSync('.private/chart-order-rollouts/renko-study-pipeline-candidate-20261119/candidate.js','utf8');
const folder='.private/chart-order-rollouts/native-renko-study-timeframe-20261119/';
function csv(name){const[h,...rows]=fs.readFileSync(folder+name,'utf8').trim().split(/\r?\n/),keys=h.split(',');return rows.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[keys[i],v])));}
const native=csv('native-30m-renko10-hourly-sma5.csv'),nativeHigher=csv('native-1h-renko10-hourly-sma5.csv');
const raw=JSON.parse(fs.readFileSync('.private/chart-order-rollouts/woodies-cci-20261119/woodies-hourly-history.json','utf8')).rows.map(r=>Object.fromEntries(['time','open','high','low','close','volume'].map((k,i)=>[k,r[i]])));
const host=native.map(r=>({sourceTime:Math.floor(Number(r.time)/1800)*1800,open:Number(r.open),high:Number(r.high),low:Number(r.low),close:Number(r.close)}));
function calculator(options={}){
 const scope={},c={settings:{type:'Renko',brickMethod:'fixed',size:10,renkoSource:'close'},history:new Map([['60',raw]]),liveStudyBars:new Map(),requestScope:{signal:scope},barReplay:null,study:{inputs:{}},indicator:{},calculation:'60',secondary:null,tickDelta:false,deltaInterval:false,studyUsesFormingBar:()=>false,Date:{now:()=>1795096800000},candleEnd:t=>t+3600,chartTickSize:()=>.05,renkoWicksVisible:()=>false,renko:lib.renko,window:{SectorPulseRenkoStudyAlignment:engine},...options};
 c.run=bars=>lib.indicators.SMA.run(bars,bars.map(b=>b.close),5,undefined,{});
 vm.createContext(c);
 const box=source.match(/^  function renkoBoxSize\([\s\S]*?^  }/m)[0];vm.runInContext(box,c);
 const a=source.indexOf('      const calculateUnshifted = data => {'),b=source.indexOf('      const offset =',a);vm.runInContext(source.slice(a,b)+'\nthis.calculate=calculateUnshifted;',c);return c;
}
test('combined constructor, actual size helper, SMA and merge reproduce native historical export rows',()=>{
 const c=calculator(),output=c.calculate(host)[0],reference=lib.renko(raw,10,undefined,'close',false),last=reference.at(-1).sourceTime;
 let checked=0,values=0,gaps=0;
 for(let i=0;i<host.length-1;i++){
  if(host[i].sourceTime<1793304000||Number(native[i+1].time)>=last)continue;
  const expected=native[i].MA===''?null:Number(native[i].MA);assert.equal(output[i],expected,'native row '+i);checked++;values+=expected!==null;gaps+=expected===null;
 }
 assert.ok(checked>150);console.log(JSON.stringify({pipelineNativeRows:checked,values,gaps}));
});
test('full native broker source reconstructs the selected native higher timeframe brick bodies',()=>{
 const reference=lib.renko(raw,10,undefined,'close',false).filter(b=>b.sourceTime>=1793304000&&b.sourceTime<1795096800);
 const selected=nativeHigher.filter(b=>Number(b.time)>=1793304000&&Number(b.time)<1795096800);
 assert.equal(reference.length,192);assert.equal(reference.length,selected.length);
 for(let i=0;i<reference.length;i++)for(const field of ['open','high','low','close'])assert.equal(reference[i][field],Number(selected[i][field]));
});
test('wait-off reference calculation excludes developing candles and keeps native confirmed values',()=>{
 const scope={},candle={time:1795096800,open:1800,high:3000,low:1,close:2900,volume:1,provisional:true};
 const c=calculator({studyUsesFormingBar:()=>true,requestScope:{signal:scope},
  history:new Map([['60',[...raw,candle]]]),
  liveStudyBars:new Map([['60',{scope,candle,updatedAt:1795090000}]])});
 const without=calculator({studyUsesFormingBar:()=>true}).calculate(host)[0];
 const output=c.calculate(host)[0];
 // Replay alignment is checked here; freshness-driven tail is tested separately.
 assert.deepEqual(Array.from(output),Array.from(without));
});
test('actual frontend candidate preserves every captured native row through the value-changing close',()=>{
 const f='.private/chart-order-rollouts/renko-value-change-20261120/';
 const wire=JSON.parse(fs.readFileSync(f+'native-wire.json','utf8'));
 const data=JSON.parse(fs.readFileSync(f+'broker-history-after.json','utf8')).result.sort((a,b)=>a.time-b.time);
 const events=new Map(),expected=new Map(),scope={};
 for(const e of wire){if(!['du','timescale_update'].includes(e.packet.m))continue;
  for(const v of Object.values(e.packet.p[1]))if(v?.t==='s2_st3')for(const row of v.st??[]){
   if(!events.has(e.received_at))events.set(e.received_at,new Map());events.get(e.received_at).set(row.v[0],row.v[1]);
  }
 }
 const c=calculator({settings:{type:'Renko',interval:'1',brickMethod:'fixed',size:10,renkoSource:'close'},
  calculation:'5',history:new Map(),requestScope:{signal:scope},studyUsesFormingBar:()=>true,candleEnd:t=>t+300});
 let checked=0;
 for(const [at,updates]of events){
  const cutoff=Math.floor(at/300)*300;
  c.Date.now=()=>at*1000;c.history.set('5',data.filter(b=>b.time+300<=cutoff));c.liveStudyBars.set('5',{scope,updatedAt:at});
  const first=!expected.size;for(const [clock,value]of updates)expected.set(clock,value);
  const clocks=[...expected.keys()].sort((a,b)=>a-b),host=clocks.map(clock=>({sourceTime:Math.floor(clock/60)*60}));
  if(first)c.calculate(host.slice(0,1));
  const actual=c.calculate(host)[0];
  for(let i=0;i<host.length;i++){assert.equal(actual[i],expected.get(clocks[i]),'frontend host '+clocks[i]);checked++;}
 }
 assert.ok(checked>=12);console.log(JSON.stringify({frontendNativePublicationRows:checked}));
});

