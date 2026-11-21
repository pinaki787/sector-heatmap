const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
require(path.resolve(process.env.CHART_STUDIES_SOURCE||'chart-workspace-studies.js'));
const indicator=globalThis.SectorPulseChartStudies.indicators.WoodiesCCI;
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
const library=fs.readFileSync(process.env.CHART_STUDIES_SOURCE||'chart-workspace-studies.js','utf8');
function colors(values,inputs){const a=library.indexOf('  function woodiesCciColors('),b=library.indexOf('  function pringSpecialK(',a);assert.ok(a>=0&&b>a);const c={};vm.createContext(c);vm.runInContext(library.slice(a,b),c);return [...c.woodiesCciColors(values,inputs)];}
test('slow14 and turbo6 have independent warmups and analytic linear-price values',()=>{
 const bars=Array.from({length:40},(_,i)=>({high:100+i,low:100+i,close:100+i}));
 const [hist,slow,turbo]=indicator.run(bars,[],undefined,undefined,{});
 assert.ok(slow.slice(0,13).every(v=>v===null));assert.ok(turbo.slice(0,5).every(v=>v===null));
 assert.ok(Math.abs(slow[13]-6.5/(.015*3.5))<1e-10);assert.ok(Math.abs(turbo[5]-2.5/(.015*1.5))<1e-10);
 assert.deepEqual([...hist],slow);
});
test('completed flat windows return documented zero CCI rather than null or infinity',()=>{
 for(const n of [1,6,14]){
  const [hist,slow,turbo]=indicator.run(Array.from({length:20},()=>({high:100,low:100,close:100})),[],undefined,undefined,{cciPeriod:n,turboPeriod:n});
  for(let i=n-1;i<20;i++){assert.equal(slow[i],0);assert.equal(turbo[i],0);assert.equal(hist.colors[i],'#787b86');}
 }
});
test('four neutral bars, fifth warning and sixth same-side trend follow documented colors',()=>{
 assert.deepEqual(colors([1,2,3,4,5,6,-1,-2,-3,-4,-5,-6]),['#787b86','#787b86','#787b86','#787b86','#fdd835','#089981','#787b86','#787b86','#787b86','#787b86','#fdd835','#f23645']);
});
test('zero, missing data and opposite-side values reset confirmation',()=>{
 assert.deepEqual(colors([1,2,3,4,0,1,2,3,4,null,1,2,3,4,-1]),Array(15).fill('#787b86'));
});
test('histogram palette accepts explicit colors and rejects malformed paint',()=>{
 const paint={upColor:'#112233',downColor:'#445566',neutralColor:'#778899',warningColor:'#aabbcc'};
 assert.deepEqual(colors([1,2,3,4,5,6],paint),['#778899','#778899','#778899','#778899','#aabbcc','#112233']);
 assert.equal(colors([-1,-2,-3,-4,-5,-6],paint).at(-1),'#445566');
 assert.equal(colors([1,2,3,4,5,6],{upColor:'bad'}).at(-1),'#089981');
});
test('invalid periods fall back to default14/6',()=>{
 const bars=Array.from({length:40},(_,i)=>({high:100+i,low:100+i,close:100+i}));
 assert.deepEqual(indicator.run(bars,[],undefined,undefined,{cciPeriod:0,turboPeriod:2.5}),indicator.run(bars,[],undefined,undefined,{}));
});
test('closed higher-timeframe plots retain the color of their mapped source bar',()=>{
 const a=source.indexOf('  function alignConfirmedStudyPlots('),b=source.indexOf('  const legacyRatingIntervals',a);assert.ok(a>=0&&b>a);
 const c={};vm.createContext(c);vm.runInContext(source.slice(a,b),c);const plot=[10,20];plot.colors=['red','green'];
 const result=c.alignConfirmedStudyPlots([plot],[{time:0},{time:3600}],Array.from({length:5},(_,i)=>({time:i*1800})),b=>b.time+3600,b=>b.time+1800)[0];
 assert.deepEqual([...result],[null,10,10,20,20]);assert.deepEqual([...result.colors],[undefined,'red','red','green','green']);
});
for(const alternate of [false,true])test((alternate?'alternate-symbol':'main-symbol')+' forming update changes only tail value and its color',()=>{
 const start=source.indexOf(alternate?'            const newPlots = run([...confirmed, live]);':'          const liveValues = run([...reference, forming]);');
 const end=source.indexOf(alternate?'          }\n          return aligned;':'        }\n        return aligned;',start);assert.ok(start>=0&&end>start);
 const plot=[1,2,3];plot.colors=['gray','yellow','red'];const live=[4];live.colors=['green'];
 const c={aligned:[plot],reference:[],forming:{},confirmed:[],live:{},indicator:{},run:()=>[live]};vm.createContext(c);vm.runInContext(source.slice(start,end),c);
 assert.deepEqual([...plot],[1,2,4]);assert.deepEqual([...plot.colors],['gray','yellow','green']);
});
test('Woodies uses normal broker calculation timeframe controls',()=>{
 const body=source.match(/const calculationTimeframeStudies = new Set\(\[([\s\S]*?)\]\);/)?.[1];assert.ok(body);assert.ok(new Function('return ['+body+']')().includes('WoodiesCCI'));
});
