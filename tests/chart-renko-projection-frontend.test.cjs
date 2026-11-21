
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
require('../chart-workspace-studies.js');const lib=globalThis.SectorPulseChartStudies,alignment=require('../chart-renko-study-alignment.js');
const source=fs.readFileSync(process.env.CHART_SOURCE||'.private/chart-order-rollouts/renko-close-projection-activation-20261120/root/chart-workspace.js','utf8');
const start=source.indexOf('  function chartRenkoBricks(size) {'),end=source.indexOf('  function completedRenkoCandles()',start);
assert.ok(start>=0&&end>start);
function run(rows,settings={},wicks=false){const c={rows,settings:{renkoSource:'close',...settings},renko:lib.renko,withRenkoVolume:require('../chart-renko-volume.js').withRenkoVolume,renkoWicksVisible:()=>wicks,window:{SectorPulseRenkoStudyAlignment:alignment}};vm.createContext(c);vm.runInContext(source.slice(start,end),c);return c.chartRenkoBricks(10);}
test('actual frontend displays native partial Close projections across captured live updates',()=>{
 const capture=JSON.parse(fs.readFileSync('.private/chart-order-rollouts/renko-projection-isolated-20261120/native-wire.json','utf8'));let previous,checked=0,partial=0;
 for(const event of capture){const packet=event.packet;if(!['du','timescale_update'].includes(packet.m))continue;const stream=packet.p[1].sds_1;if(!stream)continue;
  for(const e of capture.filter(e=>e.received_at===event.received_at&&['du','timescale_update'].includes(e.packet.m)))for(const row of e.packet.p[1].sds_1?.s??[]){const v=row.v;previous={open:v[1],close:v[4]};}
  if(!stream.ns?.d||!previous)continue;const data=JSON.parse(stream.ns.d).data;if(!data||!Number.isFinite(data.price))continue;
  assert.equal(data.boxSize,10);
  const bars=[{time:1,open:previous.open,high:previous.open,low:previous.open,close:previous.open},{time:2,open:previous.open,high:Math.max(previous.open,previous.close),low:Math.min(previous.open,previous.close),close:previous.close},{time:3,open:previous.close,high:Math.max(previous.close,data.price),low:Math.min(previous.close,data.price),close:data.price,provisional:true}];
  const original=JSON.stringify(bars),actual=run(bars),projected=actual.filter(b=>b.provisional),want=data.bars??[];
  assert.equal(projected.length,want.length,'native projection count at '+event.received_at);
  projected.forEach((b,i)=>{for(const key of ['open','high','low','close'])assert.equal(b[key],want[i][key],key);assert.equal(b.time,i+2);assert.equal(b.sourceTime,3);});
  assert.equal(JSON.stringify(bars),original);assert.equal(actual[0].open,previous.open);assert.equal(actual[0].close,previous.close);assert.equal(actual[0].provisional,false);
  checked++;partial+=projected.some(b=>Math.abs(b.close-b.open)<10);
 }
 assert.ok(checked>=80);assert.ok(partial>=70);console.log(JSON.stringify({frontendNativeProjectionUpdates:checked,partialUpdates:partial}));
});
test('projection toggle and unvalidated OHLC/wick modes preserve their existing construction',()=>{
 const bars=[{time:1,open:100,high:100,low:100,close:100},{time:2,open:100,high:110,low:100,close:110},{time:3,open:110,high:125,low:105,close:125,provisional:true}];
 assert.equal(run(bars,{renkoProjection:false}).length,1);
 for(const [settings,wicks] of [[{renkoSource:'ohlc'},false],[{},true]])assert.equal(JSON.stringify(run(bars,settings,wicks)),JSON.stringify(lib.renko(bars,10,undefined,settings.renkoSource||'close',wicks)));
 assert.equal(run(bars).at(-1).close,125);
 assert.equal(run(bars.slice(0,2)).length,1);
});
