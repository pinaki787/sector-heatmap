const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('/home/trading/sector-heatmap/.private/test-node/node_modules/jsdom');
test('Backtest direct and complete saved output use readable reports, not JSON previews',async()=>{
 const dom=new JSDOM('<section id="renko-supertrend"></section>',{url:'https://example.test/',runScripts:'outside-only'}),w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.AbortSignal.timeout=()=>undefined;w.HTMLElement.prototype.scrollIntoView=function(){};
 const result={revision:'dated-contract-master-backtest-v2',status:'SUPERSEDED',underlying:'NSE:NIFTY50-INDEX',timeframe:'5 minutes',requested:{from_date:'2026-10-16',to_date:'2026-10-16'},settings:{ema_third_enabled:true,ema_third_length:100},coverage:{observed_trading_hours:6.25},issues:[{type:'SUPERSEDED_UNVERIFIED_LOT',message:'Prior sizing is withdrawn.'}],trades:[{contract:'NSE:EXACT',lot_size:null,quantity:null,lot_size_gap:{requested_date:'2026-10-16'},gross_pnl:null,net_pnl:null}],metrics:null};
 const job={job_id:'saved-test',kind:'ANALYSIS',feature:'renko-supertrend',label:'NIFTY backtest',created:1,updated:2,status:'COMPLETED',terminal:true,output:result,request:{account_id:'dashboard',path:'/api/renko-supertrend/backtest'}};
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[],account:()=>null};w.fetch=async()=>({ok:true,json:async()=>({jobs:[job]})});
 w.eval(fs.readFileSync('renko-backtest.js','utf8'));w.eval(fs.readFileSync('analysis-jobs.js','utf8'));await new Promise(r=>setTimeout(r,40));
 const generic=w.document.querySelector('[data-generic-job-output]');assert(generic);assert.equal(generic.querySelector('pre'),null);assert(!generic.textContent.includes('"revision"'));
 [...generic.querySelectorAll('button')].find(x=>x.textContent==='Open complete saved output').click();
 const rendered=w.document.querySelector('#runner-jobs .renko-saved-backtest-report');assert(rendered);assert.match(rendered.textContent,/Revision/);assert.match(rendered.textContent,/Status/);assert.match(rendered.textContent,/Superseded/);assert.match(rendered.textContent,/EMA Third Enabled/);assert.match(rendered.textContent,/Source|Lot Evidence|Lot evidence/);assert.equal(rendered.querySelector('pre'),null);assert(!rendered.textContent.includes('ema_third_enabled'));
 assert([...w.document.querySelectorAll('#runner-jobs button')].some(x=>x.textContent==='Download JSON audit'));
 assert.equal(w.RenkoBacktest.label('source_sha256'),'Source SHA-256');assert.equal(w.RenkoBacktest.label('snapshot_as_of'),'Snapshot As Of');assert.equal(w.RenkoBacktest.label('requested_date'),'Requested Date');const formatted=w.RenkoBacktest.fields({source_row:6478,ratio:'1.234567',status:'INCOMPLETE'});assert(formatted.includes('1.23'));assert(!formatted.includes('1.234567'));
 const direct=w.RenkoBacktest.report(result);assert(!direct.includes('<pre'));assert(!direct.includes('₹-904.63'));assert(direct.includes('withdrawn'));
 dom.window.close();
});