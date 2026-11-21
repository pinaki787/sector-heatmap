const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
require('../chart-workspace-studies.js');
const lib=globalThis.SectorPulseChartStudies,engine=require('../chart-renko-study-alignment.js');
const f='.private/chart-order-rollouts/renko-live-rollover-20261120/';
const audit=JSON.parse(fs.readFileSync(f+'audit.json','utf8'));
const history=JSON.parse(fs.readFileSync(f+'broker-history-after.json','utf8')).result.sort((a,b)=>a.time-b.time);
test('combined completed-reference path matches26 native wait-off updates across5m source close',()=>{
 assert.equal(audit.samples,26);assert.equal(audit.cutoffs.length,2);
 for(const sample of audit.observations){
  const bars=history.filter(b=>b.time<sample.cutoff);
  // An extreme developing candle must never enter confirmed reference studies.
  bars.push({time:sample.cutoff,open:1,high:100000,low:1,close:99999,provisional:true});
  const host=[{sourceTime:Math.floor(sample.hostTime/60)*60,open:62750,high:62750,low:62740,close:62740}];
  const result=engine.calculateRenkoTimeframeStudy({sourceBars:bars,hostBars:host,
   renko:lib.renko,run:b=>lib.indicators.SMA.run(b,b.map(x=>x.close),5,undefined,{}),
   size:10,source:'close',showWicks:false,waitForClose:false,
   liveState:{live:true,now:sample.at,updatedAt:sample.at,confirmedThrough:sample.cutoff}});
  assert.equal(result.plots[0].at(-1),sample.native,'native update '+sample.at);
  assert.ok(result.reference.every(b=>!b.provisional));
 }
});
test('captured source close inside reversal gap creates no extra confirmed reference brick',()=>{
 const cutoff=audit.cutoffs[1],before=history.filter(b=>b.time+300<=cutoff-300),after=history.filter(b=>b.time+300<=cutoff);
 const a=lib.renko(before,10,undefined,'close',false),b=lib.renko(after,10,undefined,'close',false);
 assert.equal(after.at(-1).close,62755);assert.equal(a.length,b.length);assert.equal(a.at(-1).close,62740);
});

