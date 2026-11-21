const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {renkoStudyClock,alignRenkoStudyPlots,applyConfirmedRenkoStudyTail}=require('../chart-renko-study-alignment.js');
const bars=(times)=>times.map(sourceTime=>({sourceTime}));
test('clock retains every same-candle brick using millisecond ordering',()=>assert.deepEqual(renkoStudyClock(bars([100,100,100,200])),[100,100.001,100.002,200]));
test('clock rejects unsorted or missing source times',()=>{assert.throws(()=>renkoStudyClock(bars([2,1])));assert.throws(()=>renkoStudyClock([{}]));});
test('projections may only follow confirmed history',()=>assert.throws(()=>renkoStudyClock([{sourceTime:1,provisional:true},{sourceTime:2}])));
test('next-brick closes preserve separate intermediate values and gaps',()=>{
 const source=bars([100,100,100,200,200,500]),host=bars([100,100,150,250,250,550,600]);
 const p=[10,20,30,40,50,60];p.colors=['a','b','c','d','e','f'];
 const out=alignRenkoStudyPlots([p],source,host)[0];
 assert.deepEqual([...out],[10,20,40,null,50,null,null]);
 assert.deepEqual(out.colors,['a','b','d',undefined,'e',undefined,undefined]);
});
test('last source value has no invented fixed-duration close',()=>assert.deepEqual(alignRenkoStudyPlots([[10,20]],bars([100,200]),bars([100,200,10000]))[0],[10,null,null]));
test('projection source cannot close a confirmed predecessor',()=>assert.deepEqual(alignRenkoStudyPlots([[10,20]], [{sourceTime:100},{sourceTime:200,provisional:true}],bars([100,300]))[0],[null,null]));
test('projection host and predecessor stay unavailable',()=>assert.deepEqual(alignRenkoStudyPlots([[10,20]],bars([100,200]),[{sourceTime:100},{sourceTime:300,provisional:true}])[0],[null,null]));
test('confirmed historical prefix stays stable when a later confirmed brick arrives',()=>{
 const source=bars([100,200,300,400]),host=bars([100,250,350]),p=[[1,2,3,4]];
 const before=alignRenkoStudyPlots(p,source,host)[0];
 const after=alignRenkoStudyPlots(p,source,host.concat({sourceTime:450}))[0];
 assert.deepEqual(after.slice(0,-2),before.slice(0,-1));assert.equal(before.at(-1),null);assert.equal(after[2],3);
});
test('invalid plot shape fails clearly; inputs remain unchanged',()=>{
 const source=bars([1,2]),host=bars([1,3]),p=[[10,20]],before=JSON.stringify({source,host,p});
 assert.throws(()=>alignRenkoStudyPlots([[10]],source,host));alignRenkoStudyPlots(p,source,host);assert.equal(JSON.stringify({source,host,p}),before);
});
test('empty arrays produce correctly shaped empty outputs',()=>assert.deepEqual(alignRenkoStudyPlots([[]],[],[]),[[]]));
test('actual captured native historical values and nulls match',()=>{
 const folder='.private/chart-order-rollouts/native-renko-study-timeframe-20261119/';
 function csv(name){const [header,...lines]=fs.readFileSync(folder+name,'utf8').trim().split(/\r?\n/);const h=header.split(',');return lines.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[h[i],v])));}
 const lower=csv('native-30m-renko10-hourly-sma5.csv'),higher=csv('native-1h-renko10-hourly-sma5.csv');
 const host=lower.map(r=>({sourceTime:Math.floor(Number(r.time)/1800)*1800}));
 const ref=higher.map(r=>({sourceTime:Math.floor(Number(r.time)/3600)*3600}));
 const values=higher.map(r=>r.MA===''?null:Number(r.MA));
 const out=alignRenkoStudyPlots([values],ref,host)[0];let checked=0,gaps=0;
 for(let i=0;i<lower.length-2;i++){
  if(Number(lower[i].time)<Number(higher[0].time)||Number(lower[i+1].time)>Number(higher.at(-2).time))continue;
  const want=lower[i].MA===''?null:Number(lower[i].MA);assert.equal(out[i],want,'row '+i);checked++;gaps+=want===null;
 }
 assert.equal(checked,297);assert.equal(gaps,101);
});

test('synthetic clock collisions fail instead of silently reordering bricks',()=>assert.throws(()=>renkoStudyClock(bars([100,100,100.0005]))));

test('gap filling carries confirmed values and their colors without inventing new closes',()=>{
 const source=bars([100,200,500]),host=bars([100,250,300,550,600]),p=[10,20,30];p.colors=['red','blue','green'];
 const out=alignRenkoStudyPlots([p],source,host,{gaps:false})[0];
 assert.deepEqual([...out],[10,10,20,20,20]);assert.deepEqual(out.colors,['red','red','blue','blue','blue']);
});
test('captured native wait-off history equals confirmed next-close values carried across gaps',()=>{
 const folder='.private/chart-order-rollouts/native-renko-study-timeframe-20261119/';
 function csv(name){const [header,...lines]=fs.readFileSync(folder+name,'utf8').trim().split(/\r?\n/);const h=header.split(',');return lines.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[h[i],v])));}
 const lower=csv('native-30m-renko10-hourly-sma5-forming.csv'),higher=csv('native-1h-renko10-hourly-sma5.csv');
 const host=lower.map(r=>({sourceTime:Math.floor(Number(r.time)/1800)*1800}));
 const ref=higher.map(r=>({sourceTime:Math.floor(Number(r.time)/3600)*3600}));
 const out=alignRenkoStudyPlots([higher.map(r=>r.MA===''?null:Number(r.MA))],ref,host,{gaps:false})[0];
 let checked=0;for(let i=0;i<lower.length-2;i++){
  if(Number(lower[i].time)<Number(higher[0].time)||Number(lower[i+1].time)>Number(higher.at(-2).time))continue;
  assert.equal(out[i],Number(lower[i].MA),'row '+i);checked++;
 }assert.equal(checked,297);
});

