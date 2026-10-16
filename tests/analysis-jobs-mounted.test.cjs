const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const {JSDOM}=require('jsdom');
const tick=()=>new Promise(r=>setImmediate(r));
test('saved runner history attaches when the existing runner dialog mounts later',async()=>{
 const dom=new JSDOM('<nav></nav><section id="handoff"></section><section id="screener"></section>',{url:'https://host/',runScripts:'outside-only'});const w=dom.window;
 w.fetch=async()=>({ok:true,json:async()=>({jobs:[]})});w.BrokerForms={ready:Promise.resolve(),accounts:()=>[]};
 w.Headers=Headers;w.Response=Response;w.AbortSignal=AbortSignal;
 w.eval(fs.readFileSync('analysis-jobs.js','utf8'));await tick();
 assert(w.SectorPulseJobs);assert.equal(w.document.querySelectorAll('#handoff button').length,1);
 const dialog=w.document.createElement('dialog');dialog.setAttribute('aria-label','Runner jobs');w.document.body.append(dialog);await tick();
 assert.equal(dialog.querySelectorAll('[data-durable-jobs]').length,1);
 dialog.append(w.document.createElement('span'));await tick();assert.equal(dialog.querySelectorAll('[data-durable-jobs]').length,1);
 dom.window.close();
});

test('reload hydrates the last displayed job even when it is outside the first history page',async()=>{
 const dom=new JSDOM('<section id="handoff"></section>',{url:'https://host/',runScripts:'outside-only'});const w=dom.window;const restored=[],reads=[];const id='a'.repeat(32);
 const job={job_id:id,created:1,updated:2,feature:'handoff',kind:'ANALYSIS',status:'COMPLETED',terminal:true,request:{path:'/api/analysis-handoff/analyze-market',account_id:'dashboard'},output:{kind:'MARKET_HANDOFF',ai_review:{summary:'Saved old result'}}};
 w.Headers=Headers;w.Response=Response;w.AbortSignal=AbortSignal;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[]};
 w.localStorage.setItem('sector-pulse:durable-job-references:v1',JSON.stringify([{key:'old',base:'https://host/api/jobs',job_id:id,created:1}]));
 w.fetch=async url=>{reads.push(String(url));return {ok:true,json:async()=>new URL(url).searchParams.has('job_id')?job:{jobs:[],next_before:null}};};
 w.addEventListener('sector-pulse-job-output',event=>restored.push(event.detail.output));w.eval(fs.readFileSync('analysis-jobs.js','utf8'));await tick();await tick();
 assert(reads.some(url=>new URL(url).searchParams.get('job_id')===id));assert(restored.some(value=>value.ai_review.summary==='Saved old result'));
 dom.window.close();
});

test('a job finishing after reload automatically renders its output and stores only a reference',async()=>{
 const dom=new JSDOM('<section id="handoff"></section>',{url:'https://host/',runScripts:'outside-only'});const w=dom.window;const restored=[];const id='b'.repeat(32);
 const job={job_id:id,created:1,updated:2,feature:'handoff',kind:'ANALYSIS',status:'RUNNING',terminal:false,request:{path:'/api/analysis-handoff/analyze-market',account_id:'dashboard'},output:null};
 w.Headers=Headers;w.Response=Response;w.AbortSignal=AbortSignal;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[]};
 w.fetch=async url=>({ok:true,json:async()=>new URL(url).searchParams.has('job_id')?{...job,status:'COMPLETED',terminal:true,output:{answer:'Completed after reload'}}:{jobs:[job],next_before:null}});
 w.addEventListener('sector-pulse-job-output',event=>restored.push(event.detail.output));w.eval(fs.readFileSync('analysis-jobs.js','utf8'));await tick();await tick();
 assert(restored.some(value=>value.answer==='Completed after reload'));
 const references=JSON.parse(w.localStorage.getItem('sector-pulse:durable-job-references:v1'));assert.equal(references[0].job_id,id);assert(!JSON.stringify(references).includes('Completed after reload'));
 dom.window.close();
});

