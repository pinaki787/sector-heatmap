const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync('investment.js','utf8');
function mount(context={admin:true,allowed_features:['investment'],sidebar_visibility:{}}){
 const dom=new JSDOM('<!doctype html><nav class="nav"></nav><main class="work"><section id="sectors" class="view active"></section></main>',{url:'https://example.test',runScripts:'outside-only'});
 dom.window.SectorPulseWorkspace=context;dom.window.eval(source);dom.window.document.dispatchEvent(new dom.window.Event('DOMContentLoaded'));return dom;
}
test('mount and isolated navigation',()=>{
 const dom=mount(),w=dom.window;assert.ok(w.document.querySelector('#investment'));w.document.querySelector('[data-view=investment]').click();assert.ok(w.document.querySelector('#investment.active'));dom.window.close();
});
test('unassigned user has no investment view',()=>{const d=mount({admin:false,allowed_features:['screener']});assert.equal(d.window.document.querySelector('#investment'),null);d.window.close();});
test('hidden setting is preserved',()=>{const d=mount({admin:true,allowed_features:['investment'],sidebar_visibility:{investment:false}});assert.equal(d.window.document.querySelector('[data-view=investment]').hidden,true);d.window.close();});
test('restores rule output, escapes company text and limits displayed decimals',()=>{
 const d=mount(),w=d.window;w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{base:'https://example.test/api/jobs',job:{feature:'investment',job_id:'123456789',created:1,terminal:true,status:'COMPLETED',output:{schema:'investment/v1',policy:{distance_pct:5},coverage:{eligible:1,displayed:1},rows:[{symbol:'NSE:TEST-EQ',name:'<img src=x onerror=alert(1)>',price:123.456789,distance_pct:1.234567,rule_status:'QUALITY_REVIEW',metrics:{}}]}}}}));
 assert.match(w.document.querySelector('#investment-rows').textContent,/123.46/);assert.equal(w.document.querySelector('#investment-rows img'),null);assert.doesNotMatch(w.document.querySelector('#investment-rows').textContent,/123.456/);d.window.close();
});


test('sector RS and daily pullback render with two decimals',()=>{
 const d=mount(),w=d.window;
 const row={symbol:'NSE:TECHM-EQ',name:'Tech Mahindra',sector:'Technology Services',price:1790,reported_ath:1854,metrics:{},rule_status:'QUALITY_REVIEW',sector_strength:{status:'MIXED',windows:{'6m':{excess_pp:1.48669},'12m':{excess_pp:-6.08357}}},relative_strength:{windows:{'12m':32.52813}},daily_pullback:{price_50:1750.567,price_56:1738.567,swing_low:1600,swing_high:1800,swing_low_date:'2026-10-19',swing_high_date:'2026-11-05'},plan:{status:'CONDITIONAL',entry:1854.1,stoploss:1746.2,target:2069.9,reward_risk:2}};
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{base:'https://example.test/api/jobs',job:{feature:'investment',job_id:'abcdef1234',created:2,terminal:true,status:'COMPLETED',output:{schema:'investment/v1',policy:{distance_pct:5},coverage:{eligible:1,displayed:1},rows:[row]}}}}));
 const text=w.document.querySelector('#investment-rows').textContent;
 assert.match(text,/Technology Services/);assert.match(text,/6M \+1\.49 pp/);assert.match(text,/12M -6\.08 pp/);
 assert.match(text,/50% · ₹1,750\.57/);assert.match(text,/56% · ₹1,738\.57/);
 const button=w.document.querySelector('.investment-open');
 w.document.querySelector('#investment-detail').showModal=()=>{};
 button.click();
 const detail=w.document.querySelector('#investment-detail-body').textContent;
 assert.match(detail,/Breakout entry ₹1,854\.1/);assert.match(detail,/Stop-loss ₹1,746\.2/);assert.match(detail,/Target ₹2,069\.9/);
 assert.match(detail,/2026-10-19/);assert.match(detail,/2026-11-05/);
 assert.match(w.document.querySelector('.investment-table thead').textContent,/AI Assessment/);
 assert.equal(w.document.querySelectorAll('.investment-table th').length,8);
 d.window.close();
});


