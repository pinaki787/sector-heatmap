const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
async function report(analysis){
 const dom=new JSDOM('<section id="handoff"><header></header></section>',{url:'https://portal.example/',runScripts:'outside-only'});
 const w=dom.window;w.HTMLDialogElement.prototype.showModal=function(){this.open=true};
 w.AbortSignal.timeout=()=>undefined;w.BrokerForms={ready:Promise.resolve(),accounts:()=>[]};
 const output={schema:'sector-pulse-auto-analysis/v1',instrument_route:'stock_options',cards:[{candidate:{symbol:'NSE:TEST-EQ',direction:'BEARISH'},analysis}]};
 const original=JSON.stringify(output);
 const job={job_id:'levels',kind:'ANALYSIS',feature:'handoff',label:'handoff',created:1,updated:2,status:'COMPLETED',terminal:true,output,request:{account_id:'dashboard',path:'/api/analysis-handoff/analyze'}};
 w.fetch=async()=>({ok:true,json:async()=>({jobs:[job]})});
 w.eval(fs.readFileSync(require.resolve('../handoff-level-report.js'),'utf8')); w.eval(fs.readFileSync(require.resolve('../analysis-jobs.js'),'utf8'));await new Promise(r=>setTimeout(r,25));
 [...w.document.querySelectorAll('button')].find(b=>b.textContent==='Open saved output').click();
 const plan=w.document.querySelector('.report-plan');
 const fields=Object.fromEntries([...plan.querySelectorAll('dt')].map(n=>[n.textContent,n.nextElementSibling.textContent]));
 assert.equal(JSON.stringify(output),original,'rendering must not change saved output');
 return {dom,plan,fields};
}
test('saved bought-option proposal separates underlying invalidation and premium target',async()=>{
 const {dom,plan,fields}=await report({kind:'LONG_OPTION',entry:389.25,status:'REQUIRES_INVALIDATION_ACCEPTANCE',active_invalidation:null,recommended_invalidation:{price:411.74},proposal:{underlying_invalidation:411.74,target_exit_points:10},target:350});
 try{
  assert.equal(fields['Entry · underlying'],'₹389.25');assert.equal(fields['Stop-loss · underlying · proposed'],'₹411.74');
  assert.equal(fields['Target · option premium'],'₹10.00');assert.match(plan.textContent,/acceptance and fresh ticket review/);
  assert.match(plan.textContent,/not an option-premium stop/);assert.equal(fields['Target'],undefined);
 }finally{dom.window.close()}
});
test('accepted invalidation takes precedence without replacing premium target with underlying target',async()=>{
 const {dom,fields,plan}=await report({kind:'LONG_OPTION',entry:100,active_invalidation:{price:105,target:90},recommended_invalidation:{price:110},proposal:{underlying_invalidation:110,target_exit_points:12}});
 try{assert.equal(fields['Stop-loss · underlying'],'₹105.00');assert.equal(fields['Target · option premium'],'₹12.00');assert.doesNotMatch(plan.textContent,/Proposed invalidation only/)}finally{dom.window.close()}
});
test('legacy option proposal fallback retains stop and leaves absent premium target unset',async()=>{
 const {dom,fields}=await report({kind:'LONG_OPTION',entry:100,proposal:{underlying_invalidation:106},target:90});
 try{assert.equal(fields['Stop-loss · underlying · proposed'],'₹106.00');assert.equal(fields['Target · option premium'],'Not set in saved plan')}finally{dom.window.close()}
});
test('cash plans retain their own target and distinguish proposed sizing',async()=>{
 const {dom,fields}=await report({kind:'EQUITY',entry:100,proposed_sizing:{price:105,target:90},recommended_invalidation:{price:110}});
 try{assert.equal(fields['Entry'],'₹100.00');assert.equal(fields['Stop-loss · proposed'],'₹105.00');assert.equal(fields['Target'],'₹90.00')}finally{dom.window.close()}
});

test('estimated premium stop remains separate and recomputed stop takes precedence',async()=>{
 const {dom,fields,plan}=await report({kind:'LONG_OPTION',entry:100,active_invalidation:{price:105,premium_stop_estimate:{status:'ESTIMATED',stop_loss_price:3.25,assumptions:'Constant IV scenario; no order placed.'}},proposal:{entry_points:5,premium_stop_estimate:{status:'ESTIMATED',stop_loss_price:4},target_exit_points:10}});
 try{assert.equal(fields['Entry · option premium'],'₹5.00');assert.equal(fields['Premium stop · estimated'],'₹3.25');assert.equal(fields['Stop-loss · underlying'],'₹105.00');assert.equal(fields['Target · option premium'],'₹10.00');assert.match(plan.textContent,/Constant IV scenario/)}finally{dom.window.close()}
});

test('new saved horizon schema shows separate levels without duplicating the old flat premium target',async()=>{
 const {dom,fields,plan}=await report({kind:'LONG_OPTION',entry:950,status:'REQUIRES_INVALIDATION_ACCEPTANCE',recommended_invalidation:{price:981},proposal:{entry_points:8.8,target_exit_points:17.6,premium_stop_estimate:{status:'ESTIMATED',stop_loss_price:.6}},report_levels:{contract:{symbol:'NSE:VOLTAS26OCT940PE',strike:940,option_type:'PE',expiry:'2026-10-27'},horizons:{intraday:{basis:'Completed 15m',underlying:{entry:950,target:947.7,stop_loss:952.3},premium:{entry:8.8,target:10.25,stop_loss:7.55}},swing:{basis:'Completed Daily',underlying:{entry:950,target:919,stop_loss:981},premium:{entry:8.8,target:42.6,stop_loss:.6}}}}});
 try{assert.equal(fields['Underlying symbol'],'NSE:TEST-EQ');assert.equal(fields['Target · option premium'],undefined);assert.equal(fields['Premium stop · estimated'],undefined);assert.match(plan.textContent,/₹947.70/);assert.match(plan.textContent,/₹952.30/);assert.match(plan.textContent,/₹42.60/);assert.match(plan.textContent,/₹7.55/);assert.match(plan.textContent,/Put \(PE\)/);assert.match(plan.textContent,/2026-10-27/);assert.match(plan.textContent,/report-only/)}finally{dom.window.close()}
});
