const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {mountCompletedRenkoProjection}=require('../chart-renko-study-alignment.js');
function fixture(){let bars=[{time:1,sourceTime:100,open:100,close:110,high:110,low:100,provisional:false}],enabled=true,sets=[],updates=[];
 const mounted=mountCompletedRenkoProjection({chart:{addCandlestickSeries:options=>({setData:data=>sets.push(data),update:data=>updates.push(data)})},getBars:()=>bars,size:10,enabled:()=>enabled});
 return {mounted,sets,updates,bars,setBars:b=>bars=b,disable:()=>enabled=false};}
test('confirmed signal array stays unchanged while partial tail moves incrementally',()=>{const f=fixture(),before=JSON.stringify(f.bars);
 f.mounted.update(114,101);assert.equal(f.sets.at(-1)[0].close,114);assert.equal(f.sets.at(-1)[0].provisional,true);
 f.mounted.update(115,102);assert.equal(f.updates.length,1);assert.equal(f.updates[0].time,2);assert.equal(f.updates[0].close,115);
 assert.equal(JSON.stringify(f.bars),before);
 f.mounted.update(115,102);assert.equal(f.updates.length,1);
});
test('full price crossings remain display-only until authoritative signal arrives',()=>{const f=fixture();f.mounted.update(123,101);
 assert.deepEqual(f.sets.at(-1).map(b=>[b.time,b.close,b.provisional]),[[2,120,true],[3,123,true]]);
 f.setBars([...f.bars,{time:2,sourceTime:101,open:110,close:120}]);f.mounted.refresh();assert.deepEqual(f.sets.at(-1).map(b=>[b.time,b.close]),[[3,123]]);
});
test('reversal offset, zero remainder, unavailable quotes and toggle clear tail',()=>{const f=fixture();f.mounted.update(97,101);assert.equal(f.sets.at(-1)[0].open,100);assert.equal(f.sets.at(-1)[0].close,97);
 f.mounted.update(110,102);assert.deepEqual(f.sets.at(-1),[]);
 f.mounted.update(114,103);f.mounted.update(null,104);assert.deepEqual(f.sets.at(-1),[]);
 f.mounted.update(114,105);f.disable();f.mounted.refresh();assert.deepEqual(f.sets.at(-1),[]);
});
test('bundled browser helper matches canonical helper',()=>{const canonical=fs.readFileSync('chart-renko-study-alignment.js','utf8'),bundle=fs.readFileSync('chart-workspace-studies.js','utf8');
 const start=canonical.indexOf('  // A separate display series'),end=canonical.indexOf('  function calculateRenkoTimeframeStudy',start);assert.ok(bundle.includes(canonical.slice(start,end)));
});
test('15000 confirmed bricks are not resent during 1000 price updates',()=>{const f=fixture();f.setBars(Array.from({length:15000},(_,i)=>({...f.bars[0],time:i+1})));const start=performance.now();
 for(let i=0;i<1000;i++)f.mounted.update(111+(i%80)/10,200+i);
 assert.equal(f.sets.length,1);assert.equal(f.updates.length,999);assert.equal(f.sets[0].length,1);
 console.log(JSON.stringify({workload:'15000 confirmed bricks, 1000 quote updates',milliseconds:performance.now()-start,historyPointsSent:0,projectionPointsSent:1000,networkRequests:0}));
});

test('AI chart links enable forming display while ordinary strategy links preserve their default',()=>{
 const {embeddedRenkoChartUrl}=require('../renko-supertrend.js');
 for(const ai of [false,true]){const url=new URL(embeddedRenkoChartUrl('https://example.test/',{accountId:'delta',broker:'DELTA_INDIA',symbol:'PAXGUSD',timeframe:'1 minute',brick:1.5217391304347827,ai}));assert.equal(url.searchParams.get('projection'),ai?'1':'0');}
});

test('unfinished counter-direction remainder stays visible without committing a reversal',()=>{
 const f=fixture(),before=JSON.stringify(f.bars);
 f.mounted.update(107,101);
 assert.deepEqual(f.sets.at(-1).map(b=>[b.open,b.close,b.provisional,b.reversalPending]),[[110,107,true,true]]);
 f.mounted.update(106,102);assert.equal(f.updates.at(-1).close,106);
 assert.equal(JSON.stringify(f.bars),before);
 f.mounted.update(99,103);assert.equal(f.updates.at(-1).open,100);
 assert.equal(f.updates.at(-1).close,99);
 assert.equal(JSON.stringify(f.bars),before);
});
test('Laurus observed partial move is drawn at exact price with frozen completed-brick input',()=>{
 const bars=[{time:161,sourceTime:1795752304,open:2508.3333333333335,close:2516.666666666667}];
 const original=JSON.stringify(bars);let points;
 const p=mountCompletedRenkoProjection({chart:{addCandlestickSeries:()=>({setData:v=>points=v,update:v=>points=[v]})},getBars:()=>bars,size:100/12});
 p.update(2513.8,1795752679);
 assert.equal(points[0].close,2513.8);assert.equal(points[0].open,2516.666666666667);
 assert.equal(points[0].provisional,true);assert.equal(points[0].reversalPending,true);
 assert.equal(JSON.stringify(bars),original);
});
