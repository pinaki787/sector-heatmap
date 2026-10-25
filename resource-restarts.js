/* Restart commands are explicit; only status probes retry automatically. */
(() => {
  'use strict';
  const ACTIVE = new Set(['SUBMITTING','SCHEDULED','CHECKING','RESTARTING','WAITING','UNKNOWN']);
  function rejectedRestart(job){return !!job&&(job.submissionRejected===true||(!job.accepted&&(job.events||[]).some(event=>/^(Restart blocked:|Bounce blocked:)/.test(String(event.message||'')))));}
  function mount(section, context) {
    if (!context.admin) return;
    const panel = document.createElement('section'); panel.className='panel resource-restarts';
    panel.innerHTML='<h2>Restart services</h2><p>Restart the dashboard or one broker worker. Active runners, positions or pending orders block a restart. No runner is started automatically.</p><div class="resource-restart-actions"><button type="button" class="button" data-dashboard>Restart dashboard</button><label>Broker worker <select aria-label="Broker worker to restart"><option value="">Loading accounts…</option></select></label><button type="button" class="button" data-broker>Restart selected broker</button></div><p role="status" aria-live="polite" data-outcome>No restart requested.</p><div class="restart-progress" data-progress hidden><div class="restart-progress-heading"><strong data-phase></strong><span data-elapsed></span></div><progress max="1" aria-label="Service restart progress"></progress><ol class="restart-stages" aria-label="Restart stages"><li>Request</li><li>Restart</li><li>Readiness</li><li>Complete</li></ol><small data-probes></small></div><ol data-history></ol><button type="button" class="button" data-check hidden>Check restart status</button>';
    section.querySelector('header').after(panel);
    const style=document.createElement('style');style.textContent='.resource-restarts{margin:18px 0;border-top:3px solid #e8bd70}.resource-restart-actions{display:flex;gap:14px;align-items:end;flex-wrap:wrap}.resource-restarts label{display:grid;gap:6px}.resource-restarts [data-outcome]{padding:12px;border-left:3px solid #84c8f5;background:var(--surface);overflow-wrap:anywhere}.resource-restarts ol{font:12px/1.7 ui-monospace,monospace;max-height:180px;overflow:auto}.resource-restarts button:disabled{opacity:.5}.restart-progress{margin:14px 0;padding:14px;border:1px solid var(--border);border-radius:8px}.restart-progress-heading{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.restart-progress progress{width:100%;height:12px;margin:10px 0;accent-color:#84c8f5}.resource-restarts .restart-stages{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;list-style:none;padding:0;margin:6px 0 12px;max-height:none}.restart-stages li{border-top:3px solid #344963;padding-top:6px;color:#90a7bc}.restart-stages li[data-state=done]{border-color:#82d4ad;color:#bde9d2}.restart-stages li[data-state=current]{border-color:#84c8f5;color:#edf4ff;font-weight:bold}.restart-progress[data-status=FAILED] progress{accent-color:#e59090}.restart-progress[data-status=UNKNOWN] progress{accent-color:#e8bd70}.restart-progress[data-status=READY] progress{accent-color:#82d4ad}.restart-progress small{display:block;color:var(--muted)}@media(max-width:500px){.resource-restarts .restart-stages{font-size:11px;gap:4px}}';document.head.append(style);
    const key='sector-pulse:service-restart:'+String(context.username||context.user?.username||'administrator');
    const main=panel.querySelector('[data-dashboard]'), broker=panel.querySelector('[data-broker]'), select=panel.querySelector('select'), outcome=panel.querySelector('[data-outcome]'), history=panel.querySelector('[data-history]'), check=panel.querySelector('[data-check]');
    let job=null,csrf='',timer=null,probing=false,heartbeat=null;
    try {job=JSON.parse(localStorage.getItem(key)||'null');} catch {}
    // Older clients could poll a request that preflight rejected. Recover it
    // as terminal; preserve its history and never send a replacement command.
    if(rejectedRestart(job)){job.submissionRejected=true;job.status='BLOCKED';job.message='Restart request was blocked; no restart was scheduled. Resolve the blocker below, then submit a new restart.';}
    function save(){try{localStorage.setItem(key,JSON.stringify(job));}catch{}render();}
    const readable=message=>String(message||'').startsWith('Dashboard temporarily unreachable;')?'Dashboard temporarily unreachable; probing again in two seconds.':message;
    function progress(){
      const box=panel.querySelector('[data-progress]');box.hidden=!job;if(!job)return;
      const done=job.status==='READY',failed=['FAILED','BLOCKED'].includes(job.status),paused=job.status==='UNKNOWN';
      const stage=done?3:Math.min(2,job.stage??({SUBMITTING:0,SCHEDULED:1,CHECKING:1,RESTARTING:1,WAITING:2,UNKNOWN:2}[job.status]||0));
      const phase=job.status==='BLOCKED'?'Restart blocked · no restart scheduled':done?'Restart complete':failed?'Restart failed':paused?'Readiness unconfirmed':stage===0?'Sending restart request':stage===1?'Restart accepted':'Checking service readiness';
      box.dataset.status=job.status;panel.querySelector('[data-phase]').textContent=phase;
      const bar=box.querySelector('progress');bar.setAttribute('aria-valuetext',phase);
      if(done||failed||paused)bar.value=done?1:0;else bar.removeAttribute('value');
      const end=done||failed?(job.completedAt||job.events?.at(-1)?.at||job.startedAt):paused?(job.updatedAt||Date.now()):Date.now();
      const seconds=Math.max(0,Math.floor((end-job.startedAt)/1000));
      panel.querySelector('[data-elapsed]').textContent=seconds<60?seconds+'s elapsed':Math.floor(seconds/60)+'m '+seconds%60+'s elapsed';
      box.querySelectorAll('.restart-stages li').forEach((li,index)=>{li.dataset.state=done||index<stage?'done':index===stage?'current':'waiting';if(index===stage&&!done)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');});
      panel.querySelector('[data-probes]').textContent=(Number.isInteger(job.probes)?job.probes+' status checks':'Saved restart outcome')+(job.lastProbeAt?' · Last check '+new Date(job.lastProbeAt).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':'')+(probing&&!done&&!failed?' · Checking now…':job.lastProbeResult?' · '+job.lastProbeResult:'');
    }
    function render(){
      const active=job&&ACTIVE.has(job.status);main.disabled=broker.disabled=select.disabled=!!active;
      check.hidden=!job||rejectedRestart(job)||!['UNKNOWN','FAILED'].includes(job.status);
      progress();
      const ticking=active&&job.status!=='UNKNOWN';
      if(ticking&&!heartbeat)heartbeat=setInterval(progress,1000);
      if(!ticking&&heartbeat){clearInterval(heartbeat);heartbeat=null;}
      if(!job)return;
      outcome.textContent=job.label+' · '+job.status+' · '+readable(job.message);
      history.replaceChildren(...(job.events||[]).map(e=>{const li=document.createElement('li');li.textContent=new Date(e.at).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata'})+' IST'+' · '+readable(e.message);return li;}));
    }
    function report(status,message){if(job.status!==status||job.message!==message){job.events=(job.events||[]).concat({at:Date.now(),message}).slice(-30);}job.stage=Math.max(job.stage||0,({SUBMITTING:0,SCHEDULED:1,CHECKING:1,RESTARTING:1,WAITING:2,READY:3,UNKNOWN:2}[status]||0));job.status=status;job.message=message;job.updatedAt=Date.now();if(['READY','FAILED','BLOCKED'].includes(status))job.completedAt=Date.now();save();}
    async function api(path,body){
      if(body&&!csrf){const me=await api('me');csrf=me.csrf;}
      const response=await fetch('/api/workspaces/'+path,{cache:'no-store',signal:AbortSignal.timeout(5000),...(body?{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)}:{})});
      const data=await response.json();if(!response.ok){const error=Error(data.error||'Service request failed');error.httpStatus=response.status;throw error;}return data;
    }
    function schedule(){clearTimeout(timer);timer=setTimeout(probe,2000);}
    async function probe(){
      if(!job||probing||rejectedRestart(job))return;probing=true;job.probes=(job.probes||0)+1;job.lastProbeAt=Date.now();save();
      try{
        const state=job.kind==='dashboard'?await api('service-restart-status'):await api('bounce-status',{account_id:job.account});
        const matches=job.kind==='dashboard'?state.request_id===job.id:state.started_at*1000>=job.startedAt-1000;
        if(matches){job.lastProbeResult=state.status==='READY'?'Service ready':'Service responded';report(state.status,state.message||state.status);if(!ACTIVE.has(state.status))return;}
        else report('WAITING','Waiting for this restart request to appear; no duplicate command will be sent.');
      }catch(error){job.lastProbeResult='No response; retrying';report('WAITING','Dashboard temporarily unreachable; probing again in two seconds.');}
      finally{probing=false;progress();}
      if(Date.now()>(job.deadlineAt||job.startedAt+180000)){report('UNKNOWN','Readiness is still unconfirmed after three minutes. No second restart was sent. Use Check restart status.');return;}
      schedule();
    }
    async function start(kind){
      if(job&&ACTIVE.has(job.status))return;
      const account=select.value;if(kind==='broker'&&!account){outcome.textContent='Select a broker worker first.';return;}
      job={id:crypto.randomUUID(),kind,account,startedAt:Date.now(),deadlineAt:Date.now()+180000,probes:0,status:'SUBMITTING',label:kind==='dashboard'?'Dashboard':select.selectedOptions[0].textContent,message:'Submitting restart request…',events:[]};save();
      try{
        const result=await api(kind==='dashboard'?'service-restart':'bounce',kind==='dashboard'?{request_id:job.id}:{account_id:account});
        job.accepted=true;report(result.status,result.message||result.status);
        if(!ACTIVE.has(result.status))return;
      }catch(error){
        if(error.httpStatus){job.submissionRejected=true;report('BLOCKED',error.message+' No restart was scheduled. Resolve the blocker, then submit a new restart.');return;}
        // A lost response can mean acceptance followed by shutdown. Never replay.
        report('WAITING','Submission outcome unconfirmed; checking status without sending another restart.');
      }
      schedule();
    }
    main.onclick=()=>start('dashboard');broker.onclick=()=>start('broker');check.onclick=()=>{if(rejectedRestart(job))return;job.deadlineAt=Date.now()+180000;report('WAITING','Checking the existing restart; no new restart requested.');probe();};
    api('restart-targets').then(data=>{select.replaceChildren(new Option('Select broker worker',''),...data.accounts.map(a=>new Option(a.label+' · '+a.broker+(a.running?'':' · stopped'),a.id)));}).catch(error=>{select.replaceChildren(new Option('Accounts unavailable',''));outcome.textContent=error.message;});
    render();if(job&&ACTIVE.has(job.status))probe();
    if(!job)api('service-restart-status').then(state=>{
      if(job||state.status==='IDLE'||!state.request_id)return;
      job={id:state.request_id,kind:'dashboard',label:'Dashboard',startedAt:state.started_at*1000,
        deadlineAt:Date.now()+180000,status:state.status,message:state.message,
        events:[{at:(state.completed_at||state.started_at)*1000,message:state.message}]};
      save();if(ACTIVE.has(job.status))probe();
    }).catch(()=>{});
  }
  if(typeof module!=='undefined')module.exports={rejectedRestart};
  if(typeof window!=='undefined')window.ServerRestarts={mount};
})();
