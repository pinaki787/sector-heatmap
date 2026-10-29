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
