const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
const start=source.indexOf('  function heikinTailUpdateAllowed('),end=source.indexOf('  async function runChartPine(',start);
if(start<0&&process.env.CHART_WORKSPACE_SOURCE)throw Error('candidate gate required');
if(start<0){test('HA appended-tail gate is staged',{skip:'Frontend gate not activated'},()=>{});}else{
const gate=vm.runInNewContext(source.slice(start,end)+';heikinTailUpdateAllowed',{sameCandle:(a,b)=>['time','open','high','low','close','volume','provisional'].every(k=>a[k]===b[k])});
const bar=(time,provisional=false)=>({time,sourceTime:time,open:100,high:102,low:99,close:101,volume:10,provisional});
const previous=()=>[bar(1),bar(2),bar(3,true)];
test('no previous state requires full history',()=>assert.equal(gate(undefined,[bar(1)]),false));
test('forming tail can revise incrementally',()=>{const p=previous(),b=structuredClone(p);b[2].close=102;assert.equal(gate(p,b),true)});
test('prior forming candle may finalize and append',()=>{const p=previous(),b=structuredClone(p);b[2].close=102;b[2].provisional=false;b.push(bar(4,true));assert.equal(gate(p,b),true)});
test('several new candles can append',()=>{const p=previous(),b=structuredClone(p);b[2].provisional=false;b.push(bar(4),bar(5,true));assert.equal(gate(p,b),true)});
test('older correction requires replay',()=>{const p=previous(),b=structuredClone(p);b[0].close=100;assert.equal(gate(p,b),false)});
test('trimmed or shifted window requires replay',()=>{const p=previous();assert.equal(gate(p,p.slice(1)),false);assert.equal(gate(p,[bar(2),bar(3),bar(4,true)]),false)});
test('unchanged confirmed last candle can append',()=>{const p=previous();p[2].provisional=false;assert.equal(gate(p,[...p,bar(4,true)]),true)});
test('corrected confirmed last candle requires replay',()=>{const p=previous();p[2].provisional=false;const b=structuredClone(p);b[2].close=103;b.push(bar(4,true));assert.equal(gate(p,b),false)});
test('same timestamp finalization can update',()=>{const p=previous(),b=structuredClone(p);b[2].provisional=false;assert.equal(gate(p,b),true)});
test('changed source timestamp requires replay',()=>{const p=previous(),b=structuredClone(p);b[2].sourceTime=99;assert.equal(gate(p,b),false)});

}
