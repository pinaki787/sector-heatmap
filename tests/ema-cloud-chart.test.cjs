const {test}=require('node:test');
const assert=require('node:assert/strict');
const {displayRows}=require('../ema-cloud-chart.js');
const {signals}=require('../ema-crossover.js');
const bars=Array.from({length:120},(_,i)=>({timestamp:300*i,open:100+i,high:102+i,low:99+i,close:101+i,volume:20}));
test('forming display does not change completed strategy signals or historical EMA values',()=>{
 const forming={timestamp:36000,open:220,high:400,low:200,close:400,is_forming:true};
 const completed=signals(bars),display=displayRows([...bars,forming]);
 assert.equal(display.length,121);assert.equal(display.at(-1).is_forming,true);
 assert.deepEqual(signals([...bars,forming]),completed);
 assert.deepEqual(display.slice(0,-1).map(c=>[c.fast,c.slow]),completed.map(c=>[c.fast,c.slow]));
 const revised=displayRows([...bars,{...forming,close:300}]);
 assert.deepEqual(revised.slice(0,-1),display.slice(0,-1));
 assert.notEqual(revised.at(-1).fast,display.at(-1).fast);
});
test('RSI warmup and SMA only publish when enough source values exist',()=>{
 const rows=displayRows(bars);
 assert.equal(rows[13].rsi,null);assert.equal(rows[14].rsi,100);
 assert.equal(rows[26].rsiMa,null);assert.equal(rows[27].rsiMa,100);
});
test('completed RSI trading signals agree with display values and exclude forming reversal',()=>{
 const {rsiSignals}=require('../ema-crossover.js');
 const inputs=Array.from({length:80},(_,i)=>({timestamp:i*300,open:100+i%2,high:100+i%2,low:100+i%2,close:100+i%2}));
 const last={timestamp:80*300,open:110,high:110,low:110,close:110};
 const result=rsiSignals([...inputs,last]);assert.equal(result.at(-1).signal,null); // Continued above-MA relation is not a new cross.
 const inverse=inputs.map((c,i)=>({...c,open:101-i%2,high:101-i%2,low:101-i%2,close:101-i%2}));assert.equal(rsiSignals([...inverse,last]).at(-1).signal,'CALL');
 assert.deepEqual(rsiSignals([...inputs,last,{...last,timestamp:81*300,close:1,is_forming:true}]),result);
 assert.deepEqual(rsiSignals([...inputs,last].slice(0,60)),result.slice(0,60));
 assert.equal(rsiSignals(inputs.map(c=>({...c,open:100,high:100,low:100,close:100}))).at(-1).signal,null);
});
test('London and New York session boundaries use their local DST rules',()=>{
 const {sessionBands}=require('../ema-cloud-chart.js');
 const stamp=s=>Date.parse(s)/1000;
 const rows=['2026-10-01T06:55:00Z','2026-10-01T07:00:00Z','2026-11-02T07:55:00Z','2026-11-02T08:00:00Z'].map(t=>({timestamp:stamp(t)}));
 const london=sessionBands(rows,[{name:'London',timezone:'Europe/London',start:'08:00',end:'17:00'}]);
 assert.deepEqual(london.map(b=>b.from),[stamp('2026-10-01T07:00:00Z'),stamp('2026-11-02T08:00:00Z')]);
 const nyRows=['2026-10-01T11:55:00Z','2026-10-01T12:00:00Z','2026-11-02T12:55:00Z','2026-11-02T13:00:00Z'].map(t=>({timestamp:stamp(t)}));
 assert.deepEqual(sessionBands(nyRows,[{name:'New York',timezone:'America/New_York',start:'08:00',end:'17:00'}]).map(b=>b.from),[stamp('2026-10-01T12:00:00Z'),stamp('2026-11-02T13:00:00Z')]);
});
test('EMA smoothing seeds from first valid Wilder RSI and recurs without future leakage',()=>{
 const input=[100,102,101,103,102,104,101].map((close,i)=>({timestamp:i*300,open:close,high:close,low:close,close}));
 const rows=displayRows(input,10,30,2,3,'EMA');assert.equal(rows[1].rsiMa,null);assert.equal(rows[2].rsiMa,rows[2].rsi);assert.ok(Math.abs(rows[3].rsiMa-(rows[2].rsi+.5*(rows[3].rsi-rows[2].rsi)))<1e-10);
 assert.deepEqual(displayRows(input.slice(0,4),10,30,2,3,'EMA'),rows.slice(0,4));
});