test('confirmed live tail updates only the current host row and carries its color without mutating history',()=>{
 const aligned=[[10,null,null]],values=[20,30];aligned[0].colors=['red',undefined,undefined];values.colors=['blue','green'];
 const before=JSON.stringify(aligned),out=applyConfirmedRenkoStudyTail(aligned,[values],bars([100,200]),bars([100,150,250]),{live:true,confirmedThrough:200,now:250,updatedAt:249});
 assert.deepEqual([...out[0]],[10,null,20]);assert.deepEqual(out[0].colors,['red',undefined,'blue']);assert.equal(JSON.stringify(aligned),before);
});
test('replay, stale or future feed evidence never changes the current tail',()=>{
 const a=[[1,null]],p=[[2,3]],r=bars([100,200]),h=bars([100,250]),ok={live:true,confirmedThrough:200,now:250,updatedAt:249};
 for(const change of [{live:false},{updatedAt:190},{updatedAt:253},{confirmedThrough:251},{updatedAt:NaN}]){
  assert.equal(applyConfirmedRenkoStudyTail(a,p,r,h,{...ok,...change}),a);
 }
 h[1].historyOnly=true;assert.equal(applyConfirmedRenkoStudyTail(a,p,r,h,ok),a);
});
test('forming and history-only source bricks cannot become confirmed tail values',()=>{
 const r=[{sourceTime:100},{sourceTime:200,provisional:true}],a=[[null]],p=[[10,20]];
 assert.equal(applyConfirmedRenkoStudyTail(a,p,r,bars([100]),{live:true,confirmedThrough:300,now:310,updatedAt:309})[0][0],10);
 r[0].historyOnly=true;assert.equal(applyConfirmedRenkoStudyTail(a,p,r,bars([100]),{live:true,confirmedThrough:300,now:310,updatedAt:309}),a);
});
test('captured native hourly confirmation changes1790to1794at16UTC without inventing another brick',()=>{
 const file='.private/chart-order-rollouts/native-renko-study-timeframe-20261119/native-1h-renko10-hourly-sma5.csv';
 const [header,...lines]=fs.readFileSync(file,'utf8').trim().split(/\r?\n/),keys=header.split(',');
 const data=lines.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[keys[i],v])));
 const reference=data.map(r=>({sourceTime:Math.floor(Number(r.time)/3600)*3600})),plots=[data.map(r=>r.MA===''?null:Number(r.MA))],host=bars([1795100400]);
 const before=applyConfirmedRenkoStudyTail([[null]],plots,reference,host,{live:true,confirmedThrough:1795100400,now:1795103936,updatedAt:1795103935});
 const after=applyConfirmedRenkoStudyTail([[null]],plots,reference,host,{live:true,confirmedThrough:1795104000,now:1795105080,updatedAt:1795105079});
 assert.equal(before[0][0],1790);assert.equal(after[0][0],1794);
});

test('PAXG native minute-to-five-minute historical carry matches290rows',()=>{
 const folder='.private/chart-order-rollouts/renko-projection-reference-20261119/';
 function csv(name){const[h,...ls]=fs.readFileSync(folder+name,'utf8').trim().split(/\r?\n/),keys=h.split(',');return ls.map(l=>Object.fromEntries(l.split(',').map((v,i)=>[keys[i],v])));}
 const low=csv('native-1m-ref5m-wait-off.csv'),high=csv('native-5m-ref5m-wait-off.csv');
 const refs=high.map(r=>({sourceTime:Math.floor(Number(r.time)/300)*300})),host=low.map(r=>({sourceTime:Math.floor(Number(r.time)/60)*60}));
 const out=alignRenkoStudyPlots([high.map(r=>Number(r.MA))],refs,host,{gaps:false})[0];let checked=0;
 for(let i=0;i<low.length-2;i++){if(Number(low[i].time)<Number(high[0].time)||Number(low[i+1].time)>=refs.at(-1).sourceTime)continue;assert.equal(out[i],Number(low[i].MA),'PAXG row'+i);checked++;}
 assert.equal(checked,290);
});
test('PAXG tenth-point native brick bodies match current constructor from full captured broker prefix',()=>{
 require('../chart-workspace-studies.js');const lib=globalThis.SectorPulseChartStudies,folder='.private/chart-order-rollouts/renko-projection-reference-20261119/';
 const data=JSON.parse(fs.readFileSync(folder+'broker-c.json','utf8')),bars=data.rows.filter(b=>b.time+300<=data.captured_at);
 const [h,...lines]=fs.readFileSync(folder+'native-5m-small-brick.csv','utf8').trim().split(/\r?\n/),keys=h.split(',');
 const native=lines.map(l=>Object.fromEntries(l.split(',').map((v,i)=>[keys[i],v])));
 const actual=lib.renko(bars,.1,undefined,'close',false).slice(-native.length);assert.equal(actual.length,native.length);
 for(let i=0;i<native.length;i++)for(const k of ['open','high','low','close'])assert.ok(Math.abs(actual[i][k]-Number(native[i][k]))<1e-8,'PAXG smallbrick'+i+' '+k);
});
