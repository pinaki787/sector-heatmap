const {test}=require('node:test'),assert=require('node:assert/strict');
const {provisionalRenkoBricks,renkoStudyPoints}=require('../renko-supertrend.js');
test('price previews keep a stable axis time across ticks until a real brick arrives',()=>{
 const b=[{time:100.333,source_timestamp:100,open:90,close:100}];
 const a=provisionalRenkoBricks(b,{timestamp:101,close:105},10,true);
 const c=provisionalRenkoBricks(b,{timestamp:150,close:108},10,true);
 assert.equal(a[0].time,c[0].time);assert.notEqual(a[0].progress,c[0].progress);
 const multi=provisionalRenkoBricks(b,{timestamp:151,close:125},10,true);assert.equal(a[0].time,multi[0].time);
});
test('fractional price indicator times map onto displayed Renko times without phantom slots',()=>{
 const bricks=[{time:10.333,source_timestamp:10,indicator_timestamp:10},{time:20.833,source_timestamp:20,indicator_timestamp:20.5}];
 const out=renkoStudyPoints([{time:10,value:2},{time:20.5,value:3}],bricks);
 assert.deepEqual(out,[{time:10.333,value:2},{time:20.833,value:3}]);
 assert.deepEqual(renkoStudyPoints(out,bricks),out);
});

test('preview viewport restoration runs after the chart rebuilds provisional axis slots',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),src=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 const start=src.indexOf('    function paintBrickPreview('),end=src.indexOf("      el('brick-preview-status').hidden",start);
 let range={from:20,to:60};const frames=[],host={},scale={getVisibleLogicalRange:()=>({...range}),setVisibleLogicalRange:r=>{range={...r}},options:()=>({barSpacing:12})};
 const chart={uniformRenkoRows:[{time:100,source_timestamp:100,open:90,close:100,box:10}],timeScale:()=>scale,addCandlestickSeries:()=>({setData:()=>{}})};
 const context={chart,el:id=>id==='chart'?host:id==='chart-view'?{value:'synthetic'}:{},lastRunner:{config:{renko_confirmation:'PRICE'}},statusFrame:{},provisionalRenkoBricks,requestAnimationFrame:fn=>frames.push(fn),Date,Number,Math};
 vm.createContext(context);vm.runInContext('let previewBrickSeries=null,previewBrickFillSeries=null,previewViewportVersion=0,previewAxisAnchor=null,previewAxisTimes=[];'+src.slice(start,end)+'}paintBrickPreview({timestamp:101,close:105});',context);
 assert.equal(frames.length,1);
 // Lightweight Charts applies its queued data-axis change on the browser frame.
 range={from:19,to:59};frames.shift()();frames.shift()();
 assert.deepEqual(range,{from:20,to:60});
 assert.equal(host.renkoViewportAudit[0].after.from,20);
});
