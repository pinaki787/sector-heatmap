const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
require(path.resolve(process.env.CHART_STUDIES_SOURCE||'chart-workspace-studies.js'));
const {indicators}=globalThis.SectorPulseChartStudies;
const options={showBand1:true,showBand2:true,showBand3:true};
const info={interval:'5',sessionOffset:0,sessionOpen:0,chartType:'Renko'};
const bar=(time,price,volume)=>({time,sourceTime:time,open:price,high:price,low:price,close:price,volume,renkoVolume:true});
for(const kind of ['VWAP','AutoVWAP']){
 test(kind+' first positive volume has exactly zero band dispersion after zero volume',()=>{
  const rows=[bar(1795046400,63000,0),bar(1795046700,63036.666666666664,1427.448275862069)];
  const plots=indicators[kind].run(rows,rows.map(b=>b.close),14,undefined,{...options,anchor:kind==='VWAP'?'Session':'Auto'},info);
  for(const p of plots){assert.equal(p[0],null);assert.equal(p[1],rows[1].close);}
 });
 test(kind+' weighted bands preserve nonzero dispersion',()=>{
  const rows=[bar(1795046400,100,2),bar(1795046700,104,6)];
  const plots=indicators[kind].run(rows,rows.map(b=>b.close),14,undefined,{...options,anchor:kind==='VWAP'?'Session':'Auto'},info);
  assert.equal(plots[0][1],103);
  for(let n=1;n<=3;n++){assert.ok(Math.abs(plots[n*2-1][1]-(103+n*Math.sqrt(3)))<1e-12);assert.ok(Math.abs(plots[n*2][1]-(103-n*Math.sqrt(3)))<1e-12);}
 });
}
test('session reset gives one fresh weighted observation zero dispersion',()=>{
 const rows=[bar(1795046400,100,2),bar(1795046700,104,6),bar(1795132800,63036.666666666664,1427.448275862069)];
 const plots=indicators.VWAP.run(rows,rows.map(b=>b.close),14,undefined,{...options,anchor:'Session'},info);
 for(const p of plots)assert.equal(p[2],rows[2].close);
});
