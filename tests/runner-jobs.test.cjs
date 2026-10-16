const {test}=require('node:test'),assert=require('node:assert/strict');
const {sources,normalize,link,stopJob,netPnl}=require('../runner-jobs.js');
test('Motilal lists only its native Renko route and keeps read/stop bound to that account',()=>{
 const a={id:'motilal-owned',broker:'MOTILAL_OSWAL',label:'Motilal Oswal'},list=sources(a);
 assert.equal(list.length,1);assert.equal(list[0].url,'/api/renko-motilal/motilal-owned/instances');
 const j=normalize(a,list[0],{broker:'MOTILAL_OSWAL',instance_key:'nifty',run_id:'r',running:true,config:{underlying:'NIFTY'}});
 assert.equal(j.read,'/api/renko-motilal/motilal-owned/runner?instance=nifty');
 assert.equal(j.stop,'/api/renko-motilal/motilal-owned/stop?instance=nifty');
 const u=new URL(link(j,'https://portal.example'));assert.equal(u.searchParams.get('renkoBroker'),'MOTILAL_OSWAL');assert.equal(u.searchParams.get('brokerAccount'),a.id);
 assert.deepEqual(sources({id:'unknown',broker:'UNSUPPORTED'}),[]);
});

for(const broker of ['FYERS','DHAN','DELTA_INDIA'])test(broker+' jobs stay bound to the selected account',()=>{
 const a={id:'owned',broker,label:'Mine'},source=sources(a)[0],state={broker,instance_key:'job1',run_id:'run1',running:true,config:{underlying:'instrument',mode:'PAPER'}};
 const j=normalize(a,source,state);assert(j.read.includes('owned'));assert(j.stop.includes('owned'));assert.equal(j.status,'Watching');
 const u=new URL(link(j,'https://portal.example'));assert.equal(u.searchParams.get('brokerAccount'),'owned');assert.equal(u.searchParams.get('renkoInstance'),'job1');
 assert.equal(normalize(a,source,{...state,broker:broker==='FYERS'?'DHAN':'FYERS'}),null);
 assert(sources(a).some(s=>s.kind==='engine'));
});
test('job stop checks current run and never repeats a mutation',async()=>{
 const a={id:'owned',broker:'FYERS'},j=normalize(a,sources(a)[0],{run_id:'one',running:true,config:{underlying:'X'}});
 let posts=0;await assert.rejects(stopJob(j,async(u,o)=>{if(o)posts++;return {run_id:'two',running:true}}),/Run changed/);assert.equal(posts,0);
 const result=await stopJob(j,async(u,o)=>{if(!o)return {run_id:'one',running:true};posts++;return {running:false,pending:{id:'p'}}});
 assert.equal(posts,1);assert.match(result,/reconciliation/);
 await assert.rejects(stopJob(j,async(u,o)=>{if(!o)return {run_id:'one',running:true};posts++;throw Error('timeout')}),/timeout/);assert.equal(posts,2);
});
test('unused defaults are omitted, saved and stopped jobs remain visible',()=>{
 const a={id:'a',broker:'DHAN'},source=sources(a)[0];assert.equal(normalize(a,source,{}),null);
 assert.equal(normalize(a,source,{instrument:'X'}).status,'Saved · not started');
 assert.equal(normalize(a,source,{run_id:'r',config:{underlying:'X'}}).status,'Stopped');
});

test('Dhan nondefault strategy instances keep their own read, stop and deep link',()=>{
 const a={id:'owned',broker:'DHAN'};
 for(const kind of ['band','rsi','kama']){
  const source=sources(a).find(s=>s.kind===kind),j=normalize(a,source,{instance_key:'other',run_id:'r',config:{underlying:'X'}});
  assert.match(j.read,/form-runner\?instance=other$/);assert.match(j.stop,/form-runner-stop\?instance=other$/);
  assert.equal(new URL(link(j,'https://portal.example')).searchParams.get(kind+'Instance'),'other');
 }
});
test('legacy runners use their own account workspace and preserve stop semantics',async()=>{
 const a={id:'owned',broker:'FYERS'},src=sources(a).find(s=>s.market==='nifty'),j=normalize(a,src,{running:true,started_at:'2026-10-14T10:00:00+05:30',mode:'PAPER'});
 assert.match(link(j,'https://portal.example'),/broker-workspace\/owned/);
 assert.equal(new URL(link(j,'https://portal.example')).searchParams.get('straddleMarket'),'nifty');
 const d={id:'crypto',broker:'DELTA_INDIA'},ds=sources(d).find(s=>s.kind==='delta'),dj=normalize(d,ds,{runner:{running:true,config:{symbol:'BTCUSD',mode:'PAPER'}},paper:{position:{quantity:1}}});
 assert.equal(dj.title,'BTCUSD');assert.equal(dj.status,'Managing position');
 assert.match(await stopJob(dj,async(u,o)=>o?{runner:{running:false},paper:{position:{quantity:1}}}:{runner:{running:true,config:{mode:'PAPER'}},paper:{position:{quantity:1}}}),/Stopped|pending/);
});

