const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {JSDOM}=require('../.private/test-node/node_modules/jsdom');
require('../chart-workspace-studies.js');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
const raw=[{time:0,open:10,high:14,low:8,close:12,volume:1},{time:3600,open:12,high:20,low:10,close:18,volume:2},{time:7200,open:18,high:24,low:12,close:20,volume:3}];
const live={time:10800,open:20,high:26,low:16,close:24,volume:4,provisional:true};
function helpers(c){
 vm.createContext(c);
 const bar=source.match(/^  function heikinAshiBar\([\s\S]*?^  }/m)?.[0];assert.ok(bar);vm.runInContext(bar,c);
 const a=source.indexOf('  function studyCalculationBars('),b=source.indexOf('  function configuredCalculationInterval(',a);assert.ok(a>=0&&b>a);vm.runInContext(source.slice(a,b),c);
 const x=source.indexOf('  function alignConfirmedStudyPlots('),y=source.indexOf('  const legacyRatingIntervals',x);vm.runInContext(source.slice(x,y),c);return c;
}
test('requested HA timeframe is derived recursively from its own native OHLC',()=>{
 const c=helpers({settings:{type:'Heikin Ashi'}}),before=JSON.stringify(raw),bars=c.studyCalculationBars(raw);
 assert.deepEqual(bars.map(b=>[b.open,b.high,b.low,b.close,b.time,b.volume]),[[11,14,8,11,0,1],[11,20,10,15,3600,2],[13,24,12,18.5,7200,3]]);
 assert.equal(JSON.stringify(raw),before);assert.notEqual(bars,raw);assert.notEqual(bars[0],raw[0]);
});
test('forming HA candle starts from the last confirmed HA candle without mutating it',()=>{
 const c=helpers({settings:{type:'Heikin Ashi'}}),bars=c.studyCalculationBars(raw),before=JSON.stringify(bars);
 const current=c.studyCalculationLiveBar(live,bars);assert.equal(current.open,15.75);assert.equal(current.close,21.5);assert.equal(current.high,26);assert.equal(current.low,15.75);
 assert.equal(current.time,live.time);assert.equal(current.volume,4);assert.equal(current.provisional,true);assert.equal(JSON.stringify(bars),before);
});
test('standard chart calculations retain native array and bar identity',()=>{
 for(const type of ['Candles','Line','Renko']){const c=helpers({settings:{type}});assert.equal(c.studyCalculationBars(raw),raw);assert.equal(c.studyCalculationLiveBar(live,raw),live);}
});
test('HA exposes all broker-supported higher intervals, excluding trade-count intervals',()=>{
 const c=helpers({settings:{type:'Heikin Ashi',customIntervals:['17','100T']},requestedHourIntervals:['360','840','1320','1380'],tradeInterval:x=>/[ST]$/.test(x),sourceInterval:()=>true,projectionIntervalSeconds:x=>parseInt(x)*(/D$/.test(x)?86400:/W$/.test(x)?604800:/M$/.test(x)?2592000:60)});
 const a=source.indexOf('  function studyCalculationChoices('),b=source.indexOf('  function studyCalculationBars(',a);vm.runInContext(source.slice(a,b),c);
 const choices=[...c.studyCalculationChoices('30')];for(const value of ['60','360','840','1320','1380','1D','1W','1M','12M'])assert.ok(choices.includes(value),value);
 assert.ok(!choices.includes('100T'));c.settings.type='Renko';assert.deepEqual([...c.studyCalculationChoices('30')],[]);
});
function calculator(type,forming){
 const scope={},c=helpers({settings:{type,interval:'30'},history:new Map([['60',raw]]),liveStudyBars:new Map([['60',{scope,candle:live}]]),requestScope:{signal:scope},barReplay:null,study:{},indicator:{},calculation:'60',secondary:null,tickDelta:false,deltaInterval:false,studyUsesFormingBar:()=>forming,Date:{now:()=>13000*1000},candleEnd:(t,i)=>t+Number(i)*60});
 c.run=data=>globalThis.SectorPulseChartStudies.indicators.SMA.run(data,data.map(b=>b.close),2,undefined,{});
 const a=source.indexOf('      const calculateUnshifted = data => {'),b=source.indexOf('      const offset =',a);assert.ok(a>=0&&b>a);vm.runInContext(source.slice(a,b)+'\nthis.calculate=calculateUnshifted;',c);return c;
}
const host=Array.from({length:7},(_,i)=>({time:i*1800,provisional:i===6}));
test('actual indicator path aligns completed HA source closes rather than native prices',()=>{
 const c=calculator('Heikin Ashi',false);assert.deepEqual([...c.calculate(host)[0]],[null,null,null,13,13,16.75,16.75]);
});
test('actual forming path changes only HA tail indicator value',()=>{
 const c=calculator('Heikin Ashi',true);assert.deepEqual([...c.calculate(host)[0]],[null,null,null,13,13,16.75,20]);
});
test('Candles and Line calculation values remain native',()=>{
 for(const type of ['Candles','Line']){const c=calculator(type,true);assert.deepEqual([...c.calculate(host)[0]],[null,null,null,15,15,19,22]);}
});
function ratings(onChart){
 const dom=new JSDOM('<div id="host"></div>'),scope={},calls=[];
 const c=helpers({document:dom.window.document,settings:{type:'Heikin Ashi',interval:'30'},ratingTableIntervals:()=>[],ratingTableUsesForming:()=>true,barReplay:null,Date:{now:()=>13000*1000},intervalLabel:x=>x,sourceInterval:()=>true,shadowHistory:()=>raw,requestScope:{signal:scope},liveStudyBars:new Map([['60',{scope,candle:live}]]),candleEnd:(t,i)=>t+Number(i)*60,formatChartPrice:x=>String(x),indicators:{TechnicalRatings:{ratingColor:()=>'green',ratingCategory:()=>1,ratings:bars=>{calls.push(bars);return[{All:.2,MAs:.2,Oscillators:.2}];}}}});
 const a=source.indexOf('  function attachRatingsTable('),b=source.indexOf('  let deltaTradeCapture;',a);assert.ok(a>=0&&b>a);vm.runInContext(source.slice(a,b),c);
 const refresh=c.attachRatingsTable(dom.window.document.querySelector('#host'),{inputs:{}},onChart?'30':'60');const chart=c.studyCalculationBars(raw);refresh(chart);return{dom,c,calls,chart};
}
test('ratings table transforms higher-timeframe history and forming tail consistently',()=>{
 const f=ratings(false),bars=f.calls[0];assert.equal(bars.length,4);assert.equal(bars[2].close,18.5);assert.equal(bars[3].close,21.5);assert.equal(bars[3].open,15.75);f.dom.window.close();
});
test('ratings table never transforms already-HA chart bars twice',()=>{
 const f=ratings(true),bars=f.calls[0];assert.deepEqual(bars.map(b=>b.close),f.chart.map(b=>b.close));assert.equal(bars[2].open,13);f.dom.window.close();
});
