
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM}=require('jsdom');
test('runner inventory defaults manual, persists interval and retains cards while reading',async()=>{
 const dom=new JSDOM('<nav></nav>',{url:'https://portal.example/',runScripts:'outside-only'}),w=dom.window;
 const timers=new Map();let next=0,reads=0,hold=false,release;
 w.setInterval=(fn,ms)=>{timers.set(++next,{fn,ms});return next;};w.clearInterval=id=>timers.delete(id);
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
 w.AbortSignal.timeout=()=>undefined;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[{id:'mine',label:'Mine',broker:'MOTILAL_OSWAL',configured:true}]};
 w.fetch=async(url,options)=>{assert.notEqual(options.method,'POST');reads++;if(hold)await new Promise(r=>release=r);return {ok:true,json:async()=>({instances:[{instance_key:'x',run_id:'r',running:true,config:{underlying:'NIFTY',mode:'PAPER'},job_history:[{started_at:1,status:'Watching'}]}]})};};
 w.eval(fs.readFileSync('runner-jobs.js','utf8'));w.document.dispatchEvent(new w.Event('DOMContentLoaded'));await new Promise(setImmediate);
 const select=w.document.querySelector('[data-refresh-interval]');assert.equal(select.value,'0');assert.equal(timers.size,0);
 w.document.querySelector('nav button').click();await new Promise(setImmediate);
 const card=w.document.querySelector('.runner-job-card');assert.ok(card);card.querySelector('details').open=true;
 select.value='30000';select.dispatchEvent(new w.Event('change'));assert.equal(timers.size,1);assert.equal([...timers.values()][0].ms,30000);
 assert.equal(w.localStorage.getItem('sector-pulse:runner-jobs:refresh-interval'),'30000');
 hold=true;w.document.querySelector('[data-refresh]').click();await new Promise(setImmediate);assert.equal(w.document.querySelector('.runner-job-card'),card);
 release();await new Promise(setImmediate);assert.equal(w.document.querySelector('.runner-job-card details').open,true);
 select.value='0';select.dispatchEvent(new w.Event('change'));assert.equal(timers.size,0);assert.equal(reads,2);
 dom.window.close();
});
