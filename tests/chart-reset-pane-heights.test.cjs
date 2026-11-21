const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),test=require('node:test');
const source=fs.readFileSync(process.env.CHART_SOURCE||'chart-workspace.js','utf8');
function run(settings){const a=source.indexOf('  function resetChartPaneHeights() {'),b=source.indexOf('  function mainPaneHeight(value) {',a);assert.ok(a>=0&&b>a);const calls=[];const ctx={settings,redrawKeepingViewport:()=>calls.push('redraw'),save:()=>calls.push('save')};vm.runInNewContext(source.slice(a,b)+';resetChartPaneHeights();',ctx);return calls;}
test('explicit reset removes saved price, study and comparison heights and preserves collapse, styling and viewport',()=>{
 const settings={pricePaneHeight:548,studies:[{kind:'RSI',paneHeight:114,expandedPane:true,collapsedPane:true,length:14},{kind:'OBV',paneHeight:94,color:'#2962ff'}],comparisonStyles:{ETHUSD:{paneHeight:400,color:'#ff0000',collapsedPane:true}},range:{from:1,to:90},collapseIndicatorLegend:true,maximizedStudyIndex:1};
 assert.deepEqual(run(settings),['redraw','save']);assert.equal(settings.pricePaneHeight,undefined);
 assert.deepEqual(settings.studies,[{kind:'RSI',collapsedPane:true,length:14},{kind:'OBV',color:'#2962ff'}]);
 assert.deepEqual(settings.comparisonStyles,{ETHUSD:{color:'#ff0000',collapsedPane:true}});
 assert.deepEqual(settings.range,{from:1,to:90});assert.equal(settings.collapseIndicatorLegend,true);assert.equal(settings.maximizedStudyIndex,1);
});
test('reset is safe without comparisons and does not add new settings',()=>{const s={studies:[]};run(s);assert.deepEqual(s,{studies:[]});});

