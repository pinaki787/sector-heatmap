/* Account-owned Screener inclusion. Rendering never changes a saved selection. */
(function(root){'use strict';async function mount(){await root.BrokerForms?.ready;let current=null,busy=false;
 const api='/api/analysis-handoff/screener-selection';
 const style=document.createElement('style');style.textContent='.handoff-screener-panel{min-width:0}.handoff-screener-toolbar{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}.handoff-screener-options{display:flex;flex-wrap:wrap;gap:18px}.handoff-screener-status{line-height:1.65;overflow-wrap:anywhere}.handoff-screener-panel ul{padding-left:20px}.handoff-screener-panel button{min-height:40px}@media(max-width:640px){.handoff-screener-toolbar button{flex:1 1 100%}.handoff-screener-options{flex-direction:column}}';document.head.append(style);
 const handoff=document.getElementById('handoff'),screen=document.getElementById('screener');if(!handoff||!screen)return;
 const hp=document.createElement('section');hp.className='panel handoff-screener-panel';hp.setAttribute('aria-label','Handoff candidate sources');hp.innerHTML='<span class="label">MERGED CANDIDATE SOURCES</span><h2>Sector leaders + Screener selection</h2><p class="handoff-screener-status" role="status" data-status>Reading saved source selection…</p><div class="handoff-screener-options"><label><input type="checkbox" data-enabled> Include saved Screener selection in analysis</label><label><input type="checkbox" data-auto> Eligible for authorized Auto Live</label></div><div class="handoff-screener-toolbar"><button type="button" class="button secondary" data-save>Save source inclusion</button><button type="button" class="button secondary" data-refresh>Refresh source status</button><button type="button" class="button secondary" data-review>Review merged evidence</button></div><ul data-sources></ul><p class="muted">Highest normalized conviction score first, then recorded source rank. Duplicate underlyings merge their source labels. Fresh source membership, completed broker candles, exposure, funds, shared capital, loss cutoff and protection gates still apply. Inclusion never submits an order by itself. Existing broker orders and exits keep their current management.</p>';
 const schedule=handoff.querySelector('.handoff-schedule');if(schedule)schedule.insertAdjacentElement('afterend',hp);else handoff.prepend(hp);
 const sp=document.createElement('section');sp.className='panel handoff-screener-panel';sp.setAttribute('aria-label','Screener to Handoff selection');sp.innerHTML='<span class="label">ANALYSIS HANDOFF INTEGRATION</span><h2>Use selected Screener symbols</h2><p data-state role="status">Reading the saved Handoff source selection…</p><div class="handoff-screener-toolbar"><button type="button" class="button secondary" data-use>Use selected analysis symbols in Handoff</button><button type="button" class="button secondary" data-clear>Remove Screener selection from Handoff</button></div><p class="muted">Select symbols in the source results first. Saving replaces only the Handoff Screener selection for this selected broker account. New or edited local sources are not silently included. Names assigned to enabled Handoff Auto cannot also submit through a separate Screener batch; use Handoff or remove that ownership first.</p>';
 sp.insertAdjacentHTML('beforeend','<div class="field-grid" style="margin-top:18px"><label class="field">Allotted funds (₹)<input data-auto-capital type="number" min="1" max="100000" step="100" placeholder="Enter total funds"></label></div><div class="handoff-screener-toolbar"><button type="button" class="button" data-start-auto disabled>Enable Auto · top 5 stocks</button><button type="button" class="button secondary" data-pause-auto>Pause Auto</button><button type="button" class="button secondary" data-auto-status>Refresh Auto status</button></div><p class="muted">Auto uses the selected FYERS account and the shared Handoff schedule every 15 minutes. All source symbols are initially selected; deselect any exclusions before enabling. Every selected current source member is examined before ranking up to five high-conviction cash equities by normalized score, then source rank. Available allotted funds are shared equally, rounded down to whole shares. Fewer qualifying stocks means fewer orders; unspent cash stays available. Fresh broker funds, existing exposure, duplicate, daily-loss and protected-exit checks apply. Enabling authorizes future Live orders and replaces the account’s Handoff candidate scope. No options are included.</p><p data-auto-state class="handoff-screener-status" role="status">Auto status has not been loaded.</p>');
 let autoBusy=false,autoSupported=false;
 const autoState=sp.querySelector('[data-auto-state]');
 async function scheduleRequest(body){
  const a=root.BrokerForms.account('screener');
  if(a?.broker!=='FYERS')throw Error('Screener Auto requires the selected owned FYERS account.');
  // Shared settings belong to the portal, outside the account-workspace fetch rewrite.
  // Match the Handoff schedule transport; never retry a settings mutation.
  return new Promise((resolve,reject)=>{
   const xhr=new root.XMLHttpRequest();
   xhr.open(body?'POST':'GET','/api/notification-admin/handoff'+(body?'':'?account_id='+encodeURIComponent(a.id)));
   xhr.timeout=10000;
   xhr.setRequestHeader('Accept','application/json');
   if(body){xhr.setRequestHeader('Content-Type','application/json');xhr.setRequestHeader('X-CSRF-Token',csrf());}
   xhr.onload=()=>{
    let value;try{value=JSON.parse(xhr.responseText);}catch{reject(Error('Auto settings service returned an unexpected response. Refresh status before changing Auto settings.'));return;}
    if(xhr.status<200||xhr.status>=300){reject(Error(value.error||'Auto settings unavailable.'));return;}
    if(!value||typeof value!=='object'||Array.isArray(value)){reject(Error('Auto settings response is unavailable. Refresh status before changing Auto settings.'));return;}
    resolve(value);
   };
   xhr.onerror=()=>reject(Error('Auto settings connection failed. Refresh status before changing Auto settings.'));
   xhr.ontimeout=()=>reject(Error('Auto settings request timed out. Refresh status before changing Auto settings.'));
   xhr.send(body?JSON.stringify({...body,account_id:a.id}):null);
  });
 }
 function showAuto(value){
  const p=value.policy||{};
  const supported=(value.supported_candidate_scopes||[]).includes('SCREENER_EQUITY');autoSupported=supported;
  sp.querySelector('[data-start-auto]').disabled=!supported||autoBusy;
  autoState.textContent=(p.enabled?'Enabled':'Paused')+' · '+p.mode+' · '+(p.candidate_scope==='SCREENER_EQUITY'?'Screener equities only':'Merged Handoff candidates')+' · allotted ₹'+Number(p.capital||0).toLocaleString('en-IN',{maximumFractionDigits:2})+' · '+(value.activation||'status unavailable')+(value.latest?' · '+value.latest.state:'')+(value.latest?.error?' · '+value.latest.error:'');
  if(!supported)autoState.textContent+=' · Auto activation pending server update';
  if(!sp.querySelector('[data-auto-capital]').matches(':focus'))sp.querySelector('[data-auto-capital]').value=p.capital||'';
 }
 async function refreshAuto(){try{showAuto(await scheduleRequest());}catch(e){autoState.textContent=e.message;}}
 sp.querySelector('[data-start-auto]').onclick=()=>{if(autoBusy)return;root.dispatchEvent(new CustomEvent('sector-pulse-screener-selection-request',{detail:{action:'ENABLE_SCREENER_AUTO'}}));};
 sp.querySelector('[data-pause-auto]').onclick=async()=>{try{showAuto(await scheduleRequest({enabled:false}));}catch(e){autoState.textContent=e.message;}};
 sp.querySelector('[data-auto-status]').onclick=refreshAuto;
 const board=screen.querySelector('#screener-analysis');if(board)board.before(sp);else screen.append(sp);
 function scopeScreener(){sp.hidden=!['FYERS','DHAN'].includes(root.BrokerForms.account('screener')?.broker);}
 scopeScreener();root.addEventListener('broker-accounts-ready',scopeScreener);root.addEventListener('broker-account-change',()=>{scopeScreener();void refreshAuto();});
 function csrf(){return root.BrokerForms.context?.()?.csrf||root.SectorPulseWorkspace?.csrf||'';}
 async function request(kind,body){const options=body?{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf()},body:JSON.stringify(body)}:undefined;const response=await root.BrokerForms.fetch(kind,api,options);const value=await response.json();if(!response.ok)throw Error(value.error||'Source selection unavailable.');return value;}
 function paint(value){current=value;hp.querySelector('[data-enabled]').checked=value.enabled;hp.querySelector('[data-auto]').checked=value.auto_enabled;const text=(value.enabled?'Included':'Not included')+' · '+(value.symbols||[]).length+' explicitly selected symbols · '+(value.sources||[]).length+' source(s) · '+(value.auto_enabled?'eligible for the existing authorized Auto mode':'analysis only');hp.querySelector('[data-status]').textContent=text;sp.querySelector('[data-state]').textContent=text;const list=hp.querySelector('[data-sources]');list.replaceChildren();for(const source of value.sources||[]){const li=document.createElement('li');li.textContent=source.label+' · '+source.symbols.length+' selected symbols';list.append(li);}if(value.latest){const line=document.createElement('p');line.textContent='Last scan: '+value.latest.status+' · '+value.latest.analyzed+' examined · '+value.latest.matched+' full-alignment matches · '+(value.latest.duplicates_merged||0)+' duplicates merged';hp.querySelector('[data-status]').append(line);for(const failure of value.latest.source_failures||[]){const reason=document.createElement('p');reason.textContent=failure.label+': '+failure.reason;hp.querySelector('[data-status]').append(reason);}}}
 async function load(){try{const a=root.BrokerForms.account('handoff');if(!['FYERS','DHAN'].includes(a?.broker))throw Error('Select an owned FYERS or Dhan Handoff account.');paint(await request('handoff'));}catch(e){hp.querySelector('[data-status]').textContent=e.message;}}
 async function save(body,kind='handoff'){if(busy)return;busy=true;try{const a=root.BrokerForms.account(kind);if(!['FYERS','DHAN'].includes(a?.broker))throw Error('Select the owned FYERS or Dhan account; no alternate broker is used.');if(kind==='screener'&&root.BrokerForms.account('handoff')?.id!==a.id)throw Error('Select the same broker account in Screener and Handoff before replacing its selection.');const value=await request(kind,{...body,broker:a.broker,account_id:a.id});paint(value);sp.querySelector('[data-state]').append(document.createTextNode(' · Saved. No order submitted.'));}catch(e){sp.querySelector('[data-state]').textContent=e.message;hp.querySelector('[data-status]').textContent=e.message;}finally{busy=false;}}
 hp.querySelector('[data-refresh]').onclick=load;hp.querySelector('[data-review]').onclick=()=>root.dispatchEvent(new CustomEvent('sector-pulse-handoff-source-review'));hp.querySelector('[data-save]').onclick=()=>{if(!current)return;save({enabled:hp.querySelector('[data-enabled]').checked,auto_enabled:hp.querySelector('[data-auto]').checked,symbols:current.symbols,sources:current.sources});};
 sp.querySelector('[data-use]').onclick=()=>root.dispatchEvent(new CustomEvent('sector-pulse-screener-selection-request'));
 root.addEventListener('sector-pulse-screener-selection',async event=>{
  const v=event.detail;if(v?.error){sp.querySelector('[data-state]').textContent=v.error;autoState.textContent=v.error;return;}
  if(v?.action!=='ENABLE_SCREENER_AUTO'){save({enabled:true,auto_enabled:current?.auto_enabled===true,symbols:v.symbols,sources:v.sources},'screener');return;}
  if(autoBusy)return;autoBusy=true;sp.querySelector('[data-start-auto]').disabled=true;
  try{
   const a=root.BrokerForms.account('screener'),capital=Number(sp.querySelector('[data-auto-capital]').value);
   if(!Number.isFinite(capital)||capital<1||capital>100000)throw Error('Enter allotted funds between ₹1 and ₹1,00,000.');
   const before=await scheduleRequest();
   if(!(before.supported_candidate_scopes||[]).includes('SCREENER_EQUITY'))throw Error('Screener Auto activation is pending the server update.');
   if(before.policy.enabled)throw Error('Pause the existing shared Handoff schedule before changing its selection or enabling Screener Auto.');
   if(root.BrokerForms.account('screener')?.id!==a.id)throw Error('Account changed; review and enable again.');
   paint(await request('screener',{enabled:true,auto_enabled:true,symbols:v.symbols,sources:v.sources,broker:a.broker,account_id:a.id}));
   if(root.BrokerForms.account('screener')?.id!==a.id)throw Error('Account changed; selection saved but Auto was not enabled.');
   showAuto(await scheduleRequest({enabled:true,mode:'AUTO',candidate_scope:'SCREENER_EQUITY',capital,ai_provider:'RULES_ONLY',cash_product:'CNC',live_authorized:true,amo:false}));
  }catch(e){autoState.textContent=e.message;}finally{autoBusy=false;sp.querySelector('[data-start-auto]').disabled=!autoSupported;}
 });
 sp.querySelector('[data-clear]').onclick=()=>save({enabled:false,auto_enabled:false,symbols:[],sources:[]},'screener');
 root.addEventListener('broker-account-change',event=>{if(['handoff','manual','screener'].includes(event.detail.kind))void load();});
 root.addEventListener('sector-pulse-job-output',event=>{const s=event.detail?.output?.scope?.screener;if(!s)return;const p=document.createElement('p');p.textContent='Screener analysis: '+s.status+' · '+s.analyzed+'/'+(s.current_selected??s.selected)+' examined · '+s.matched+' matched · '+(s.duplicates_merged||0)+' duplicate underlying(s) merged';hp.querySelector('[data-status]').append(p);});
 await load();await refreshAuto();}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void mount());else void mount();})(window);
