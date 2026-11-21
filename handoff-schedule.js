/* Owner-bound Handoff schedule settings. No activation on page load. */
(function(root){
'use strict';
function policyPayload(fields,account){
 if(!account?.id)throw Error('Choose your saved broker account.');
 const capital=Number(fields.capital);
 if(!Number.isFinite(capital)||capital<1||capital>100000)throw Error('Shared capital must be between ₹1 and ₹1,00,000.');
 if(!['MANUAL','AUTO'].includes(fields.mode))throw Error('Choose Manual or Auto.');
 return {account_id:account.id,enabled:fields.enabled===true,mode:fields.mode,capital,ai_provider:fields.ai_provider,cash_product:'CNC',live_authorized:fields.mode==='AUTO',amo:false,allow_duplicate_reports:fields.allow_duplicate_reports===true};
}
if(typeof module!=='undefined'&&module.exports){module.exports={policyPayload};return;}
if(new URLSearchParams(location.search).get('renkoBatchChart')==='1')return;
async function mount(){
 await root.BrokerForms?.ready;
 const section=document.getElementById('handoff');if(!section)return;
 if(!document.getElementById('handoff-schedule-layout')){const style=document.createElement('style');style.id='handoff-schedule-layout';style.textContent="#handoff .handoff-schedule{padding:clamp(18px,2vw,28px);min-width:0}#handoff .handoff-schedule h2{margin:4px 0 12px}#handoff .handoff-schedule p{line-height:1.6}#handoff .handoff-schedule .handoff-settings-grid{display:grid;grid-template-columns:minmax(230px,1.4fr) repeat(2,minmax(150px,1fr));gap:16px;margin:22px 0 16px;align-items:end}#handoff .handoff-schedule .handoff-settings-grid>.field{display:flex;flex-direction:column;gap:8px;min-width:0;margin:0}#handoff .handoff-schedule .handoff-settings-grid input,#handoff .handoff-schedule .handoff-settings-grid select{box-sizing:border-box;width:100%;min-width:0;min-height:44px}#handoff .handoff-schedule .handoff-report-options{display:flex;flex-wrap:wrap;gap:14px 24px;margin:16px 0 22px;padding:16px;border:1px solid #3b5068;border-radius:10px;background:#15243a}#handoff .handoff-schedule .handoff-report-options label{display:inline-flex;align-items:center;gap:9px;min-height:28px;margin:0;line-height:1.5}#handoff .handoff-schedule .handoff-report-options input{flex:0 0 auto;margin:0}#handoff .handoff-schedule .handoff-action-row{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:16px 0;min-width:0}#handoff .handoff-schedule .handoff-action-row>.button{flex:0 1 auto;margin:0;min-height:44px;max-width:100%;white-space:normal;line-height:1.35}#handoff .handoff-schedule [data-status]{padding:14px 16px;border-left:3px solid #7bbfb9;background:#17273a;border-radius:6px;overflow-wrap:anywhere}#handoff .handoff-schedule [data-manual]{margin-top:26px;padding-top:22px;border-top:1px solid #3b5068}#handoff .handoff-schedule [data-manual]>h3{margin:0 0 12px}#handoff .handoff-schedule [data-selection-note]{margin-bottom:18px}#handoff .handoff-schedule [data-opportunities]:empty{display:none}#handoff .handoff-schedule [data-review]{margin-top:22px;padding-top:18px;border-top:1px solid #3b5068}#handoff .handoff-schedule [data-review]>.field{margin:16px 0}#handoff .handoff-schedule .muted{font-size:13px;line-height:1.6}@media(max-width:760px){#handoff .handoff-schedule .handoff-settings-grid{grid-template-columns:repeat(2,minmax(0,1fr))}#handoff .handoff-schedule .handoff-settings-grid>.field:first-child{grid-column:1/-1}}@media(max-width:480px){#handoff .handoff-schedule .handoff-settings-grid{grid-template-columns:minmax(0,1fr)}#handoff .handoff-schedule .handoff-action-row>.button{flex:1 1 100%;width:100%}#handoff .handoff-schedule .handoff-report-options{flex-direction:column;align-items:flex-start}}";document.head.append(style);}
 const panel=document.createElement('section');panel.className='panel handoff-schedule';panel.setAttribute('aria-label','Analysis Handoff schedule');
 panel.innerHTML='<p class="label">SCHEDULE &amp; EXECUTION</p><h2>Analysis every 15 minutes</h2><p>Top-five high-conviction reports go to Sector Pulse Trade Alerts in both modes. Positions and P&amp;L remain private.</p><div class="handoff-settings-grid"><label class="field">Submission mode<select data-mode aria-label="Handoff submission mode"><option value="MANUAL">Manual — select and review orders</option><option value="AUTO" selected>Auto Submission — protected Live orders</option></select></label><label class="field">Candidate universe<select data-candidate-scope><option value="MERGED">Sector leaders + saved Screener</option><option value="SCREENER_EQUITY">Selected Screener cash equities only</option></select></label><label class="field">Shared capital (₹)<input data-capital aria-label="Handoff shared capital" type="number" min="1" max="100000" value="100000"></label><label class="field">Daily loss cutoff<input aria-label="Handoff daily loss cutoff" value="₹10,000" readonly></label></div><div class="handoff-report-options"><label><input data-enabled type="checkbox"> Schedule enabled</label><label><input data-duplicate-reports aria-label="Allow duplicate reports" type="checkbox"> Allow duplicate reports</label></div><p>Overnight/CNC first where valid; cash shorts remain Intraday. One bought option lot per stock first; the balance is shared equally across equities. Existing exposure is excluded. Enable duplicate reports to repeat unchanged findings each cycle. Duplicate orders are always blocked.</p><div class="handoff-action-row"><button type="button" class="button" data-save>Save schedule</button><button type="button" class="button secondary" data-pause>Pause schedule</button><button type="button" class="button secondary" data-refresh>Refresh status</button><button type="button" class="button secondary" data-diagnose>Diagnose current scan</button><button type="button" class="button secondary" data-resume-entries hidden>Resume new entries</button></div><p data-status role="status">Reading account schedule…</p><div data-diagnostic-details class="muted" aria-label="Read-only scan evidence"></div><p class="muted">After market: the enabled schedule waits for fresh analysis at the next trading-session open. Auto can then send regular protected orders; no broker AMO or old-price order is submitted. Dashboard logout or expiry does not stop an authorized schedule. New orders require a valid broker session and all safety checks. Pause schedule revokes its saved authorization.</p>';
 panel.insertAdjacentHTML('beforeend','<section data-manual><h3>Scheduled opportunities · highest conviction first</h3><p data-selection-note>No eligible scheduled recommendations yet.</p><div class="handoff-action-row"><button type="button" class="button" data-select-all>Select all eligible</button><button type="button" class="button secondary" data-clear>Clear selection</button></div><div data-opportunities></div><div class="handoff-action-row"><button type="button" class="button" data-prepare>Prepare selected Live tickets</button></div><section data-review hidden><h4>Exact Manual order review</h4><div data-preview style="overflow-x:auto"></div><label class="field">Type the exact confirmation shown above<input data-confirmation autocomplete="off"></label><button type="button" class="button" data-submit disabled>Submit reviewed Live tickets</button></section></section>');
 const context=section.querySelector('.handoff-analysis-context');if(context)context.after(panel);else section.querySelector('header').after(panel);
 const node=k=>panel.querySelector('[data-'+k+']'),status=node('status');
 let csrf='',revision=0,manualPreview=null,currentPolicy=null;
 const account=()=>root.BrokerForms?.account('handoff');
 async function api(payload,endpoint='handoff'){
  const aid=account()?.id;if(!aid)throw Error('Choose your saved broker account.');
  if(payload&&!csrf){const response=await root.fetch('/api/workspaces/me',{cache:'no-store'});const me=await response.json();if(!response.ok)throw Error(me.error||'Sign in again.');csrf=me.csrf;}
  const data=await new Promise((resolve,reject)=>{
   const xhr=new XMLHttpRequest();
   xhr.open(payload?'POST':'GET','/api/notification-admin/'+endpoint+(payload?'':'?account_id='+encodeURIComponent(aid)));
   xhr.timeout=10000;
   if(payload){xhr.setRequestHeader('Content-Type','application/json');xhr.setRequestHeader('X-CSRF-Token',csrf);}
   xhr.onload=()=>{let value;try{value=JSON.parse(xhr.responseText);}catch{reject(Error('The schedule settings service is not available yet.'));return;}
    if(xhr.status<200||xhr.status>=300)reject(Error(value.error||'Schedule unavailable.'));else resolve(value);};
   xhr.onerror=()=>reject(Error('Schedule settings connection failed.'));
   xhr.ontimeout=()=>reject(Error('Schedule settings timed out; refresh status before saving again.'));
   xhr.send(payload?JSON.stringify(payload):null);
  });
  return data;
 }
  const currency=value=>Number.isFinite(Number(value))?new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(Number(value)):'Unavailable';
 function renderManualPreview(data){
  const preview=node('preview');preview.replaceChildren();
  const summary=document.createElement('p');summary.textContent=(data.broker||'Selected account')+' · total planned capital '+currency(data.allocated);preview.append(summary);
  const table=document.createElement('table');table.style.width='100%';
  const header=table.createTHead().insertRow();
  for(const name of ['Instrument','Direction','Action','Quantity','Entry','Stop','Target']){const cell=document.createElement('th');cell.textContent=name;header.append(cell);}
  const body=table.createTBody();
  for(const item of data.items||[]){const row=body.insertRow();for(const value of [item.symbol,item.direction,item.action,item.quantity,currency(item.entry),currency(item.stop),currency(item.target)])row.insertCell().textContent=String(value??'Unavailable');}
  preview.append(table);
  for(const item of data.excluded||[]){const note=document.createElement('p');note.textContent='Excluded: '+item.symbol+' · '+item.reason;preview.append(note);}
  const phrase=document.createElement('p');phrase.textContent='Confirmation: ';const code=document.createElement('code');code.textContent=data.confirmation_phrase;phrase.append(code);preview.append(phrase);
  if(Number.isFinite(data.expires_at)){const expires=document.createElement('p');expires.textContent='Review expires at '+new Date(data.expires_at*1000).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit'})+' IST.';preview.append(expires);}
 }
 function invalidateManual(){manualPreview=null;node('review').hidden=true;node('confirmation').value='';node('submit').disabled=true;}
 function renderOpportunities(data){
  invalidateManual();currentPolicy=data.policy;node('opportunities').replaceChildren();
  const rows=data.recommendations||[];
  const scopes=(data.analysis_scopes||[]).map(r=>r.scope||{});
  const scanned=scopes.reduce((sum,s)=>sum+Number(s.scanned_stocks||0),0);
  const matched=scopes.reduce((sum,s)=>sum+Number(s.matched_stocks||0),0);

  node('selection-note').textContent=rows.length?rows.length+' eligible high-conviction recommendations. Selection does not submit orders.':'No eligible scheduled recommendations yet.';
  if(!rows.length&&scopes.length)node('selection-note').textContent='No eligible high-conviction recommendations. Across both route scans: '+scanned+' stocks examined, '+matched+' full-alignment matches. Existing exposure and execution eligibility are checked before selection. '+(data.policy.allow_duplicate_reports?'Duplicate reporting is allowed; duplicate orders remain blocked.':'Unchanged reports are suppressed.');
  for(const row of rows){
   const label=document.createElement('label');label.className='candidate-card '+String(row.direction||'').toLowerCase();
   const input=document.createElement('input');input.type='checkbox';input.value=row.fingerprint;input.checked=true;input.dataset.recommendation='1';
   input.disabled=data.policy.mode!=='MANUAL';input.onchange=invalidateManual;
   const text=document.createElement('span');const score=Number(row.score_fraction)*10;
   text.textContent=row.symbol+' · '+row.direction+' · '+(Number.isFinite(score)?score.toFixed(2)+'/10 evidence':'conviction unavailable')+' · entry '+row.entry+' · stop '+row.stop+' · target '+row.target;
   if(row.provenance?.length){const source=document.createElement('small');source.textContent='Sources: '+[...new Set(row.provenance.map(p=>p.label))].join(' + ');text.append(document.createElement('br'),source);}
   label.append(input,text);node('opportunities').append(label);
  }
  const disabled=!rows.length||data.policy.mode!=='MANUAL';
  for(const name of ['select-all','clear','prepare'])node(name).disabled=disabled;
 }
 function render(data){
  renderOpportunities(data);
  node('resume-entries').hidden=!data.policy.entries_halted;
  node('mode').value=data.policy.mode;node('capital').value=data.policy.capital;node('enabled').checked=data.policy.enabled;node('duplicate-reports').checked=data.policy.allow_duplicate_reports===true;
  node('candidate-scope').value=data.policy.candidate_scope||'MERGED';
  status.textContent=(data.policy.enabled?'Enabled':'Paused')+' · '+data.policy.mode+' · '+(data.session_bound?(data.authorization_basis==='BROKER_SESSION_AND_SAVED_OWNER_GRANT'?'saved Auto authorization active':'account session bound'):'save to authorize this schedule')+(data.latest?' · latest '+data.latest.state:' · no scheduled run yet')+((data.runtime_error||data.latest?.error)?' · '+(data.runtime_error||data.latest.error):'')+(data.allocation?.blocked?' · '+data.allocation.blocked:'')+(data.policy.entries_halted?' · new entries halted: '+(data.policy.halt_reason||'review required'):'')+(data.deferred?.state==='WAITING_FRESH_ANALYSIS'?' · waiting for next-open fresh analysis':'');
  if(data.allocation?.available!=null)status.textContent+=' · available for new entries '+currency(data.allocation.available);
  const diagnostic=data.diagnostic;
  if(diagnostic)status.textContent+=' · read-only scan '+diagnostic.state+(diagnostic.eligible!==undefined?' ('+diagnostic.eligible+' eligible)':'')+(diagnostic.error?' · '+diagnostic.error:'');
  node('diagnose').disabled=diagnostic?.state==='RUNNING';
  const evidence=node('diagnostic-details');evidence.replaceChildren();
  if(diagnostic?.state==='COMPLETED'){
   const lines=['Read-only check: '+diagnostic.eligible+' execution-eligible recommendations; no orders or shared posts sent.'];
   for(const row of diagnostic.analysis_scopes||[]){
    const scope=row.scope||{};lines.push(row.route+': '+Number(scope.eligible_sectors||0)+' eligible sectors, '+Number(scope.scanned_stocks||0)+' stocks scanned, '+Number(scope.matched_stocks||0)+' alignment matches.');
    for(const item of scope.sector_exclusions||[])if(String(item.alignment||'').includes('BEARISH'))lines.push(item.name+': '+item.alignment+' · '+item.reason);
   }
   for(const item of (diagnostic.exclusions||[]).slice(0,25))lines.push((item.symbol||item.name||item.kind||'Plan')+': '+item.reason);
   for(const text of lines){const line=document.createElement('p');line.textContent=text;evidence.append(line);}
  }

  node('mode').querySelector('option[value="AUTO"]').disabled=!data.automatic_broker_supported;
  if(!data.automatic_broker_supported)status.textContent+=' · protected Auto integration pending for this broker';
 }
 async function refresh(){const ticket=++revision;try{const data=await api();if(ticket===revision)render(data);}catch(error){if(ticket===revision)status.textContent=error.message;}}
 async function save(pause=false){
  const ticket=++revision;node('save').disabled=true;node('pause').disabled=true;
  try{
   const data=await api({...policyPayload({capital:node('capital').value,enabled:pause?false:node('enabled').checked,allow_duplicate_reports:node('duplicate-reports').checked,mode:node('mode').value,ai_provider:root.HandoffAIProvider?.selected()||'RULES_ONLY'},account()),candidate_scope:node('candidate-scope').value});
   if(ticket===revision)render(data);
  }catch(error){if(ticket===revision)status.textContent=error.message;}
  finally{node('save').disabled=false;node('pause').disabled=false;}
 }
 node('select-all').onclick=()=>{invalidateManual();for(const input of panel.querySelectorAll('[data-recommendation]:not(:disabled)'))input.checked=true;};
 node('clear').onclick=()=>{invalidateManual();for(const input of panel.querySelectorAll('[data-recommendation]'))input.checked=false;};
 node('prepare').onclick=async()=>{
  const ticket=++revision;invalidateManual();node('prepare').disabled=true;
  try{
   const selected=[...panel.querySelectorAll('[data-recommendation]:checked:not(:disabled)')].map(n=>n.value);
   if(!selected.length)throw Error('Select at least one eligible recommendation.');
   const data=await api({account_id:account()?.id,selected},'handoff-prepare');
   if(ticket!==revision)return;
   manualPreview=data;renderManualPreview(data);node('review').hidden=false;
   status.textContent='Review exact contract, quantity, entry, stop and target. Nothing has been submitted.';
  }catch(error){if(ticket===revision)status.textContent=error.message;}
  finally{node('prepare').disabled=currentPolicy?.mode!=='MANUAL';}
 };
 node('confirmation').oninput=()=>{node('submit').disabled=!(manualPreview?.live_submission_enabled&&node('confirmation').value===manualPreview.confirmation_phrase);};
 node('submit').onclick=async()=>{
  if(!manualPreview)return;const preview=manualPreview,ticket=++revision;node('submit').disabled=true;
  try{
   const result=await api({account_id:account()?.id,preview_id:preview.preview_id,confirmation:node('confirmation').value},'handoff-submit');
   if(ticket!==revision)return;
   invalidateManual();status.textContent=result.status+' · '+result.results.length+' submitted · '+result.unsubmitted+' unsubmitted. Confirmed fills use your private notification route.';
  }catch(error){if(ticket===revision){invalidateManual();status.textContent=error.message;}}
 };
 node('diagnose').onclick=async()=>{
  node('diagnose').disabled=true;
  try{await api({account_id:account()?.id},'handoff-diagnose');await refresh();}
  catch(error){status.textContent=error.message;}
  finally{node('diagnose').disabled=false;}
 };
 node('mode').onchange=invalidateManual;
 node('resume-entries').onclick=async()=>{
  try{const data=await api({account_id:account()?.id,resume_entries:true});render(data);}
  catch(error){status.textContent=error.message;}
 };
 node('save').onclick=()=>save();node('pause').onclick=()=>save(true);node('refresh').onclick=refresh;
 root.addEventListener('broker-account-change',event=>{if(['handoff','manual'].includes(event.detail?.kind)){csrf='';void refresh();}});
 await refresh();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})(typeof window==='undefined'?globalThis:window);

/* Shared reporting controls inside existing permission-governed report headers. */
(function(root){
'use strict';
function reportDeliveryText(data){
 if(data.global_paused)return 'Global Telegram pause is on. Your report preference is saved; global pause still blocks delivery.';
 if(!data.configured_enabled)return 'Reports paused. Resume sends new reports only; older updates are not replayed.';
 if(!data.service_running)return 'Reports enabled, but the reporting service is unavailable. Save enabled settings to retry.';
 if(!data.refresh_interval_ms)return 'Reports on · every '+(data.interval_minutes || 15)+' minutes during NSE market hours. Interval synchronization awaits service activation.';
 const ms=data.refresh_interval_ms;
 return 'Reports on · every '+(ms<60000 ? ms/1000+' seconds' : ms/60000+' minutes')+' during NSE market hours · follows Sector Rotation.';
}
if(typeof module!=='undefined'&&module.exports){module.exports.reportDeliveryText=reportDeliveryText;return;}
if(new URLSearchParams(location.search).get('renkoBatchChart')==='1')return;
async function mount(){
 await root.BrokerForms?.ready;
 const panels=[];let csrf='';
 function request(section,payload){return new Promise(async(resolve,reject)=>{
  try{
   if(payload&&!csrf){const r=await root.fetch('/api/workspaces/me',{cache:'no-store'});const v=await r.json();if(!r.ok)throw Error('Sign in again to save report settings.');csrf=v.csrf;}
   const xhr=new root.XMLHttpRequest();xhr.open(payload?'POST':'GET','/api/notification-admin/reports'+(payload?'':'?section='+encodeURIComponent(section)));xhr.timeout=60000;
   if(payload){xhr.setRequestHeader('Content-Type','application/json');xhr.setRequestHeader('X-CSRF-Token',csrf);}
   xhr.onload=()=>{let d;try{d=JSON.parse(xhr.responseText);}catch{reject(Error('Report settings unavailable. Refresh to retry.'));return;}if(xhr.status<200||xhr.status>=300){const e=Error(d.error||'Report settings unavailable.');e.status=xhr.status;reject(e);}else resolve(d);};
   xhr.onerror=()=>reject(Error('Connection failed. Refresh status before saving again.'));xhr.ontimeout=()=>reject(Error('Save outcome unconfirmed. Refresh status before trying again.'));xhr.send(payload?JSON.stringify(payload):null);
  }catch(e){reject(e);}
 });}
 root.addEventListener('sector-rotation-interval-change',async event=>{
  const control=document.getElementById('analysis-refresh-interval');
  try{
   if(control)control.disabled=true;
   const data=await request('sectors',{section:'sectors',refresh_interval_ms:event.detail});
   for(const p of panels)render(p,data);
  }catch(error){const saved=panels.find(p=>p.section==='sectors')?.data?.refresh_interval_ms; if(saved)root.dispatchEvent(new CustomEvent('sector-rotation-interval-loaded',{detail:saved})); for(const p of panels)p.status.textContent='Telegram interval was not saved: '+error.message;}
  finally{if(control)control.disabled=false;}
 });
 function render(p,data){
  if(p.section==='sectors')root.dispatchEvent(new CustomEvent('sector-rotation-interval-loaded',{detail:data.refresh_interval_ms || 900000}));
  p.data=data;if(!p.dirty)p.input.checked=data.configured_enabled;
  p.badge.textContent=data.enabled?'On':data.configured_enabled?'Held':'Paused';p.badge.dataset.on=String(data.enabled);
  p.destination.textContent=data.destination+' · Sector rotation + Analysis Handoff';
  p.status.textContent=reportDeliveryText(data)+(data.last_delivery_at?' Last report sent: '+new Date(data.last_delivery_at*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',maximumFractionDigits:0})+' IST.':'');
 }
 const style=document.createElement('style');style.textContent='.head.report-delivery-host{flex-wrap:wrap}.report-delivery-control{width:100%;flex:1 0 100%;min-width:0;box-sizing:border-box;display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px 20px;border-top:1px solid var(--border,#3b5068);padding-top:16px;margin-top:16px}.report-delivery-control strong{font-size:14px}.report-delivery-control p{margin:5px 0 0;font-size:12px;line-height:1.6;color:var(--muted,#a6b8ce);overflow-wrap:anywhere}.report-delivery-actions{display:flex;align-items:center;flex-wrap:wrap;gap:10px}.report-delivery-actions label{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;font-size:13px}.report-delivery-actions input{width:17px;height:17px;margin:0;accent-color:#7bbfb9}.report-delivery-actions button{min-height:40px;margin:0;white-space:normal}.report-delivery-badge{display:inline-block;margin-left:10px;padding:3px 9px;border:1px solid #4a5d73;border-radius:6px;font-size:11px;color:#c7d5e5}.report-delivery-badge[data-on="true"]{border-color:#377c71;color:#99ddd0;background:#16362f}.report-delivery-control [role="status"]{grid-column:1/-1;margin:0;border-left:2px solid #7bbfb9;padding-left:10px}.report-delivery-actions button:focus-visible,.report-delivery-actions input:focus-visible{outline:2px solid #91c8ff;outline-offset:3px}@media(max-width:700px){.report-delivery-control{grid-template-columns:minmax(0,1fr)}.report-delivery-actions{justify-content:flex-start}.report-delivery-actions button{flex:1 1 auto}}';document.head.append(style);
 for(const section of ['sectors','handoff']){
  const parent=document.getElementById(section),header=parent?.querySelector(':scope > header.head');if(!header)continue;
  let data;try{data=await request(section);}catch{continue;}
  const bar=document.createElement('div');bar.className='report-delivery-control';bar.setAttribute('aria-label','Telegram analysis report settings');
  bar.innerHTML='<div><strong>Telegram reports</strong><span class="report-delivery-badge" data-badge></span><p data-destination></p></div><div class="report-delivery-actions"><label><input type="checkbox" aria-label="Enable sector and Handoff Telegram reports">Enable reports</label><button type="button" class="button" data-save>Save report settings</button><button type="button" class="button secondary" data-refresh>Refresh status</button></div><p role="status" data-status></p>';
  const p={bar,section,input:bar.querySelector('input'),badge:bar.querySelector('[data-badge]'),destination:bar.querySelector('[data-destination]'),status:bar.querySelector('[data-status]'),save:bar.querySelector('[data-save]'),refresh:bar.querySelector('[data-refresh]'),dirty:false};
  p.input.onchange=()=>{p.dirty=true;p.status.textContent='Unsaved report preference. Select Save report settings to apply.';};
  p.save.onclick=async()=>{for(const x of panels){x.save.disabled=true;x.input.disabled=true;}p.status.textContent='Saving report settings…';try{const d=await request(section,{section,enabled:p.input.checked});for(const x of panels){x.dirty=false;render(x,d);}}catch(e){p.status.textContent=e.message;}finally{for(const x of panels){x.save.disabled=false;x.input.disabled=false;}}};
  p.refresh.onclick=async()=>{p.refresh.disabled=true;try{p.dirty=false;render(p,await request(section));}catch(e){p.status.textContent=e.message;}finally{p.refresh.disabled=false;}};
  header.classList.add('report-delivery-host');header.append(bar);p.section=section;panels.push(p);render(p,data);
 }
 root.addEventListener('focus',()=>{for(const p of panels)if(!p.dirty)request(p.section).then(d=>render(p,d)).catch(()=>{});});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{void mount();});else void mount();
})(typeof window==='undefined'?globalThis:window);
