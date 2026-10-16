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
if(typeof module!=='undefined'&&module.exports){module.exports={eligible,jobsURL,createClient};return;}
if(new URLSearchParams(location.search).get('renkoBatchChart')==='1')return;
const baseFetch=root.fetch.bind(root),records=new Map(),submissions=new Map(),cursors=new Map();let modal,list,output,status,older;
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
 const key=String(base)+':'+job.job_id;
 if(job.status==='CONNECTION_DELAYED'){const old=records.get(key);if(old)job={...old.job,message:job.message};}
 records.set(key,{job,base:String(base)});render();
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
function button(label,click){const b=document.createElement('button');b.type='button';b.className='button';b.textContent=label;b.onclick=click;return b;}
function showOutput(record){
 output.replaceChildren();const title=document.createElement('h3');title.textContent=record.job.label+' · '+record.job.status;output.append(title);
 const pre=document.createElement('pre');pre.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere;max-height:55vh;overflow:auto';pre.textContent=JSON.stringify(record.job.output,null,2);output.append(pre);
 output.append(button('Restore output to its card',()=>restore(record)));
 output.append(button('Download output',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(record.job.output,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=record.job.job_id+'.json';a.click();URL.revokeObjectURL(url);}));
}
function restore(record){
 root.dispatchEvent(new CustomEvent('sector-pulse-job-output',{detail:{job:record.job,output:record.job.output,path:record.job.request.path,base:record.base}}));
}
function render(){
 if(!list)return;list.replaceChildren();if(older)older.disabled=![...cursors.values()].some(Boolean);
 for(const record of [...records.values()].sort((a,b)=>b.job.created-a.job.created)){
  const row=document.createElement('article');row.className='panel';row.style.padding='12px';
  const title=document.createElement('strong');title.textContent=record.job.label||record.job.job_id;row.append(title);
  const note=document.createElement('p');note.textContent=record.job.status+' · '+(record.job.message||'')+' · '+new Date((record.job.updated||Date.now()/1000)*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'});row.append(note);
  if(record.job.output)row.append(button('Open saved output',()=>showOutput(record)));
  if(!record.job.terminal&&record.job.status!=='CONNECTION_DELAYED')row.append(button(record.job.kind==='RUNNER'?'Stop runner job':'Stop analysis',async()=>{try{await client.cancel(record.base,record.job.job_id);}catch(error){status.textContent=error.message;}}));
  list.append(row);
 }
 if(!records.size)list.textContent='No saved jobs for your permitted broker accounts.';
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
   for(const job of data.jobs||[]){records.set(base.href+':'+job.job_id,{job,base:base.href});if(!job.terminal)client.watch(base,job.job_id);}
  }catch(error){failures++;}
 }));
 const permitted=new Set(sources.map(base=>base.href));
 await Promise.all(references().filter(ref=>permitted.has(ref.base)&&/^[a-f0-9]{32}$/.test(ref.job_id)&&!records.has(ref.base+':'+ref.job_id)).map(async ref=>{
  try{const job=await client.read(ref.base,ref.job_id);records.set(ref.base+':'+job.job_id,{job,base:ref.base});if(!job.terminal)client.watch(ref.base,job.job_id);}catch{}
 }));render();if(status)status.textContent=failures?'Some account job histories are unavailable; completed outputs remain saved.':'Outputs are saved on the server. Leaving this page does not stop jobs.';
}
async function loadOlder(){
 if(older)older.disabled=true;
 await Promise.all([...cursors].filter(([,cursor])=>cursor).map(async([base,cursor])=>{
  try{const url=new URL(base);url.searchParams.set('before',cursor);const response=await baseFetch(url.href,{cache:'no-store',signal:AbortSignal.timeout(10000)});const data=await response.json();if(!response.ok)throw Error(data.error||'Job history unavailable.');
   cursors.set(base,data.next_before||null);for(const job of data.jobs||[])records.set(base+':'+job.job_id,{job,base});
  }catch(error){if(status)status.textContent=error.message;}
 }));render();
}
async function mount(){
 await root.BrokerForms?.ready;
 modal=document.createElement('dialog');modal.setAttribute('aria-label','Saved analysis and runner jobs');modal.style.cssText='width:min(1150px,94vw);max-height:88vh;overflow:auto;background:#142033;color:#e4ecf7;border:1px solid #53647e;border-radius:12px;padding:22px';
 const heading=document.createElement('h2');heading.textContent='Saved analysis and runner jobs';older=button('Load older jobs',loadOlder);older.disabled=true;modal.append(heading,button('Close',()=>modal.close()),button('Refresh jobs',refresh),older);
 status=document.createElement('p');status.setAttribute('role','status');modal.append(status);list=document.createElement('div');output=document.createElement('section');modal.append(list,output);document.body.append(modal);
 for(const id of ['handoff','screener']){
  const section=document.getElementById(id);if(section)section.prepend(button('Saved jobs & outputs',()=>{modal.showModal();refresh();}));
 }
 const attachRunnerHistory=()=>{
  const dialog=document.querySelector('dialog[aria-label="Runner jobs"]');if(!dialog)return false;
  if(!dialog.querySelector('[data-durable-jobs]')){const open=button('Saved jobs & outputs',()=>{modal.showModal();refresh();});open.dataset.durableJobs='1';dialog.prepend(open);}
  return true;
 };
 if(!attachRunnerHistory()){
  const observer=new MutationObserver(()=>{if(attachRunnerHistory())observer.disconnect();});
  observer.observe(document.body,{childList:true,subtree:true});
 }

 await refresh();
 const restoreLatest=()=>{
  const seen=new Set();
  for(const record of [...records.values()].sort((a,b)=>b.job.created-a.job.created)){
   if(record.job.kind!=='ANALYSIS'||!record.job.output)continue;
   const key=(record.job.request.account_id||'dashboard')+':'+record.job.feature+':'+record.job.request.path;
   if(seen.has(key))continue;seen.add(key);restore(record);
  }
 };
 restoreLatest();root.addEventListener('broker-account-change',()=>queueMicrotask(restoreLatest));
}
root.SectorPulseJobs={client,refresh,records,restore,open:()=>{modal?.showModal();refresh();}};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>mount());else mount();
})(typeof window==='undefined'?globalThis:window);
