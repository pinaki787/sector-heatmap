
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync(process.env.CHART_SOURCE||'.private/chart-order-rollouts/renko-projection-tail-update-20261120/root/chart-workspace.js','utf8');
const classifier=source.slice(source.indexOf('  function sameRenkoBrick('),source.indexOf('  function matchingChartBars('));
const start=source.indexOf('    if (isRenko) {\n      // Shape primitives'),end=source.indexOf('    const canReconcilePriceSeries',start);
const run=new Function('bars','next',`
 ${classifier}
 const study={kind:'Pine',workerRuntime:true},settings={hideStudies:false,studies:[study]};
 const isRenko=true,size=10,drawings=[],shapes=[],priceFib=()=>false;
 const rangeStudies=[],pivotStudies=[],studyNotices=[],recolorStudies=[],studyVisible=()=>true;
 const renkoBoxSize=()=>size,completedRenkoCandles=()=>[],chartTickSize=()=>.5;
 const chartRenkoBricks=()=>next;
 const sameCandle=(a,b)=>['open','high','low','close','provisional'].every(k=>a[k]===b[k]);
 const matchingChartBars=(a,b)=>{let i=0;while(i<Math.min(a.length,b.length)&&sameCandle(a[i],b[i])&&a[i].sourceTime===b[i].sourceTime)i++;return i;};
 const renkoSourceByTime=new Map(),pendingSyntheticPlots=new Map(),firstBrickBySource=new Map();
 const byTime=new Map(bars.map(b=>[b.time,b])),indexes=new Map(bars.map((b,i)=>[b.time,i]));
 let updates=0,replacements=0,points=0,invalidations=0,studyRefreshes=0,updateLastPrice;
 const pineStudies=new Map(),overlay=()=>true;overlay.invalidateRenkoFrame=()=>invalidations++;
 const pineOverlayUpdates=new Map([[study,overlay]]);
 const range={from:200,to:300};let restored;
 const chart={timeScale:()=>({getVisibleLogicalRange:()=>range,setVisibleLogicalRange:r=>restored=r}),clearCrosshairPosition(){}},charts=[chart];
 const mainSeries={update:p=>{updates++;points++;},setData:p=>{replacements++;points+=p.length;}};
 const pricePoint=b=>({time:b.time,open:b.open,close:b.close});
 const studyUpdates=[()=>studyRefreshes++],brokerPriceLine={applyOptions(){}};
 const inspectedBarTime=()=>undefined;let dataWindowPinned=false,cursorTime,cursorLevel,horizontalShortcutPrice,shortcutDrawingAnchor,movingCrosshair;
 const clearDataWindowPin=()=>{},inspect=()=>{},updateLatestButton=()=>{},priceHistoryDetail=()=>'';
 const refreshAnchoredVwaps=[],refreshVolumeProfiles=()=>false,repaintDrawingAnchors=()=>{};
 const panel={querySelector:()=>({})};
 ${source.slice(start,end)}
 const ok=updateLastPrice({time:500000,close:next.at(-1).close,provisional:true});
 return {ok,updates,replacements,points,invalidations,studyRefreshes,restored,count:bars.length,last:bars.at(-1)};
`);
function fixture(){const bars=Array.from({length:15000},(_,i)=>({time:i+1,sourceTime:i,open:100,high:110,low:100,close:110,provisional:false}));bars.push({time:15001,sourceTime:500000,open:110,high:112,low:110,close:112,provisional:true});return bars;}
test('a changing partial Renko body updates one chart point rather than replacing15001 points',()=>{
 const bars=fixture(),next=bars.map(b=>({...b}));next.at(-1).high=next.at(-1).close=113.5;const r=run(bars,next);
 assert.equal(r.ok,true);assert.equal(r.updates,1);assert.equal(r.replacements,0);assert.equal(r.points,1);
 assert.equal(r.invalidations,1);assert.equal(r.studyRefreshes,1);assert.deepEqual(r.restored,{from:200,to:300});assert.equal(r.last.close,113.5);
});
test('removing or reusing a projected suffix still replaces the series and invalidates stale Pine geometry',()=>{
 for(const mode of ['remove','reverse']){const bars=fixture(),next=bars.map(b=>({...b}));if(mode==='remove')next.pop();else Object.assign(next.at(-1),{open:100,high:100,low:99,close:99});
 const r=run(bars,next);assert.equal(r.ok,true);assert.equal(r.updates,0);assert.equal(r.replacements,1);assert.equal(r.invalidations,1);assert.equal(r.studyRefreshes,1);}
});
