const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
require('../chart-workspace-studies.js');const lib=globalThis.SectorPulseChartStudies,alignment=require('../chart-renko-study-alignment.js'),sizing=require('../chart-renko-sizing.js');
const folder='.private/chart-order-rollouts/renko-percentage-reference-20261120/',stage='.private/chart-order-rollouts/renko-percentage-activation-20261120/';
const captures=JSON.parse(fs.readFileSync(folder+'native-histories.json','utf8')),source=fs.readFileSync(process.env.CHART_SOURCE||stage+'root/chart-workspace.js','utf8');
function raw(symbol,minutes){return JSON.parse(fs.readFileSync(folder+'broker-'+symbol.split(':')[1].replace('.P','')+'-'+minutes+'m.json','utf8')).rows.map(r=>Object.fromEntries(['time','open','high','low','close','volume'].map((k,i)=>[k,r[i]]))).sort((a,b)=>a.time-b.time);}
function calculator(capture){
 const tick=capture.symbol.includes('BTC')?.5:.01,scope={};
 const reference=raw(capture.symbol,5).filter(b=>b.time+300<=capture.capturedAt);
 const c={settings:{type:'Renko',interval:'1',brickMethod:'percent',brickPercent:.01,renkoSource:'close'},generation:1,barReplay:null,
  history:new Map([['5',reference]]),liveStudyBars:new Map(),requestScope:{signal:scope},study:{inputs:{waitForTimeframeClose:false}},
  indicator:{},calculation:'5',secondary:null,tickDelta:false,deltaInterval:false,Date:{now:()=>capture.capturedAt*1000},
  candleEnd:t=>t+300,studyUsesFormingBar:()=>true,chartTickSize:()=>tick,renkoWicksVisible:()=>false,renko:lib.renko,renkoAtrSize:lib.renkoAtrSize,
  window:{SectorPulseRenkoStudyAlignment:alignment,SectorPulseRenkoSizing:sizing}};
 c.run=b=>lib.indicators.SMA.run(b,b.map(x=>x.close),5,undefined,{});
 vm.createContext(c);
 const a=source.indexOf('  let renkoPercentReference;'),b=source.indexOf('  function visiblePlotColor',a);
 vm.runInContext(source.slice(a,b),c);
 const x=source.indexOf('      const calculateUnshifted = data => {'),y=source.indexOf('      const offset =',x);
 vm.runInContext(source.slice(x,y)+'\nthis.calculate=calculateUnshifted;',c);return c;
}
test('actual chart percentage sizing matches all36 native cases and preserves empty-history handling',()=>{
 const cases=JSON.parse(fs.readFileSync(folder+'native-cases.json','utf8')),c=calculator(captures[0]),ticks={'DELTAIN:BTCUSD.P':.5,'DELTAIN:PAXGUSD.P':.01,'DELTAIN:ETHUSD.P':.05};
 for(const row of cases){const size=c.renkoBoxSize({brickMethod:'percent',brickPercent:row.percent},[{close:row.price}],ticks[row.symbol]);assert.ok(Math.abs(size-row.boxSize)<1e-8);}
 assert.ok(Number.isNaN(c.renkoBoxSize({brickMethod:'percent'},[],.5)));
});
test('broker-based Percentage sizing reconstructs1183 captured native bricks and synthetic clocks',()=>{
 let checked=0;
 for(const cap of captures){
  const c=calculator(cap),dt=cap.minutes*60,bars=raw(cap.symbol,cap.minutes).filter(b=>b.time+dt<=cap.capturedAt);
  const size=c.renkoBoxSize(c.settings,bars,c.chartTickSize(),true),all=lib.renko(bars,size,undefined,'close',false),clocks=alignment.renkoStudyClock(all);
  const start=Math.floor(cap.series[0].v[0]/dt)*dt+dt,cutoff=Math.floor(cap.capturedAt/dt)*dt;
  const selected=cap.series.filter(r=>r.v[0]>=start&&r.v[0]<cutoff),indices=all.map((b,i)=>[b,i]).filter(([b])=>b.sourceTime>=start);
  assert.equal(selected.length,indices.length);
  for(let i=0;i<selected.length;i++){const [bar,index]=indices[i];for(const [key,col]of [['open',1],['high',2],['low',3],['close',4]])assert.ok(Math.abs(bar[key]-selected[i].v[col])<1e-8,key+' '+cap.symbol);assert.ok(Math.abs(clocks[index]-selected[i].v[0])<1e-6);checked++;}
 }
 assert.equal(checked,1183);console.log(JSON.stringify({nativePercentageBricks:checked,ohlcFields:checked*4}));
});
test('actual frontend Percentage timeframe calculation matches503 native lower-chart SMA rows',()=>{
 let checked=0;
 for(const cap of captures.filter(c=>c.minutes===1)){
  const c=calculator(cap),bars=raw(cap.symbol,1).filter(b=>b.time+60<=cap.capturedAt),size=c.renkoBoxSize(c.settings,bars,c.chartTickSize(),true);
  const host=lib.renko(bars,size,undefined,'close',false),clocks=alignment.renkoStudyClock(host),out=c.calculate(host)[0];
  const reference=c.history.get('5'),ref=lib.renko(reference,c.renkoBoxSize(c.settings,reference,c.chartTickSize()),undefined,'close',false),refClocks=alignment.renkoStudyClock(ref);
  const native=new Map(cap.study.map(r=>[r.v[0].toFixed(3),r.v[1]])),start=Math.floor(cap.series[0].v[0]/60)*60+60;
  for(let i=0;i<host.length-2;i++){const value=native.get(clocks[i].toFixed(3));if(clocks[i]<start||value===undefined||clocks[i]>=refClocks.at(-2)||clocks[i+1]>=refClocks.at(-1))continue;assert.ok(Math.abs(out[i]-value)<1e-7,'SMA '+cap.symbol+' '+clocks[i]);checked++;}
 }
 assert.equal(checked,503);console.log(JSON.stringify({frontendNativePercentageMtfRows:checked}));
});
test('all seven browser bundles preserve the study engine and add percentage sizing',()=>{
 const files=JSON.parse(fs.readFileSync(stage+'files.json','utf8'));let bundles=0,pages=0;
 for(const r of files){if(r.target.endsWith('chart-workspace-studies.js')){const c={window:{}};vm.createContext(c);vm.runInContext(fs.readFileSync(r.staged,'utf8'),c);assert.equal(typeof c.window.SectorPulseRenkoStudyAlignment.calculateRenkoTimeframeStudy,'function');assert.equal(c.window.SectorPulseRenkoSizing.renkoPercentageSize(62520,1,.5),500);bundles++;}
  if(r.target.endsWith('.html')){assert.equal((fs.readFileSync(r.staged,'utf8').match(/renko-percent=20261120-1/g)??[]).length,2);pages++;}}
 assert.equal(bundles,7);assert.equal(pages,21);
});
test('Percentage calculation choices are enabled while unresolved ATR remains excluded',()=>{
 const c={settings:{type:'Renko',brickMethod:'percent'},requestedHourIntervals:['360','840','1320','1380'],tradeInterval:()=>false,sourceInterval:()=>true,projectionIntervalSeconds:x=>parseInt(x)*60};
 vm.createContext(c);const a=source.indexOf('  function studyCalculationChoices('),b=source.indexOf('  function studyCalculationBars(',a);vm.runInContext(source.slice(a,b),c);
 for(const interval of ['5','360','840','1320','1380'])assert.ok(c.studyCalculationChoices('1').includes(interval));
 c.settings.brickMethod='atr';assert.deepEqual([...c.studyCalculationChoices('1')],[]);
});

