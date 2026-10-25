/* Durable server jobs. Navigation never owns or cancels server work. */
(function(root){
'use strict';
function eligible(url,method='GET'){
 const path=new URL(url,'https://local.invalid').pathname;
 if(method.toUpperCase()!=='POST'||!path.includes('/api/'))return false;
 if(/trade-ticket|submit|override|squareoff|login|auth\/|diagnostic/.test(path))return false;
 if(path.endsWith('/analysis-handoff/preview'))return true;
 return /\/(analyze|analyze-options|analyze-market|analysis|ai-review|ai-analysis|backtest|start|runner-start|form-runner-start|start-selected|start-paper)$/.test(path);
}
function jobsURL(responseURL,accountID){
 const u=new URL(responseURL,root.location?.href||'https://local.invalid');
 const match=u.pathname.match(/^\/broker-workspace\/([a-f0-9]{32})\//);
 u.pathname=match?'/broker-workspace/'+match[1]+'/api/jobs':'/api/jobs';u.search='';
 if(!match&&accountID&&accountID!=='dashboard')u.searchParams.set('account_id',accountID);
 return u;
}
function createClient(fetcher,{onUpdate=()=>{},sleep=ms=>new Promise(r=>setTimeout(r,ms))}={}){
 const watching=new Map(),latest=new Map();
 async function read(base,id){const u=new URL(base);u.searchParams.set('job_id',id);const r=await fetcher(u.href,{cache:'no-store',signal:AbortSignal.timeout(10000)});const value=await r.json();if(!r.ok)throw Error(value.error||'Job unavailable.');return value;}
 function watch(base,id){
  const key=String(base)+':'+id;
  if(watching.has(key))return watching.get(key);
  const promise=(async()=>{
   while(true){
    let job;
    try{job=await read(base,id);}catch(error){onUpdate({job_id:id,status:'CONNECTION_DELAYED',message:error.message},base);await sleep(3000);continue;}
    latest.set(key,job);onUpdate(job,base);
    if(job.terminal)return job;
    await sleep(1500);
   }
  })().finally(()=>watching.delete(key));watching.set(key,promise);return promise;
 }
 async function cancel(base,id){const u=new URL(base);u.pathname+='/cancel';const r=await fetcher(u.href,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:id,account_id:u.searchParams.get('account_id')||undefined})});const value=await r.json();if(!r.ok)throw Error(value.error||'Stop failed.');onUpdate(value,base);return value;}
 return {read,watch,cancel,peek:(base,id)=>latest.get(String(base)+':'+id)};
}
if(typeof module!=='undefined'&&module.exports){module.exports={eligible,jobsURL,createClient,savedOutputOrder};return;}
if(new URLSearchParams(location.search).get('renkoBatchChart')==='1')return;
const baseFetch=root.fetch.bind(root),records=new Map(),submissions=new Map(),cursors=new Map();let modal,list,output,status,older,openedOutput=null;const pendingOutputs=new Map();let outputObserver;
const referencesKey='sector-pulse:durable-job-references:v1';
function references(){try{const value=JSON.parse(localStorage.getItem(referencesKey)||'[]');return Array.isArray(value)?value.slice(0,200):[];}catch{return [];}}
function remember(job,base){
 if(job?.kind!=='ANALYSIS'||!job.request?.path||!job.job_id)return;
 const key=String(base)+':'+job.feature+':'+job.request.path,refs=references(),old=refs.find(r=>r.key===key);
 if(old&&old.created>job.created)return;
 try{localStorage.setItem(referencesKey,JSON.stringify([{key,base:String(base),job_id:job.job_id,created:job.created},...refs.filter(r=>r.key!==key)].slice(0,200)));}catch{}
}
function isLatest(job,base){const key=String(base)+':'+job.feature+':'+job.request?.path;return !references().some(r=>r.key===key&&r.created>job.created);}
const client=createClient(baseFetch,{onUpdate(job,base){
 const key=job.job_id;
 if(job.status==='CONNECTION_DELAYED'){const old=records.get(key);if(old)job={...old.job,message:job.message};}
 records.set(key,{job,base:String(base)});render();
 if(openedOutput?.base===String(base)&&openedOutput.id===job.job_id&&job.kind==='RUNNER')showOutput({job,base:String(base)});
 remember(job,base);
 if(job.terminal&&job.output&&job.kind==='ANALYSIS'&&!submissions.has(job.job_id)&&isLatest(job,base))restore({job,base:String(base)});
 root.dispatchEvent(new CustomEvent('sector-pulse-job-update',{detail:{job,base:String(base)}}));
}});
root.fetch=async function(input,options={}){
 const url=typeof input==='string'||input instanceof URL?String(input):input.url;
 const method=options.method||input?.method||'GET';
 const selected=eligible(url,method);
 if(selected){const headers=new Headers(options.headers||input?.headers);if(!headers.has('X-Job-Request-ID'))headers.set('X-Job-Request-ID',crypto.randomUUID());options={...options,headers};}
 const response=await baseFetch(input,options);
 if(!selected||response.status!==202)return response;
 const accepted=await response.clone().json();if(!accepted.job_id)return response;
 const base=jobsURL(response.url||url,accepted.account_id);submissions.set(accepted.job_id,{base:String(base),url});
 remember(accepted.job,base);
 root.dispatchEvent(new CustomEvent('sector-pulse-job-submitted',{detail:{job:accepted.job,base:String(base)}}));
 if(!accepted.job?.terminal)void client.watch(base,accepted.job_id);
 const returnAccepted=new Headers(options.headers||input?.headers).get('X-Job-Return-Accepted')==='1';
 if(returnAccepted&&!accepted.job?.terminal){
  submissions.delete(accepted.job_id);
  return new Response(JSON.stringify({...accepted,job_accepted:true}),{status:202,headers:{'Content-Type':'application/json'}});
 }
 let job=accepted.job;
 const form=accepted.job?.feature==='renko-engine'?null:({handoff:'handoff',screener:'screener','ema-band':'band','ema-cross':'rsi',kama:'kama','renko-supertrend':'renko','trade-parser':'parser'})[accepted.job?.feature]||root.BrokerForms?.kind(accepted.job?.request?.path||url);
 const initialAccount=accepted.account_id==='dashboard'?null:accepted.account_id;
 while(true){
  if(job){
   if(job.kind==='RUNNER'&&job.output){submissions.delete(accepted.job_id);return new Response(JSON.stringify({...job.output,job_id:job.job_id}),{status:200,headers:{'Content-Type':'application/json'}});}
   if(job.terminal){
    submissions.delete(accepted.job_id);
    const current=root.BrokerForms?.account(form)?.id;
    if(initialAccount&&form&&current&&current!==initialAccount)return new Response(JSON.stringify({error:'Job output is saved for the previous broker account. Open Saved jobs to retrieve it.'}),{status:409,headers:{'Content-Type':'application/json'}});
    return new Response(JSON.stringify(job.status==='COMPLETED'?job.output:{error:job.error||job.message,job_id:job.job_id}),{status:job.status==='COMPLETED'?200:409,headers:{'Content-Type':'application/json'}});
   }
  }
  await new Promise(r=>setTimeout(r,750));
  job=client.peek(base,accepted.job_id)||job;
 }
};
function button(label,click){const b=document.createElement('button');if(['Saved jobs & outputs','Open complete saved output'].includes(label))b.dataset.feature='runner-jobs';b.type='button';b.className='button';b.textContent=label;b.onclick=click;return b;}
function renderSavedAnalysis(target,saved,job){
 if(job?.request?.path?.split('?')[0].endsWith('/renko-supertrend/backtest')&&root.RenkoBacktest?.render){root.RenkoBacktest.render(target,saved);return;}
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);return n;};
 if(!document.getElementById('saved-analysis-report-style')){
  const style=el('style');style.id='saved-analysis-report-style';style.textContent=
  '.saved-analysis-report{padding:20px;background:#101e30;border:1px solid #48617b;border-radius:12px;margin:18px 0;color:#e4ecf7}.saved-analysis-report h4{font-size:20px;margin:0 0 10px}.saved-analysis-report p{line-height:1.6}.saved-analysis-report .report-meta{color:#b6c8da}.saved-analysis-report .report-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px;margin:18px 0}.saved-analysis-report .report-plan{padding:18px;border:1px solid #48617b;border-left:5px solid #e8ba63;border-radius:8px;min-width:0;overflow-wrap:anywhere}.saved-analysis-report .report-plan.bearish{border-left-color:#ff8396}.saved-analysis-report .report-plan.bullish{border-left-color:#6bdbc3}.saved-analysis-report .direction.bearish{color:#ff9bab}.saved-analysis-report .direction.bullish{color:#7ce0cc}.saved-analysis-report .direction{font-weight:700}.saved-analysis-report dl{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:9px 14px;margin:16px 0 0}.saved-analysis-report dt{color:#b6c8da}.saved-analysis-report dd{margin:0;font-variant-numeric:tabular-nums;font-weight:650;overflow-wrap:anywhere}.saved-analysis-report summary{cursor:pointer;padding:12px 0;font-weight:600}.saved-analysis-report li{margin:10px 0;line-height:1.5}.saved-analysis-report pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:45vh;overflow:auto;font-size:12px}';document.head.append(style);
 }
 const section=el('section');section.className='saved-analysis-report';section.setAttribute('aria-label','Saved analysis report');
 const handoff=saved.schema==='sector-pulse-auto-analysis/v1'||job.feature==='handoff';
 section.append(el('h4',handoff?'Analysis Handoff report':'Saved analysis report'));
 const when=Date.parse(saved.generated_at||'')||Number(job.updated)*1000;
 const stamp=Number.isFinite(when)?new Date(when).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'})+' IST':'Time unavailable';
 const human=value=>String(value??'Unavailable').replaceAll('_',' ');
 const route={cash_equity:'Cash equities',stock_options:'Bought stock options'}[saved.instrument_route]||'Analysis';
 const meta=el('p',(saved.source?.broker||saved.broker||'Saved account')+' · '+route+' · '+stamp);meta.className='report-meta';section.append(meta);
 const cards=Array.isArray(saved.cards)?saved.cards:[];
 const aiSelected=saved.ai_provider==='CODEX_CHATGPT'||job.request?.payload?.ai_provider==='CODEX_CHATGPT';
 if(handoff){
  const scope=saved.scope||{};
  if(scope.screener)section.append(el('p','Screener '+scope.screener.status+' · '+scope.screener.analyzed+'/'+(scope.screener.current_selected??scope.screener.selected)+' examined · '+scope.screener.matched+' full-alignment matches · '+(scope.screener.duplicates_merged||0)+' duplicates merged'));
  if(scope.scanned_stocks!==undefined)section.append(el('p',Number(scope.scanned_stocks)+' stocks examined · '+Number(scope.matched_stocks||0)+' alignment matches · '+Number(scope.eligible_sectors||0)+' eligible sectors'));
  section.append(el('p',cards.length?cards.length+' saved recommendation '+(cards.length===1?'card':'cards'):'No eligible recommendation cards in this saved analysis.'));
  const grid=el('div');grid.className='report-grid';
  const price=value=>typeof value==='number'&&Number.isFinite(value)?new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(value):'Unavailable';
  for(const card of cards.slice(0,50)){
   const c=card.candidate||{},a=card.analysis||{},active=a.active_invalidation||a.proposed_sizing||{},conv=a.conviction||{};
   const option=a.kind==='LONG_OPTION',proposal=a.proposal||{};
   const accepted=typeof a.active_invalidation?.price==='number'&&Number.isFinite(a.active_invalidation.price);
   const stop=active.price??a.stop_invalidation??a.recommended_invalidation?.price??proposal.underlying_invalidation;
   const stopLabel=(option?'Stop-loss · underlying':'Stop-loss')+(accepted?'':' · proposed');
   const premiumStop=a.active_invalidation?.premium_stop_estimate||proposal.premium_stop_estimate;
   const direction=String(a.direction||c.direction||'UNAVAILABLE').toUpperCase(),tone=direction==='BEARISH'?'bearish':direction==='BULLISH'?'bullish':'neutral';
   const plan=el('article');plan.className='report-plan '+tone;
   plan.append(el('h4',c.name||a.name||c.symbol||'Instrument'));
   if(c.source_summary)plan.append(el('p','Sources: '+c.source_summary));
   const badge=el('p',human(direction)+' · '+(option?'Bought option · price bases shown below':'Cash equity'));badge.className='direction '+tone;plan.append(badge);
   const ratio=Number(conv.score)/Number(conv.maximum_score);
   const fields=[['Conviction',Number.isFinite(ratio)&&Number(conv.maximum_score)>0?(ratio*10).toFixed(2)+'/10 · '+human(conv.rating):'Unavailable'],
    ['Symbol',c.symbol||a.symbol||'Unavailable'],[option?'Entry · underlying':'Entry',price(a.entry)],[stopLabel,price(stop)],
    [option?'Target · option premium':'Target',option?(proposal.target_exit_points==null?'Not set in saved plan':price(proposal.target_exit_points)):price(active.target??a.target)],['Plan status',human(a.status)],['Data quality',human(a.data_quality||c.data_quality)]];
   if(option){fields.splice(3,0,['Entry · option premium',price(proposal.entry_points)],['Premium stop · estimated',premiumStop?.status==='ESTIMATED'?price(premiumStop.stop_loss_price):'Not available in saved plan']);}
   if(option&&a.report_levels&&root.HandoffLevelReport)fields.splice(1,fields.length-1,['Underlying symbol',c.symbol||a.symbol||'Unavailable'],['Plan status',human(a.status)],['Data quality',human(a.data_quality||c.data_quality)]);
   const dl=el('dl');for(const [label,value] of fields)dl.append(el('dt',label),el('dd',value));plan.append(dl);
   if(!accepted&&stop!=null)plan.append(el('p','Proposed invalidation only; acceptance and fresh ticket review are required.'));
   if(option)plan.append(el('p',a.report_levels&&root.HandoffLevelReport?'Horizon entries, targets and stops are shown below in separate underlying-price and option-premium rows. These are report-only scenarios.':'The stop above is an underlying-price invalidation, not an option-premium stop. The target is a saved option-premium objective, not an underlying target or a confirmed protective order.'));
   if(option&&premiumStop&&!a.report_levels)plan.append(el('p',premiumStop.assumptions||premiumStop.reason));
   if(option&&root.HandoffLevelReport){const levels=el('div');levels.innerHTML=root.HandoffLevelReport.html(card);plan.append(levels);}
   if(root.CompanyFundamentalsReport){const fundamentals=el('div');fundamentals.innerHTML=root.CompanyFundamentalsReport.html(a.fundamentals,aiSelected);plan.append(fundamentals);}
   if(a.reason||a.proposal_warning)plan.append(el('p',a.reason||a.proposal_warning));
   grid.append(plan);
  }
  section.append(grid);
  if(cards.length>50)section.append(el('p','Showing the first 50 cards; the full saved result is available below.'));
  const excluded=Array.isArray(saved.exclusions)?saved.exclusions:[];
  if(excluded.length){
   const detail=el('details');detail.dataset.auditKey='analysis-exclusions';detail.append(el('summary',excluded.length+' excluded '+(excluded.length===1?'candidate':'candidates')));
   const list=el('ul');for(const row of excluded.slice(0,100))list.append(el('li',(row.name||row.symbol||human(row.kind)||'Candidate')+': '+(row.reason||'No eligible plan')));detail.append(list);if(root.HandoffLevelReport)for(const row of excluded.slice(0,100)){const evidence=el('div');evidence.innerHTML=root.HandoffLevelReport.rejectionHtml(row);detail.append(evidence);}section.append(detail);
  }
  section.append(el('p','Saved analysis only. Entry, stop-loss and target are plan levels, not confirmed orders or fills.'));
 }else if(job.feature==='holdings'&&Array.isArray(saved.rows)){
  section.append(el('p',(saved.ai_provider==='CODEX_CHATGPT'?'AI-based company feedback':aiSelected?'AI selected · captured AI feedback unavailable in this older snapshot':'Rule-based analysis')+' · '+saved.rows.length+' holding/position rows · snapshot '+(saved.as_of||'Unavailable')));
  for(const row of saved.rows.slice(0,100)){const article=el('article');article.className='report-plan';article.append(el('h4',row.symbol+' · '+human(row.action)),el('p',(row.reasons||[]).join(' ')));if(row.ai_commentary?.rationale)article.append(el('p',row.ai_commentary.rationale));if(root.CompanyFundamentalsReport){const fundamentals=el('div');fundamentals.innerHTML=root.CompanyFundamentalsReport.html(row.fundamentals,aiSelected);article.append(fundamentals);}section.append(article);}
 }else{
  const summary=saved.summary||saved.message||saved.status;
  if(typeof summary==='string')section.append(el('p',human(summary)));
  const keys=Object.entries(saved).filter(([k,v])=>v===null||['string','number','boolean'].includes(typeof v));
  const dl=el('dl');for(const [key,value] of keys.slice(0,30))dl.append(el('dt',human(key)),el('dd',human(value)));section.append(dl);
 }
 const full=el('details');full.dataset.auditKey='full-saved-data';full.append(el('summary','Report details'));const detail=el('div');if(root.RenkoBacktest?.fields)detail.innerHTML=root.RenkoBacktest.fields(saved);else detail.textContent='Download the JSON audit for the complete retained data.';full.append(detail);section.append(full);target.append(section);
}

