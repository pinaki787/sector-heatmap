const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8'),start=s.indexOf('  function compactDeltaInstrumentDescription('),end=s.indexOf('  function syncInstrumentDescription(',start);assert.ok(start>=0&&end>start);
const compact=vm.runInNewContext(s.slice(start,end)+';compactDeltaInstrumentDescription');
for(const [row,expected] of [
[{contract_type:'perpetual_futures',description:'Ethereum Perpetual futures, quoted, settled & margined in US Dollar'},'Ethereum'],
[{contract_type:'perpetual_futures',description:'Bitcoin Perpetual futures'},'Bitcoin'],
[{contract_type:'perpetual_futures',description:' Odd contract description '},'Odd contract description'],
[{contract_type:'call_options',description:'ETH Call option expiring on20Nov'},'ETH Call option expiring on20Nov'],
[{contract_type:'spot',description:'Bitcoin / INR'},'Bitcoin / INR'],
[undefined,'']
])test('Compact '+String(row?.contract_type)+' description',()=>assert.equal(compact(row),expected));
test('Full tooltip retained and duplicate Delta venue removed',()=>{assert.match(s,/description\.title = deltaInstrument\?\.description \|\| instrumentName/);assert.match(s,/venue === broker\.name \|\| deltaSymbolSelection \? broker\.name/);});
