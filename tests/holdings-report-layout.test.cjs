const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('/tmp/sector-parser-test-deps/node_modules/jsdom');
test('AI evidence stays collapsed in its holding row; updates preserve filters and disclosure state',async()=>{
 const d=new JSDOM('<nav class="nav"><button data-view="investment"></button></nav><main class="work"></main>',{url:'https://example.test',runScripts:'outside-only'}),w=d.window;
 const account={id:'owned',broker:'DHAN',label:'Algo',configured:true};
 w.SectorPulseWorkspace={username:'test-user',admin:false,allowed_features:['holdings'],holdings_review_available:true};
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[account],account:()=>account,initial:()=>null};
 w.eval(fs.readFileSync('fundamental-report.js','utf8'));w.eval(fs.readFileSync('holdings-review.js','utf8'));
 w.document.dispatchEvent(new w.Event('DOMContentLoaded'));await new Promise(setImmediate);
 const row={id:'r',symbol:'NSE:TEST-EQ',action:'REVIEW_NEEDED',kind:'DELIVERY_EQUITY',quantity:1,average_price:100,price:101,currency:'INR',gross_pnl:1,reasons:['Captured evidence'],limitations:['Captured limit'],fundamentals:{evidence:{company_name:'Test Company',status:'VERIFIED',metrics:{revenue_crore:123}},feedback:{summary:'Preserved financial evidence'}}};
 const job={job_id:'job',feature:'holdings',kind:'ANALYSIS',status:'RUNNING',terminal:false,request:{account_id:'owned',payload:{broker:'DHAN'}},output:{account_id:'owned',broker:'DHAN',ai_provider:'CODEX_CHATGPT',as_of:new Date().toISOString(),rows:[row],total:1,analysed:1}};
 const output=()=>w.dispatchEvent(new w.CustomEvent('sector-pulse-job-output',{detail:{job}}));output();
 assert.equal(w.document.querySelector('#holdings-ai-feedback'),null);
 const evidence=w.document.querySelector('#holdings-rows tr .fundamental-report');assert.ok(evidence);assert.equal(evidence.open,false);assert.match(evidence.textContent,/Preserved financial evidence/);
 evidence.open=true;w.document.querySelector('#holdings-pnl-filter').value='PROFIT';w.document.querySelector('#holdings-filter').value='REVIEW_NEEDED';output();
 assert.equal(w.document.querySelector('#holdings-rows .fundamental-report').open,true);
 assert.equal(w.document.querySelector('#holdings-pnl-filter').value,'PROFIT');assert.equal(w.document.querySelector('#holdings-filter').value,'REVIEW_NEEDED');
 assert.equal(w.document.querySelectorAll('.fundamental-report').length,1);d.window.close();
});
