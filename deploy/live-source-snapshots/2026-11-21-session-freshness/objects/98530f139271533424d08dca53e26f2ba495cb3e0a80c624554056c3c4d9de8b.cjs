const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
for(const file of ['renko-supertrend.js','.private/dashboard-login/accounts/bf46fc364b610a0dfd338419e133cb41/source/renko-supertrend.js'].filter(file=>fs.existsSync(file))){
 const source=fs.readFileSync(file,'utf8');
 test(file+': hovered candle survives ticks/history; pointer exit restores latest',()=>{
  const nodes=new Map(),options=[];
  const el=id=>{if(!nodes.has(id))nodes.set(id,{value:id,handlers:{},addEventListener(k,fn){this.handlers[k]=fn;},textContent:''});return nodes.get(id);};
  const ctx={renderCandleInspection:()=>{},el,chart:{timeScale:()=>({applyOptions:o=>options.push(o)})},chartControl:el,stamp:String,price:String};
  vm.createContext(ctx);
  const start=source.indexOf('let inspectedCandleTime=null'),end=source.indexOf('    const storage=',start);
  vm.runInContext(source.slice(start,end),ctx);
  vm.runInContext("readCandle({time:650,open:1,high:3,low:1,close:2},true)",ctx);
  // Real pointer movement permits one hover; setData/update-generated events cannot select a different bar.
  el('chart').handlers.pointermove();
  assert.equal(vm.runInContext('acceptInspectionHover()',ctx),true);
  assert.equal(vm.runInContext('acceptInspectionHover()',ctx),false);
  el('chart').handlers.pointermove();
  assert.equal(vm.runInContext('acceptInspectionHover()',ctx),true);
  const hovered=el('candle-readout').textContent;
  vm.runInContext("readCandle({time:655,open:2,high:4,low:2,close:3})",ctx);
  assert.equal(el('candle-readout').textContent,hovered);
  vm.runInContext("readCandle({time:660,open:3,high:5,low:3,close:4})",ctx);
  assert.equal(el('candle-readout').textContent,hovered);
  el('chart').handlers.pointerleave();
  assert.match(el('candle-readout').textContent,/660 IST/);
  assert.equal(options[0].shiftVisibleRangeOnNewBar,false);
  assert.equal(options.at(-1).shiftVisibleRangeOnNewBar,false);
  assert.equal(vm.runInContext('acceptInspectionHover()',ctx),false); // queued crosshair after pointer exit

 });
 test(file+': refresh preserves explicit ranges at desktop and narrow widths',()=>{
  const start=source.indexOf('if(previousRange&&same&&Number.isFinite(previousLastLogical))'),end=source.indexOf('}else if(plotted.length)',start)+1;
  const code=source.slice(start,end);
  for(const range of [{from:80,to:120},{from:100,to:112}]){
   const ctx={previousRange:range,same:true,previousLastLogical:200,previousVisible:{from:50},previousLeftLogical:range.from,plotted:[{time:250}],logicalAt:t=>t===250?201:range.from,viewport:{}};
   vm.runInNewContext(code,ctx);
   assert.equal(ctx.viewport.follow,false);
   assert.equal(ctx.viewport.range.from,range.from);assert.equal(ctx.viewport.range.to,range.to);
  }
 });
}

test('collapsed studies never ask the chart library for invisible crosshair coordinates',()=>{
 const source=fs.readFileSync('renko-supertrend.js','utf8');
 const start=source.indexOf('    function paintStudyHover('),end=source.indexOf('    function syncStudyPanes(',start);
 let positioned=0;const pane={fold:{hidden:false,open:false},host:{clientWidth:0,clientHeight:0},points:new Map(),latest:null,value:{dataset:{}},view:{setCrosshairPosition(){positioned++;},clearCrosshairPosition(){}},series:{}};
 const ctx={studyHoverValue:()=>({available:true,hovered:true,value:10}),stamp:String,pane};vm.createContext(ctx);vm.runInContext(source.slice(start,end)+';paintStudyHover(pane,100);',ctx);
 assert.equal(positioned,0);
});
