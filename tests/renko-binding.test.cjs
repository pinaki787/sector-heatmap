const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const r=require('../renko-supertrend.js');
test('draft identity includes account, broker, instance and strategy surface',()=>{
 const a={account:'A',broker:'FYERS',instance:'GOLD'};
 const keys=[a,{...a,account:'B'},{...a,broker:'DHAN'},{...a,instance:'SILVER'},{...a,engine:true}].map(r.runnerScopeKey);
 assert.equal(new Set(keys).size,5);
});
test('crypto and Indian forms discard controls from other segments',()=>{
 const delta=r.scopedFormFields({symbol:'BTCUSD','commodity-holding':'','cash-product':'CNC','carry-policy':'CONTINUOUS'},'DELTA_INDIA');
 assert.ok(!Object.hasOwn(delta,'commodity-holding'));assert.ok(!Object.hasOwn(delta,'cash-product'));assert.equal(delta['carry-policy'],'CONTINUOUS');
 const mcx=r.scopedFormFields({symbol:'MCX:GOLDM26NOVFUT','commodity-holding':'CARRY_FORWARD','delta-execution-route':'DELTA_PERPETUAL'},'FYERS');
 assert.equal(mcx['commodity-holding'],'CARRY_FORWARD');assert.ok(!Object.hasOwn(mcx,'delta-execution-route'));
});
test('runner frames must match broker, instrument and instance',()=>{
 const scope={broker:'DELTA_INDIA',symbol:'BTCUSD',instance:'B'};
 const state={runner_binding:{broker:'DELTA_INDIA',instrument:'BTCUSD',instance_key:'B'},config:{underlying:'BTCUSD'}};
 assert.equal(r.runnerResponseMatches(state,scope),true);
 assert.equal(r.runnerResponseMatches({...state,config:{underlying:'ETHUSD'}},scope),false);
 for(const delta of [{broker:'FYERS'},{symbol:'ETHUSD'},{instance:'A'}])assert.equal(r.runnerResponseMatches(state,{...scope,...delta}),false);
});
function router(){const context={URL,URLSearchParams,location:{href:'https://example.test/',origin:'https://example.test'},addEventListener(){},module:{exports:{}},console};vm.createContext(context);vm.runInContext(fs.readFileSync(require.resolve('../broker-form-routing.js'),'utf8'),context);return context.module.exports;}
test('broker switch clears prior runner and chart task identities',()=>{
 const u=new URL(router().renkoSwitchUrl('https://example.test/?renkoInstance=OLD&renkoChartSymbol=MCX:GOLD&renkoSymbol=MCX:GOLD&renkoBatchChart=1&renkoNextMode=LIVE&renkoBroker=FYERS',{id:'DELTA',broker:'DELTA_INDIA'}));
 assert.equal(u.searchParams.get('renkoAccount'),'DELTA');assert.equal(u.searchParams.get('renkoBroker'),'DELTA_INDIA');
 for(const k of ['renkoInstance','renkoChartSymbol','renkoSymbol','renkoBatchChart','renkoNextMode'])assert.equal(u.searchParams.has(k),false);
});
test('cross-broker and cross-account runner routes fail closed',()=>{
 const {route}=router();
 assert.throws(()=>route('renko','/api/renko-supertrend/start',{id:'D',broker:'DELTA_INDIA'}),/differs/);
 assert.throws(()=>route('renko','/api/renko-dhan/OTHER/start',{id:'A',broker:'DHAN'}),/differs/);
});
test('response from an earlier selected instance is discarded',async()=>{
 const line=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8').split('\n').find(s=>s.includes('async function request(path,body)'));
 let resolve;const c={instanceId:'A',selectionEpoch:1,apiBase:'/api/renko-supertrend/',fetch:()=>new Promise(r=>resolve=r),AbortSignal,encodeURIComponent};vm.createContext(c);vm.runInContext(line,c);
 const pending=vm.runInContext("request('runner')",c);c.instanceId='B';c.selectionEpoch=2;resolve({ok:true,json:async()=>({config:{underlying:'OLD'}})});
 await assert.rejects(pending,/selection changed/);
});


test('broker landing selects its own active runner or newest recorded task',()=>{
 const rows=[{broker:'FYERS',instance_key:'G',instrument:'MCX:GOLD',running:true,started_at:10},{broker:'DELTA_INDIA',instance_key:'B',instrument:'BTCUSD',running:true,started_at:20},{broker:'DELTA_INDIA',instance_key:'E',instrument:'ETHUSD',running:false,started_at:30}];
 assert.equal(r.chooseBrokerRunner(rows,'DELTA_INDIA').runner.instrument,'BTCUSD');
 assert.equal(r.chooseBrokerRunner(rows,'FYERS').runner.instrument,'MCX:GOLD');
 rows[2].running=true;assert.equal(r.chooseBrokerRunner(rows,'DELTA_INDIA').requiresSelection,true);
 rows[1].running=false;rows[2].running=false;assert.equal(r.chooseBrokerRunner(rows,'DELTA_INDIA').runner.instrument,'ETHUSD');
});

test('stopped-runner status cannot overwrite its restored next-Start flags',()=>{
 const src=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8');
 for(const [name,busy,id,revision,key] of [['paintTrendReentry','trendReentryBusy','trend-reentry-enabled','trend-brick-toggle-v1','trend_reentry_control_revision'],['paintSpreadFilter','spreadFilterBusy','spread-filter-enabled','optional-entry-spread-v1','spread_filter_control_revision']]){
  const start=src.indexOf('    function '+name+'('),end=src.indexOf(String.fromCharCode(10)+'    }',start)+6;
  const input={checked:name==='paintSpreadFilter',disabled:false},note={textContent:''};
  const ctx={[busy]:false,el:x=>x===id?input:note};vm.createContext(ctx);vm.runInContext(src.slice(start,end),ctx);
  const before=input.checked;ctx.state={running:false,config:{trend_reentry_enabled:true,spread_filter_enabled:false},[key]:revision};
  vm.runInContext(name+'(state)',ctx);assert.equal(input.checked,before);
  ctx.state.running=true;vm.runInContext(name+'(state)',ctx);assert.equal(input.checked,name==='paintTrendReentry');
 }
});
