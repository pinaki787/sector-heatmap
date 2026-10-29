const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const {runnerChartContext}=require('../renko-supertrend.js');
const fields={symbol:'BTCUSD',timeframe:'5 minutes','strategy-basis':'RENKO','brick-mode':'Auto','atr-length':5,factor:3};
test('active legacy run never acquires newly approved sizing from form defaults',()=>{
 const state={running:true,run_id:'OLD',config:{underlying:'BTCUSD',timeframe:'5 minutes',strategy_basis:'RENKO',brick_mode:'Auto'},last_signal:{box:56.5}};
 assert.equal(runnerChartContext(fields,state).settings.auto_sizing_policy,'legacy-history-seed-v1');
 assert.equal(runnerChartContext(fields,{...state,running:false}).settings.auto_sizing_policy,'session-atr-scaled-v1');
});
test('old backend is visibly identified and requested calculations retain their version',()=>{
 const src=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8'),start=src.indexOf('    function boundChartContext()'),end=src.indexOf('    function chartControl(',start);
 const c={isEngine:false,values:()=>fields,lastRunner:{},chartBasisPreview:false,runnerChartContext};vm.createContext(c);
 let result=vm.runInContext(src.slice(start,end)+'boundChartContext()',c);
 assert.equal(result.settings.auto_sizing_policy,'legacy-history-seed-v1');assert.match(result.label,/awaits backend activation/);
 c.lastRunner={session_auto_revision:'session-atr-scaled-v1'};result=vm.runInContext('boundChartContext()',c);
 assert.equal(result.settings.auto_sizing_policy,'session-atr-scaled-v1');assert.doesNotMatch(result.label,/legacy Auto/);
});
test('new-policy Start is blocked before a write when the worker is old',async()=>{
 const src=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8');const line=src.split('\n').find(s=>s.includes('async function request(path,body)'));
 let writes=0;const c={lastRunner:{},fetch:()=>{writes++;throw Error('unexpected network')}};vm.createContext(c);vm.runInContext(line,c);
 await assert.rejects(vm.runInContext("request('start',{auto_sizing_policy:'session-atr-scaled-v1',brick_mode:'Auto',strategy_basis:'RENKO'})",c),/approved backend reload/);
 assert.equal(writes,0);
});
