const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8'),start=s.indexOf('  function deltaPineInstrumentType('),end=s.indexOf('  function workerPineSymbolInfo(',start);assert.ok(start>=0&&end>start);
for(const [type,expected] of [['call_options','option'],['put_options','option'],['move_options','option'],['spot','crypto'],['perpetual_futures','crypto'],[undefined,'crypto']])test(String(type)+' is classified from catalog',()=>{
const c=vm.createContext({deltaCatalog:[{symbol:'TEST',contract_type:type}]});const fn=vm.runInContext(s.slice(start,end)+';deltaPineInstrumentType',c);assert.equal(fn('TEST'),expected);assert.equal(fn('UNKNOWN'),'crypto');
});
test('Worker metadata uses catalog classification',()=>{assert.match(s,/deltaSymbolSelection \? deltaPineInstrumentType\(symbol\)/);});
