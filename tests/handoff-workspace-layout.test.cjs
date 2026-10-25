const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('/home/trading/sector-heatmap/.private/test-node/node_modules/jsdom');
const {organizeHandoff}=require('../market-handoff.js');
function fixture(){return new JSDOM('<section id="handoff"><button id="saved">Saved jobs & outputs</button><header class="head"><h1>Analysis handoff</h1></header><div class="handoff-grid"><section class="panel"><label>Broker<select id="ticket-broker"><option value="FYERS" selected>FYERS</option></select></label><section id="provider"><label>Provider<select aria-label="AI analysis path"><option>Rules</option></select></label></section><div class="step-title"><h2>Stocks</h2><button id="collect-candidates">Collect cash equity matches</button></div><div class="route-set"><input type="radio" checked></div><div id="candidate-batch-actions" hidden><button id="select-all-candidates">Select all eligible</button><button id="clear-candidate-selection">Clear selection</button><label>Budget<input id="budget" value="50000"></label><button id="prepare-handoff-batch">Prepare allocation</button></div></section></div><section id="market"><h3>AI index & commodity analysis</h3><p>Evidence</p><select multiple><option selected>NIFTY</option></select><button>Load broker instruments</button><button>Analyze selected instruments</button><button>Stop analysis</button></section><section id="ticket-panel" hidden><button id="submit-ticket" disabled>Submit order</button></section></section>',{url:'https://example.test/',runScripts:'outside-only'});}
test('actions are grouped by purpose without replacing account controls or handlers',()=>{
 const dom=fixture(),d=dom.window.document,section=d.querySelector('#handoff'),broker=d.querySelector('#ticket-broker'),budget=d.querySelector('#budget'),submit=d.querySelector('#submit-ticket');
 let calls=0;d.querySelector('#collect-candidates').onclick=()=>calls++;d.querySelector('#saved').onclick=()=>calls+=10;
 organizeHandoff(section,d.querySelector('#provider'),d.querySelector('#market'));
 assert.equal(d.querySelector('#ticket-broker'),broker);assert.equal(broker.value,'FYERS');assert.equal(budget.value,'50000');
 assert.ok(d.querySelector('.handoff-analysis-context').contains(broker));
 assert.equal(d.querySelector('[data-handoff-output-actions] button').textContent,'Saved jobs & outputs');
 assert.equal(d.querySelector('.handoff-collect-actions button').id,'collect-candidates');
 assert.equal(d.querySelector('.handoff-market-actions button').textContent,'Analyze selected instruments');
 assert.ok(d.querySelector('.handoff-market-actions .danger').textContent.includes('Stop'));
 assert.equal(d.querySelector('#candidate-batch-actions').hidden,true);assert.equal(submit.disabled,true);assert.equal(d.querySelector('#ticket-panel').hidden,true);
 d.querySelector('#collect-candidates').click();[...d.querySelectorAll('.handoff-market-actions button')].find(n=>n.textContent==='Saved jobs & outputs').click();assert.equal(calls,11);
 assert.equal(section.querySelectorAll('#ticket-broker').length,1);dom.window.close();
});
test('saved exclusions render for their broker and account changes clear foreign output',async()=>{
 const dom=fixture(),w=dom.window,d=w.document;
 await new Promise(resolve=>w.addEventListener('load',resolve,{once:true}));
 d.querySelector('#provider').remove();d.querySelector('#market').remove();
 let current='FYERS',requests=0;
 const job={created:100,updated:101,status:'COMPLETED',terminal:true,request:{account_id:'FYERS',path:'/api/analysis-handoff/analyze-market'},output:{kind:'MARKET_HANDOFF',created_at:100,completed_at:101,instruments:[],exclusions:[{symbol:'NIFTY',reason:'Fresh tick required'}],ai_review:{summary:'No eligible evidence'}}};
 w.BrokerForms={ready:Promise.resolve(),account:()=>({id:current}),fetch:async()=>{requests++;throw Error('Unexpected request');}};
 w.SectorPulseJobs={records:new Map([['saved',{job,base:'https://example.test/api/jobs'}]])};
 w.eval(fs.readFileSync('market-handoff.js','utf8'));await new Promise(resolve=>setTimeout(resolve,20));
 const results=d.querySelector('[aria-label="Index and commodity analysis outcomes"]');assert.ok(results);assert.match(results.textContent,/No eligible recommendations/);assert.match(results.textContent,/Fresh tick required/);assert.match(results.textContent,/COMPLETED/);
 current='DHAN';w.dispatchEvent(new w.Event('broker-account-change'));assert.equal(results.textContent,'');assert.equal(requests,0);
 current='FYERS';w.dispatchEvent(new w.Event('broker-account-change'));assert.match(results.textContent,/Fresh tick required/);
 w.SectorPulseJobs.records.clear();job.status='CANCELLED';job.created=110;job.output.exclusions=[];w.SectorPulseJobs.records.set('cancelled',{job,base:'x'});w.dispatchEvent(new w.Event('sector-pulse-jobs-refreshed'));assert.match(results.textContent,/Analysis cancelled/);
 assert.equal(requests,0);dom.window.close();
});