test('crowded Fib, period and zone captions stay separate while level anchors remain exact',()=>{
 const {paintCaptions}=require('../ema-cloud-chart.js'),boxes=[];const labels=Array.from({length:18},(_,i)=>({text:'LONDON O '+i,x:280,y:170+(i%3),color:'#537ee7',bg:'#131722'}));
 labels.push({text:'DEMAND 8735–8764',x:650,y:171,color:'#eee',bg:'#235e56'},{text:'Current Week High',x:12,y:171,color:'#ce72c5',bg:'#131722'});const original=JSON.parse(JSON.stringify(labels));
 const ctx={measureText:t=>({width:t.length*6}),fillRect:(x,y,w,h)=>boxes.push({x,y,w,h}),fillText(){},setLineDash(){},beginPath(){},moveTo(){},lineTo(){},stroke(){}};paintCaptions(ctx,labels,900,380);assert.equal(boxes.length,labels.length);assert.deepEqual(labels,original);
 for(let i=0;i<boxes.length;i++){const a=boxes[i];assert.ok(a.x>=0&&a.x+a.w<=900&&a.y>=0&&a.y+a.h<=384);for(const b of boxes.slice(i+1))assert.ok(!(a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y));}
});

test('Bollinger uses close SMA and population deviation with warmup and no future leakage',()=>{
 const {bollingerRows}=require('../ema-cloud-chart.js'),bars=[1,2,3,4].map((close,timestamp)=>({timestamp,close}));const r=bollingerRows(bars,3,2);assert.deepEqual(r[1],{time:1});assert.equal(r[2].middle,2);assert.equal(r[2].upper,2+2*Math.sqrt(2/3));assert.equal(r[2].lower,2-2*Math.sqrt(2/3));assert.deepEqual(bollingerRows(bars.slice(0,3),3,2),r.slice(0,3));assert.throws(()=>bollingerRows(bars,1,2));assert.throws(()=>bollingerRows(bars,20,0));
});

test('ADX graph uses Wilder warmup and excludes forming candle values',()=>{const {adxRows}=require('../ema-cloud-chart.js');const rows=Array.from({length:50},(_,i)=>({timestamp:i*300,high:102+i,low:99+i,close:101+i}));const values=adxRows(rows);assert.equal(values[26].value,undefined);assert.equal(values[27].value,100);assert.equal(values[49].value,100);rows[49].is_forming=true;assert.equal(adxRows(rows)[49].value,undefined);assert.equal(adxRows(rows.map(r=>({...r,high:100,low:100,close:100,is_forming:false})))[49].value,0);});
test('Renko emits full close-based bricks, uses two-brick reversals and excludes forming prices',()=>{
 const {renkoRows}=require('../ema-cloud-chart.js');
 const rows=[100,103,102,101,104].map((close,i)=>({timestamp:i*60,close}));
 const bricks=renkoRows(rows,1);
 assert.deepEqual(bricks.map(b=>[b.open,b.close]),[[100,101],[101,102],[102,103],[102,101],[102,103],[103,104]]);
 assert.ok(bricks.every((b,i)=>!i||b.time>bricks[i-1].time));
 assert.deepEqual(renkoRows([...rows,{timestamp:300,close:120,is_forming:true}],1),bricks);
 assert.deepEqual(renkoRows(rows.slice(0,3),1),bricks.slice(0,3));
 assert.throws(()=>renkoRows(rows,0),/greater than zero/);
 assert.throws(()=>renkoRows([{timestamp:0,close:100},{timestamp:60,close:10000}],1),/increase brick size/);
});
