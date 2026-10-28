const {test}=require('node:test'),assert=require('node:assert/strict');
const {refreshChartViewport,runnerStartContext}=require('../renko-supertrend.js');
const rows=Array.from({length:100},(_,i)=>({time:i}));
test('live edge advances on append without resetting zoom',()=>{
 const r=refreshChartViewport(rows,[...rows,{time:100}],{from:70,to:102},true);
 assert.equal(r.follow,true);assert.deepEqual(r.range,{from:71,to:103});
});
test('manual history is anchored to time across rolling-window trimming',()=>{
 const r=refreshChartViewport(rows,[...rows.slice(5),{time:100}],{from:20.5,to:40.5},true);
 assert.equal(r.follow,false);assert.deepEqual(r.range,{from:15.5,to:35.5});
});
test('recorded eligible event is not retroactively excluded by later errors',()=>{
 const c=runnerStartContext(rows,{started_at:10,eligible_since:50,run_id:'r',config:{mode:'PAPER'},execution_signals:[{run_id:'r',event_at:30,eligible:true,status:'BLOCKED',reason:'Quote unavailable'}]},300);
 assert.equal(c.eventTiming,'AFTER_START');assert.equal(c.event.status,'BLOCKED');
});

test('mounted reset resolves the latest time on the actual mixed-series axis',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),src=fs.readFileSync('renko-supertrend.js','utf8');
 const a=src.indexOf("el('readable-chart').onclick=()=>"),b=src.indexOf(";el('fit-chart')",a);
 let range;const node={clientWidth:1000,clientHeight:600};
 const scale={applyOptions(){},timeToCoordinate:()=>400,coordinateToLogical:()=>1000,setVisibleLogicalRange:r=>{range=r}};
 const ctx={el:id=>id==='readable-chart'?button:node,chart:{applyOptions(){},priceScale:()=>({applyOptions(){}}),timeScale:()=>scale},plottedCount:100,currentPlotted:[{time:1234}],readableChartViewport:()=>({range:{from:60,to:120}}),isMotilal:false,rsiChart:null,positionAssessment(){}},button={};
 vm.createContext(ctx);vm.runInContext(src.slice(a,b),ctx);button.onclick();
 assert.equal(range.from,961);assert.equal(range.to,1021);
});
test('refresh follows the true axis index, not the smaller Renko row count',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),src=fs.readFileSync('renko-supertrend.js','utf8');
 const a=src.indexOf('if(previousRange&&same&&Number.isFinite(previousLastLogical))'),b=src.indexOf('if(!viewport.follow',a);
 const ctx={previousRange:{from:900,to:1020},same:true,previousLastLogical:1000,previousVisible:{from:1},previousLeftLogical:900,plotted:[{time:2}],logicalAt:t=>t===2?1001:901,viewport:{}};
 vm.createContext(ctx);vm.runInContext(src.slice(a,b),ctx);
 assert.equal(ctx.viewport.follow,true);assert.equal(ctx.viewport.range.from,901);assert.equal(ctx.viewport.range.to,1021);
 ctx.previousRange={from:400,to:500};ctx.previousLeftLogical=400;ctx.logicalAt=t=>t===2?1001:395;ctx.viewport={};
 vm.runInContext(src.slice(a,b),ctx);
 assert.equal(ctx.viewport.follow,false);assert.equal(ctx.viewport.range.from,395);assert.equal(ctx.viewport.range.to,495);
});
