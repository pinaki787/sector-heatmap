const test=require('node:test'),assert=require('node:assert/strict');
const {markers}=require('../renko-ai-chart-markers.js');
test('confirmed exact contract fills attach to the final confirmed brick of that source bar',()=>{
 const bars=[{time:1,sourceTime:100},{time:2,sourceTime:100},{time:3,sourceTime:200,provisional:true}];
 const events=[{symbol:'CE-A',timestamp:100,action:'BUY',mode:'PAPER',confirmed:true,price:40.1234},{symbol:'CE-B',timestamp:100,action:'SELL',confirmed:true},{symbol:'CE-A',timestamp:200,action:'SELL',confirmed:true},{symbol:'CE-A',timestamp:100,action:'SELL',confirmed:false}];
 assert.deepEqual(markers(events,bars,'CE-A'),[{time:2,position:'belowBar',color:'#26a69a',shape:'arrowUp',text:'PAPER ENTRY 40.12'}]);
 assert.deepEqual(markers(events,bars,'UNDERLYING'),[]);
});


test('confirmed fill without a new source-bar brick attaches only to the latest preceding confirmed brick',()=>{
 const {markers}=require('../renko-ai-chart-markers.js');
 const result=markers([{symbol:'EXACT',source_timestamp:180,timestamp:181,confirmed:true,action:'BUY',mode:'PAPER',price:40}],
 [{time:1,sourceTime:60},{time:2,sourceTime:120},{time:3,sourceTime:240},{time:4,sourceTime:150,provisional:true}],'EXACT');
 assert.equal(result.length,1);assert.equal(result[0].time,2);assert.equal(result[0].text,'PAPER ENTRY 40.00');
 assert.deepEqual(markers([{symbol:'EXACT',timestamp:1,confirmed:true,action:'BUY',mode:'LIVE'}],[{time:1,sourceTime:60}],'EXACT'),[]);
});
