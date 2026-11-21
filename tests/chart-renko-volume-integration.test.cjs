
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const base='.private/chart-order-rollouts/renko-volume-integration-20261120/',owner=process.env.CHART_OWNER||'root';
const scope={console};vm.createContext(scope);vm.runInContext(fs.readFileSync(base+owner+'/chart-workspace-studies.js','utf8'),scope);
const lib=scope.SectorPulseChartStudies,alignment=scope.SectorPulseRenkoStudyAlignment;
const main=fs.readFileSync(base+owner+'/chart-workspace.js','utf8');
const bars=[{time:0,open:100,high:100,low:100,close:100,volume:10},{time:60,open:100,high:125,low:100,close:125,volume:30}];
test('integrated constructor conserves source volume and retains the original full-brick geometry',()=>{
 const result=lib.renko(bars,10);assert.deepEqual(Array.from(result,b=>b.volume),[20,20]);assert.ok(result.every(b=>b.renkoVolume));
 assert.deepEqual(Array.from(result,b=>[b.open,b.high,b.low,b.close]),[[100,110,100,110],[110,120,110,120]]);
});
test('actual chart partial projections receive zero allocated volume without changing confirmed values',()=>{
 const source=[...bars,{time:120,open:125,high:129,low:125,close:129,volume:11,provisional:true}];
 const c={rows:source,settings:{renkoSource:'close'},renko:lib.renko,withRenkoVolume:lib.withRenkoVolume,renkoWicksVisible:()=>false,window:{SectorPulseRenkoStudyAlignment:alignment}};
 vm.createContext(c);const a=main.indexOf('  function chartRenkoBricks(size)'),b=main.indexOf('  function completedRenkoCandles()',a);vm.runInContext(main.slice(a,b),c);
 const result=c.chartRenkoBricks(10);assert.deepEqual(Array.from(result,b=>b.volume),[20,20,0]);assert.equal(result.at(-1).close,129);assert.ok(result.at(-1).renkoVolume);
});
test('Pine host mapper accepts allocated Renko volume, preserves zero and rejects uncertified synthetic volume',()=>{
 const a=main.indexOf('  function pineSyntheticHostBar('),b=main.indexOf('  function pinePlotEntries(',a),c={candleEnd:t=>t+60};vm.createContext(c);vm.runInContext(main.slice(a,b),c);
 const allocated=lib.renko(bars,10)[0];assert.equal(c.pineSyntheticHostBar(allocated,'1','renko').volume,20);
 assert.equal(c.pineSyntheticHostBar({...allocated,volume:0,provisional:true},'1','renko').volume,0);
 assert.ok(Number.isNaN(c.pineSyntheticHostBar({...allocated,renkoVolume:false},'1','renko').volume));
});
test('higher-timeframe reference construction passes the same allocated volume into its indicator',()=>{
 let received;const reference=lib.renko(bars,10);
 const result=alignment.calculateRenkoTimeframeStudy({sourceBars:bars,hostBars:reference,renko:lib.renko,size:10,run:data=>{received=data;return lib.indicators.Volume.run(data);},waitForClose:false});
 assert.deepEqual(Array.from(received,b=>b.volume),[20,20]);assert.deepEqual(Array.from(result.reference,b=>b.volume),[20,20]);
});
test('volume picker permits twenty volume studies while preserving time-bar requirements for volume delta',()=>{
 const a=main.indexOf('  function indicatorAvailable('),b=main.indexOf('  function matchIndicator(',a);
 const x=main.indexOf('  function volumeUnavailable('),y=main.indexOf('  const defaultChartTypeFavorites',x);
 const c={indicators:lib.indicators,settings:{type:'Renko',studies:[]},hasVolume:true,broker:{nse:false}};vm.createContext(c);vm.runInContext(main.slice(a,b)+main.slice(x,y),c);
 let allowed=0,denied=0;
 for(const [kind,d]of Object.entries(lib.indicators)){if(!d.volume)continue;if(d.deltaCandles){assert.equal(c.indicatorAvailable(kind,d),false);assert.match(c.volumeUnavailable({kind}),/time-based/);denied++;}else{assert.equal(c.indicatorAvailable(kind,d),true);assert.equal(c.volumeUnavailable({kind}),'');allowed++;}}
 assert.equal(allowed,20);assert.equal(denied,2);
});
test('Renko CSV retains allocated precision and session VWAP uses source timestamps rather than brick indexes',()=>{
 const source=[{time:0,open:100,high:100,low:100,close:100,volume:0},{time:60,open:100,high:125,low:100,close:125,volume:40},{time:86400,open:125,high:135,low:125,close:135,volume:30}];
 const bricks=lib.renko(source,10),csv=lib.chartCsv(bricks,[]).trim().split(/\r?\n/);assert.equal(Number(csv[1].split(',')[6]),20);
 const vwap=lib.indicators.VWAP.run(bricks,[],undefined,undefined,{anchor:'Session',source:'hlc3'},{sessionOffset:0})[0];assert.ok(Math.abs(vwap.at(-1)-380/3)<1e-10);
});
test('integrated broker reconstruction preserves1183 native brick OHLC and retains seven volume differences',()=>{
 const folder='.private/chart-order-rollouts/renko-percentage-reference-20261120/',captures=JSON.parse(fs.readFileSync(folder+'native-histories.json','utf8'));let checked=0,volumeGroups=0,matches=0;
 for(const c of captures){const symbol=c.symbol.split(':')[1].replace('.P',''),raw=JSON.parse(fs.readFileSync(folder+'broker-'+symbol+'-'+c.minutes+'m.json','utf8')).rows.map(r=>Object.fromEntries(['time','open','high','low','close','volume'].map((k,i)=>[k,r[i]]))).sort((a,b)=>a.time-b.time).filter(b=>b.time+c.minutes*60<=c.capturedAt);
  const size=scope.SectorPulseRenkoSizing.renkoPercentageSize(raw.at(-1).close,c.percentage,symbol==='BTCUSD'?.5:.01),actual=lib.renko(raw,size),start=Math.floor(c.series[0].v[0]/(c.minutes*60))*c.minutes*60+c.minutes*60,cutoff=Math.floor(c.capturedAt/(c.minutes*60))*c.minutes*60;
  const selected=c.series.filter(r=>r.v[0]>=start&&r.v[0]<cutoff),app=actual.filter(b=>b.sourceTime>=start);assert.equal(app.length,selected.length);let last;
  for(let i=0;i<selected.length;i++){for(const [key,column]of [['open',1],['high',2],['low',3],['close',4]])assert.ok(Math.abs(app[i][key]-selected[i].v[column])<1e-8);checked++;if(app[i].sourceTime===last)continue;last=app[i].sourceTime;const indexes=app.map((b,j)=>b.sourceTime===last?j:-1).filter(j=>j>=0);volumeGroups++;matches+=indexes.every(j=>Math.abs(app[j].volume-selected[j].v[5])<1e-6);}
 }
 assert.equal(checked,1183);assert.equal(volumeGroups,204);assert.equal(matches,197);
});
