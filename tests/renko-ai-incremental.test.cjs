const test=require('node:test'),assert=require('node:assert/strict');
require('../chart-workspace-studies.js');
const {renko}=globalThis.SectorPulseChartStudies;
const {OwnedRenkoCache}=require('../renko-ai-incremental.js');
test('incremental owned Renko equals complete recurrence through multibrick moves and reversals',()=>{
 const rows=[],cache=new OwnedRenkoCache(renko);
 for(const [i,close] of [100,100.2,101,103,102.5,100,98,99,103,105,104,100].entries()){
  rows.push({time:100+i/10,open:null,high:null,low:null,close,volume:null});
  assert.deepEqual(cache.build(rows,1,'run'),renko(rows,1,undefined,'close',false));
 }
});
test('unchanged source does no Renko recomputation and append processes only the tail',()=>{
 const counts=[],wrapped=(rows,...args)=>{counts.push(rows.length);return renko(rows,...args);};
 const cache=new OwnedRenkoCache(wrapped),rows=[{time:1,close:100},{time:2,close:102}];
 cache.build(rows,1,'run');cache.build(rows,1,'run');
 rows.push({time:3,close:103});cache.build(rows,1,'run');
 assert.deepEqual(counts,[2,1]);
});
test('scope, brick-size and source replacement rebuild; returned array cannot corrupt cache',()=>{
 const cache=new OwnedRenkoCache(renko),rows=[{time:1,close:100},{time:2,close:104}];
 const first=cache.build(rows,1,'one');first.pop();
 assert.equal(cache.build(rows,1,'one').length,4);
 assert.deepEqual(cache.build(rows,2,'one'),renko(rows,2,undefined,'close',false));
 const replacement=rows.map(r=>({...r}));replacement[0].close=99;
 assert.deepEqual(cache.build(replacement,1,'two'),renko(replacement,1,undefined,'close',false));
});
