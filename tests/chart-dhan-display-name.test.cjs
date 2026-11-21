const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const s=fs.readFileSync(process.env.CHART_WORKSPACE_SOURCE||'chart-workspace.js','utf8');
function extract(a,b){const x=s.indexOf(a),y=s.indexOf(b,x);assert.ok(x>=0&&y>x);return s.slice(x,y);}
for(const mode of ['ticker','description','both'])test('Catalog name respects '+mode+' title mode',()=>{
const nodes={'[data-chart-legend-symbol]':{},'[data-chart-legend-description]':{textContent:'HDFC Bank'},'[data-status-instrument-title]':{}};
const ctx=vm.createContext({dhanSymbolSelection:true,dhanPineInstruments:new Map([['NSE_EQ:1333',{symbol:'HDFCBANK'}]]),chartSymbol:()=> 'NSE_EQ:1333',settings:{instrumentTitleMode:mode},panel:{querySelector:q=>nodes[q]}});
vm.runInContext(extract('  function chartDisplayTicker()','  function syncInstrumentDescription')+extract('  function syncInstrumentTitle()','  function syncStatusLine()')+';syncInstrumentTitle()',ctx);
assert.equal(nodes['[data-chart-legend-symbol]'].textContent,mode==='description'?'HDFC Bank':'HDFCBANK');
assert.equal(nodes['[data-chart-legend-symbol]'].title,'NSE_EQ:1333 · HDFC Bank');
assert.equal(nodes['[data-chart-legend-description]'].hidden,mode!=='both');
});
test('Unresolved native identity is retained',()=>{const c=vm.createContext({dhanSymbolSelection:true,dhanPineInstruments:new Map(),chartSymbol:()=> 'NSE_EQ:1333'});assert.equal(vm.runInContext(extract('  function chartDisplayTicker()','  function syncInstrumentDescription')+';chartDisplayTicker()',c),'NSE_EQ:1333');});
test('Other sources retain their own ticker',()=>{const c=vm.createContext({dhanSymbolSelection:false,chartSymbol:()=> 'PAXGUSD'});assert.equal(vm.runInContext(extract('  function chartDisplayTicker()','  function syncInstrumentDescription')+';chartDisplayTicker()',c),'PAXGUSD');});
