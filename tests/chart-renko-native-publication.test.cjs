const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
require('../chart-workspace-studies.js');
const lib=globalThis.SectorPulseChartStudies,engine=require('../chart-renko-study-alignment.js');
for(const folder of ['renko-live-rollover-20261120','renko-value-change-20261120']){
 test('every native published host row remains aligned: '+folder,()=>{
  const f='.private/chart-order-rollouts/'+folder+'/';
  const wire=JSON.parse(fs.readFileSync(f+'native-wire.json','utf8'));
  const history=JSON.parse(fs.readFileSync(f+'broker-history-after.json','utf8')).result.sort((a,b)=>a.time-b.time);
  const events=new Map();
  for(const e of wire){if(!['du','timescale_update'].includes(e.packet.m))continue;
   for(const v of Object.values(e.packet.p[1]))if(v?.t==='s2_st3')for(const row of v.st??[]){
    if(!events.has(e.received_at))events.set(e.received_at,new Map());
    events.get(e.received_at).set(row.v[0],row.v[1]);
   }
  }
  assert.ok(events.size>=2);
  const expected=new Map(),publication={};let checks=0;
  for(const [at,updates]of events){
   const cutoff=Math.floor(at/300)*300;
   const before=new Map(expected);
   for(const [clock,value]of updates)expected.set(clock,value);
   const clocks=[...expected.keys()].sort((a,b)=>a-b);
   const host=clocks.map(clock=>({sourceTime:Math.floor(clock/60)*60}));
   const calculate=bars=>engine.calculateRenkoTimeframeStudy({sourceBars:history.filter(b=>b.time+300<=cutoff),hostBars:bars,renko:lib.renko,
    run:b=>lib.indicators.SMA.run(b,b.map(x=>x.close),5,undefined,{}),size:10,source:'close',waitForClose:false,
    liveState:{live:true,now:at,updatedAt:at,confirmedThrough:cutoff},publication});
   // Seed the prior current host before observing the first appended batch.
   if(!before.size)calculate(host.slice(0,1));
   const output=calculate(host).plots[0];
   for(let i=0;i<clocks.length;i++){assert.equal(output[i],expected.get(clocks[i]),'host '+clocks[i]+' at '+at);checks++;}
  }
  console.log(JSON.stringify({folder,publicationChecks:checks,nativeValues:[...new Set(expected.values())]}));
 });
}

test('publication state is scoped to the same study, request and settings',()=>{
 const study={},scope={},one=engine.renkoStudyPublication(study,scope,'a');
 assert.equal(engine.renkoStudyPublication(study,scope,'a'),one);
 assert.notEqual(engine.renkoStudyPublication(study,scope,'b'),one);
 assert.notEqual(engine.renkoStudyPublication(study,{},'a'),one);
 assert.equal(engine.renkoStudyPublication(study,{aborted:true},'a'),undefined);
});
test('published rows and colors persist while a new batch updates the prior tail and all appended rows',()=>{
 const state={},ref=[{sourceTime:100}],source=[[20]],options={live:true,now:500,updatedAt:500,confirmedThrough:200};
 source[0].colors=['green'];
 const old=[{sourceTime:100},{sourceTime:150}];
 engine.applyRenkoStudyPublication([[1,2]],source,ref,old,options,state);
 const host=[...old,{sourceTime:250},{sourceTime:250}];
 const result=engine.applyRenkoStudyPublication([[1,2,2,2]],source,ref,host,options,state);
 assert.deepEqual([...result[0]],[1,20,20,20]);
 assert.deepEqual(result[0].colors,[undefined,'green','green','green']);
 source[0][0]=30;source[0].colors[0]='red';
 const later=engine.applyRenkoStudyPublication([[1,2,2,2]],source,ref,host,options,state);
 assert.deepEqual([...later[0]],[1,20,20,30]);
 assert.deepEqual(later[0].colors,[undefined,'green','green','red']);
 const stale=engine.applyRenkoStudyPublication([[1,2,2,2]],source,ref,host,{...options,updatedAt:400},state);
 assert.deepEqual([...stale[0]],[1,20,20,30]);
 const replay=engine.applyRenkoStudyPublication([[1,2,2,2]],source,ref,host,{...options,live:false},state);
 assert.deepEqual(replay,[[1,2,2,2]]);
});

