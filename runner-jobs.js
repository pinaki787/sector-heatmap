/* Account-bound runner inventory. Existing durable runners remain execution owners. */
(function(root){
'use strict';
const names={FYERS:'FYERS',DHAN:'Dhan',DELTA_INDIA:'Delta India',MOTILAL_OSWAL:'Motilal Oswal'};
function sources(a){
 if(a.broker==='MOTILAL_OSWAL')return [{kind:'renko',label:'Renko Supertrend',url:'/api/renko-motilal/'+encodeURIComponent(a.id)+'/instances',many:true}];
 if(!['FYERS','DHAN','DELTA_INDIA'].includes(a.broker))return [];
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
const featureKeys={renko:'renko-supertrend',engine:'renko-engine',band:'ema-band',rsi:'ema-cross',kama:'kama',straddle:'straddles',delta:'delta-india'};
function unwrap(source,state){
 if(source.kind==='delta')return {...state.runner,pnl_currency:state.pnl_currency,cost_pnl:state.cost_pnl,broker:'DELTA_INDIA',position:state.runner?.config?.mode==='PAPER'?state.paper?.position:state.runner_position};
 return state;
}
function normalize(a,source,state){
 state=unwrap(source,state);
 const c=state.config||{},instance=state.instance_key||'default';
 if(state.broker&&state.broker!==a.broker)return null;
 if(!c.underlying&&!c.symbol&&!state.instrument&&!state.running&&!state.position&&!state.pending&&!state.started_at&&!state.job_history?.length)return null;
 const prefix=a.broker==='MOTILAL_OSWAL'?'/api/renko-motilal/'+encodeURIComponent(a.id)+'/':a.broker==='DHAN'?'/api/renko-dhan/'+a.id+'/':'/broker-workspace/'+a.id+(a.broker==='DELTA_INDIA'?'/api/renko-delta/':'/api/renko-supertrend/');
 const suffix='?instance='+encodeURIComponent(instance);
 const active=!!(state.running||state.position||state.pending);
 return {key:[a.id,source.kind,source.market||instance].join(':'),account:a,source,instance,state,active,
  title:c.underlying||state.instrument||c.symbol||source.label,
  status:state.pending?'Order reconciliation':state.shutdown_pending?'Stopping':state.running?(state.position?'Managing position':'Watching'):state.position?'Monitoring paused':state.run_id?'Stopped':'Saved · not started',
  read:source.many?(source.readPrefix||prefix+'runner')+suffix:source.url,stop:source.many?(source.kind==='renko'?prefix+'stop':source.stop)+suffix:source.stop};
}
function netPnl(job){
 const cost=job.state.cost_pnl,value=cost?.total_net;
 const currency=job.state.pnl_currency||(job.account.broker==='DELTA_INDIA'?null:'INR');
 return {text:typeof value==='number'&&Number.isFinite(value)&&currency?currency+' '+value.toFixed(2):'Net unavailable',
 detail:cost?.basis||'After-cost valuation is not supplied by this runner.',value:typeof value==='number'&&Number.isFinite(value)?value:null};
}
function link(job,origin){
 const u=new URL(['straddle','delta'].includes(job.source.kind)?'/broker-workspace/'+job.account.id+'/':'/',origin);u.searchParams.set('brokerForm',job.source.kind);u.searchParams.set('brokerAccount',job.account.id);u.searchParams.set(job.source.kind+'Account',job.account.id);
 if(job.source.kind==='renko'){u.searchParams.set('renkoBroker',job.account.broker);u.searchParams.set('renkoInstance',job.instance);}
 if(['band','rsi','kama'].includes(job.source.kind))u.searchParams.set(job.source.kind+'Instance',job.instance);
 if(job.source.kind==='straddle')u.searchParams.set('straddleMarket',job.source.market);
 return u.href;
}
async function readSources(tasks,request,onResult){
 await Promise.all(tasks.map(async task=>{
  try{onResult(task,await request(task.source.url),null);}catch(error){onResult(task,null,error);}
 }));
}
async function stopJob(job,request){
 const current=unwrap(job.source,await request(job.read));
 if((current.run_id||current.run_started_at||current.started_at||null)!==(job.state.run_id||job.state.run_started_at||job.state.started_at||null))throw Error('Run changed. Refresh the job list before stopping.');
 if(!(current.running||current.position||current.pending))return 'Already stopped';
 const result=unwrap(job.source,await request(job.stop,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run_id:current.run_id,started_at:current.run_started_at||current.started_at})}));
 return result.running||result.position||result.pending?'Stopping / reconciliation pending':'Stopped';
}
if(typeof module!=='undefined'&&module.exports){module.exports={sources,normalize,link,stopJob,netPnl,readSources};return;}
root.RunnerJobInventory={sources,normalize,link};
async function mount(){
 if(new URLSearchParams(location.search).get('renkoBatchChart')==='1')return;
 await root.BrokerForms.ready;
 const nav=document.querySelector('nav');if(!nav)return;
 const open=document.createElement('button');open.type='button';open.dataset.feature='runner-jobs';open.hidden=true;open.textContent='Runner jobs';nav.append(open);
 const help=document.createElement('a');help.href='/user-guide.html';help.dataset.feature='user-guide';help.hidden=true;help.textContent='?';help.className='portal-help-icon';help.setAttribute('aria-label','Help / User guide');help.title='Help / User guide';document.body.append(help);
 const dialog=document.createElement('dialog');dialog.setAttribute('aria-label','Runner jobs');
 dialog.innerHTML=`<header><div><p class="job-window-eyebrow">RUNNERS &amp; EXECUTION</p><h2>Runner jobs</h2><p class="job-window-caption">Follow each runner, its trades and its journal.</p></div><button type="button" data-close>Close</button></header><div class="job-summary" data-count></div><div class="job-toolbar"><label>Find a job<input type="search" data-job-search placeholder="Instrument, strategy or account"></label><label class="job-history-toggle"><input type="checkbox" data-history> Include stopped / saved</label><button type="button" data-refresh>Refresh</button></div><div class="job-selection"><button type="button" data-select-all>Select active jobs</button><button type="button" data-clear>Clear selection</button><button type="button" data-stop disabled>Stop selected jobs</button><small>Stop follows the runner’s exit policy. Check pending orders in job details.</small></div><p data-message role="status" class="job-source-status"></p><div class="job-card-list" aria-label="Runner inventory"></div>`;
 document.body.append(dialog);
 const style=document.createElement('style');style.textContent=`
.portal-help-icon{position:fixed;top:16px;right:20px;z-index:100;width:36px;height:36px;display:grid;place-items:center;border:1px solid #53647e;border-radius:50%;background:#142033;color:#e4ecf7;font-size:20px;text-decoration:none}.portal-help-icon[hidden]{display:none}
dialog[aria-label="Runner jobs"]{--job-line:#344960;--job-muted:#a9bbcd;width:min(1120px,94vw);max-height:88vh;box-sizing:border-box;overflow:auto;background:#142033;color:#e4ecf7;border:1px solid #53647e;border-radius:16px;padding:28px;font:14px/1.5 system-ui,sans-serif}dialog[aria-label="Runner jobs"]::backdrop{background:#07101bd9}dialog[aria-label="Runner jobs"]>header{display:flex;justify-content:space-between;align-items:start;gap:16px}dialog[aria-label="Runner jobs"] h2{margin:0;font-size:28px;line-height:1.2;letter-spacing:-.025em}.job-window-eyebrow{font:11px/1.5 ui-monospace,monospace;letter-spacing:.12em;color:#9ab6d2;margin:0 0 8px}.job-window-caption{color:var(--job-muted);margin:8px 0 0}.job-summary{margin:24px 0 20px;padding:14px 0;border-block:1px solid var(--job-line);font:15px/1.6 ui-monospace,monospace;color:#b9d9f1}.job-toolbar{display:flex;align-items:end;gap:18px;flex-wrap:wrap}.job-toolbar>label:first-child{flex:1;min-width:220px}.job-toolbar label{font-size:12px;color:var(--job-muted)}.job-toolbar input[type=search]{display:block;box-sizing:border-box;width:100%;margin-top:6px;background:#0f1b2a;border:1px solid #52647e;color:#e4ecf7;border-radius:8px;padding:11px;font:14px system-ui,sans-serif}.job-history-toggle{display:flex;align-items:center;gap:8px;min-height:42px}.job-selection{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-top:16px}.job-selection small{flex-basis:100%;color:var(--job-muted);margin-top:4px}.job-source-status{font-size:12px;color:var(--job-muted);overflow-wrap:anywhere;max-height:90px;overflow:auto;margin:18px 0 12px}.job-card-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,430px),1fr));gap:14px}.runner-job-card{min-width:0;border:1px solid var(--job-line);border-left:3px solid #61758b;border-radius:10px;background:#19283b;padding:18px;overflow-wrap:anywhere}.runner-job-card.is-active{border-left-color:#71cfb1}.job-card-heading{display:flex;gap:12px;align-items:start}.job-card-heading>div{flex:1;min-width:0}.job-card-heading h3{margin:0 0 4px;font-size:18px;line-height:1.35;letter-spacing:-.015em}.job-card-account{margin:0;color:var(--job-muted);font-size:12px}.job-card-heading input{margin-top:6px;flex:none}.job-card-state{display:inline-block;margin:14px 0 8px;padding:3px 9px;background:#263b50;border-radius:5px;color:#b9d9f1;font-size:12px}.job-card-metrics{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:8px 0 14px}.job-card-metrics dt{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--job-muted)}.job-card-metrics dd{margin:4px 0 0;font:14px/1.5 ui-monospace,monospace}.job-card-note{font-size:12px;color:var(--job-muted);margin:8px 0;max-height:64px;overflow:auto}.job-card-actions{display:flex;align-items:center;gap:16px;flex-wrap:wrap;border-top:1px solid var(--job-line);padding-top:14px;margin-top:16px}.job-card-actions a{color:#a9d4fb;font-size:13px}.job-empty{grid-column:1/-1;text-align:center;border:1px dashed var(--job-line);border-radius:10px;padding:36px 20px}.job-empty h3{font-size:20px;margin:0 0 8px}.job-empty p{color:var(--job-muted);margin:0 0 18px}dialog[aria-label="Runner jobs"] button{padding:9px 13px;background:#263953;color:#e4ecf7;border:1px solid #52647e;border-radius:7px;font:13px/1.4 system-ui,sans-serif;cursor:pointer}dialog[aria-label="Runner jobs"] button:disabled{opacity:.45;cursor:default}dialog[aria-label="Runner jobs"] [data-stop]:not(:disabled){background:#583741;border-color:#a96a76}dialog[aria-label="Runner jobs"] :is(button,input,a):focus-visible{outline:2px solid #91c4ff;outline-offset:3px}.job-detail-pane{margin-top:22px}.job-detail-pane:empty{display:none}@media(max-width:600px){dialog[aria-label="Runner jobs"]{padding:18px;width:96vw}.job-toolbar>label:first-child{flex-basis:100%}.job-selection small{font-size:11px}.job-card-list{grid-template-columns:1fr}.job-card-metrics{gap:10px}}
`;document.head.append(style);
 const body=dialog.querySelector('.job-card-list'),message=dialog.querySelector('[data-message]'),stop=dialog.querySelector('[data-stop]'),count=dialog.querySelector('[data-count]');
 let jobs=[],selected=new Set(),busy=false,loading=false,revision=0,detailJob=null,detailBusy=false,detailRevision=0;
 const detail=document.createElement('section');detail.className='job-detail-pane';dialog.append(detail);
 function savedAudit(job){
  const run=root.RunnerJobDetails?.identity(job.state);
  if(!run)return null;
  for(const record of [...(root.SectorPulseJobs?.records?.values()||[])].sort((a,b)=>b.job.updated-a.job.updated)){
   if(record.job.request?.account_id!==job.account.id)continue;
   const output=record.job.output||{};
   const audit=[output.job_audit,...(output.job_audits||[])].find(a=>a&&a.run_id===run);
   if(audit)return audit;
  }
  return null;
 }
 function renderDetails(error){
  if(!detailJob||!root.RunnerJobDetails)return;
  root.RunnerJobDetails.render(detail,{state:detailJob.state,account:detailJob.account,title:detailJob.title,strategy:detailJob.source.label,
   audit:savedAudit(detailJob),chartUrl:link(detailJob,location.origin),observedAt:detailJob.receivedAt,connectionError:error,
   onRefresh:()=>void refreshDetail(),onStop:detailJob.active?async()=>{try{await stopJob(detailJob,request);await refreshDetail();}catch(error){renderDetails(error.message);}}:null});
 }
 async function refreshDetail(){
  if(!detailJob||detailBusy)return;
  detailBusy=true;const ticket=detailRevision,job=detailJob;
  try{
   const state=unwrap(job.source,await request(job.read));
   if(ticket!==detailRevision)return;
   const identity=root.RunnerJobDetails.identity;
   if(identity(state)!==identity(job.state)){renderDetails('Runner changed. Reopen the new run from the job list.');return;}
   detailJob={...job,state,receivedAt:Date.now()/1000,active:!!(state.running||state.position||state.pending)};renderDetails();
  }catch(error){if(ticket===detailRevision)renderDetails(error.message);}
  finally{detailBusy=false;}
 }

 const request=async(url,options={})=>{const r=await root.fetch(url,{...options,cache:'no-store',signal:AbortSignal.timeout(30000)});const d=await r.json();if(!r.ok||d.error)throw Error(d.error||'Job request failed');return d;};
 function render(){
  body.replaceChildren();count.textContent=jobs.filter(j=>j.state.running).length+' running · '+jobs.filter(j=>j.active).length+' active jobs';
  const query=dialog.querySelector('[data-job-search]').value.trim().toLowerCase();
  const visible=jobs.filter(j=>(j.active||dialog.querySelector('[data-history]').checked)&&(!query||[j.title,j.account.label,j.source.label,j.status].join(' ').toLowerCase().includes(query)));
  if(!visible.length){const empty=document.createElement('div');empty.className='job-empty';const heading=document.createElement('h3');heading.textContent=loading?'Reading your runners…':query?'No matching runners':dialog.querySelector('[data-history]').checked?'No saved runners':'No runners are active';const caption=document.createElement('p');caption.textContent=query?'Try another instrument, strategy or account.':'Completed and stopped runs remain available with their recorded journals.';empty.append(heading,caption);if(!loading&&!dialog.querySelector('[data-history]').checked){const history=document.createElement('button');history.type='button';history.textContent='View stopped / saved runners';history.onclick=()=>{dialog.querySelector('[data-history]').checked=true;render();};empty.append(history);}body.append(empty);}
  for(const job of visible){
   const card=document.createElement('article');card.className='runner-job-card'+(job.active?' is-active':'');
   const heading=document.createElement('div');heading.className='job-card-heading';
   const check=document.createElement('input');check.type='checkbox';check.setAttribute('aria-label','Select '+job.title+' '+job.account.label);check.disabled=busy||loading||!job.active;check.checked=selected.has(job.key);check.onchange=()=>{check.checked?selected.add(job.key):selected.delete(job.key);stop.disabled=busy||loading||selected.size===0;};
   const identity=document.createElement('div'),title=document.createElement('h3'),account=document.createElement('p');title.textContent=job.title;account.className='job-card-account';account.textContent=(names[job.account.broker]||job.account.broker)+' · '+job.account.label+' · '+job.source.label;identity.append(title,account);heading.append(check,identity);card.append(heading);
   const status=document.createElement('span');status.className='job-card-state';status.textContent=job.status;card.append(status);
   const metrics=document.createElement('dl');metrics.className='job-card-metrics';
   const metric=(label,value)=>{const group=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;group.append(dt,dd);metrics.append(group);return dd;};
   const profit=netPnl(job),pnl=metric('Net P&L',profit.text);pnl.title=profit.detail;if(profit.value!==null)pnl.style.color=profit.value<0?'#ff9e9e':'#9ce5b7';
   metric('Mode · timeframe',(job.state.config?.mode||job.state.mode||'—')+' · '+(job.state.config?.timeframe||'—'));
   metric('Started',job.state.started_at?new Date(typeof job.state.started_at==='number'?job.state.started_at*1000:job.state.started_at).toLocaleString():'Not recorded');
   metric('Run ID',String(job.state.run_id||'Not started'));card.append(metrics);
   const note=document.createElement('p');note.className='job-card-note';note.textContent=(job.state.status_read_delayed?'Runner busy · showing saved status. ':'')+(job.state.message||job.state.last_event?.message||'');card.append(note);
   if(job.state.job_history?.length){const history=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Submission history ('+job.state.job_history.length+')';history.append(summary);for(const run of job.state.job_history){const row=document.createElement('p');row.className='job-card-note';row.textContent=new Date(run.started_at*1000).toLocaleString()+' · '+(run.config?.mode||'—')+' · '+(run.status||'Unknown')+' · '+(run.message||'');history.append(row);}card.append(history);}
   const actions=document.createElement('div');actions.className='job-card-actions';const view=document.createElement('button');view.type='button';view.textContent='View job details';view.onclick=()=>{detailRevision++;detailJob={...job,receivedAt:Date.now()/1000};renderDetails();detail.scrollIntoView?.({block:'start',behavior:'auto'});void refreshDetail();};actions.append(view);
   const a=document.createElement('a');a.textContent='Settings & chart';a.href=link(job,location.origin);actions.append(a);card.append(actions);body.append(card);
  }
  stop.disabled=busy||loading||selected.size===0;
 }
 async function refresh(){
  if(loading||busy)return;loading=true;const ticket=++revision;message.textContent='Reading server jobs…';
  const next=[],errors=[];
  const tasks=root.BrokerForms.accounts().filter(a=>a.configured).flatMap(account=>sources(account).filter(source=>!root.SectorPulseWorkspace||root.SectorPulseWorkspace.allowed_features?.includes(featureKeys[source.kind])).map(source=>({account,source})));
  let completed=0;
  jobs=[];render();
  await readSources(tasks,request,({account,source},data,error)=>{
   if(ticket!==revision)return;
   completed++;
   if(error)errors.push(account.label+' / '+source.label+': '+error.message);
   else for(const state of source.many?data.instances||[]:[data]){const job=normalize(account,source,state);if(job)next.push(job);}
   jobs=[...next];render();
   message.textContent='Received '+completed+'/'+tasks.length+' job sources'+(completed<tasks.length?' · remaining sources are still responding…':'')+(errors.length?' · Some jobs unavailable: '+errors.join(' | '):'');
  });
  if(ticket!==revision)return;
  loading=false;jobs=next;selected=new Set([...selected].filter(k=>jobs.some(j=>j.key===k&&j.active)));render();message.textContent='Updated '+new Date().toLocaleTimeString()+(errors.length?' · Some jobs unavailable: '+errors.join(' | '):' · All listed sources responded.');
 }
 dialog.querySelector('[data-select-all]').onclick=()=>{if(busy||loading)return;selected=new Set(jobs.filter(j=>j.active).map(j=>j.key));render();};
 dialog.querySelector('[data-clear]').onclick=()=>{if(busy)return;selected.clear();render();};
 dialog.querySelector('[data-history]').onchange=render;
 dialog.querySelector('[data-job-search]').oninput=render;
 open.onclick=()=>{dialog.showModal();void refresh();};dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.querySelector('[data-refresh]').onclick=()=>void refresh();
 stop.onclick=async()=>{
  if(busy||loading)return;busy=true;render();const results=[];
  await Promise.all(jobs.filter(j=>selected.has(j.key)).map(async job=>{try{results.push(job.title+': '+await stopJob(job,request));}catch(e){results.push(job.title+': '+e.message+' — check status before retrying');}}));
  busy=false;selected.clear();await refresh();message.textContent=results.join(' | ');
 };
 setInterval(()=>{if(dialog.open&&!document.hidden)void refresh();},15000);
 setInterval(()=>{if(dialog.open&&!document.hidden&&detailJob)void refreshDetail();},2500);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void mount());else void mount();
})(typeof window==='undefined'?globalThis:window);