function showOutput(record,reveal=false){
 if(reveal&&!openJobs())return;
 const expanded=new Set([...output.querySelectorAll('details[open]')].map(n=>n.dataset.auditKey).filter(Boolean));
 openedOutput={base:String(record.base),id:record.job.job_id};
 output.replaceChildren();const title=document.createElement('h3');title.textContent=record.job.label+' · '+record.job.status;output.append(title);
 const reportActions=document.createElement('div');reportActions.className='saved-jobs-actions';reportActions.append(button('Back to saved runs',()=>{const row=[...list.querySelectorAll('[data-job-id]')].find(n=>n.dataset.jobId===record.job.job_id);(row||list).scrollIntoView?.({block:'center',behavior:'auto'});row?.querySelector('button')?.focus({preventScroll:true});}));output.append(reportActions);
 const saved=record.job.output||{};
 if(record.job.kind==='RUNNER'&&root.RunnerJobDetails){
  const snapshots=saved.runner_outputs||[saved.runner||saved];
  for(const state of snapshots){const section=document.createElement('section');output.append(section);
   const account=root.BrokerForms?.accounts().find(a=>a.id===record.job.request.account_id)||{id:record.job.request.account_id};
   const audit=[saved.job_audit,...(saved.job_audits||[])].find(a=>a&&a.run_id===root.RunnerJobDetails.identity(state));
   const inventory=root.RunnerJobInventory,kind={'renko-supertrend':'renko','renko-engine':'engine','ema-band':'band','ema-cross':'rsi',kama:'kama','delta-india':'delta',straddles:'straddle'}[record.job.feature];
   const source=inventory?.sources(account).find(s=>s.kind===kind&&(!s.market||record.job.request.path.includes(s.market)));
   const native=source?inventory.normalize(account,source,state):null;
   root.RunnerJobDetails.render(section,{state,account,audit,jobId:record.job.job_id,lifecycleStatus:record.job.status,title:record.job.label,observedAt:record.job.updated,chartUrl:native?inventory.link(native,location.origin):null,connectionError:record.job.health?.state==='NO_RECENT_PROGRESS'?record.job.health.message:null,
    onRefresh:async()=>{const fresh=await client.read(record.base,record.job.job_id);showOutput({...record,job:fresh});},
    onStop:record.job.terminal?null:async()=>{await client.cancel(record.base,record.job.job_id);showOutput({...record,job:await client.read(record.base,record.job.job_id)});}});
  }
 }else{renderSavedAnalysis(output,saved,record.job);}
 for(const node of output.querySelectorAll('details'))if(expanded.has(node.dataset.auditKey))node.open=true;
 if(record.job.kind==='ANALYSIS'&&record.job.terminal&&record.job.request?.path?.split('?')[0]==='/api/renko-supertrend/backtest'&&record.job.request?.payload?.settings){
  const rerun=button('Rerun captured backtest',async()=>{
   rerun.disabled=true;rerun.textContent='Creating saved backtest…';
   try{
    const u=new URL(record.base,location.href);u.pathname=u.pathname.replace(/\/api\/jobs$/,'')+'/api/renko-supertrend/backtest';u.searchParams.delete('job_id');
    const response=await root.fetch(u.href,{method:'POST',headers:{'Content-Type':'application/json','X-Job-Return-Accepted':'1'},body:JSON.stringify(record.job.request.payload)}),value=await response.json();
    if(!response.ok)throw Error(value.error||'Backtest could not be created.');
    if(!value.job_id)throw Error('Saved backtest identity was not returned.');
    const jobBase=jobsURL(u.href,record.job.request.account_id);status.textContent='Saved backtest created from the captured settings. Research only.';
    const finished=await client.watch(jobBase,value.job_id);showOutput({job:finished,base:String(jobBase)},true);
   }catch(error){status.textContent=error.message;}finally{rerun.disabled=false;rerun.textContent='Rerun captured backtest';}
  });reportActions.append(rerun);
 }
 reportActions.append(button('Restore output to its card',()=>restore(record)));
 reportActions.append(button('Download JSON audit',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(record.job.output,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=record.job.job_id+'.json';a.click();URL.revokeObjectURL(url);}));
 render();
 if(reveal){output.setAttribute('tabindex','-1');output.focus({preventScroll:true});output.scrollIntoView?.({block:'start',behavior:'auto'});}
}
function restore(record){
 const path=new URL(record.job.request?.path||'/',location.href).pathname;
 const handled=/\/(analysis-handoff\/(analyze|analyze-market)|chartink\/analyze|holdings-analysis\/analyze)$/.test(path);
 if(record.job.kind==='ANALYSIS'&&record.job.output&&!handled){
  const feature=record.job.feature,kind=({'renko-engine':'engine','renko-supertrend':'renko','ema-band':'band','ema-cross':'rsi',kama:'kama',handoff:'handoff',screener:'screener'})[feature]||root.BrokerForms?.kind(path);
  const selected=root.BrokerForms?.account(kind)?.id,owner=record.job.request.account_id;
  const section=document.getElementById(feature)||document.getElementById(kind),pendingKey=feature+':'+owner;
  if(!section){
   pendingOutputs.set(pendingKey,record);
   if(!outputObserver)outputObserver=new MutationObserver(()=>{for(const value of [...pendingOutputs.values()])restore(value);if(!pendingOutputs.size)outputObserver.disconnect();});
   outputObserver.observe(document.body,{childList:true,subtree:true});
  }else pendingOutputs.delete(pendingKey);
  if(section&&(!selected||owner==='dashboard'||owner===selected)){
   let panel=section.querySelector('[data-generic-job-output]');if(!panel){panel=document.createElement('section');panel.className='panel';panel.dataset.genericJobOutput='1';panel.style.padding='16px';section.append(panel);}
   panel.dataset.accountId=owner||'dashboard';panel.replaceChildren();const heading=document.createElement('h3');heading.textContent=record.job.label+' · '+record.job.status;panel.append(heading);
   if(path.endsWith('/renko-supertrend/backtest')){const summary=document.createElement('p');const saved=record.job.output;summary.textContent='Backtest report · '+(saved.status||record.job.status)+' · '+(saved.underlying||'Instrument unavailable')+' · '+(saved.requested?.from_date||'')+' — '+(saved.requested?.to_date||'');panel.append(summary,button('Open complete saved output',()=>{modal.showModal();showOutput(record,true);}));}
   else{
   const summary=document.createElement('p');summary.textContent='Saved analysis report · '+(record.job.output?.status||record.job.status)+' · Full output retained for review.';panel.append(summary,button('Open complete saved output',()=>{modal.showModal();showOutput(record,true);}));
   }
   if(record.job.terminal)root.HandoffLevelReport?.complete(panel,{key:owner+':'+feature+':'+path,label:'Completed output · '+record.job.label+' · '+record.job.status});
  }
 }
 root.dispatchEvent(new CustomEvent('sector-pulse-job-output',{detail:{job:record.job,output:record.job.output,path:record.job.request.path,base:record.base}}));
}
function savedOutputOrder(a,b){
 return Number(b.job.created||0)-Number(a.job.created||0)||String(b.job.job_id).localeCompare(String(a.job.job_id));
}
function jobsViewAllowed(){const c=root.SectorPulseWorkspace||root.BrokerForms?.context?.();return (!c||c.admin||c.allowed_features?.includes('runner-jobs'))&&c?.sidebar_visibility?.['runner-jobs']!==false;}
function accountID(record){return record.job.request?.account_id||new URL(record.base,location.href).pathname.match(/broker-workspace\/([^/]+)/)?.[1]||new URL(record.base,location.href).searchParams.get('account_id')||record.job.owner?.split(':').at(-1)||'dashboard';}
function accountName(record){const id=accountID(record),a=root.BrokerForms?.accounts?.().find(x=>x.id===id);return a?(a.label+' · '+a.broker):id==='dashboard'?'Dashboard':record.job.broker||'Saved account';}
function visibleRecords(){const term=modal?.querySelector('[data-jobs-search]')?.value.toLowerCase().trim()||'',account=modal?.querySelector('[data-jobs-account]')?.value||'',kind=modal?.querySelector('[data-jobs-kind]')?.value??'ANALYSIS',state=modal?.querySelector('[data-jobs-state]')?.value||'';return [...records.values()].filter(r=>(!account||accountID(r)===account)&&(!kind||r.job.kind===kind)&&(!state||(state==='ACTIVE'?!r.job.terminal:r.job.status===state))&&(!term||(r.job.label+' '+accountName(r)+' '+r.job.feature+' '+(r.job.output?.underlying||'')+' '+r.job.job_id).toLowerCase().includes(term))).sort(savedOutputOrder);}
function openJobs(kind){
 if(!modal||!jobsViewAllowed())return false;
 const live=kind==='LIVE';if(kind&&kind!=='LIVE')modal.querySelector('[data-jobs-kind]').value=kind==='ALL'?'':kind;
 for(const view of document.querySelectorAll('.view'))view.classList.toggle('active',view===modal);
 for(const nav of document.querySelectorAll('.nav [data-view]')){const active=nav.dataset.view==='runner-jobs';nav.classList.toggle('active',active);nav.setAttribute('aria-pressed',String(active));}
 modal.hidden=false;modal.style.display='';modal.classList.add('active');
 for(const node of modal.querySelectorAll('[data-saved-catalog]'))node.hidden=live;
 const liveHost=modal.querySelector('[data-live-host]');liveHost.hidden=!live;
 if(!live){const inventory=liveHost.querySelector('dialog[open]');inventory?.close();}
 try{localStorage.setItem('sector-pulse:selected-view','runner-jobs');}catch{}
 if(live){if(root.RunnerJobInventory?.open)root.RunnerJobInventory.open(liveHost);else status.textContent='Runner controls are loading. Select Active runner controls again.';}
 render();return true;
}
function render(){
 if(!list)return;list.replaceChildren();if(older)older.disabled=![...cursors.values()].some(Boolean);
 const rows=visibleRecords(),summary=modal.querySelector('[data-jobs-summary]');
 if(summary)summary.textContent=!modal.querySelector('[data-live-host]').hidden?'Current runner inventory · account-scoped status and existing controls':rows.length+' displayed · '+records.size+' loaded · '+[...records.values()].filter(r=>!r.job.terminal).length+' active in loaded results · newest run first';
 for(const record of rows){
  const row=document.createElement('article');row.className='saved-job-row'+(openedOutput?.id===record.job.job_id?' is-selected':'');row.dataset.jobId=record.job.job_id;
  const date=document.createElement('time'),created=Number(record.job.created||0);if(Number.isFinite(created)&&created>0){date.dateTime=new Date(created*1000).toISOString();date.textContent=new Date(created*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'})+' IST';}else date.textContent='Run date unavailable';row.append(date);
  const description=document.createElement('div');description.className='saved-job-title';const title=document.createElement('strong');title.textContent=record.job.label||record.job.job_id;description.append(title);const kind=document.createElement('small');kind.textContent=(record.job.kind==='ANALYSIS'?'Analysis':'Runner history')+' · '+record.job.job_id;description.append(kind);row.append(description);
  const account=document.createElement('div');account.textContent=accountName(record);account.style.fontSize='12px';row.append(account);
  const state=document.createElement('div');state.className='saved-job-state-cell';const badge=document.createElement('span');badge.className='saved-job-state '+String(record.job.status).toLowerCase();badge.textContent=record.job.status;state.append(badge);
  if(record.job.output?.status&&record.job.output.status!==record.job.status){const quality=document.createElement('small');quality.textContent='Report: '+record.job.output.status;state.append(quality);}row.append(state);
  const actions=document.createElement('div');actions.className='saved-jobs-actions';if(record.job.output)actions.append(button('Open saved output',()=>showOutput(record,true)));
  if(!record.job.terminal&&record.job.status!=='CONNECTION_DELAYED'){const stop=button(record.job.kind==='RUNNER'?'Stop runner job':'Stop analysis',async()=>{try{await client.cancel(record.base,record.job.job_id);}catch(error){status.textContent=error.message;}});stop.classList.add('job-stop');actions.append(stop);}row.append(actions);
  if(record.job.error){const error=document.createElement('p');error.className='saved-job-error';error.textContent=record.job.error;row.append(error);}
  list.append(row);
 }
 if(!rows.length){const empty=document.createElement('p');empty.className='saved-jobs-empty';empty.textContent=records.size?'No saved runs match these filters. Change the type, account or search.':'No saved jobs for your permitted broker accounts.';list.append(empty);}
}
async function refresh(){
 await root.BrokerForms?.ready;
 const sources=[new URL('/api/jobs',location.origin)];
 for(const a of root.BrokerForms?.accounts()||[]){
  if(!a.configured)continue;
  sources.push(new URL(['FYERS','DELTA_INDIA'].includes(a.broker)?'/broker-workspace/'+a.id+'/api/jobs':'/api/jobs?account_id='+a.id,location.origin));
 }
 let failures=0;
 await Promise.all(sources.map(async base=>{
  try{const r=await baseFetch(base.href,{cache:'no-store',signal:AbortSignal.timeout(10000)}),data=await r.json();if(!r.ok)throw Error(data.error);
   cursors.set(base.href,data.next_before||null);
   for(const job of data.jobs||[]){records.set(job.job_id,{job,base:base.href});if(!job.terminal)client.watch(base,job.job_id);}
  }catch(error){failures++;}
 }));
 const permitted=new Set(sources.map(base=>base.href));
 for(const [id,record] of records)if(!permitted.has(record.base))records.delete(id);
 await Promise.all(references().filter(ref=>permitted.has(ref.base)&&/^[a-f0-9]{32}$/.test(ref.job_id)&&!records.has(ref.job_id)).map(async ref=>{
  try{const job=await client.read(ref.base,ref.job_id);records.set(job.job_id,{job,base:ref.base});if(!job.terminal)client.watch(ref.base,job.job_id);}catch{}
 }));render();root.dispatchEvent(new CustomEvent('sector-pulse-jobs-refreshed'));if(status)status.textContent=failures?'Some account job histories are unavailable; completed outputs remain saved.':'Outputs are saved on the server. Leaving this page does not stop jobs.';
}
async function loadOlder(){
 if(older)older.disabled=true;
 await Promise.all([...cursors].filter(([,cursor])=>cursor).map(async([base,cursor])=>{
  try{const url=new URL(base);url.searchParams.set('before',cursor);const response=await baseFetch(url.href,{cache:'no-store',signal:AbortSignal.timeout(10000)});const data=await response.json();if(!response.ok)throw Error(data.error||'Job history unavailable.');
   cursors.set(base,data.next_before||null);for(const job of data.jobs||[])records.set(job.job_id,{job,base});
  }catch(error){if(status)status.textContent=error.message;}
 }));render();
}
async function mount(){
 await root.BrokerForms?.ready;
 const css=document.createElement('style');css.id='saved-jobs-fullpage-style';css.textContent="#runner-jobs{--sj-line:#35465d;--sj-muted:#9eb1c9;color:#dbe6f4;min-width:0}#runner-jobs .saved-jobs-head{display:flex;align-items:start;justify-content:space-between;gap:24px;margin:0 0 24px}#runner-jobs h1{font:600 29px/1.2 \"Avenir Next\",system-ui,sans-serif;letter-spacing:-.7px;margin:6px 0 9px}#runner-jobs .saved-jobs-kicker{color:#8fa8cb;font:11px Menlo,monospace;letter-spacing:1.3px}#runner-jobs p{line-height:1.6}#runner-jobs .saved-jobs-head p{max-width:750px;color:var(--sj-muted);font-size:13px;margin:0}#runner-jobs button{cursor:pointer}#runner-jobs .saved-jobs-actions{display:flex;gap:8px;flex-wrap:wrap}#runner-jobs .saved-jobs-actions button{white-space:nowrap}#runner-jobs .saved-jobs-summary{padding:16px 0;border-block:1px solid var(--sj-line);font:12px Menlo,monospace;color:#a9c8dc;line-height:1.8;margin-bottom:20px}#runner-jobs .saved-jobs-toolbar{display:grid;grid-template-columns:minmax(240px,2fr) repeat(3,minmax(130px,1fr));gap:16px;margin:20px 0}#runner-jobs label{display:grid;gap:7px;font-size:11px;color:var(--sj-muted)}#runner-jobs input,#runner-jobs select{width:100%;min-width:0;box-sizing:border-box;background:#15243a;color:#e2ecf8;border:1px solid #435975;border-radius:6px;padding:10px;font:13px system-ui,sans-serif}#runner-jobs .saved-jobs-message{font-size:12px;color:var(--sj-muted);min-height:20px}#runner-jobs .saved-job-row{display:grid;grid-template-columns:155px minmax(220px,1fr) 170px 140px 205px;gap:16px;align-items:center;padding:18px 16px;margin:0;border:0;border-bottom:1px solid var(--sj-line);border-radius:0;background:#17263a}#runner-jobs .saved-job-row:nth-child(even){background:#192a40}#runner-jobs .saved-job-row.is-selected{box-shadow:inset 3px 0 #76cabb;background:#20364a}#runner-jobs .saved-job-row strong{display:block;font-size:14px;font-weight:600;line-height:1.45;overflow-wrap:anywhere}#runner-jobs .saved-job-row small{display:block;color:var(--sj-muted);font-size:11px;line-height:1.7;margin-top:4px;overflow-wrap:anywhere}#runner-jobs .saved-job-row time{font:11px/1.8 Menlo,monospace;color:#a8bad0}#runner-jobs .saved-job-state{display:inline-block;padding:5px 8px;border:1px solid #51637c;border-radius:5px;font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#bfcee0}#runner-jobs .saved-job-state.completed{border-color:#397b70;color:#8ad2c1}#runner-jobs .saved-job-state.failed,#runner-jobs .saved-job-state.interrupted{border-color:#865a64;color:#e7afb9}#runner-jobs .saved-job-state.running,#runner-jobs .saved-job-state.queued{border-color:#8b7548;color:#e2c488}#runner-jobs .saved-job-row .saved-jobs-actions{justify-content:flex-end}#runner-jobs .saved-job-row button{font-size:11px;padding:9px 11px;border-radius:5px}#runner-jobs .saved-job-row .job-stop{background:#583340;color:#ffd6df}#runner-jobs .saved-job-error{grid-column:2/-1;font-size:12px;color:#e4a5b1;margin:0}#runner-jobs .saved-jobs-empty{padding:42px 20px;border:1px dashed #52617a;border-radius:8px;text-align:center;color:var(--sj-muted)}#runner-jobs .saved-jobs-report{border-top:2px solid #76cabb;margin-top:30px;padding-top:22px;scroll-margin-top:24px;min-width:0}#runner-jobs .saved-jobs-report:empty{display:none}#runner-jobs .saved-jobs-report>h3{font:600 20px \"Avenir Next\",system-ui,sans-serif;margin:0 0 16px}#runner-jobs .saved-jobs-report>button{margin:12px 8px 0 0}#runner-jobs .saved-jobs-footer{margin-top:18px;display:flex;justify-content:space-between;align-items:center;gap:16px;color:var(--sj-muted);font-size:12px}#runner-jobs [hidden]{display:none!important}#runner-jobs dialog.fullpage-runner-pane{display:block;position:static;width:100%;max-width:none;max-height:none;height:auto;overflow:visible;margin:20px 0 0;padding:0;background:transparent;border:0;border-radius:0;color:inherit}#runner-jobs dialog.fullpage-runner-pane:not([open]){display:none}#runner-jobs dialog.fullpage-runner-pane>header{display:none}#runner-jobs .saved-jobs-live-host{min-width:0}.saved-jobs-page button:focus-visible,.saved-jobs-page input:focus-visible,.saved-jobs-page select:focus-visible{outline:2px solid #8bbce9;outline-offset:3px}@media(max-width:1200px){#runner-jobs .saved-job-row{grid-template-columns:145px minmax(180px,1fr) 180px}#runner-jobs .saved-job-state-cell{grid-column:1}#runner-jobs .saved-job-row .saved-jobs-actions{grid-column:2/-1}#runner-jobs .saved-job-error{grid-column:1/-1}}@media(max-width:720px){#runner-jobs .saved-jobs-head{flex-direction:column;gap:16px}#runner-jobs h1{font-size:25px}#runner-jobs .saved-jobs-toolbar{grid-template-columns:1fr 1fr;gap:12px}#runner-jobs .saved-jobs-toolbar label:first-child{grid-column:1/-1}#runner-jobs .saved-job-row{grid-template-columns:1fr 1fr;gap:10px;padding:16px 12px}#runner-jobs .saved-job-title{grid-column:1/-1;grid-row:1}#runner-jobs .saved-job-row .saved-jobs-actions{grid-column:1/-1;justify-content:stretch}#runner-jobs .saved-job-row .saved-jobs-actions button{flex:1}#runner-jobs .saved-job-state-cell{grid-column:1/-1}#runner-jobs .saved-jobs-footer{align-items:start;flex-direction:column}#runner-jobs .saved-jobs-summary{font-size:11px}#runner-jobs .saved-jobs-report{margin-top:22px}body:has(#runner-jobs.active) .desk{grid-template-columns:minmax(0,1fr)}body:has(#runner-jobs.active) .work,body:has(#runner-jobs.active) .side{min-width:0;max-width:100%;box-sizing:border-box}body:has(#runner-jobs.active) .side{padding:10px;gap:8px}body:has(#runner-jobs.active) .side .nav{display:flex;gap:6px;overflow-x:auto}body:has(#runner-jobs.active) .side .nav button{flex:none;white-space:nowrap}body:has(#runner-jobs.active) .side .trading-strategies-nav{display:contents}body:has(#runner-jobs.active) .side .trading-strategies-heading{display:none}body:has(#runner-jobs.active) .work{padding:16px 10px}}\n";document.head.append(css);
 modal=document.createElement('section');modal.id='runner-jobs';modal.className='view saved-jobs-page';modal.setAttribute('aria-label','Saved analysis and runner jobs');
 modal.innerHTML='<header class="saved-jobs-head"><div><span class="saved-jobs-kicker">RESEARCH & EXECUTION · RUN LEDGER</span><h1>Saved analysis and runner jobs</h1><p>Browse saved runs across your permitted accounts. Open a report without losing your place. Navigation never starts or stops a job.</p></div><div class="saved-jobs-actions" data-page-actions></div></header><div class="saved-jobs-summary" data-jobs-summary></div><div class="saved-jobs-toolbar" data-saved-catalog><label>Find a saved run<input type="search" data-jobs-search placeholder="Instrument, strategy or report ID"></label><label>Job type<select data-jobs-kind><option value="ANALYSIS">Analysis</option><option value="RUNNER">Runner history</option><option value="">All saved runs</option></select></label><label>Account<select data-jobs-account><option value="">All permitted accounts</option><option value="dashboard">Dashboard</option></select></label><label>Status<select data-jobs-state><option value="">All statuses</option><option value="ACTIVE">Active</option><option value="COMPLETED">Completed</option><option value="FAILED">Failed</option><option value="CANCELLED">Cancelled</option><option value="INTERRUPTED">Interrupted</option></select></label></div><p class="saved-jobs-message" role="status"></p><div data-live-host hidden></div>';
 const actions=modal.querySelector('[data-page-actions]');actions.append(button('Saved analyses',()=>openJobs('ANALYSIS')),button('Runner history',()=>openJobs('RUNNER')),button('Active runner controls',()=>openJobs('LIVE')),button('Refresh jobs',refresh));
 status=modal.querySelector('[role=status]');list=document.createElement('div');list.className='saved-jobs-catalog';list.dataset.savedCatalog='1';output=document.createElement('section');output.id='saved-job-report';output.className='saved-jobs-report';output.dataset.savedCatalog='1';
 const footer=document.createElement('div');footer.className='saved-jobs-footer';footer.dataset.savedCatalog='1';const note=document.createElement('span');note.textContent='Run dates determine order. Progress refreshes never move an older run above a newer run.';older=button('Load older jobs',loadOlder);older.disabled=true;footer.append(note,older);modal.append(list,footer,output);(document.querySelector('.work')||document.body).append(modal);
 modal.showModal=()=>openJobs();modal.close=()=>{modal.classList.remove('active');};
 const nav=document.querySelector('.nav')||document.querySelector('nav');if(nav){const entry=nav.querySelector('[data-feature="runner-jobs"]')||document.createElement('button');entry.type='button';entry.dataset.feature='runner-jobs';entry.dataset.view='runner-jobs';entry.textContent='Saved jobs & reports';entry.setAttribute('aria-pressed','false');entry.hidden=!jobsViewAllowed();entry.style.display=entry.hidden?'none':'';entry.onclick=()=>{if(openJobs())void refresh();};if(!entry.parentElement)nav.append(entry);}
 const account=modal.querySelector('[data-jobs-account]');for(const a of root.BrokerForms?.accounts?.()||[]){if(!a.configured)continue;const option=document.createElement('option');option.value=a.id;option.textContent=a.label+' · '+a.broker;account.append(option);}
 for(const control of modal.querySelectorAll('input,select'))control.addEventListener(control.type==='search'?'input':'change',render);
 for(const id of ['handoff','screener']){const section=document.getElementById(id);if(section){const open=button('Saved jobs & outputs',()=>{if(openJobs())void refresh();});if(id==='handoff'){let actions=section.querySelector('[data-handoff-output-actions]');if(!actions){actions=document.createElement('nav');actions.dataset.handoffOutputActions='1';section.querySelector('header').after(actions);}actions.prepend(open);}else section.prepend(open);}}
 if(new URLSearchParams(location.search).get('view')==='runner-jobs'||localStorage.getItem('sector-pulse:selected-view')==='runner-jobs')openJobs('ANALYSIS');
 await refresh();
 const restoreLatest=()=>{
  const seen=new Set();
  for(const record of [...records.values()].sort((a,b)=>b.job.created-a.job.created)){
   if(record.job.kind!=='ANALYSIS'||!record.job.output)continue;
   const key=(record.job.request.account_id||'dashboard')+':'+record.job.feature+':'+record.job.request.path;
   if(seen.has(key))continue;seen.add(key);restore(record);
  }
 };
 restoreLatest();root.addEventListener('broker-account-change',()=>{for(const panel of document.querySelectorAll('[data-generic-job-output]'))panel.remove();queueMicrotask(restoreLatest);});
}
root.SectorPulseJobs={client,refresh,records,restore,open:(kind)=>{if(openJobs(kind))void refresh();},page:()=>modal,canOpen:jobsViewAllowed,savedOutputOrder};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>mount());else mount();
})(typeof window==='undefined'?globalThis:window);