test('native five-minute Percentage chart SMA matches592 completed reference values',()=>{
 let checked=0;
 for(const cap of captures.filter(c=>c.minutes===5)){
  const c=calculator(cap),bars=raw(cap.symbol,5).filter(b=>b.time+300<=cap.capturedAt),size=c.renkoBoxSize(c.settings,bars,c.chartTickSize(),true);
  const reference=lib.renko(bars,size,undefined,'close',false),clocks=alignment.renkoStudyClock(reference),plots=lib.indicators.SMA.run(reference,reference.map(b=>b.close),5,undefined,{})[0];
  const native=new Map(cap.study.map(r=>[r.v[0].toFixed(3),r.v[1]])),start=Math.floor(cap.series[0].v[0]/300)*300+300;
  for(let i=0;i<reference.length-2;i++){const value=native.get(clocks[i].toFixed(3));if(clocks[i]<start||value===undefined||clocks[i]>=clocks.at(-2)||clocks[i+1]>=clocks.at(-1))continue;assert.ok(Math.abs(plots[i]-value)<1e-7,'native reference SMA '+cap.symbol);checked++;}
 }
 assert.equal(checked,592);console.log(JSON.stringify({nativePercentageReferenceSmaRows:checked}));
});

test('forming and future reference candles cannot alter fresh confirmed Percentage study values',()=>{
 const cap=captures.find(c=>c.minutes===1&&c.symbol.includes('BTC')),c=calculator(cap);
 const bars=raw(cap.symbol,1).filter(b=>b.time+60<=cap.capturedAt),size=c.renkoBoxSize(c.settings,bars,c.chartTickSize(),true);
 const host=lib.renko(bars,size,undefined,'close',false),scope=c.requestScope.signal;
 c.liveStudyBars.set('5',{scope,updatedAt:cap.capturedAt});
 const expected=Array.from(c.calculate(host)[0]),confirmed=c.history.get('5');
 const time=Math.floor(cap.capturedAt/300)*300;
 for(const provisional of [true,false]){
  c.history.set('5',[...confirmed,{time,open:100000,high:100000,low:100000,close:100000,volume:1,provisional}]);
  assert.deepEqual(Array.from(c.calculate(host)[0]),expected,'developing candle flagged '+provisional);
 }
});

