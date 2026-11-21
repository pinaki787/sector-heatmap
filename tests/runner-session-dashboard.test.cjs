const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {sources,normalize,startSpec,startJob,sessionChartLink,visibleJobs}=require('../runner-jobs.js');
const {runnerChartContext,runnerChartAlignment}=require('../renko-supertrend.js');
function job(broker='FYERS',changes={}){
 const account={id:'owned',label:'My account',broker,configured:true};
 const state={broker,account_id:'owned',instance_key:'symbol1',run_id:'old-run',runtime_revision:'renko-supertrend-assessment-recovery-v14',running:false,position:null,pending:null,config:{strategy:'RENKO_SUPERTREND_V1',underlying:'NSE:NIFTY50-INDEX',timeframe:'1 minute',mode:'LIVE',lots:2,max_trades:5,...changes}};
 return normalize(account,sources(account)[0],state);
}
for(const broker of ['FYERS','DHAN','DELTA_INDIA','MOTILAL_OSWAL'])test(broker+' start keeps account, instance, mode and settings',async()=>{
 const j=job(broker);let posts=[];
 const result=await startJob(j,async(url,options)=>{if(!options)return j.state;posts.push({url,body:JSON.parse(options.body)});return {...j.state,running:true};});
 assert.equal(result,'Started');assert.equal(posts.length,1);assert(posts[0].url.includes('owned'));assert(posts[0].url.endsWith('?instance=symbol1'));
 assert.equal(posts[0].body.mode,'LIVE');assert.equal(posts[0].body.lots,2);assert.equal(posts[0].body.timeframe,'1 minute');assert.equal(posts[0].body.broker,broker);assert.equal(posts[0].body.account_id,'owned');
});
test('start refuses changed run, changed settings, wrong account and retained exposure without mutation',async()=>{
 const j=job();let posts=0;
 for(const changed of [{run_id:'new-run'},{config:{...j.state.config,lots:3}},{account_id:'other'},{position:{symbol:'held'}}]){
  await assert.rejects(startJob(j,async(url,options)=>{if(options)posts++;return {...j.state,...changed};}));
 }
 assert.equal(posts,0);
});
test('start does not retry after an uncertain response',async()=>{
 const j=job();let posts=0;
 await assert.rejects(startJob(j,async(url,options)=>{if(!options)return j.state;posts++;throw Error('connection lost');}),/connection lost/);
 assert.equal(posts,1);
});
test('missing configuration or runtime revision requires settings rather than an invented start',()=>{
 const j=job();assert.equal(startSpec({...j,state:{...j.state,config:null}}),null);
 assert.equal(startSpec({...j,state:{...j.state,runtime_revision:undefined}}),null);
 assert.equal(startSpec({...j,state:{...j.state,running:true}}),null);
});
test('session links carry exact account, instance, run and captured timeframe',()=>{
 const j=job(),u=new URL(sessionChartLink(j,'https://portal.example'));
 assert.equal(u.searchParams.get('brokerAccount'),'owned');assert.equal(u.searchParams.get('renkoInstance'),'symbol1');
 assert.equal(u.searchParams.get('renkoSession'),'old-run');assert.equal(u.searchParams.get('renkoSessionTimeframe'),'1 minute');
});
test('stopped-session chart uses captured rules and rejects a replaced session',()=>{
 const j=job(),state={...j.state,confirmed_feed_revision:'shared-confirmed-live-v1'};
 const fields={symbol:state.config.underlying,timeframe:'1 minute','session-run-id':state.run_id,'atr-length':5,factor:3,'brick-mode':'Auto'};
 const context=runnerChartContext(fields,state);
 assert.equal(context.basis,'recorded');assert.equal(context.settings.confirmed_run_id,'old-run');assert.equal(context.runId,'old-run');
 const stale=runnerChartContext({...fields,'session-run-id':'older-run'},state);
 assert.match(stale.error,/changed/);assert.equal(runnerChartAlignment(stale,state,{}).blocked,true);
});
test('only running sessions are visible by default while filters still limit select-all scope',()=>{
 const stopped=job(),running={...job('DHAN'),state:{...job('DHAN').state,running:true},title:'GOLD'},attention={...job(),state:{...job().state,position:{symbol:'owned'}}};
 assert.equal(visibleJobs([stopped,running,attention]).length,1);
 assert.equal(visibleJobs([stopped,running,attention],true).length,3);
 assert.equal(visibleJobs([stopped,running,attention],false).length,1);
 assert.equal(visibleJobs([stopped,running,attention],true,'GOLD').length,1);
});
test('restored page reuses existing permission key and opens the sessions tab',()=>{
 const source=fs.readFileSync(require.resolve('../analysis-jobs.js'),'utf8');
 assert.match(source,/const live=kind==null\|\|kind==='LIVE'/);
 assert.match(source,/data-feature.*runner-jobs|dataset\.feature='runner-jobs'/);
 assert.match(source,/jobsViewAllowed\(\)/);
});
test('select-all exposes both start and stop, and cancelling review sends no mutation',async()=>{
 const {JSDOM}=require('jsdom');
 const dom=new JSDOM('<nav></nav>',{url:'https://portal.example/',runScripts:'outside-only'}),w=dom.window;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
 w.AbortSignal.timeout=()=>undefined;w.setInterval=()=>0;
 const a=job('DHAN'),active={...a.state,instance_key:'active',run_id:'running',running:true};
 let posts=0;
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[a.account]};
 w.fetch=async(url,options={})=>{if(options.method==='POST')posts++;return {ok:true,json:async()=>url.endsWith('/instances')&&url.includes('/renko-dhan/')?{instances:[a.state,active]}:{instances:[]}};};
 w.eval(fs.readFileSync(require.resolve('../runner-jobs.js'),'utf8'));w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
 await new Promise(r=>setImmediate(r));w.document.querySelector('nav button').click();await new Promise(r=>setImmediate(r));
 assert.equal(w.document.querySelector('[data-history]').checked,false);assert.equal(w.document.querySelectorAll('.runner-job-card').length,1);
 const history=w.document.querySelector('[data-history]');history.checked=true;history.dispatchEvent(new w.Event('change'));
 assert.equal(w.document.querySelectorAll('.runner-job-card').length,2);
 w.document.querySelector('[data-select-all]').click();
 assert.equal(w.document.querySelector('[data-start]').disabled,false);assert.equal(w.document.querySelector('[data-stop]').disabled,false);assert.equal(posts,0);
 w.document.querySelector('[data-start]').click();await new Promise(r=>setImmediate(r));
 const review=w.document.querySelector('.job-start-review');assert(review);assert.match(review.textContent,/LIVE/);
 [...review.querySelectorAll('button')].find(b=>b.textContent==='Cancel').click();await new Promise(r=>setImmediate(r));
 assert.equal(posts,0);dom.window.close();
});

test('Renko sessions start collapsed and stopped rows require explicit history toggle',()=>{const s=fs.readFileSync(require.resolve('../renko-supertrend.js'),'utf8');assert.match(s,/savedDisclosure.open=false/);assert.match(s,/session-history.*checked/);assert.match(s,/Show stopped \/ saved/);});
