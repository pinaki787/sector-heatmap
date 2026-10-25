const test=require('node:test'),assert=require('node:assert/strict');
const {rejectedRestart}=require('../resource-restarts.js');
test('rejected request stays terminal after legacy waiting/unknown transitions',()=>{
 for(const status of ['FAILED','WAITING','UNKNOWN'])assert.equal(rejectedRestart({status,events:[{message:'Restart blocked: stop and reconcile active runners, retained positions and pending orders first.'},{message:'Waiting for this restart request to appear; no duplicate command will be sent.'}]}),true);
 assert.equal(rejectedRestart({submissionRejected:true}),true);
});
test('accepted or transport-uncertain restart still supports readiness probes',()=>{
 assert.equal(rejectedRestart({status:'WAITING',events:[{message:'Submission outcome unconfirmed; checking status without sending another restart.'}]}),false);
 assert.equal(rejectedRestart({accepted:true,events:[{message:'Restart accepted'}]}),false);
 assert.equal(rejectedRestart(null),false);
});

test('mount recovers the reported stale request without polling or offering status check',async()=>{
 const {JSDOM}=require('/home/trading/sector-heatmap/.private/test-node/node_modules/jsdom');
 const fs=require('node:fs'),dom=new JSDOM('<section id="resources"><header></header></section>',{url:'https://example.test/',runScripts:'outside-only'});
 const w=dom.window,calls=[];w.AbortSignal=AbortSignal;
 w.localStorage.setItem('sector-pulse:service-restart:test',JSON.stringify({id:'rejected-request',kind:'dashboard',label:'Dashboard',status:'UNKNOWN',startedAt:1,events:[{at:1,message:'Restart blocked: stop and reconcile active runners, retained positions and pending orders first.'}]}));
 w.fetch=async url=>{calls.push(url);return {ok:true,json:async()=>({accounts:[]})};};
 w.eval(fs.readFileSync('resource-restarts.js','utf8'));w.ServerRestarts.mount(w.document.querySelector('#resources'),{admin:true,username:'test'});
 await new Promise(resolve=>setTimeout(resolve,10));
 assert.equal(w.document.querySelector('[data-check]').hidden,true);
 assert.equal(w.document.querySelector('[data-dashboard]').disabled,false);
 assert.match(w.document.querySelector('[data-outcome]').textContent,/BLOCKED.*no restart was scheduled/);
 assert.equal(calls.filter(url=>/service-restart-status|bounce-status/.test(url)).length,0);
 dom.window.close();
});
