const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
test('scheduled Manual selection and preview never submit; exact confirmation does',async()=>{
 const dom=new JSDOM('<section id="handoff"><header></header><section class="handoff-analysis-context"></section></section>',{url:'https://portal.example/',runScripts:'outside-only'});
 const w=dom.window,requests=[];
 w.BrokerForms={ready:Promise.resolve(),account:()=>({id:'owned',broker:'FYERS'})};
 w.fetch=async()=>({ok:true,json:async()=>({csrf:'synthetic'})});
 const data={policy:{mode:'MANUAL',capital:100000,enabled:true},session_bound:true,automatic_broker_supported:true,allocation:{available:'0'},
 recommendations:[{fingerprint:'a'.repeat(64),symbol:'NSE:TEST-EQ',direction:'BULLISH',score_fraction:'1',entry:100,stop:95,target:108}]};
 class XHR{
  open(method,url){this.method=method;this.url=url;} setRequestHeader(){}
  send(body){requests.push({method:this.method,url:this.url,body:body&&JSON.parse(body)});
   const result=this.url.endsWith('handoff-prepare')?{preview_id:'review',confirmation_phrase:'CONFIRM review',live_submission_enabled:true,items:[]}:
    this.url.endsWith('handoff-submit')?{status:'BROKER_REGISTERED',results:[{}],unsubmitted:0}:data;
   queueMicrotask(()=>{this.status=200;this.responseText=JSON.stringify(result);this.onload();});
  }
 }
 w.XMLHttpRequest=XHR;
 w.eval(fs.readFileSync(require.resolve('../handoff-schedule.js'),'utf8'));
 await new Promise(r=>setTimeout(r,25));
 const p=w.document.querySelector('.handoff-schedule'),n=k=>p.querySelector('[data-'+k+']');
 assert.equal(n('duplicate-reports').checked,false);
 assert.match(n('status').textContent,/available for new entries ₹0/);
 assert.equal(requests.filter(r=>r.method==='POST').length,0);
 n('clear').click();n('select-all').click();assert.equal(requests.filter(r=>r.method==='POST').length,0);
 n('prepare').click();await new Promise(r=>setImmediate(r));
 assert.deepEqual(requests.filter(r=>r.method==='POST').map(r=>r.url),['/api/notification-admin/handoff-prepare']);
 assert(n('submit').disabled);n('confirmation').value='wrong';n('confirmation').dispatchEvent(new w.Event('input'));assert(n('submit').disabled);
 n('confirmation').value='CONFIRM review';n('confirmation').dispatchEvent(new w.Event('input'));assert(!n('submit').disabled);
 n('submit').click();await new Promise(r=>setImmediate(r));n('submit').click();
 assert.equal(requests.filter(r=>r.url.endsWith('handoff-submit')).length,1);
 assert.equal(requests.find(r=>r.url.endsWith('handoff-submit')).body.confirmation,'CONFIRM review');
 dom.window.close();
});
