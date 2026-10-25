const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
test('aliased account histories show one failed job and its actionable error',async()=>{
 const dom=new JSDOM('<section id="handoff"><header></header></section>',{url:'https://portal.example/broker-workspace/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/',runScripts:'outside-only'});
 const w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.AbortSignal.timeout=()=>undefined;
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[{id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',broker:'FYERS',configured:true}]};
 const job={job_id:'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',kind:'ANALYSIS',feature:'handoff',label:'handoff · analysis',created:1,updated:2,status:'FAILED',terminal:true,error:'FYERS account read timed out; refresh required.',request:{account_id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',path:'/api/analysis-handoff/analyze'}};
 w.fetch=async()=>({ok:true,json:async()=>({jobs:[job]})});
 w.eval(fs.readFileSync(require.resolve('../analysis-jobs.js'),'utf8'));
 await new Promise(r=>setTimeout(r,25));
 assert.equal(w.SectorPulseJobs.records.size,1);
 const rows=w.document.querySelectorAll('#runner-jobs .saved-jobs-catalog > article');
 assert.equal(rows.length,1);
 assert.match(rows[0].textContent,/account read timed out/);
 dom.window.close();
});

test('opening a saved output focuses and reveals it below a long job list',async()=>{
 const dom=new JSDOM('<section id="handoff"><header></header></section>',{url:'https://portal.example/',runScripts:'outside-only'});
 const w=dom.window;w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.AbortSignal.timeout=()=>undefined;
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[]};
 const job={job_id:'saved',kind:'ANALYSIS',feature:'handoff',label:'Saved findings',created:1,updated:2,status:'COMPLETED',terminal:true,
  output:{cards:[{candidate:{name:'Synthetic Equity'}}]},request:{account_id:'dashboard',path:'/api/analysis-handoff/analyze'}};
 w.fetch=async()=>({ok:true,json:async()=>({jobs:[job]})});
 let revealed=null;w.HTMLElement.prototype.scrollIntoView=function(){revealed=this};
 w.eval(fs.readFileSync(require.resolve('../analysis-jobs.js'),'utf8'));
 await new Promise(r=>setTimeout(r,25));
 const open=[...w.document.querySelectorAll('button')].find(b=>b.textContent==='Open saved output');
 w.SectorPulseJobs.open();
 open.click();assert(revealed);assert.equal(w.document.activeElement,revealed);
 assert.match(revealed.textContent,/Synthetic Equity/);
 dom.window.close();
});

test('saved Handoff reports show readable prices and directions with raw data collapsed',async()=>{
 const dom=new JSDOM('<section id="handoff"><header></header></section>',{url:'https://portal.example/',runScripts:'outside-only'});
 const w=dom.window;w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.AbortSignal.timeout=()=>undefined;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[]};
 const output={schema:'sector-pulse-auto-analysis/v1',generated_at:'2026-10-21T10:30:00+05:30',source:{broker:'FYERS'},instrument_route:'cash_equity',
 scope:{scanned_stocks:6,matched_stocks:2,eligible_sectors:2},
 cards:[{candidate:{name:'<img src=x onerror=alert(1)>',symbol:'NSE:TEST-EQ',direction:'BEARISH'},analysis:{kind:'EQUITY',entry:100,target:90,status:'REQUIRES_INVALIDATION',active_invalidation:{price:105,target:90},conviction:{score:6,maximum_score:6,rating:'High'},data_quality:'DELAYED'}}],
 exclusions:[{symbol:'NSE:OTHER-EQ',reason:'Existing position'}]};
 const job={job_id:'formatted',kind:'ANALYSIS',feature:'handoff',label:'handoff · analysis',created:1,updated:2,status:'COMPLETED',terminal:true,output,request:{account_id:'dashboard',path:'/api/analysis-handoff/analyze'}};
 w.fetch=async()=>({ok:true,json:async()=>({jobs:[job]})});
 w.eval(fs.readFileSync(require.resolve('../analysis-jobs.js'),'utf8'));await new Promise(r=>setTimeout(r,25));
 w.SectorPulseJobs.open();
 [...w.document.querySelectorAll('button')].find(b=>b.textContent==='Open saved output').click();
 const report=w.document.querySelector('.saved-analysis-report');
 assert.match(report.textContent,/6 stocks examined/);assert.match(report.textContent,/10.00\/10/);
 assert.match(report.textContent,/₹100.00/);assert.match(report.textContent,/₹105.00/);
 assert(report.querySelector('.report-plan.bearish'));assert.equal(report.querySelectorAll('img').length,0);
 assert.equal(report.querySelector('details[data-audit-key="full-saved-data"]').open,false);
 assert.equal(report.querySelector('details[data-audit-key="analysis-exclusions"]').open,false);
 dom.window.close();
});

test('saved outputs use creation time, unaffected by incidental progress refreshes',async()=>{
 const dom=new JSDOM('<section id="handoff"><header></header></section>',{url:'https://portal.example/',runScripts:'outside-only'});
 const w=dom.window;w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.AbortSignal.timeout=()=>undefined;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[]};
 const make=(id,label,created,updated,kind='ANALYSIS')=>({job_id:id,label,kind,feature:'handoff',created,updated,status:'COMPLETED',terminal:true,output:{cards:[]},request:{account_id:'dashboard',path:'/api/analysis-handoff/analyze'}});
 const jobs=[make('old','Earlier completion',20,30),make('runner','Runner history',100,200,'RUNNER'),make('new','Latest completed analysis',10,90),make('missing','Fallback creation time',5,undefined)];
 w.fetch=async()=>({ok:true,json:async()=>({jobs})});
 w.eval(fs.readFileSync(require.resolve('../analysis-jobs.js'),'utf8'));await new Promise(r=>setTimeout(r,25));
 w.document.querySelector('[data-jobs-kind]').value='';w.document.querySelector('[data-jobs-kind]').dispatchEvent(new w.Event('change'));
 const labels=[...w.document.querySelectorAll('#runner-jobs .saved-job-title strong')].map(n=>n.textContent);
 assert.deepEqual(labels,['Runner history','Earlier completion','Latest completed analysis','Fallback creation time']);
 dom.window.close();
});
