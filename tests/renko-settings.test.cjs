const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');
const {configurationText,toggleState}=require('../renko-supertrend.js');
test('dated text preserves unsaved fields, false toggles, optional blanks and separates active settings',()=>{
const x=configurationText({broker:'FYERS',instance:'default',fields:[{id:'lots',label:'Lots',value:'3'},{id:'trailing-enabled',label:'Trailing',value:false},{id:'daily-budget',label:'Daily budget',value:''}],requested:{underlying:'MCX:CRUDEOIL26OCTFUT',lots:'3',trailing_enabled:false},active:{underlying:'MCX:CRUDEOIL26OCTFUT',lots:1,position:{symbol:'SECRET'},access_token:'SECRET'},now:'2026-10-07T17:40:00Z'});
assert.match(x.filename,/2026-10-07-23-10-00-IST.txt$/);assert.match(x.text,/Lots \[lots\]: 3/);assert.match(x.text,/Trailing \[trailing-enabled\]: false/);assert.match(x.text,/blank \/ optional default/);assert.match(x.text,/save not confirmed/);assert.doesNotMatch(x.text,/SECRET/);
const d=JSON.parse(x.text.split('Serialized configuration (text JSON):\n')[1]);assert.equal(d.requested_start_configuration.lots,'3');assert.equal(d.active_runner_configuration.lots,1);
});
test('chart and header reuse identical lifecycle handler, including in-flight and stop payload',async()=>{
const src=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8');const start=src.indexOf('    function syncChartControl()');const end=src.indexOf('    function renderTrades(',start);const nodes=Object.fromEntries(['toggle','chart-toggle','action-error','chart-action-error'].map(k=>[k,{hidden:true}]));const calls=[];let resolve;
const context={lastRunner:{running:false},toggleBusy:false,running:false,owned:false,el:k=>nodes[k],toggleState,payload:()=>({mode:'PAPER',underlying:'MCX:TEST'}),request:(route,payload)=>{calls.push({route,payload});return new Promise(r=>resolve=r);},status:async()=>{}};vm.createContext(context);vm.runInContext(src.slice(start,end),context);
assert.equal(nodes.toggle.onclick,nodes['chart-toggle'].onclick);const p=nodes['chart-toggle'].onclick();assert.equal(nodes.toggle.disabled,true);assert.equal(nodes['chart-toggle'].disabled,true);await nodes.toggle.onclick();assert.equal(calls.length,1);resolve();await p;
context.running=true;context.owned=true;context.lastRunner={running:true};const stop=nodes['chart-toggle'].onclick();assert.equal(calls[1].route,'stop');assert.equal(JSON.stringify(calls[1].payload),'{}');resolve();await stop;
context.request=async()=>{throw Error('fixture rejection')};await nodes['chart-toggle'].onclick();assert.equal(nodes['chart-action-error'].textContent,'fixture rejection');assert.equal(nodes['chart-action-error'].hidden,false);
});
test('explicit preference save preserves draft only and never calls runner lifecycle',async()=>{
const src=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8');const start=src.indexOf('    let savedDraft=null');const end=src.indexOf('    function invalidate()',start);const nodes=Object.fromEntries(['config-state','save-settings','export-settings'].map(k=>[k,{}]));const calls=[];const stored=[];const draft={symbol:'MCX:TEST',lots:'2','trailing-enabled':false};
const ctx={values:()=>draft,lastRunner:{running:true,config:{underlying:'MCX:TEST',mode:'PAPER'}},instanceId:'default',el:k=>nodes[k],stamp:()=> 'fixture time',request:async(route,p)=>{calls.push({route,p});return {saved_at:100};},localStorage:{setItem:(...a)=>stored.push(a)},storage:'settings',prefsTimer:null,clearTimeout};vm.createContext(ctx);vm.runInContext(src.slice(start,end),ctx);await nodes['save-settings'].onclick();
assert.equal(calls.length,1);assert.equal(calls[0].route,'settings');assert.equal(JSON.stringify(calls[0].p.settings),JSON.stringify(draft));assert.equal(JSON.parse(stored[0][1]).__saved_at,100);assert.match(nodes['config-state'].textContent,/Draft saved/);assert.match(nodes['config-state'].textContent,/edits apply on next Start/);
});
