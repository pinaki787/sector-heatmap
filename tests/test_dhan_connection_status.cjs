const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {JSDOM}=require(process.env.RENKO_JSDOM_MODULE||'jsdom');
test('Dhan status ignores unrelated edits, bounds pending requests, and reports unknown on timeout',async()=>{
 const dom=new JSDOM('<div class="view active" id="renko-supertrend"></div><select id="renko-broker"><option>DHAN</option></select><div class="broker-card"><span class="label"></span></div>',{url:'https://example.test'});
 const w=dom.window;w.BrokerForms={context:()=>({workspace:null}),account:()=>({id:'owned',broker:'DHAN'})};
 let calls=0,interval,abortTimer;
 w.setInterval=f=>{interval=f};w.setTimeout=f=>{abortTimer=f;return 1};w.clearTimeout=()=>{};
 w.fetch=(url,options)=>{calls++;return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('timeout'))));};
 vm.runInNewContext(fs.readFileSync('broker-connection-status.js','utf8'),{window:w,document:w.document,location:w.location,URLSearchParams:w.URLSearchParams,fetch:w.fetch,AbortController,setTimeout:w.setTimeout,clearTimeout:w.clearTimeout,setInterval:w.setInterval,queueMicrotask,Date});
 interval();await Promise.resolve();
 for(let n=0;n<4;n++)w.document.dispatchEvent(new w.Event('change'));
 assert.equal(calls,1);assert.match(w.document.querySelector('#selected-broker-connection').textContent,/Checking/);
 abortTimer();await new Promise(setImmediate);
 assert.match(w.document.querySelector('#selected-broker-connection').textContent,/Status unavailable/);
 assert.equal(w.document.querySelector('#selected-broker-connect').hidden,true);
 dom.window.close();
});


test('confirmed Dhan expiry opens one account-bound reauthentication prompt',async()=>{
 const dom=new JSDOM('<div class="view active" id="renko-supertrend"></div><select id="renko-broker"><option>DHAN</option></select><div class="broker-card"><span class="label"></span></div>',{url:'https://example.test',pretendToBeVisual:true});
 const w=dom.window;w.BrokerForms={context:()=>({workspace:null}),account:()=>({id:'owned',broker:'DHAN',label:'My Dhan'})};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 let interval;w.setInterval=f=>{interval=f};
 w.fetch=async()=>({ok:true,json:async()=>({authenticated:false,reauthentication_required:true})});
 vm.runInNewContext(fs.readFileSync('broker-connection-status.js','utf8'),{window:w,document:w.document,location:w.location,URLSearchParams:w.URLSearchParams,fetch:w.fetch,AbortController,setTimeout,clearTimeout,setInterval:w.setInterval,queueMicrotask,Date});
 await interval();await new Promise(setImmediate);
 assert.equal(w.document.querySelectorAll('dialog').length,1);
 assert.match(w.document.querySelector('dialog a').href,/reauth_dhan=owned/);
 assert.match(w.document.querySelector('#selected-broker-connection').textContent,/Sign-in required/);
 await interval();assert.equal(w.document.querySelectorAll('dialog').length,1);
 w.close();
});

test('Holdings selection and Investment retain the owned Dhan account for sidebar status',async()=>{
 const dom=new JSDOM('<div class="view active" id="holdings"></div><div class="broker-card"><span class="label"></span></div>',{url:'https://example.test'});
 const w=dom.window,owned={id:'private-dhan',broker:'DHAN',configured:true};
 const kinds=[],urls=[];let interval;
 w.BrokerForms={context:()=>({workspace:null}),accounts:()=>[owned],account:kind=>{kinds.push(kind);return kind==='holdings'?owned:null;}};
 w.setInterval=f=>{interval=f};w.fetch=async url=>{urls.push(url);return {ok:true,json:async()=>({authenticated:true})};};
 vm.runInNewContext(fs.readFileSync('broker-connection-status.js','utf8'),{window:w,document:w.document,location:w.location,URLSearchParams:w.URLSearchParams,fetch:w.fetch,AbortController,setTimeout,clearTimeout,setInterval:w.setInterval,queueMicrotask,Date});
 await new Promise(setImmediate);
 assert.ok(kinds.includes('holdings'));
 assert.deepEqual(urls,['/api/dhan/status?account_id=private-dhan']);
 assert.match(w.document.querySelector('#selected-broker-connection').textContent,/Dhan · Connected/);
 w.document.querySelector('.view').id='investment';await interval();
 assert.match(w.document.querySelector('#selected-broker-connection').textContent,/Dhan · Connected/);
 assert.equal(urls.length,1);
 w.close();
});

test('FYERS only prompts after confirmed rejection and reuses daily dismissal across reloads',async()=>{
 const dom=new JSDOM('<div class="view active" id="handoff"></div><div class="broker-card"><span class="label"></span></div>',{url:'https://example.test',pretendToBeVisual:true,runScripts:'outside-only'});
 const w=dom.window,owned={id:'fyers-owned',broker:'FYERS',label:'My FYERS'};
 w.BrokerForms={context:()=>({workspace:null}),account:()=>owned};w.setInterval=()=>1;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;};
 let rejected=false;
 w.fetch=async()=>({ok:true,json:async()=>({authenticated:false,reauthentication_required:rejected,status_unavailable:!rejected})});
 const source=fs.readFileSync('broker-connection-status.js','utf8');
 w.eval(source);await new Promise(setImmediate);
 assert.equal(w.document.querySelectorAll('dialog').length,0);
 rejected=true;w.eval(source);await new Promise(setImmediate);
 assert.equal(w.document.querySelectorAll('dialog').length,1);
 assert.match(w.document.querySelector('dialog').textContent,/latest saved authorization/);
 w.document.querySelector('dialog button').click();
 w.eval(source);await new Promise(setImmediate);
 assert.equal(w.document.querySelectorAll('dialog').length,0);
 assert.match(w.document.querySelector('#selected-broker-connection').textContent,/Sign-in required/);
 w.close();
});
