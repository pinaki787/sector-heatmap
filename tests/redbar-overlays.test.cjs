const {test}=require('node:test'),assert=require('node:assert/strict');
const {supplyDemand,sessionMarkers}=require('../redbar-overlays.js');
const start=Date.parse('2026-10-01T03:30:00Z')/1000;
const base=Array.from({length:40},(_,i)=>({timestamp:start+i*300,open:100,high:102,low:98,close:100}));
test('Pine compact-base/ATR departure creates strong supply and tracks retests and close breaches',()=>{
 const departure={timestamp:start+40*300,open:100,high:101,low:91,close:92};
 const zones=supplyDemand([...base,departure],'MCX:TESTFUT');assert.equal(zones.length,1);assert.equal(zones[0].supply,true);assert.equal(zones[0].strong,true);assert.deepEqual([zones[0].low,zones[0].high],[100,102]);assert.equal(zones[0].touches,0);
 const touch={timestamp:start+41*300,open:97,high:101,low:95,close:97};
 const retested=supplyDemand([...base,departure,touch],'MCX:TESTFUT');assert.equal(retested[0].touches,1);
 const breach={timestamp:start+42*300,open:101,high:104,low:100,close:103};assert.equal(supplyDemand([...base,departure,touch,breach],'MCX:TESTFUT').filter(z=>z.supply).length,0);
 assert.deepEqual(supplyDemand([...base,departure,{...breach,is_forming:true}],'MCX:TESTFUT'),zones);
});
test('Pine zones respect commodity/equity exchange sessions',()=>{
 const at9=base.slice(0,20).map(c=>({...c,timestamp:c.timestamp-9*3600}));assert.deepEqual(supplyDemand(at9,'MCX:TESTFUT'),[]);
});
test('Pine scheduled session openings match source defaults and DST conversion',()=>{
 const today=sessionMarkers([{timestamp:Date.parse('2026-10-01T10:00:00Z')/1000}]);
 assert.deepEqual(today.map(s=>new Date(s.timestamp*1000).toISOString()),['2026-10-01T00:00:00.000Z','2026-10-01T07:00:00.000Z','2026-10-01T12:00:00.000Z']);
 const winter=sessionMarkers([{timestamp:Date.parse('2026-11-02T10:00:00Z')/1000}]);assert.equal(new Date(winter[1].timestamp*1000).toISOString(),'2026-11-02T08:00:00.000Z');assert.equal(new Date(winter[2].timestamp*1000).toISOString(),'2026-11-02T13:00:00.000Z');
});
test('zone lifecycle preserves wick touches, counts contiguous visits once and expires by source age',()=>{
 const departure={timestamp:start+40*300,open:100,high:101,low:91,close:92};
 const touches=Array.from({length:3},(_,i)=>({timestamp:start+(41+i)*300,open:97,high:103,low:95,close:97}));
 const initial=supplyDemand([...base,departure,...touches],'MCX:TESTFUT').find(z=>z.supply&&z.low===100);assert.ok(initial);assert.equal(initial.touches,1);
 const away={timestamp:start+44*300,open:96,high:99,low:93,close:95};
 const second={timestamp:start+45*300,open:97,high:101,low:95,close:97};
 assert.equal(supplyDemand([...base,departure,...touches,away,second],'MCX:TESTFUT').find(z=>z.supply&&z.low===100).touches,2);
 const later=Array.from({length:12},(_,i)=>({timestamp:start+(41+i)*300,open:94,high:95,low:93,close:94}));
 assert.equal(supplyDemand([...base,departure,...later],'MCX:TESTFUT',{age:10}).filter(z=>z.supply&&z.low===100).length,0);
});
test('fixed red Fibonacci excludes session-opening red; floating includes latest confirmed red',()=>{
 const {fibonacciReferences}=require('../redbar-overlays.js');
 const bars=[{timestamp:Date.parse('2026-10-01T03:30:00Z')/1000,open:100,high:110,low:90,close:95},{timestamp:Date.parse('2026-10-01T03:35:00Z')/1000,open:95,high:100,low:90,close:96},{timestamp:Date.parse('2026-10-01T03:40:00Z')/1000,open:96,high:99,low:89,close:90}];
 const first=fibonacciReferences(bars.slice(0,2));assert.equal(first.fixed.length,3);assert.equal(first.floating[0].timestamp,bars[0].timestamp);assert.equal(first.floating[0].price,110-20*.382);
 const full=fibonacciReferences(bars);assert.equal(full.fixed.length,6);assert.equal(full.fixed.filter(f=>!f.opening)[0].timestamp,bars[2].timestamp);
 assert.deepEqual(fibonacciReferences([...bars,{...bars[2],timestamp:bars[2].timestamp+300,close:1,is_forming:true}]),full);
});

test('daily reference CPR uses previous day and period ranges include developing price',()=>{
 const {dailyReferences}=require('../redbar-overlays.js');const stamp=s=>Date.parse(s)/1000;
 const refs=dailyReferences([[stamp('2026-09-30T00:00:00Z'),100,110,90,105],[stamp('2026-10-01T00:00:00Z'),105,112,101,108]],120,stamp('2026-10-01T10:00:00Z'));
 assert.equal(refs.find(r=>r.name==='CPR Pivot').price,305/3);assert.equal(refs.find(r=>r.name==='Current Month High').price,120);assert.equal(refs.find(r=>r.name==='Current Week Low').price,90);
});