test('assigned user Investment stays in primary research navigation before parser and asset groups',()=>{
 const d=new JSDOM('<!doctype html><nav class="nav"><button data-view="sectors">Sector rotation</button><button data-view="screener">Screener</button><div class="parsers-nav"><button data-view="trade-parser">Parser</button></div><div class="assets-nav">Assets</div></nav><main class="work"></main>',{url:'https://example.test',runScripts:'outside-only'});
 d.window.SectorPulseWorkspace={admin:false,allowed_features:['investment'],sidebar_visibility:{investment:true}};
 d.window.eval(source);d.window.document.dispatchEvent(new d.window.Event('DOMContentLoaded'));
 const nav=d.window.document.querySelector('.nav'),investment=nav.querySelector('[data-view="investment"]');
 assert.equal(investment.parentElement,nav);
 assert.equal(investment.previousElementSibling.dataset.view,'screener');
 assert.equal(investment.nextElementSibling.className,'parsers-nav');
 investment.click();assert.ok(d.window.document.querySelector('#investment.active'));
 d.window.close();
});

test('each sort covers all pages at full precision and retains symbol selection',()=>{
 const d=mount(),w=d.window,doc=w.document;
 const rows=Array.from({length:27},(_,i)=>({symbol:'NSE:EQ'+i+'-EQ',name:'Equity '+i,metrics:{'Perf.6M':i+0.001,'Perf.Y':27-i}}));
 rows[0].metrics={};
 rows[26].metrics['Perf.6M']=25.002;
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{job:{feature:'investment',job_id:'sort-fixture',created:1,terminal:true,status:'COMPLETED',output:{schema:'investment/v1',coverage:{eligible:27,displayed:27},rows}}}}));
 const set=(id,value)=>{const element=doc.getElementById(id);element.value=value;element.dispatchEvent(new w.Event('change'));};
 const boxes=()=>[...doc.querySelectorAll('.investment-select')];
 boxes()[1].click();
 set('investment-period','6');
 for(const metric of ['return','cagr']){
  set('investment-sort',metric+'-desc');
  assert.equal(boxes()[0].value,rows[26].symbol);
  assert.equal(boxes()[1].value,rows[25].symbol);
  assert.equal(boxes().length,25);
  doc.getElementById('investment-next').click();
  assert.equal(boxes()[0].value,rows[1].symbol);
  assert.equal(boxes()[0].checked,true);
  assert.equal(boxes()[1].value,rows[0].symbol);
  set('investment-sort',metric+'-asc');
  assert.equal(boxes()[0].value,rows[1].symbol);
  assert.equal(boxes()[0].checked,true);
  doc.getElementById('investment-next').click();
  assert.equal(boxes()[0].value,rows[26].symbol);
  assert.equal(boxes()[1].value,rows[0].symbol);
 }
 set('investment-period','12');
 assert.equal(boxes()[0].value,rows[26].symbol);
 let exported;
 w.SectorPulseInvestmentExports={workbook:(chosen,growth)=>{exported=chosen.map(row=>row.symbol);assert.ok(Math.abs(growth(chosen[0],'6')-2.01202001)<1e-8);}};
 doc.getElementById('investment-xlsx').click();
 assert.deepEqual(Array.from(exported),[rows[1].symbol]);
 d.window.close();
});

test('ten-year returns and CAGR sort across pages and export all checked rows',()=>{
 const d=mount(),w=d.window,doc=w.document;
 const rows=Array.from({length:29},(_,i)=>({
  symbol:'NSE:YEAR'+i+'-EQ',name:'Equity '+i,
  annual_returns:i===28?{}:{'10':{return_pct:i-10.001,from_date:'2016-11-11',to_date:'2026-11-12'}}
 })).reverse();
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{job:{feature:'investment',job_id:'annual-fixture',created:1,terminal:true,status:'COMPLETED',output:{schema:'investment/v1',coverage:{eligible:29,displayed:29},rows}}}}));
 const set=(id,value)=>{const element=doc.getElementById(id);element.value=value;element.dispatchEvent(new w.Event('change'));};
 const boxes=()=>[...doc.querySelectorAll('.investment-select')];
 const symbol=i=>'NSE:YEAR'+i+'-EQ';
 assert.equal(doc.querySelectorAll('#investment-period option').length,12);
 set('investment-period','10y');
 for(const metric of ['return','cagr']){
  set('investment-sort',metric+'-asc');
  assert.equal(boxes()[0].value,symbol(0));
  assert.match(doc.querySelector('#investment-rows').textContent,/10Y return -10%/);
  doc.getElementById('investment-next').click();
  assert.equal(boxes().at(-1).value,symbol(28));
  set('investment-sort',metric+'-desc');
  assert.equal(boxes()[0].value,symbol(27));
  doc.getElementById('investment-next').click();
  assert.equal(boxes().at(-1).value,symbol(28));
 }
 set('investment-sort','return-asc');
 boxes()[0].click();
 doc.getElementById('investment-next').click();
 boxes()[0].click();
 assert.equal(doc.getElementById('investment-selection').textContent,'2 selected');
 let exported;
 w.SectorPulseInvestmentExports={workbook:(chosen,growth,returns)=>{
  exported=Array.from(chosen,row=>row.symbol);
  assert.equal(returns(chosen[0],'10y'),14.999);
  assert.ok(Math.abs(growth(chosen[0],'10y')-100*(Math.pow(1.14999,.1)-1))<1e-9);
 }};
 doc.getElementById('investment-xlsx').click();
 assert.deepEqual(exported,[symbol(25),symbol(0)]);
 d.window.close();
});

