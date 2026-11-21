const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync('chart-workspace.js','utf8');
const start=source.indexOf('    if (action.chartNavigate && charts.length) {');
const end=source.indexOf("    if (action.action === 'restore-date-view')",start);
assert.ok(start>=0&&end>start);
const run=new Function('action','charts','displayedBars','settings','latestChartBar','chartRangeToLatest','priceAxis','draw','save',source.slice(start,end));
function navigate(direction,range={from:995,to:1021}){
 const applied=[],drawn=[],saved=[],settings={range:{...range},manualPriceScale:{from:1,to:2},priceBarRatio:4};
 const scale={getVisibleLogicalRange:()=>({...range}),setVisibleLogicalRange:next=>applied.push({...next})};
 const chart={timeScale:()=>scale,priceScale:()=>({applyOptions(){}})};
 const latest=count=>count-1+7;
 run({chartNavigate:direction},[chart],Array(999),settings,latest,
  (count,from)=>({from:Math.min(from,latest(count)-2),to:latest(count)}),()=> 'right',
  ()=>drawn.push({...settings.range}),()=>saved.push({...settings.range}));
 return {applied,drawn,saved,settings};
}
test('reset preserves its requested recent-candle range while chart readback is delayed',()=>{
 const result=navigate('reset');
 const expected={from:899,to:1005};
 assert.deepEqual(result.applied,[expected]);
 assert.deepEqual(result.drawn,[expected]);
 assert.deepEqual(result.saved,[expected]);
 assert.deepEqual(result.settings.range,expected);
 assert.equal(result.settings.manualPriceScale,undefined);
 assert.equal(result.settings.priceBarRatio,undefined);
});
test('zoom and pan persist requested navigation instead of the prior frame range',()=>{
 const expected={in:{from:73,to:97},out:{from:66.25,to:103.75},
  left:{from:62,to:92},right:{from:78,to:108},latest:{from:975,to:1005}};
 for(const [direction,range]of Object.entries(expected)){
  const result=navigate(direction,{from:70,to:100});
  assert.deepEqual(result.applied,[range],direction);
  assert.deepEqual(result.saved,[range],direction);
  assert.deepEqual(result.drawn,[],direction);
 }
});

const keyboardStart=source.indexOf("    stage.addEventListener('keydown', event => {");
const keyboardEnd=source.indexOf("    status = panel.querySelector",keyboardStart);
assert.ok(keyboardStart>=0&&keyboardEnd>keyboardStart);
const keyboardBody=source.slice(keyboardStart,keyboardEnd);
const keyboard=new Function('event','selectedDrawings','lineToolbar','panel','usesMacKeys','barReplay','charts','settings','save',
 keyboardBody.slice(keyboardBody.indexOf('{')+1,keyboardBody.lastIndexOf('});')));
function navigateKeyboard(key,modifiers={}){
 const range={from:70,to:100},applied=[],saved=[],settings={range:{...range}};
 const scale={getVisibleLogicalRange:()=>({...range}),setVisibleLogicalRange:next=>applied.push({...next})};
 const chart={timeScale:()=>scale,chartElement:()=>({getClientRects:()=>[{}]})};
 let prevented=false;
 const event={key,code:key,defaultPrevented:false,isComposing:false,shiftKey:false,
  ctrlKey:false,metaKey:false,altKey:false,repeat:false,target:{closest:()=>null},
  preventDefault:()=>{prevented=true},...modifiers};
 keyboard(event,new Set(),{hidden:true},{},true,false,[chart],settings,()=>saved.push({...settings.range}));
 return{applied,saved,settings,prevented};
}
test('Mac Command and Control keyboard zoom persist before the next chart frame',()=>{
 for(const modifier of ['metaKey','ctrlKey']){
  for(const [key,expected]of Object.entries({ArrowUp:{from:73,to:97},ArrowDown:{from:66.25,to:103.75}})){
   const result=navigateKeyboard(key,{[modifier]:true});
   assert.deepEqual(result.applied,[expected]);
   assert.deepEqual(result.saved,[expected]);
   assert.deepEqual(result.settings.range,expected);
   assert.equal(result.prevented,true);
  }
 }
});
test('keyboard one-bar and accelerated pan retain the requested viewport',()=>{
 for(const [key,modifier,expected]of [
  ['ArrowLeft',{}, {from:69,to:99}],['ArrowRight',{}, {from:71,to:101}],
  ['ArrowLeft',{metaKey:true},{from:62,to:92}],['ArrowRight',{ctrlKey:true},{from:78,to:108}]
 ]){
  const result=navigateKeyboard(key,modifier);
  assert.deepEqual(result.saved,[expected]);
  assert.deepEqual(result.applied,[expected]);
 }
});
