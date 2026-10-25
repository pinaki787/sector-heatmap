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
 panel.innerHTML='<p class="label">SCHEDULE &amp; EXECUTION</p><h2>Analysis every 15 minutes</h2><p>Top-five high-conviction reports go to Sector Pulse Trade Alerts in both modes. Positions and P&amp;L remain private.</p><div class="handoff-settings-grid"><label class="field">Submission mode<select data-mode aria-label="Handoff submission mode"><option value="MANUAL">Manual — select and review orders</option><option value="AUTO">Auto — submit protected Live orders</option></select></label><label class="field">Shared capital (₹)<input data-capital aria-label="Handoff shared capital" type="number" min="1" max="100000" value="100000"></label><label class="field">Daily loss cutoff<input aria-label="Handoff daily loss cutoff" value="₹10,000" readonly></label></div><div class="handoff-report-options"><label><input data-enabled type="checkbox"> Schedule enabled</label><label><input data-duplicate-reports aria-label="Allow duplicate reports" type="checkbox"> Allow duplicate reports</label></div><p>Overnight/CNC first where valid; cash shorts remain Intraday. One bought option lot per stock first; the balance is shared equally across equities. Existing exposure is excluded. Enable duplicate reports to repeat unchanged findings each cycle. Duplicate orders are always blocked.</p><div class="handoff-action-row"><button type="button" class="button" data-save>Save schedule</button><button type="button" class="button secondary" data-pause>Pause schedule</button><button type="button" class="button secondary" data-refresh>Refresh status</button><button type="button" class="button secondary" data-diagnose>Diagnose current scan</button><button type="button" class="button secondary" data-resume-entries hidden>Resume new entries</button></div><p data-status role="status">Reading account schedule…</p><div data-diagnostic-details class="muted" aria-label="Read-only scan evidence"></div><p class="muted">After market: the enabled schedule waits for fresh analysis at the next trading-session open. Auto can then send regular protected orders; no broker AMO or old-price order is submitted. Dashboard logout or expiry does not stop an authorized schedule. New orders require a valid broker session and all safety checks. Pause schedule revokes its saved authorization.</p>';
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
   const data=await api(policyPayload({capital:node('capital').value,enabled:pause?false:node('enabled').checked,allow_duplicate_reports:node('duplicate-reports').checked,mode:node('mode').value,ai_provider:root.HandoffAIProvider?.selected()||'RULES_ONLY'},account()));
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
