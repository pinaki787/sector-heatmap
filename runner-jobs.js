/* Account-bound runner inventory. Existing durable runners remain execution owners. */
(function(root){
'use strict';
const names={FYERS:'FYERS',DHAN:'Dhan',DELTA_INDIA:'Delta India'};
function sources(a){
 const p='/broker-workspace/'+encodeURIComponent(a.id),d=a.broker==='DHAN';
 const list=[{kind:'renko',label:'Renko Supertrend',url:d?'/api/renko-dhan/'+a.id+'/instances':p+'/api/renko-instances',many:true}];
 if(a.broker!=='DELTA_INDIA')for(const [kind,label,base] of [['band','EMA Band','ema-band'],['rsi','EMA Crossover','ema-crossover'],['kama','KAMA','kama']]){
  const prefix=d?'/api/'+(kind==='rsi'?'ema':kind)+'-dhan/'+a.id+'/':p+'/api/'+base+'/';
  list.push({kind,label,url:prefix+(d?'instances':'runner'),many:d,readPrefix:d?prefix+'form-runner':null,stop:prefix+(d?'form-runner-stop':kind==='rsi'?'stop':'runner/stop')});
 }
 const engine=(a.broker==='FYERS'?p:'')+'/api/renko-engine/'+a.id+'/';
 list.push({kind:'engine',label:'Renko Engine',url:engine+'runner',stop:engine+'stop'});
 if(a.broker==='FYERS')for(const market of ['sensex','nifty'])list.push({kind:'straddle',market,label:market.toUpperCase()+' Straddle',url:p+'/api/'+market+'-straddle',stop:p+'/api/'+market+'-straddle/stop'});
 if(a.broker==='DELTA_INDIA')list.push({kind:'delta',label:'Delta strategy',url:p+'/api/delta-india/status',stop:p+'/api/delta-india/runner-stop'});
 return list;
}
function unwrap(source,state){
 if(source.kind==='delta')return {...state.runner,broker:'DELTA_INDIA',position:state.runner?.config?.mode==='PAPER'?state.paper?.position:state.runner_position};
 return state;
}
function normalize(a,source,state){
 state=unwrap(source,state);
 const c=state.config||{},instance=state.instance_key||'default';
 if(state.broker&&state.broker!==a.broker)return null;
 if(!c.underlying&&!c.symbol&&!state.instrument&&!state.running&&!state.position&&!state.pending&&!state.started_at)return null;
 const prefix=a.broker==='DHAN'?'/api/renko-dhan/'+a.id+'/':'/broker-workspace/'+a.id+(a.broker==='DELTA_INDIA'?'/api/renko-delta/':'/api/renko-supertrend/');
 const suffix='?instance='+encodeURIComponent(instance);
 const active=!!(state.running||state.position||state.pending);
 return {key:[a.id,source.kind,source.market||instance].join(':'),account:a,source,instance,state,active,
  title:c.underlying||state.instrument||c.symbol||source.label,
  status:state.pending?'Order reconciliation':state.shutdown_pending?'Stopping':state.running?(state.position?'Managing position':'Watching'):state.position?'Monitoring paused':state.run_id?'Stopped':'Saved · not started',
  read:source.many?(source.readPrefix||prefix+'runner')+suffix:source.url,stop:source.many?(source.kind==='renko'?prefix+'stop':source.stop)+suffix:source.stop};
}
function link(job,origin){
 const u=new URL(['straddle','delta'].includes(job.source.kind)?'/broker-workspace/'+job.account.id+'/':'/',origin);u.searchParams.set('brokerForm',job.source.kind);u.searchParams.set('brokerAccount',job.account.id);u.searchParams.set(job.source.kind+'Account',job.account.id);
 if(job.source.kind==='renko'){u.searchParams.set('renkoBroker',job.account.broker);u.searchParams.set('renkoInstance',job.instance);}
 if(['band','rsi','kama'].includes(job.source.kind))u.searchParams.set(job.source.kind+'Instance',job.instance);
 if(job.source.kind==='straddle')u.searchParams.set('straddleMarket',job.source.market);
 return u.href;
}
async function stopJob(job,request){
 const current=unwrap(job.source,await request(job.read));
 if((current.run_id||current.started_at||null)!==(job.state.run_id||job.state.started_at||null))throw Error('Run changed. Refresh the job list before stopping.');
 if(!(current.running||current.position||current.pending))return 'Already stopped';
 const result=unwrap(job.source,await request(job.stop,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run_id:current.run_id})}));
 return result.running||result.position||result.pending?'Stopping / reconciliation pending':'Stopped';
}
if(typeof module!=='undefined'&&module.exports){module.exports={sources,normalize,link,stopJob};return;}
async function mount(){
 if(new URLSearchParams(location.search).get('renkoBatchChart')==='1')return;
 await root.BrokerForms.ready;
 const nav=document.querySelector('nav');if(!nav)return;
 const open=document.createElement('button');open.type='button';open.textContent='Runner jobs';nav.append(open);
 const dialog=document.createElement('dialog');dialog.setAttribute('aria-label','Runner jobs');
 dialog.innerHTML='<header><h2>Runner jobs</h2><button type="button" data-close>Close</button></header><p>Server-managed runners for your accounts. Opening a job does not start it. Stop uses each strategy’s existing stop behavior: some close positions; others stop monitoring only. Pending orders may still require reconciliation.</p><div class="job-actions"><button type="button" data-refresh>Refresh jobs</button><button type="button" data-stop disabled>Stop selected jobs</button><span data-count></span></div><p data-message role="status"></p><div class="job-table"><table><thead><tr><th>Select</th><th>Account / strategy</th><th>Instrument</th><th>Mode / timeframe</th><th>Status</th><th>Started</th><th>Open</th></tr></thead><tbody></tbody></table></div>';
 document.body.append(dialog);
 const style=document.createElement('style');style.textContent='dialog[aria-label="Runner jobs"]{width:min(1180px,94vw);max-height:85vh;overflow-y:scroll;background:#142033;color:#e4ecf7;border:1px solid #53647e;border-radius:12px;padding:24px}dialog[aria-label="Runner jobs"]::backdrop{background:#0009}dialog[aria-label="Runner jobs"] header,.job-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap}dialog[aria-label="Runner jobs"] header h2{margin-right:auto}.job-table{overflow-x:auto}.job-table table{width:100%;border-collapse:collapse}.job-table td,.job-table th{padding:12px;text-align:left;border-bottom:1px solid #34445c;font-size:13px}.job-table a{color:#91c4ff}.job-table small{display:block;color:#a9b7cc}.job-actions button,dialog[aria-label="Runner jobs"] header button{padding:9px 14px;background:#263953;color:#e4ecf7;border:1px solid #52647e;border-radius:5px}';document.head.append(style);
 const body=dialog.querySelector('tbody'),message=dialog.querySelector('[data-message]'),stop=dialog.querySelector('[data-stop]'),count=dialog.querySelector('[data-count]');
 let jobs=[],selected=new Set(),busy=false,loading=false,revision=0;
 const request=async(url,options={})=>{const r=await root.fetch(url,{...options,cache:'no-store',signal:AbortSignal.timeout(30000)});const d=await r.json();if(!r.ok||d.error)throw Error(d.error||'Job request failed');return d;};
 function render(){
  body.replaceChildren();count.textContent=jobs.filter(j=>j.state.running).length+' running · '+jobs.length+' jobs';
  for(const job of jobs){
   const tr=document.createElement('tr'),cell=()=>{const td=document.createElement('td');tr.append(td);return td;};
   const check=document.createElement('input');check.type='checkbox';check.setAttribute('aria-label','Select '+job.title+' '+job.account.label);check.disabled=busy||!job.active;check.checked=selected.has(job.key);check.onchange=()=>{check.checked?selected.add(job.key):selected.delete(job.key);stop.disabled=busy||selected.size===0;};cell().append(check);
   cell().textContent=(names[job.account.broker]||job.account.broker)+' · '+job.account.label+' / '+job.source.label;cell().textContent=job.title;
   cell().textContent=(job.state.config?.mode||job.state.mode||'—')+' · '+(job.state.config?.timeframe||'—');
   const status=cell();status.textContent=job.status;const note=document.createElement('small');note.textContent=job.state.message||job.state.last_event?.message||'';status.append(note);
   cell().textContent=job.state.started_at?new Date(typeof job.state.started_at==='number'?job.state.started_at*1000:job.state.started_at).toLocaleString(): 'Not recorded';
   const a=document.createElement('a');a.textContent='Open settings & chart';a.href=link(job,location.origin);cell().append(a);body.append(tr);
  }
  stop.disabled=busy||selected.size===0;
 }
 async function refresh(){
  if(loading||busy)return;loading=true;const ticket=++revision;message.textContent='Reading server jobs…';
  const next=[],errors=[];
  await Promise.all(root.BrokerForms.accounts().filter(a=>a.configured).map(async a=>{
   await Promise.all(sources(a).map(async source=>{try{const data=await request(source.url);for(const state of source.many?data.instances||[]:[data]){const job=normalize(a,source,state);if(job)next.push(job);}}catch(e){errors.push(a.label+' / '+source.label+': '+e.message);}}));
  }));
  if(ticket!==revision)return;loading=false;jobs=next;selected=new Set([...selected].filter(k=>jobs.some(j=>j.key===k&&j.active)));render();message.textContent='Updated '+new Date().toLocaleTimeString()+(errors.length?' · Some jobs unavailable: '+errors.join(' | '):' · All listed sources responded.');
 }
 open.onclick=()=>{dialog.showModal();void refresh();};dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.querySelector('[data-refresh]').onclick=()=>void refresh();
 stop.onclick=async()=>{
  if(busy||loading)return;busy=true;render();const results=[];
  for(const job of jobs.filter(j=>selected.has(j.key)))try{results.push(job.title+': '+await stopJob(job,request));}catch(e){results.push(job.title+': '+e.message+' — check status before retrying');}
  busy=false;selected.clear();await refresh();message.textContent=results.join(' | ');
 };
 setInterval(()=>{if(dialog.open&&!document.hidden)void refresh();},15000);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void mount());else void mount();
})(typeof window==='undefined'?globalThis:window);
