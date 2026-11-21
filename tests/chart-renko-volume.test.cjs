
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {withRenkoVolume}=require('../chart-renko-volume.js');
const brick=(sourceTime,provisional=false)=>({time:sourceTime,sourceTime,open:100,high:110,low:100,close:110,provisional});
test('volume accumulates through candles with no brick and splits over every new brick',()=>{
 const source=[{time:1,volume:12},{time:2,volume:18},{time:3,volume:3},{time:4,volume:9}];
 const bricks=[brick(2),brick(2),brick(4),brick(4),brick(4)];
 const before=JSON.stringify({source,bricks}),out=withRenkoVolume(source,bricks);
 assert.deepEqual(out.map(b=>b.volume),[15,15,4,4,4]);assert.equal(out.reduce((n,b)=>n+b.volume,0),42);
 assert.equal(JSON.stringify({source,bricks}),before);
});
test('missing, negative or overflowing source volume remains unavailable until its emitted group ends',()=>{
 for(const volume of [undefined,null,NaN,-1,Infinity]){
  const out=withRenkoVolume([{time:1,volume},{time:2,volume:5},{time:3,volume:8}],[brick(2),brick(3)]);
  assert.equal(out[0].volume,null);assert.equal(out[1].volume,8);
 }
 assert.equal(withRenkoVolume([{time:1,volume:Number.MAX_VALUE},{time:2,volume:Number.MAX_VALUE}],[brick(2)])[0].volume,null);
 assert.equal(withRenkoVolume([{time:1,volume:0}],[brick(1)])[0].volume,0);
});
test('open-candle projection volume is zero and cannot consume confirmed source volume',()=>{
 const rows=[{time:1,volume:20},{time:2,volume:9,provisional:true}],bricks=[brick(1),brick(2,true),brick(2,true)];
 assert.deepEqual(withRenkoVolume(rows,bricks).map(b=>b.volume),[20,0,0]);rows[1].provisional=false;bricks[1].provisional=bricks[2].provisional=false;
 assert.deepEqual(withRenkoVolume(rows,bricks).map(b=>b.volume),[20,4.5,4.5]);
});
test('missing source, duplicate times and inconsistent finality fail explicitly',()=>{
 assert.throws(()=>withRenkoVolume([{time:1,volume:1}],[brick(2)]),/missing/);
 assert.throws(()=>withRenkoVolume([{time:1},{time:1}],[]),/unique/);
 assert.throws(()=>withRenkoVolume([{time:1,volume:1,provisional:true}],[brick(1)]),/finality/);
});
test('native captured volume agrees on197 groups with seven unresolved native-versus-broker volume differences retained',()=>{
 const folder='.private/chart-order-rollouts/renko-percentage-reference-20261120/';
 const captures=JSON.parse(fs.readFileSync(folder+'native-histories.json','utf8'));let groups=0,matched=0;const differences=[];
 for(const c of captures){
  const symbol=c.symbol.split(':')[1].replace('.P',''),raw=JSON.parse(fs.readFileSync(folder+'broker-'+symbol+'-'+c.minutes+'m.json','utf8')).rows;
  const source=raw.map(r=>({time:r[0],volume:r[5]})).sort((a,b)=>a.time-b.time);
  const native=c.series.map(r=>({sourceTime:Math.floor(r.v[0]+1e-7),open:r.v[1],high:r.v[2],low:r.v[3],close:r.v[4],volume:r.v[5]}));
  const actual=withRenkoVolume(source,native),first=native[0].sourceTime,seen=new Set();
  for(let i=0;i<native.length;i++){
   if(native[i].sourceTime===first||seen.has(native[i].sourceTime))continue;seen.add(native[i].sourceTime);groups++;
   const same=native.map((b,j)=>b.sourceTime===native[i].sourceTime?j:-1).filter(j=>j>=0);
   const ok=same.every(j=>Math.abs(actual[j].volume-native[j].volume)<1e-6);matched+=ok;
   if(!ok)differences.push({symbol,minutes:c.minutes,time:native[i].sourceTime,bricks:same.length,brokerDerived:actual[i].volume,native:native[i].volume});
   for(const j of same)for(const key of ['open','high','low','close'])assert.equal(actual[j][key],native[j][key]);
  }
 }
 assert.equal(groups,204);assert.equal(matched,197);assert.equal(differences.length,7);
 console.log(JSON.stringify({comparableNativeGroups:groups,matchingVolumeGroups:matched,retainedNativeVolumeDifferences:differences}));
});

test('captured native projection geometry carries zero volume until source confirmation',()=>{
 const capture=JSON.parse(fs.readFileSync('.private/chart-order-rollouts/renko-projection-isolated-20261120/native-wire.json','utf8'));let rows=0;
 for(const event of capture){if(!['du','timescale_update'].includes(event.packet.m))continue;const raw=event.packet.p[1]?.sds_1?.ns?.d;if(!raw)continue;for(const bar of JSON.parse(raw).data?.bars??[]){assert.equal(bar.volume,0);rows++;}}
 assert.ok(rows>=70);console.log(JSON.stringify({nativeZeroVolumeProjectionRows:rows}));
});
