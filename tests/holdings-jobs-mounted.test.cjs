const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const {JSDOM}=require('jsdom');
const tick=()=>new Promise(r=>setImmediate(r));
const output={broker:'FYERS',as_of:'2026-10-16T08:00:00Z',generated_at:'2026-10-16T08:01:00Z',scope:'Fixture',total:1,analysed:1,portfolio:{priced_holdings_value:200,priced_rows:1,complete:true},rows:[{symbol:'VALIDATION_ONLY',action:'HOLD',kind:'DELIVERY_EQUITY',quantity:2,price:100,average_price:90,currency:'INR',reasons:['Fixture only'],limitations:[],evidence:{}}]};
test('holdings restores owned output and submits one cancellable server job',async()=>{
 const dom=new JSDOM('<nav class="nav"></nav><main class="work"></main>',{url:'https://host/',runScripts:'outside-only'});const w=dom.window;const calls=[],stops=[];let finish;
 const saved={feature:'holdings',status:'COMPLETED',created:1,request:{account_id:'dashboard',payload:{broker:'FYERS'}},output};
 w.SectorPulseWorkspace={admin:true,holdings_review_available:true,workspace:null,csrf:'fixture-csrf'};
 w.SectorPulseJobs={records:new Map([['saved',{job:saved}]]),open:()=>{},client:{cancel:async(base,id)=>stops.push({base,id})}};
 w.fetch=async(url,options)=>{calls.push({url,options});w.dispatchEvent(new w.CustomEvent('sector-pulse-job-submitted',{detail:{job:{...saved,job_id:'active',output:null},base:'https://host/api/jobs'}}));return new Promise(r=>{finish=r;});};
 w.eval(fs.readFileSync('holdings-review.js','utf8'));await tick();
 assert(w.document.body.textContent.includes('VALIDATION_ONLY'));
 w.document.getElementById('holdings-analyse').click();await tick();
 assert.equal(calls.length,1);assert.equal(calls[0].options.method,'POST');assert.equal(calls[0].url,'/api/holdings-analysis/analyze');assert.equal(calls[0].options.headers['X-CSRF-Token'],'fixture-csrf');
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{job:{...saved,job_id:'active',status:'RUNNING'},base:'https://host/api/jobs'}}));
 w.document.getElementById('holdings-cancel').click();await tick();assert.deepEqual(stops,[{base:'https://host/api/jobs',id:'active'}]);
 finish({ok:false,json:async()=>({error:'Stopped; partial output saved.'})});await tick();
 assert(w.document.body.textContent.includes('VALIDATION_ONLY'));assert(w.document.getElementById('holdings-status').textContent.includes('Partial review retained'));
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-output',{detail:{job:{...saved,request:{...saved.request,account_id:'other'},output:{...output,rows:[]}}}}));
 assert(w.document.body.textContent.includes('VALIDATION_ONLY'));
 dom.window.close();
});

test('all four owned brokers are selectable and native analysis releases on acceptance',async()=>{
 const dom=new JSDOM('<nav class="nav"></nav><main class="work"></main>',{url:'https://host/',runScripts:'outside-only'}),w=dom.window;
 const accounts=['FYERS','DHAN','MOTILAL_OSWAL','DELTA_INDIA'].map((broker,i)=>({id:'owner-'+i,broker,label:'Account '+i,configured:true}));
 const calls=[];
 w.SectorPulseWorkspace={admin:true,holdings_review_available:true,csrf:'test'};
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>accounts,initial:()=>null,account:()=>accounts.find(a=>'account:'+a.id===w.document.getElementById('holdings-broker').value),onChange:()=>{},fetch:async(kind,url,options)=>{calls.push({kind,url,options});return {ok:true,json:async()=>({job_accepted:true})};}};
 w.eval(fs.readFileSync('holdings-review.js','utf8'));await tick();
 const select=w.document.getElementById('holdings-broker');assert.equal(select.options.length,4);
 for(const a of accounts){select.value='account:'+a.id;select.dispatchEvent(new w.Event('change'));w.document.getElementById('holdings-analyse').click();await tick();const call=calls.at(-1),payload=JSON.parse(call.options.body);assert.equal(payload.account_id,a.id);assert.equal(payload.broker,a.broker);assert.equal(call.options.headers['X-Job-Return-Accepted'],'1');assert.equal(w.document.getElementById('holdings-analyse').disabled,false);}
 dom.window.close();
});
