const {test}=require('node:test'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
const {entrySignals,preserveRange}=require('../ema-cloud-chart.js'),{fibonacciReferences,referencesForView}=require('../redbar-overlays.js');
test('Delta browser touch signals match backend for both directions, crossover priority and forming exclusion',()=>{
 const bars=[100,102,101,103,102,105,106,107,106,104,103,102].map((c,i)=>({timestamp:i*300+1,open:c,close:c,high:c+20,low:c-20}));bars.push({...bars.at(-1),timestamp:3601,is_forming:true});
 const python=JSON.parse(execFileSync('.venv/bin/python',['-c',"import json,sys;from sector_heatmap.delta_signals import delta_rsi_series;print(json.dumps(delta_rsi_series(json.load(sys.stdin),3,3,'EMA')))"],{input:JSON.stringify(bars),encoding:'utf8'}));
 const browser=entrySignals(bars,3,3,'EMA');assert.equal(browser.length,python.length);for(let i=0;i<browser.length;i++)for(const field of ['cross_direction','entry_direction','entry_reason','touch_evidence'])assert.deepEqual(browser[i][field],python[i][field]);
});
test('latest view excludes carried sessions and future London; historical view restores original O/R refs',()=>{
 const stamp=s=>Date.parse(s)/1000,bars=['2026-10-01T12:00Z','2026-10-01T12:05Z','2026-10-02T00:00Z','2026-10-02T00:05Z','2026-10-02T06:55Z'].map((s,i)=>({timestamp:stamp(s),open:100,high:110,low:90,close:i%2?95:105}));
 const refs=fibonacciReferences(bars),latest=referencesForView(refs,bars,{from:0,to:5});assert.ok(latest.fixed.every(f=>f.name==='ASIA'));assert.deepEqual(latest.markers.map(m=>m.name),['ASIA']);
 const historical=referencesForView(refs,bars,{from:0,to:1});assert.ok(historical.fixed.some(f=>f.name==='NEW YORK'));assert.equal(historical.fixed.find(f=>!f.opening).timestamp,bars[1].timestamp);
 const beforeAsia=[{...bars[0],timestamp:stamp('2026-10-01T12:00Z')},{...bars[1],timestamp:stamp('2026-10-01T20:00Z')}];assert.equal(referencesForView(fibonacciReferences(beforeAsia),beforeAsia,{from:0,to:2}).fixed.length,0);
});
test('historical viewport follows timestamp anchors when rolling history drops left candles',()=>{
 const old=Array.from({length:100},(_,i)=>({timestamp:i*300})),next=old.slice(1).concat({timestamp:30000});assert.deepEqual(preserveRange(old,next,{from:25.5,to:60.5},false),{from:24.5,to:59.5});assert.deepEqual(preserveRange(old,next,{from:20,to:108},true),{from:20,to:108});
});
