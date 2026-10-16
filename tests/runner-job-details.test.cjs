const {test}=require('node:test'),assert=require('node:assert/strict');
const {rows,lifecycle,tradePnl,render,installStyle}=require('../runner-job-details.js');
const {JSDOM}=require('jsdom');
test('journal assigns only exact run ownership or confirmed legacy start times',()=>{
 const state={run_id:'owned',started_at:100,trade_history:[{run_id:'other',entry_time:120},{entry_time:90},{entry_time:101},{run_id:'owned'},{entry_time:130,orders:[{run_id:'owned'},{run_id:'other'}]},{}]};
 assert.equal(rows(state).length,2);assert.deepEqual(rows(state,{run_id:'other',trades:[{run_id:'other'}]}),rows(state));
});
test('quiet state changes do not falsely declare a stalled runner',()=>{
 assert.equal(lifecycle({running:true,updated_at:1}).label,'Running');assert.equal(lifecycle({running:true,status_read_delayed:true}).label,'Running');
 assert.equal(lifecycle({running:true,heartbeat:{stalled:true}}).label,'Stalled');assert.equal(lifecycle({pending:{id:'x'},running:false}).label,'Reconciling order');
});
test('trade P&L never treats unknown values as zero or net costs as gross',()=>{
 assert.equal(tradePnl({}).value,null);assert.deepEqual(tradePnl({realized_pnl:12}),{value:12,basis:'Realized · before fees'});
 assert.equal(tradePnl({costs:{realized_net:10,unrealized_net:2},remaining_quantity:1}).value,12);
 assert.equal(tradePnl({costs:{realized_net:10},remaining_quantity:1}).value,null);
});
test('detail view renders all fifteen real trades, their criteria, prices and audit without interpreting HTML',()=>{
 const dom=new JSDOM('<section></section>',{url:'https://host/'}),doc=dom.window.document,container=doc.querySelector('section');installStyle(doc);
 const trades=Array.from({length:15},(_,i)=>({trade_id:String(i),run_id:'ours',contract:'NIFTY-'+i,status:'CLOSED',entry_time:101+i,exit_time:201+i,entry_price:10,exit_price:12,entry_filled:65,realized_pnl:130,entry_reasons:['<img src=x onerror=alert(1)>'],exit_reasons:['COMPLETED_EMA_EXIT'],entry_indicator_snapshot:{ema10:100,close:101},orders:[{order_id:'local-fixture'}]}));
 render(container,{state:{run_id:'ours',started_at:100,config:{mode:'PAPER'},cost_pnl:{total_net:1900}},account:{id:'a',broker:'FYERS',label:'My account'},audit:{run_id:'ours',trades},chartUrl:'https://host/?renkoInstance=ours',observedAt:300});
 assert.equal(container.querySelectorAll('tbody tr').length,15);assert.match(container.textContent,/1,900.00/);assert.match(container.textContent,/COMPLETED_EMA_EXIT/);assert.equal(container.querySelector('img'),null);assert.match(container.querySelector('a').href,/renkoInstance=ours/);
 assert.match(container.textContent,/Entry indicator evidence/);assert.match(container.textContent,/Order and fill events/);dom.window.close();
});

test('runner detail refresh stays bound to its account and preserves opened audits',async()=>{
 const fs=require('node:fs'),dom=new JSDOM('<nav></nav>',{url:'https://host/',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,intervals=[],reads=[];let pnl=2;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};w.setInterval=(fn,ms)=>intervals.push({fn,ms});w.AbortSignal.timeout=()=>undefined;
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[{id:'own',broker:'DHAN',label:'Mine',configured:true}]};
 const state=()=>({run_id:'r',running:true,instance_key:'nifty',started_at:100,config:{underlying:'NIFTY',mode:'PAPER'},cost_pnl:{total_net:pnl},trade_history:[{run_id:'r',trade_id:'one',contract:'NIFTY',entry_time:101,entry_price:10,entry_filled:1,status:'OPEN',entry_reasons:['EMA_COMPLETED_CANDLE']}]});
 w.fetch=async(url,options={})=>{reads.push(url);return {ok:true,json:async()=>url.includes('/renko-dhan/')?url.endsWith('/instances')?{instances:[state()]}:state():{instances:[]}}};
 w.eval(fs.readFileSync('runner-job-details.js','utf8'));w.eval(fs.readFileSync('runner-jobs.js','utf8'));await new Promise(r=>setImmediate(r));w.document.querySelector('nav button').click();await new Promise(r=>setImmediate(r));
 [...w.document.querySelectorAll('button')].find(n=>n.textContent==='View job details').click();await new Promise(r=>setImmediate(r));
 const trade=w.document.querySelector('details[data-audit-key="trade:one"]');trade.open=true;pnl=5;intervals.find(i=>i.ms===2500).fn();await new Promise(r=>setImmediate(r));
 assert.match(w.document.querySelector('.runner-detail-metrics').textContent,/5.00/);assert.equal(w.document.querySelector('details[data-audit-key="trade:one"]').open,true);
 assert.match(reads.at(-1),/renko-dhan\/own\/runner\?instance=nifty$/);assert.match(w.document.querySelector('.runner-detail-actions a').href,/brokerAccount=own/);dom.window.close();
});