test('equity entry preview, explicit enable, and per-stock stop use the selected account',async()=>{
 const d=mount({admin:true,username:'reviewer',allowed_features:['investment'],sidebar_visibility:{}}),w=d.window;
 const doc=w.document,requests=[];
 w.BrokerAccountOptions=require('../broker-account-options.js');
 w.BrokerForms={accounts:()=>[{id:'dhan-one',broker:'DHAN',label:'Owned Dhan',configured:true},{id:'fyers-one',broker:'FYERS',label:'Owned FYERS',configured:true}]};
 const resultJob={job_id:'monitor-job',status:'RUNNING',terminal:false};
 w.fetch=async (url,opts)=>{
  const body=JSON.parse(opts.body);
  requests.push({action:url.split('/').at(-1),body});
  const action=requests.at(-1).action;
  const response=action==='status'?{job:null}:action==='preview'?{
   preview_id:'INV-EXAMPLE',confirmation:'ENABLE INV-EXAMPLE',
   plan:{account_label:'Owned Dhan',symbol:'NSE:TEST-EQ',quantity:10,limit_price:'95.05',ratio:'56',notional:'950.50'}
  }:action==='enable'?{job:resultJob}:{job:{...resultJob,status:'CANCELLED',terminal:true}};
  return {ok:true,json:async()=>response};
 };
 w.dispatchEvent(new w.CustomEvent('sector-pulse-job-update',{detail:{job:{feature:'investment',job_id:'research-job',created:1,terminal:true,status:'COMPLETED',output:{schema:'investment/v1',coverage:{eligible:1},rows:[{symbol:'NSE:TEST-EQ',daily_pullback:{price_50:100,price_56:95.081}}]}}}}));
 doc.querySelector('#investment-detail').showModal=()=>{};
 doc.querySelector('.investment-open').click();
 const delivery=doc.querySelector('#investment-broker');
 delivery.value='dhan-one';delivery.dispatchEvent(new w.Event('change'));
 await new Promise(resolve=>setImmediate(resolve));
 doc.querySelector('#investment-entry-level').value='56';
 doc.querySelector('#investment-entry-quantity').value='10';
 doc.querySelector('#investment-entry-preview').click();
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(doc.querySelector('#investment-entry-confirmation').hidden,false);
 assert.match(doc.querySelector('#investment-entry-terms').textContent,/Buy up to 10 delivery shares at ₹95\.05/);
 doc.querySelector('#investment-entry-phrase').value='ENABLE INV-EXAMPLE';
 doc.querySelector('#investment-entry-enable').click();
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(doc.querySelector('#investment-entry-stop').hidden,false);
 doc.querySelector('#investment-entry-stop').click();
 await new Promise(resolve=>setImmediate(resolve));
 assert.match(doc.querySelector('#investment-entry-status').textContent,/Existing broker orders and holdings stay in place/);
 assert.deepEqual(requests.map(x=>x.action),['status','preview','enable','stop']);
 assert.ok(requests.every(x=>x.body.account_id==='dhan-one'&&x.body.symbol==='NSE:TEST-EQ'));
 assert.equal(requests[1].body.research_job_id,'research-job');
 assert.equal(requests[3].body.monitor_job_id,'monitor-job');
 d.window.close();
});

