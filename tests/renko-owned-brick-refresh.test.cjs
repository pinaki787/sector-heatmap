const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('chart-workspace.js','utf8');
test('plotted completed bricks are a snapshot, not the append-mutated signal cache',()=>{
 const start=source.indexOf('  function chartRenkoBricks('),end=source.indexOf('  function noteOwnedRenkoTail(',start);
 const cache=[{time:1,close:100}];
 const c={completedBrickSignalView:()=>true,aiRuntimeParams:new URLSearchParams('aiRun=owned'),window:{RenkoAiChartSource:{signalBars:()=>cache}},location:{href:'https://example.test'},chartSymbol:()=> 'PAXGUSD'};
 vm.createContext(c);vm.runInContext(source.slice(start,end)+';globalThis.plotted=chartRenkoBricks(1);',c);
 cache.push({time:2,close:99});assert.equal(c.plotted.length,1);assert.notEqual(c.plotted,cache);
});
test('new owned bricks update the existing series even when minute candles did not change',()=>{
 const start=source.indexOf('  function syncOwnedRenkoSignals('),end=source.indexOf('  function renkoRebasedRange(',start);
 let appended=0,noted=0,redraws=0;
 const displayed=[{time:1,close:100}],exact=[...displayed,{time:2,close:99},{time:3,close:98}];
 const c={settings:{type:'Renko'},completedBrickSignalView:()=>true,window:{RenkoAiChartSource:{context:()=>({run:'owned'}),signalBars:()=>exact}},location:{href:'https://example.test'},rows:[{time:60,close:100}],displayedBars:displayed,chartSymbol:()=> 'PAXGUSD',chartGestureActive:()=>false,updateLastPrice:()=>{while(displayed.length<exact.length){displayed.push(exact[displayed.length]);appended++;}return true;},noteOwnedRenkoTail:()=>noted++,redrawKeepingViewport:()=>redraws++,reconcileRecentBars:()=>{throw Error('Unnecessary history replay');}};
 vm.createContext(c);vm.runInContext(source.slice(start,end)+';syncOwnedRenkoSignals();syncOwnedRenkoSignals();',c);
 assert.equal(appended,2);assert.equal(noted,1);assert.equal(redraws,0);assert.equal(c.rows.length,1);
 c.chartGestureActive=()=>true;exact.push({time:4,close:97});vm.runInContext('syncOwnedRenkoSignals()',c);assert.equal(displayed.length,3);
 c.chartGestureActive=()=>false;vm.runInContext('syncOwnedRenkoSignals()',c);assert.equal(displayed.length,4);
});
test('actual PAXG captured tail appends both missing confirmed bricks using the renderer updater',()=>{
 const points=require('./fixtures/paxg-owned-brick-tail-20261127.json');
 const updater=source.slice(source.lastIndexOf('      updateLastPrice = bar => {'),source.indexOf('      reconcileRecentBars =',source.lastIndexOf('      updateLastPrice = bar => {')));
 const helpers=source.slice(source.indexOf('  function matchingChartBars('),source.indexOf('  function pinePlotsChangeAtTail('))+source.slice(source.indexOf('  function sameCandle('),source.indexOf('  function fyersFormingLiveBar('));
 const plotted=points.slice(0,3),cache=points.slice(),updates=[];let ltpWrites=0;
 const c={ownedProjectionContext:true,completedProjection:{refresh(){}},settings:{},renkoBoxSize:()=>1.6304347826086956,completedRenkoCandles:()=>[],chartTickSize:()=>.01,size:1.6304347826086956,bars:plotted,chartRenkoBricks:()=>cache.slice(),renkoSourceGeometryChanged:()=>false,renkoSourceByTime:new Map(),renkoProjectionReplaced:()=>false,drawingsNeedNewSeries:false,canUpdateRenkoStudies:true,studiesNeedConfirmedBricks:false,activeRenkoStudies:[],rebaseRenkoHistory:()=>{throw Error('Unexpected full replay');},brokerPriceLine:{applyOptions(){ltpWrites++;}},inspectedBarTime:()=>undefined,byTime:new Map(plotted.map(b=>[b.time,b])),cursorTime:undefined,firstBrickBySource:new Map(),indexes:new Map(),pendingSyntheticPlots:new Map(),mainSeries:{update:p=>updates.push(p),setData:()=>{throw Error('Unexpected replacement');}},pricePoint:b=>({...b}),studyUpdates:[],refreshAnchoredVwaps:[],refreshVolumeProfiles:()=>false,inspect(){},dataWindowPinned:false,updateLatestButton(){},chart:{timeScale:()=>({getVisibleLogicalRange:()=>({from:0,to:6})})},panel:{querySelector:()=>({textContent:''})},priceHistoryDetail:()=>''};
 vm.createContext(c);vm.runInContext(helpers+updater+';updateLastPrice({time:60,close:3660.3260869565215});updateLastPrice({time:60,close:3660.3260869565215});',c);
 assert.deepEqual(updates.map(p=>p.time),[5592,5593]);
 assert.equal(updates.at(-1).close,3657.065217391304);
 assert.equal(c.bars.length,5);assert.equal(ltpWrites,0,'a historical candle must not overwrite the live LTP line');
});