test('explicit asynchronous submission returns its job immediately and later renders output automatically',async()=>{
 const dom=new JSDOM('<section id="handoff"></section>',{url:'https://host/',runScripts:'outside-only'}),w=dom.window;const restored=[],id='c'.repeat(32);let finish;
 const pending=new Promise(resolve=>finish=resolve);
 const job={job_id:id,created:1,updated:2,feature:'handoff',kind:'ANALYSIS',status:'RUNNING',terminal:false,request:{path:'/api/analysis-handoff/analyze',account_id:'dashboard'},output:null};
 w.Headers=Headers;w.Response=Response;w.AbortSignal=AbortSignal;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[]};
 w.fetch=async(url,options={})=>options.method==='POST'?new Response(JSON.stringify({job_id:id,account_id:'dashboard',job}),{status:202,headers:{'Content-Type':'application/json'}}):new URL(url,w.location.href).searchParams.has('job_id')?pending:{ok:true,json:async()=>({jobs:[]})};
 w.addEventListener('sector-pulse-job-output',event=>restored.push(event.detail.output));w.eval(fs.readFileSync('analysis-jobs.js','utf8'));await tick();
 const accepted=await w.fetch('/api/analysis-handoff/analyze',{method:'POST',headers:{'X-Job-Return-Accepted':'1'}});assert.equal(accepted.status,202);assert.equal((await accepted.json()).job_accepted,true);assert.equal(restored.length,0);
 finish({ok:true,json:async()=>({...job,status:'COMPLETED',terminal:true,output:{answer:'Later output'}})});await tick();await tick();assert.equal(restored[0].answer,'Later output');dom.window.close();
});

test('a backtest without a dedicated restore handler renders its saved output in the correct section',async()=>{
 const dom=new JSDOM('<section id="renko-engine"></section>',{url:'https://host/',runScripts:'outside-only'}),w=dom.window;let selected='ours';
 const job={job_id:'d'.repeat(32),created:1,updated:2,feature:'renko-engine',kind:'ANALYSIS',label:'Fixture backtest',status:'COMPLETED',terminal:true,request:{path:'/api/renko-engine/ours/backtest',account_id:'ours'},output:{summary:'Retained simulated research'}};
 w.Headers=Headers;w.Response=Response;w.AbortSignal=AbortSignal;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[],account:()=>({id:selected})};w.fetch=async()=>({ok:true,json:async()=>({jobs:[job],next_before:null})});
 w.eval(fs.readFileSync('analysis-jobs.js','utf8'));await tick();await tick();assert.match(w.document.querySelector('[data-generic-job-output]').textContent,/Retained simulated research/);
 selected='other';w.dispatchEvent(new w.CustomEvent('broker-account-change'));await tick();assert.equal(w.document.querySelector('[data-generic-job-output]'),null);dom.window.close();
});

test('saved analysis waits for a strategy section that mounts later',async()=>{
 const dom=new JSDOM('<main></main>',{url:'https://host/',runScripts:'outside-only'}),w=dom.window;
 const job={job_id:'e'.repeat(32),created:1,updated:2,feature:'renko-engine',kind:'ANALYSIS',label:'Late backtest',status:'COMPLETED',terminal:true,request:{path:'/api/renko-engine/a/backtest',account_id:'a'},output:{summary:'Late section result'}};
 w.Headers=Headers;w.Response=Response;w.AbortSignal=AbortSignal;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[],account:()=>({id:'a'})};w.fetch=async()=>({ok:true,json:async()=>({jobs:[job]})});w.eval(fs.readFileSync('analysis-jobs.js','utf8'));await tick();
 const section=w.document.createElement('section');section.id='renko-engine';w.document.querySelector('main').append(section);await tick();assert.match(section.textContent,/Late section result/);dom.window.close();
});

test('native holdings paths with account query use the portfolio renderer',async()=>{
 const dom=new JSDOM('<section id="holdings"></section>',{url:'https://host/',runScripts:'outside-only'}),w=dom.window;const outputs=[];
 const job={job_id:'f'.repeat(32),created:1,updated:2,feature:'holdings',kind:'ANALYSIS',label:'Portfolio analysis',status:'COMPLETED',terminal:true,request:{path:'/api/motilal/holdings-analysis/analyze?account_id=ours',account_id:'ours'},output:{rows:[]}};
 w.Headers=Headers;w.Response=Response;w.AbortSignal=AbortSignal;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[],account:()=>({id:'ours'}),kind:()=> 'holdings'};w.fetch=async()=>({ok:true,json:async()=>({jobs:[],next_before:null})});
 w.addEventListener('sector-pulse-job-output',e=>outputs.push(e.detail));w.eval(fs.readFileSync('analysis-jobs.js','utf8'));await tick();w.SectorPulseJobs.restore({job,base:'https://host/api/jobs'});assert.equal(outputs.length,1);assert.equal(w.document.querySelector('[data-generic-job-output]'),null);dom.window.close();
});
