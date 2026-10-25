/* Explicit enablement UI for account-owned protective-stop monitoring. */
(() => {
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const brokerName=b=>({DHAN:'Dhan',FYERS:'FYERS',MOTILAL_OSWAL:'Motilal Oswal',DELTA_INDIA:'Delta India'}[b]||b);
const num=v=>v==null?'—':new Intl.NumberFormat('en-IN',{maximumFractionDigits:2}).format(v);
const money=(v,c='INR')=>(c==='INR'?'₹':c+' ')+num(v);
const stamp=v=>v?new Date(v*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',hour12:true}):'—';
let dialog=null,poll=null,active=null,preview=null;const cache=new Map();
const style=document.createElement('style');style.textContent=`
.holding-trail-dialog{width:min(850px,94vw)}.holding-trail-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:20px 0}
.holding-trail-summary>div{background:#15283e;border:1px solid #2f475f;border-radius:8px;padding:15px}
.holding-trail-summary small{display:block;color:#9fb4c9;margin-bottom:8px}.holding-trail-summary strong{display:block;font-size:17px;font-variant-numeric:tabular-nums}
.holding-trail-meta{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:18px 0;color:#b6cadd;font-size:13px}
.holding-trail-review{border-top:1px solid #324b65;margin-top:20px;padding-top:20px}
.holding-trail-dialog .trail-buttons{display:flex;gap:12px;justify-content:flex-end;margin-top:18px;flex-wrap:wrap}
.holding-trail-dialog .trail-status{padding:12px 15px;background:#0a1829;border:1px solid #30465c;border-radius:7px}
.holding-trail-dialog .trail-stop{background:transparent;border:1px solid #ad7e7f;color:#ffd3d1}
.holding-trail-note{font-size:11px;color:#a7bdd0;text-align:center;line-height:1.4}
.holding-trail-active{color:#83d8b0!important;border-color:#4c8c73!important}
@media(max-width:650px){.holding-trail-summary{grid-template-columns:1fr}.holding-trail-meta{grid-template-columns:1fr}}
`;document.head.append(style);
async function call(source,action,payload={}){
 const headers={'Content-Type':'application/json'};if(window.SectorPulseWorkspace?.csrf)headers['X-CSRF-Token']=window.SectorPulseWorkspace.csrf;
 const options={method:'POST',headers,body:JSON.stringify({...payload,broker:source.broker,account_id:source.accountId})};
 const response=await (source.fetch?source.fetch('/api/holdings-analysis/'+action,options):window.BrokerForms.fetch('holdings','/api/holdings-analysis/'+action,options));
 const result=await response.json();if(!response.ok)throw Error(result.error||'Trailing request failed.');
 return result;
}
async function status(source,force=false){
 const key=source.accountId,cached=cache.get(key);
 if(!force&&cached&&Date.now()-cached.at<10000)return cached.promise;
 const promise=call(source,'trail-status');cache.set(key,{at:Date.now(),promise});return promise;
}
function matches(row,m){return m.security_id===String(row.native_identity?.securityId)&&m.exchange_segment===row.native_identity?.exchangeSegment;}
function paint(state){
 const stop=state?.managed_stop?.ticket;
 dialog.querySelector('[data-monitor-state]').textContent=state?.status?.replaceAll('_',' ')||'Off';
 dialog.querySelector('[data-monitor-stop]').textContent=stop?money(stop.triggerPrice,state.currency||active?.row.currency||'INR'):'Not set by this monitor';
 dialog.querySelector('[data-monitor-qty]').textContent=state?num(Math.abs(state.quantity))+(state.broker==='DELTA_INDIA'?' contracts':' shares'):'—';
 dialog.querySelector('[data-last-check]').textContent=stamp(state?.last_checked_at);
 dialog.querySelector('[data-next-check]').textContent=stamp(state?.next_check_at);
 dialog.querySelector('[data-heartbeat]').textContent=state?.status==='SLEEPING'?'Sleeping · resumes at session open':stamp(state?.heartbeat_at);
 dialog.querySelector('[data-monitor-message]').textContent=state?.message||'Automatic trailing is off. No order is placed until you review and explicitly enable it.';
 const running=!!state?.running;
 dialog.querySelector('[data-stop-trail]').hidden=!running;
 dialog.querySelector('[data-trail-preview]').disabled=running||active?.row.action!=='TRAIL';
 dialog.querySelector('[data-interval]').disabled=false;
 dialog.querySelector('[data-save-interval]').hidden=!running;
 if(state?.interval_minutes&&running&&!dialog.querySelector('[data-interval]').dataset.dirty)dialog.querySelector('[data-interval]').value=String(state.interval_minutes);
}
async function refresh(force=true){
 if(!active||!dialog?.open)return;
 const captured=active;
 try{
  const data=await status(captured.source,force);
  if(active!==captured)return;
  const records=data.monitors.filter(m=>matches(captured.row,m));
  captured.monitor=records[0]||null;paint(captured.monitor);
 }catch(error){if(active===captured)dialog.querySelector('[data-monitor-message]').textContent=error.message;}
}
async function open(row,source){
 clearTimeout(poll);preview=null;
 if(!dialog){
  dialog=document.createElement('dialog');dialog.className='holding-dialog holding-trail-dialog';dialog.id='holding-trailing-dialog';document.body.append(dialog);
  dialog.addEventListener('close',()=>{clearTimeout(poll);active=null;preview=null;});
 }
 active={row,source,monitor:null};
 dialog.setAttribute('aria-label','Automatic trailing for '+row.symbol);
 dialog.innerHTML=`<header><div><span class="label">PROTECTIVE STOP MONITOR</span><h2>Automatic trailing · ${esc(row.symbol)}</h2></div><button class="button" data-close>Close</button></header>
 <p>${source.broker==='DELTA_INDIA'?'Delta India crypto monitoring runs 24 hours a day, including weekends. Long stops rise and short stops fall; neither is loosened.':'NSE/BSE equity checks run only from <b>9:15 a.m. to 3:30 p.m. IST</b> on exchange trading days. Outside the session, the worker sleeps until the next opening without broker polling or recalculation. The broker stop stays active between checks. At your selected interval, recalculate the completed-daily recommendation and raise the stop only when the new level is higher. This does not execute other recommendations such as “Exit”.'}${source.broker==='DELTA_INDIA'?' Recalculate from completed UTC daily candles. Reduce-only stop-limit protection cannot add reverse exposure.':''}</p>
 <div class="holding-trail-summary"><div><small>Monitor status</small><strong data-monitor-state>Checking…</strong></div><div><small>Broker stop trigger</small><strong data-monitor-stop>—</strong></div><div><small>Protected quantity</small><strong data-monitor-qty>—</strong></div></div>
 <div class="holding-trail-meta"><span>Last review: <b data-last-check>—</b></span><span>Next check: <b data-next-check>—</b></span><span>Last heartbeat: <b data-heartbeat>—</b></span><span>Broker: <b>${esc(brokerName(source.broker))} · ${esc(row.holding_type)}</b></span></div>
 <p class="trail-status" data-monitor-message role="status">Reading saved monitor status…</p>
 <div class="trail-buttons"><button class="button trail-stop" data-stop-trail hidden>Stop monitoring</button></div>
 <section class="holding-trail-review"><label class="field">Checking interval<select data-interval><option value="60" selected>Every 1 hour</option><option value="30">Every 30 minutes</option></select></label><button class="button" data-save-interval hidden>Update interval</button>
 <p>Initial recommended stop: <b>${esc(money(row.candidate_stop,row.currency))}</b> · ${num(Math.abs(row.quantity))} ${source.broker==='DELTA_INDIA'?'contracts':'shares'}. Levels use completed daily candles, so they may remain unchanged during the session. Monitoring continues when you leave the page, within the applicable exchange session. A server interruption requires explicit enablement again.</p>
 <p>Stopping monitoring keeps the last broker stop in place. It does not cancel protection or sell the holding.</p>
 <div class="trail-buttons"><button class="button" data-trail-preview>Review enablement</button></div>
 <div data-trail-plan hidden></div><p role="status" data-enable-message>Off by default. Review is read-only.</p></section>`;
 dialog.querySelector('[data-close]').onclick=()=>dialog.close();
 dialog.querySelector('[data-interval]').onchange=()=>{dialog.querySelector('[data-interval]').dataset.dirty='1';preview=null;dialog.querySelector('[data-trail-plan]').hidden=true;dialog.querySelector('[data-enable-message]').textContent='Interval changed. Review enablement again.';};
 dialog.querySelector('[data-save-interval]').onclick=async()=>{
  const captured=active;if(!captured?.monitor?.running)return;
  const button=dialog.querySelector('[data-save-interval]');button.disabled=true;
  try{
   await call(source,'trail-interval',{monitor_id:captured.monitor.monitor_id,interval_minutes:Number(dialog.querySelector('[data-interval]').value)});
   delete dialog.querySelector('[data-interval]').dataset.dirty;
   dialog.querySelector('[data-enable-message]').textContent='Interval updated. The monitor continues without restarting.';
   await refresh();
  }catch(error){dialog.querySelector('[data-enable-message]').textContent=error.message;}
  finally{button.disabled=false;}
 };
 dialog.querySelector('[data-stop-trail]').onclick=async()=>{
  const captured=active;if(!captured?.monitor)return;
  const button=dialog.querySelector('[data-stop-trail]');button.disabled=true;
  try{await call(source,'trail-stop',{monitor_id:captured.monitor.monitor_id});await refresh();}
  catch(error){dialog.querySelector('[data-monitor-message]').textContent=error.message;}
  finally{button.disabled=false;}
 };
 dialog.querySelector('[data-trail-preview]').onclick=async()=>{
  const captured=active,button=dialog.querySelector('[data-trail-preview]'),message=dialog.querySelector('[data-enable-message]'),plan=dialog.querySelector('[data-trail-plan]');
  button.disabled=true;plan.hidden=true;preview=null;
  try{
   if(!source.job?.job_id)throw Error('Run a fresh completed portfolio review first.');
   message.textContent='Checking current holdings, exact stop ownership and broker protection…';
   const value=await call(source,'trail-preview',{job_id:source.job.job_id,row_id:row.id,interval_minutes:Number(dialog.querySelector('[data-interval]').value)});
   if(active!==captured||!dialog.open)return;
   preview=value;const t=value.ticket;
   plan.innerHTML=`<h3>Review automatic broker actions</h3><pre>${esc(row.symbol)} · ${esc(t.transactionType)} stop for ${num(t.quantity)} ${esc(t.productType)} ${source.broker==='DELTA_INDIA'?'contracts':'shares'}\n${value.existing_stop?'Use the verified existing broker stop':value.description||'Create the initial native broker stop'}\nInitial trigger ${esc(money(t.triggerPrice,row.currency))} · ${esc(t.transactionType)} limit ${esc(money(t.price,row.currency))}\nCheck every ${value.interval_minutes} minutes · tighten only\nFuture updates remain LIMIT stops, with the same 0.5% trigger-to-limit buffer.\n${esc(value.policy)}</pre>
    <p>A trigger does not guarantee a fill. Broker/data uncertainty, external stop edits or changed holdings pause monitoring for review, without an automatic order retry.</p>
    <label class="live-consent"><input type="checkbox" data-auto-consent> I authorize the initial broker stop and automatic stop tightening for this exact holding and quantity at the selected interval. Never loosen the stop.</label>
    <label class="field">Type ${esc(value.confirmation_phrase)}<input data-auto-phrase autocomplete="off"></label>
    <div class="trail-buttons"><button class="button" data-enable-trail disabled>Enable automatic trailing</button></div>`;
   plan.hidden=false;message.textContent=value.live_submission_enabled?'Preview ready. No order or monitor has been started.':'Live capability is disabled. Preview only.';
   const enable=plan.querySelector('[data-enable-trail]');
   const update=()=>{enable.disabled=!value.live_submission_enabled||!plan.querySelector('[data-auto-consent]').checked||plan.querySelector('[data-auto-phrase]').value!==value.confirmation_phrase;};
   plan.querySelector('[data-auto-consent]').onchange=update;plan.querySelector('[data-auto-phrase]').oninput=update;
   enable.onclick=async()=>{
    if(preview!==value||active!==captured)return;
    preview=null;enable.disabled=true;button.disabled=true;plan.querySelectorAll('input').forEach(n=>n.disabled=true);
    message.textContent='Enabling the explicitly reviewed monitor once…';
    try{
     const result=await call(source,'trail-enable',{preview_id:value.preview_id,confirmation:plan.querySelector('[data-auto-phrase]').value,automatic_order_consent:true});
     message.textContent=result.message;plan.hidden=true;cache.delete(source.accountId);await refresh();
    }catch(error){message.textContent=error.message+' Check the saved monitor and broker orders before another enablement. No automatic retry.';}
   };
  }catch(error){message.textContent=error.message+' No order or monitor was started by this preview.';}
  finally{if(active===captured)button.disabled=!!captured.monitor?.running;}
 };
 dialog.showModal();await refresh();
 const tick=async()=>{await refresh();if(dialog.open&&active)poll=setTimeout(tick,15000);};poll=setTimeout(tick,15000);
}
window.HoldingsTrailing={open,decorate(button,row,source){
 button.onclick=()=>open(row,source);
 status(source).then(data=>{
  const state=data.monitors.find(m=>matches(row,m)&&m.running);
  if(state){button.textContent='Trailing active';button.classList.add('holding-trail-active');button.title=state.status+' · every '+state.interval_minutes+' minutes';}
 }).catch(()=>{button.title='Open to inspect the current monitor status.';});
}};
window.addEventListener('broker-account-change',event=>{if(event.detail?.kind==='holdings'){dialog?.close();cache.clear();}});
window.addEventListener('protection-account-change',event=>{if(active?.source?.origin===event.detail?.origin){dialog?.close();cache.clear();}});
})();
