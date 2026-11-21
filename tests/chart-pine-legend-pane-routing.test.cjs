const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('chart-workspace.js','utf8');
const a=source.indexOf('  function pineIndicatorOptions('),b=source.indexOf('  function pinePlotMetadata(',a);
const c=source.indexOf('  function studyLegendPlotsForPane('),d=source.indexOf('  function legendPlotReadings(',c);
assert.ok(a>=0&&b>a&&c>=0&&d>c);
const context=vm.createContext({});
vm.runInContext(source.slice(a,b)+source.slice(c,d),context);
const select=context.studyLegendPlotsForPane;
test('mixed Pine keeps oscillator ranges and RSI readings out of price legend',()=>{
 const study={kind:'Pine',source:'indicator("Mixed", overlay=false)'};
 const rows=[{label:'0',forceOverlay:false},{label:'40',forceOverlay:false},{label:'RSI',forceOverlay:false},{label:'V1 price',forceOverlay:true}];
 const before=JSON.stringify(rows);
 assert.deepEqual(Array.from(select(study,rows)).map(x=>x.label),['V1 price']);
 assert.deepEqual(Array.from(select(study,rows,true)).map(x=>x.label),['0','40','RSI']);
 assert.equal(JSON.stringify(rows),before);
});
test('explicit price placement and overlay scripts preserve their price readings',()=>{
 const rows=[{label:'RSI',forceOverlay:false},{label:'Forced',forceOverlay:true}];
 assert.equal(select({kind:'Pine',placement:'price',source:'indicator("X", overlay=false)'},rows),rows);
 assert.equal(select({kind:'Pine',source:'indicator("X", overlay=true)'},rows),rows);
});
test('pure oscillator pane and built-in indicators retain existing pane behavior',()=>{
 const rows=[{label:'RSI',forceOverlay:false}];
 assert.equal(select({kind:'Pine',source:'indicator("RSI", overlay=false)'},rows).length,0);
 assert.deepEqual(Array.from(select({kind:'Pine',source:'indicator("RSI", overlay=false)'},rows,true)).map(x=>x.label),['RSI']);
 assert.equal(select({kind:'SMA'},rows),rows);
});
