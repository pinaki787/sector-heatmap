const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const start=s.indexOf('  function latestCompletedChartTime('),end=s.indexOf('  function deltaFormingFromNative(',start);
assert.ok(start>=0&&end>start);
test('Feed detail separates completed history from latest tick',()=>{
const badge={dataset:{},setAttribute(){}},description={},details={querySelector:()=>description};
const ctx=vm.createContext({rows:[{time:100},{time:200,provisional:true}],settings:{interval:'30'},
panel:{querySelector:q=>q==='[data-chart-feed]'?badge:details},chartTime:t=>'T'+t,intervalLabel:i=>i+'m',refreshFeedDetail:undefined});
vm.runInContext(s.slice(start,end)+';setFeedStatus("historical","Outside trading hours","Connected",300)',ctx);
assert.equal(description.textContent,'ConnectedT300');
assert.equal(badge.title,'ConnectedT300 · Latest completed broker candle T100 (30m)');
assert.notEqual(badge.title,description.textContent);
ctx.rows=[{time:400}];ctx.refreshFeedDetail();assert.match(badge.title,/T400 \(30m\)$/);
});
test('No timestamp is invented for empty or projected-only history',()=>{
const ctx=vm.createContext();const fn=vm.runInContext(s.slice(start,s.indexOf('  function setFeedStatus',start))+';latestCompletedChartTime',ctx);
assert.equal(fn([]),undefined);assert.equal(fn([{time:50,provisional:true}]),undefined);assert.equal(fn([{time:NaN}]),undefined);
assert.equal(fn([{time:50},{time:100,provisional:true}]),50);
});
