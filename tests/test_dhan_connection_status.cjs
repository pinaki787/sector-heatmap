const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {JSDOM}=require(process.env.RENKO_JSDOM_MODULE||'/tmp/renko-family-dom/node_modules/jsdom');
test('Dhan status ignores unrelated edits, bounds pending requests, and reports unknown on timeout',async()=>{
 const dom=new JSDOM('<div class="view active" id="renko-supertrend"></div><select id="renko-broker"><option>DHAN</option></select><div class="broker-card"><span class="label"></span></div>',{url:'https://example.test'});
 const w=dom.window;w.BrokerForms={account:()=>({id:'owned',broker:'DHAN'})};
 let calls=0,interval,abortTimer;
 w.setInterval=f=>{interval=f};w.setTimeout=f=>{abortTimer=f;return 1};w.clearTimeout=()=>{};
 w.fetch=(url,options)=>{calls++;return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('timeout'))));};
 vm.runInNewContext(fs.readFileSync('broker-connection-status.js','utf8'),{window:w,document:w.document,fetch:w.fetch,AbortController,setTimeout:w.setTimeout,clearTimeout:w.clearTimeout,setInterval:w.setInterval,queueMicrotask,Date});
 interval();await Promise.resolve();
 for(let n=0;n<4;n++)w.document.dispatchEvent(new w.Event('change'));
 assert.equal(calls,1);assert.match(w.document.querySelector('#selected-broker-connection').textContent,/Checking/);
 abortTimer();await new Promise(setImmediate);
 assert.match(w.document.querySelector('#selected-broker-connection').textContent,/Status unavailable/);
 assert.equal(w.document.querySelector('#selected-broker-connect').hidden,true);
 dom.window.close();
});

