const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
require(path.resolve(process.env.CHART_STUDIES_SOURCE||'chart-workspace-studies.js'));
const indicator=globalThis.SectorPulseChartStudies.indicators.SpecialK;
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
test('Special K and its double-smoothed signal respect exact warmups',()=>{
 const bars=Array.from({length:923},()=>({open:100,high:100,low:100,close:100}));
 const [special,signal]=indicator.run(bars,[],undefined,undefined,{});
 assert.ok(special.slice(0,724).every(v=>v===null));assert.equal(special[724],0);
 assert.ok(signal.slice(0,922).every(v=>v===null));assert.equal(signal[922],0);
});
test('constant geometric growth matches the12 documented weighted ROC terms',()=>{
 const bars=Array.from({length:1000},(_,i)=>({close:100*Math.pow(1.001,i)}));
 const expected=[[10,1],[15,2],[20,3],[30,4],[40,1],[65,2],[75,3],[100,4],[195,1],[265,2],[390,3],[530,4]]
  .reduce((sum,[n,w])=>sum+100*(Math.pow(1.001,n)-1)*w,0);
 const [special,signal]=indicator.run(bars,[],undefined,undefined,{});
 for(let i=724;i<bars.length;i++)assert.ok(Math.abs(special[i]-expected)<1e-8);
 for(let i=922;i<bars.length;i++)assert.ok(Math.abs(signal[i]-expected)<1e-8);
});
test('zero denominators never create fabricated or infinite Special K values',()=>{
 const [special,signal]=indicator.run(Array.from({length:1000},()=>({close:0})),[],undefined,undefined,{});
 assert.ok(special.every(v=>v===null));assert.ok(signal.every(v=>v===null));
});
test('invalid signal lengths fall back to valid100/100 defaults',()=>{
 const bars=Array.from({length:1000},(_,i)=>({close:100+i}));
 assert.deepEqual(indicator.run(bars,[],undefined,undefined,{signalLength1:0,signalLength2:-3}),indicator.run(bars,[],undefined,undefined,{}));
});
test('source and both signal controls have valid editable defaults',()=>{
 assert.equal(indicator.minimumBars,725);
 for(const input of indicator.inputs)if(typeof input.value==='number')assert.ok(input.value>=input.min&&input.value<=input.max);
 assert.equal(indicator.inputs.find(i=>i.id==='source').options.length,7);
});
function fixture(){
 const c={indicators:{SpecialK:indicator,SMA:{}},displayedBars:[],settings:{interval:'30'},history:new Map(),calculationInterval:study=>study.calculation};
 vm.createContext(c);const a=source.indexOf('  function studyMinimumHistoryNotice('),b=source.indexOf('  function studyTimeframeLabel(',a);assert.ok(a>=0&&b>a);vm.runInContext(source.slice(a,b),c);return c;
}
test('history notice reports actual chart coverage and clears at725 bars',()=>{
 const c=fixture();c.displayedBars=Array(724).fill({});assert.equal(c.studyMinimumHistoryNotice({kind:'SpecialK'}),'Requires 725 bars (724 loaded)');
 c.displayedBars.push({});assert.equal(c.studyMinimumHistoryNotice({kind:'SpecialK'}),'');assert.equal(c.studyMinimumHistoryNotice({kind:'SMA'}),'');
});
test('history notice measures selected calculation timeframe rather than host count',()=>{
 const c=fixture();c.displayedBars=Array(2000).fill({});const s={kind:'SpecialK',calculation:'60'};
 assert.equal(c.studyMinimumHistoryNotice(s),'Requires 725 bars (0 loaded)');c.history.set('60',Array(725).fill({}));assert.equal(c.studyMinimumHistoryNotice(s),'');
});
test('Special K is included in existing broker calculation timeframe controls',()=>{
 const body=source.match(/const calculationTimeframeStudies = new Set\(\[([\s\S]*?)\]\);/)?.[1];assert.ok(body);
 assert.ok(new Function('return ['+body+']')().includes('SpecialK'));
});
