const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {closeRenkoProjection}=require('../chart-renko-study-alignment.js');
const folder='.private/chart-order-rollouts/renko-projection-isolated-20261120/';
test('Close-source projected geometry matches captured native updates after confirmed baseline',()=>{
 const capture=JSON.parse(fs.readFileSync(folder+'native-wire.json','utf8'));let previous,checked=0,partial=0;
 for(const event of capture){const packet=event.packet;if(!['du','timescale_update'].includes(packet.m))continue;
  const stream=packet.p[1].sds_1;if(!stream)continue;
  // One native frame can publish successive brick records with a shared receive
  // clock. Projection payload refers to the final confirmed state of that frame.
  const sameFrame=capture.filter(e=>e.received_at===event.received_at&&['du','timescale_update'].includes(e.packet.m));
  for(const e of sameFrame)for(const row of e.packet.p[1].sds_1?.s??[]){const v=row.v;previous={open:v[1],close:v[4]};}
  const raw=stream.ns?.d;if(!raw||!previous)continue;
  const data=JSON.parse(raw).data;if(!data||!Number.isFinite(data.price))continue;
  const actual=closeRenkoProjection(previous,data.price,data.boxSize,Math.floor(event.received_at/60)*60);
  const want=data.bars??[];
  assert.equal(actual.length,want.length,'projection count at '+event.received_at);
  for(let i=0;i<want.length;i++)for(const k of ['open','high','low','close'])assert.equal(actual[i][k],want[i][k],k+' at '+event.received_at);
  checked++;partial+=actual.some(b=>Math.abs(b.close-b.open)<data.boxSize);
 }
 assert.ok(checked>=20);assert.ok(partial>0);console.log(JSON.stringify({nativeProjectionUpdates:checked,partialUpdates:partial}));
});
test('projection reversal requires crossing one whole gap and never mutates confirmed brick',()=>{
 const prior={open:100,close:110};const original={...prior};
 assert.deepEqual(closeRenkoProjection(prior,100,10,1),[]);
 assert.deepEqual(closeRenkoProjection(prior,105,10,1),[]);
 assert.equal(closeRenkoProjection(prior,99,10,1)[0].open,100);
 assert.equal(closeRenkoProjection(prior,99,10,1)[0].close,99);
 assert.deepEqual(prior,original);
 assert.throws(()=>closeRenkoProjection(prior,90,0,1),/Invalid/);
});

