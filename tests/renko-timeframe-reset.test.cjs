const {test}=require('node:test'),assert=require('node:assert/strict');
const {renkoChartSeries,chartPreviewPolicy}=require('../renko-supertrend.js');
test('clearing a study cannot repopulate old timeframe bricks',()=>{
 const rows=[];const chart={uniformRenkoRows:[{time:1,close:10,supertrend:9,ema10:8}],addLineSeries:()=>({setData:points=>rows.push(points),update:()=>{}})};
 renkoChartSeries(chart,'line');const st=chart.addLineSeries({title:'1-minute Supertrend'});
 st.setData([{time:1,value:9}]);assert.equal(rows.at(-1)[0].value,9);
 st.setData([]);assert.deepEqual(rows.at(-1),[]);
 chart.uniformRenkoRows=[{time:2,close:20,supertrend:19,ema10:18}];
 st.setData([{time:2,value:19}]);assert.deepEqual(rows.at(-1),[{time:2,value:19,color:'#26a69a'}]);
 st.setData([]);assert.deepEqual(rows.at(-1),[]);
 chart.uniformRenkoRows=[{time:3,close:30,supertrend:29}];st.setData([{time:3,value:29}]);assert.equal(rows.at(-1)[0].time,3);
});
test('unready timeframe with live ticks cannot draw provisional bricks',()=>{
 for(const basis of ['draft','active','recorded'])assert.match(chartPreviewPolicy({basis},0,false),/withheld until its confirmed analysis is ready/);
 assert.equal(chartPreviewPolicy({basis:'draft'},0,true),null);
 assert.match(chartPreviewPolicy({basis:'draft'},1,true),/withheld/);
});
test('selected historical chart shows one computed signal set; active chart uses only actual fills',()=>{
 const fs=require('node:fs'),vm=require('node:vm');const src=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 const start=src.indexOf('    function paintMarkers()'),end=src.indexOf('    function paintPnl(',start);
 let plotted,basis='draft';const context={chart:{},historicalMarkers:[{time:1,text:'SELL',shape:'arrowDown',position:'aboveBar'}],lastRunner:{config:{underlying:'BTCUSD',timeframe:'1 minute'},execution_signals:[{timestamp:1,direction:'BEARISH',status:'FILLED'}]},paintEntryPrice:()=>{},boundChartContext:()=>({basis}),executionMarkers:require('../renko-supertrend.js').executionMarkers,mapExecutionMarkers:require('../renko-supertrend.js').mapExecutionMarkers,el:id=>({value:id==='symbol'?'BTCUSD':'1 minute'}),candles:{setMarkers:m=>plotted=m}};
 vm.createContext(context);vm.runInContext(src.slice(start,end)+'paintMarkers();',context);assert.deepEqual(plotted,context.historicalMarkers);
 basis='active';vm.runInContext('paintMarkers()',context);assert.deepEqual(plotted,[]);
});
