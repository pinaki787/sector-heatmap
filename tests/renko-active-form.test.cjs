const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const r=require('../renko-supertrend.js');
const saved={symbol:'NSE:NIFTY50-INDEX',mode:'LIVE',timeframe:'5 minutes','supertrend-enabled':true,'ema-fast-enabled':true,'ema-fast-enabled-indicator':true,'ema-family-enabled':true};
const runner={running:true,run_id:'paper-run',config:{underlying:saved.symbol,mode:'PAPER',timeframe:'1 minute',supertrend_enabled:false,ema_family_enabled:false,ema_fast_enabled:true,ema_fast_enabled_indicator:true,indicator_family_choices:{ema_fast_enabled:true}}};
test('active Paper settings override stale Live, timeframe and indicator choices without modifying stored data',()=>{
 const before=JSON.stringify([saved,runner]);const p=r.activeRunnerFields(saved,runner);assert.equal(p.mode,'PAPER');assert.equal(p.timeframe,'1 minute');assert.equal(p['supertrend-enabled'],false);assert.equal(p['ema-fast-enabled'],false);assert.equal(p['ema-fast-enabled-indicator'],false);assert.equal(JSON.stringify([saved,runner]),before);
});
test('stopped and other-instrument drafts remain editable and separate',()=>{assert.equal(r.activeRunnerFields(saved,{...runner,running:false}),null);assert.equal(r.activeRunnerFields({...saved,symbol:'OTHER'},runner),null);});
test('mounted sync corrects visible controls and locks execution settings only',()=>{
 const source=fs.readFileSync('renko-supertrend.js','utf8');const start=source.indexOf('    function synchronizeActiveRunnerForm('),end=source.indexOf('    let renderedOrderKey',start);
 const nodes={};for(const id of ['mode','timeframe','runner-timeframe','supertrend-enabled','ema-fast-enabled','ema-fast-enabled-indicator','ema-family-enabled'])nodes[id]={value:saved[id]||'',checked:true,type:id.includes('enabled')?'checkbox':'select-one',style:{},dataset:{},setAttribute(){},closest(){return {after(n){nodes['active-settings-note']=n;}}}};
 const ctx={activeRunnerFields:r.activeRunnerFields,values:()=>({...saved}),lastRunner:runner,el:id=>nodes[id],activeFormKey:'',prefsTimer:null,clearTimeout(){},document:{createElement:()=>({style:{},setAttribute(){}})}};
 vm.createContext(ctx);vm.runInContext(source.slice(start,end)+';synchronizeActiveRunnerForm(lastRunner);lockActiveRunnerForm();',ctx);
 assert.equal(nodes.mode.value,'PAPER');assert.equal(nodes.timeframe.value,'1 minute');assert.equal(nodes['runner-timeframe'].value,'1 minute');assert.equal(nodes['supertrend-enabled'].checked,false);assert.equal(nodes.mode.disabled,true);assert.equal(nodes.timeframe.disabled,true);assert.notEqual(nodes['ema-fast-enabled-indicator'].disabled,true);assert.match(nodes['active-settings-note'].textContent,/Showing active PAPER/);
});