test('rendered inventory reports server status and selection sends only one scoped stop',async()=>{
 const {JSDOM}=require('jsdom'),fs=require('node:fs');
 const dom=new JSDOM('<nav></nav>',{url:'https://portal.example/',runScripts:'outside-only'});
 const w=dom.window;let calls=[],running=true;
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
 w.AbortSignal.timeout=()=>undefined;w.setInterval=()=>0;
 w.BrokerForms={ready:Promise.resolve(),accounts:()=>[{id:'mine',label:'Mine',broker:'DHAN',configured:true},{id:'motilal',label:'Motilal Oswal',broker:'MOTILAL_OSWAL',configured:true}]};

 const state=()=>({broker:'DHAN',instance_key:'x',run_id:'r',running,config:{underlying:'NIFTY',mode:'PAPER'}});
 w.fetch=async(url,o)=>{calls.push([url,o.method]);if(o.method==='POST'){running=false;return {ok:true,json:async()=>state()};}
 return {ok:true,json:async()=>url.includes('/renko-dhan/')?(url.endsWith('/instances')?{instances:[state()]}:state()):{instances:[]}}};
 w.eval(fs.readFileSync(require.resolve('../runner-jobs.js'),'utf8'));w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
 await new Promise(r=>setImmediate(r));
 w.document.querySelector('nav button').click();await new Promise(r=>setImmediate(r));
 assert.match(w.document.querySelector('[data-count]').textContent,/1 running/);assert.equal(calls.filter(c=>c[1]==='POST').length,0);
 assert(calls.some(c=>c[0]==='/api/renko-motilal/motilal/instances'));
 assert(!calls.some(c=>c[0].includes('/broker-workspace/motilal/')||c[0].includes('/renko-engine/motilal/')));
 assert.doesNotMatch(w.document.querySelector('[data-message]').textContent,/Some jobs unavailable/);

 w.document.querySelector('[data-select-all]').click();
 assert.equal(w.document.querySelector('tbody input').checked,true);
 w.document.querySelector('[data-stop]').click();await new Promise(r=>setImmediate(r));
 assert.equal(calls.filter(c=>c[1]==='POST').length,1);assert.equal(calls.find(c=>c[1]==='POST')[0],'/api/renko-dhan/mine/stop?instance=x');
 assert.match(w.document.querySelector('[data-count]').textContent,/0 running/);
 assert.equal(w.document.querySelector('tbody input'),null);
 const history=w.document.querySelector('[data-history]');history.checked=true;history.dispatchEvent(new w.Event('change'));
 assert.equal(w.document.querySelector('tbody input').disabled,true);dom.window.close();
});

test('net P&L uses after-cost native currency only, never gross or missing as zero',()=>{
 assert.equal(netPnl({account:{broker:'DHAN'},state:{cost_pnl:{total_net:-12.3}}}).text,'INR -12.30');
 assert.equal(netPnl({account:{broker:'DELTA_INDIA'},state:{pnl_currency:'USD',cost_pnl:{total_net:4}}}).text,'USD 4.00');
 assert.equal(netPnl({account:{broker:'DHAN'},state:{pnl:{unrealized:100},cost_pnl:{total_net:null}}}).text,'Net unavailable');
 assert.equal(netPnl({account:{broker:'DELTA_INDIA'},state:{cost_pnl:{total_net:4}}}).text,'Net unavailable');
});
