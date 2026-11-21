const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
const {inventoryGroup}=require('../runner-jobs.js');
test('stopped exposure and pending orders are separate from running and clean history',()=>{
 for(const state of [{position:{}},{pending:{id:'p'}}])assert.equal(inventoryGroup({state}),'attention');
 assert.equal(inventoryGroup({state:{running:true,position:{}}}),'running');
 assert.equal(inventoryGroup({state:{shutdown_pending:true}}),'running');
 assert.equal(inventoryGroup({state:{running:false}}),'history');
});
test('unchecked history hides stopped exposure; select running excludes it',async()=>{
 const dom=new JSDOM('<nav></nav>',{url:'https://portal.example/',runScripts:'outside-only'}),w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.setInterval=()=>0;w.AbortSignal.timeout=()=>undefined;
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[{id:'mine',label:'Mine',broker:'MOTILAL_OSWAL',configured:true}]};
 const states=[{instance_key:'run',running:true},{instance_key:'exposure',position:{quantity:1}},{instance_key:'pending',pending:{id:'p'}},{instance_key:'flat'}].map(s=>({...s,run_id:s.instance_key,config:{underlying:s.instance_key}}));
 w.fetch=async(url,o)=>{assert.notEqual(o.method,'POST');return {ok:true,json:async()=>({instances:states})};};
 w.eval(fs.readFileSync('runner-jobs.js','utf8'));w.document.dispatchEvent(new w.Event('DOMContentLoaded'));await new Promise(setImmediate);
 w.document.querySelector('nav button').click();await new Promise(setImmediate);
 assert.equal(w.document.querySelector('[data-count]').textContent,'1 running · 2 stopped requiring review');
 assert.equal(w.document.querySelectorAll('article[data-inventory-group="attention"]').length,0);
 assert.equal(w.document.querySelectorAll('article[data-inventory-group="history"]').length,0);
 w.document.querySelector('[data-select-all]').click();
 assert.equal(w.document.querySelectorAll('article input:checked').length,1);
 assert.equal(w.document.querySelector('article[data-inventory-group="running"] input').checked,true);
 const history=w.document.querySelector('[data-history]');history.checked=true;history.dispatchEvent(new w.Event('change'));
 assert.equal(w.document.querySelectorAll('article[data-inventory-group="history"]').length,1);
 assert.equal(w.document.querySelectorAll('article[data-inventory-group="attention"]').length,2);
 history.checked=false;history.dispatchEvent(new w.Event('change'));
 assert.equal(w.document.querySelectorAll('article[data-inventory-group="attention"]').length,0);
 history.checked=true;history.dispatchEvent(new w.Event('change'));

 assert.equal(w.document.querySelector('article[data-inventory-group="history"] input').disabled,true);
 dom.window.close();
});
