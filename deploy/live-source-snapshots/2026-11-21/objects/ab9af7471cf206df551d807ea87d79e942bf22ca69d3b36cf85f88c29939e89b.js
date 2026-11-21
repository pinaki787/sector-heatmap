;(() => {
 'use strict';
 const root=window,$=id=>document.getElementById(id),navRoot=document.querySelector('.nav');
 if(!navRoot)return;
 const old=document.querySelector('[data-view="trade-parser"]');if(old)old.textContent='FYERS Trade Parser';
 let nav=navRoot.querySelector('[data-view="telegram-parser"]');
 if(!nav){nav=document.createElement('button');nav.type='button';nav.dataset.view='telegram-parser';nav.textContent='Telegram Trade Parser';nav.setAttribute('aria-pressed','false');navRoot.append(nav);}
 let parsers=navRoot.querySelector('.parsers-nav');
 if(!parsers){parsers=document.createElement('div');parsers.className='parsers-nav trading-strategies-nav';parsers.setAttribute('role','group');parsers.setAttribute('aria-label','Parsers');const heading=document.createElement('div');heading.className='trading-strategies-heading';heading.textContent='Parsers';parsers.append(heading);const strategies=navRoot.querySelector('.trading-strategies-nav');navRoot.insertBefore(parsers,strategies);}
 parsers.append(nav);if(old)parsers.append(old);
 const host=document.createElement('section');host.id='telegram-parser';host.className='view';
 host.innerHTML=`<header class="head"><div><span class="label">TELEGRAM RECOMMENDATIONS</span><h1>Telegram Trade Parser</h1><p>One mode and quantity for automatic recommendations and pasted text.</p></div></header>
 <p id="tg-capability" class="ticket-warning" role="status"></p>
 <section class="panel"><h2>1. Connect your source</h2><p id="tg-reception" role="status">Checking source…</p><button id="tg-connect" class="button">Connect & receive</button> <button id="tg-disconnect" class="button secondary">Disconnect reader</button>
 <details><summary>Source settings and sign-in</summary><div class="field-grid">
 <label class="field">Reader<select id="tg-route"><option value="SUBSCRIBER">Subscribed Telegram account</option><option value="BOT">Dedicated channel bot</option></select></label>
 <label class="field">Channel display name<input id="tg-channel-label"></label><label class="field">Channel ID or username<input id="tg-channel"></label>
 <label class="field">Bot token<input id="tg-token" type="password" autocomplete="new-password" placeholder="Blank keeps saved token"></label>
 <label class="field">Subscriber API ID<input id="tg-api-id" type="password" autocomplete="off" placeholder="Blank keeps saved ID"></label>
 <label class="field">Subscriber API hash<input id="tg-api-hash" type="password" autocomplete="new-password" placeholder="Blank keeps saved hash"></label>
 <label class="field">Phone<input id="tg-phone" type="password" autocomplete="off"></label><label class="field">Login code<input id="tg-code" type="password" autocomplete="one-time-code"></label><label class="field">Two-step password<input id="tg-password" type="password" autocomplete="off"></label>
 </div><button id="tg-source-save" class="button secondary">Save source</button> <button id="tg-login" class="button secondary">Sign in / reuse session</button> <button id="tg-code-submit" class="button secondary">Confirm code</button> <button id="tg-password-submit" class="button secondary">Confirm password</button>
 <p>Connecting receives new recommendations only. It does not start execution. Use a dedicated bot if selecting Bot; do not share a bot's update reader with another application.</p></details></section>
 <section class="panel"><h2>2. Choose execution</h2><p id="tg-owner"></p><div class="field-grid">
 <label class="field">Execution mode<select id="tg-mode"><option value="PAPER">Paper · simulated fills</option><option value="LIVE">Live · real option orders</option></select></label>
 <label class="field">Whole option contracts<input id="tg-quantity" type="number" min="1" max="100000" step="1" value="1000"></label>
 <label class="field">Product<select id="tg-product"><option value="ATM_OPTIONS">Bought ATM Call / Put · Renko exits</option></select></label>
 </div><p>Fresh recommendations enter a bought ATM option at the current quote: BUY maps to Call, SELL to Put. Recommendation entry/stop/targets are references; this does not wait for the underlying trigger or attach those prices as broker protective orders. Renko owns confirmed fills and selected exits.</p>
 <details><summary>Exit settings and gold proxy</summary><div class="field-grid"><label class="field">Renko timeframe<select id="tg-timeframe"><option>1 minute</option><option>3 minutes</option><option selected>5 minutes</option><option>15 minutes</option><option>30 minutes</option><option>1 hour</option></select></label><label class="field">EMA length<input id="tg-ema-length" type="number" min="1" max="200" value="10"></label></div>
 <label class="choice"><input id="tg-ema" type="checkbox" checked>Completed-candle EMA exit</label><label class="choice"><input id="tg-st" type="checkbox" checked>Renko Supertrend exit</label><label class="choice"><input id="tg-gold-proxy" type="checkbox">Allow XAUUSD → XAUT gold-token proxy (a different underlying)</label></details>
 <label id="tg-live-consent-label" class="choice" hidden><input id="tg-live-consent" type="checkbox">I authorize real Live option entries for fresh recommendations using the displayed quantity, immediate entry policy and Renko exits.</label>
 <button id="tg-save-settings" class="button secondary">Save settings</button> <button id="tg-run" class="button">Run Paper</button> <button id="tg-stop" class="button secondary">Stop new entries</button>
 <p id="tg-execution" role="status"></p><p>Stop leaves reception and existing owned exits running. Restart never resumes execution or replays the backlog.</p><div id="tg-outcomes"></div></section>
 <section class="panel"><h2>Paste a recommendation</h2><p>Uses the same selected mode, product, quantity and exits above. Parse previews only.</p><label class="field">Recommendation text<textarea id="tg-text" rows="5"></textarea></label><button id="tg-preview" class="button secondary">Parse / preview</button><pre id="tg-preview-result" style="white-space:pre-wrap"></pre><button id="tg-submit" class="button" disabled>Submit reviewed recommendation</button></section>
 <section class="panel"><h2>Received recommendations & retained order history</h2><p>Older messages and existing native orders stay here for audit; they are never replayed by the new executor.</p><div id="tg-queue"></div></section><p id="tg-message" role="status"></p>`;
 document.querySelector('.work').append(host);
 let state=null,execution=null,preview=null,selected=null,hydrated=false,sourceHydrated=false,dirty=false,busy=false;
 async function api(action,body){const r=await fetch('/api/telegram/'+action,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok){const message=d.error||'Request failed';if(message.includes('Unknown Telegram action'))throw Error('This running backend does not support '+action+'. The Telegram page is newer than this workspace process; backend activation is required. Existing reception and trading were not changed.');throw Error(message);}return d;}
 const capable=()=>execution?.api_version===1;
 const settings=()=>({mode:$('tg-mode').value,quantity:Number($('tg-quantity').value),product:'ATM_OPTIONS',gold_proxy:$('tg-gold-proxy').checked,timeframe:$('tg-timeframe').value,ema_exit_enabled:$('tg-ema').checked,ema_exit_length:Number($('tg-ema-length').value),supertrend_exit_enabled:$('tg-st').checked});
 function clearPreview(){preview=null;$('tg-submit').disabled=true;$('tg-preview-result').textContent='';}
 function resultText(r){
  const native=!!r.request_id&&!!r.request,mode=r.execution_mode||r.mode||(native?'LIVE native order':'mode unavailable'),requested=r.quantity??r.request?.size??r.position?.quantity;
  const filled=r.filled_contracts??r.position?.quantity,lines=[mode+' · '+(native&&r.status==='pending'&&r.request.stop_price?'waiting for trigger · unfilled':r.status||r.state||'response received')];
  if(r.symbol||r.position?.symbol)lines.push(r.symbol||r.position.symbol);
  if(requested!=null)lines.push('Requested contracts: '+requested);
  lines.push('Confirmed fills: '+(filled??'not confirmed'));
  if(r.request?.stop_price)lines.push('Trigger '+r.request.stop_price+' · limit '+r.request.limit_price+' · existing Live native order');
  if(r.pending)lines.push('Broker acknowledgement only; fill reconciliation pending.');
  if(r.management_owner)lines.push('Exit owner: Renko');
  if(r.message||r.error)lines.push(r.message||r.error);
  return lines.join('\n');
 }
 function controls(){
  const owner=state?.workspace_broker==='DELTA_INDIA',ready=capable()&&owner,active=capable()?execution.running:!!state?.paper_pipeline?.running;
  $('tg-live-consent-label').hidden=$('tg-mode').value!=='LIVE';
  $('tg-run').textContent='Run '+$('tg-mode').value+' · '+($('tg-quantity').value||'—')+' contracts';
  $('tg-run').disabled=busy||!ready||active||!state?.configured||($('tg-mode').value==='LIVE'&&!$('tg-live-consent').checked);
  $('tg-save-settings').disabled=busy||!ready||active;
  $('tg-preview').disabled=busy||!ready;
  $('tg-stop').disabled=busy||!active;
  $('tg-connect').disabled=busy||!!state?.running||!state?.configured;
  $('tg-disconnect').disabled=busy||active||!state?.running;
  for(const id of ['mode','quantity','product','timeframe','ema-length','ema','st','gold-proxy'])$('tg-'+id).disabled=busy||!ready||active;
  $('tg-submit').textContent='Submit '+(preview?.execution_mode||$('tg-mode').value)+' · '+(preview?.quantity??$('tg-quantity').value)+' contracts';
  $('tg-submit').disabled=busy||!ready||!preview||dirty||(preview.execution_mode==='LIVE'&&!$('tg-live-consent').checked);
 }
 function render(s){
  state=s;execution=s.execution||null;
  const p=execution||s.paper_pipeline;
  if(!sourceHydrated){$('tg-route').value=s.route||'SUBSCRIBER';$('tg-channel').value=s.channel||'';$('tg-channel-label').value=s.channel_label||'';sourceHydrated=true;}
  if(!hydrated&&p){
   const cfg=p.settings||{mode:p.mode||'PAPER',quantity:p.quantity||1000,...p.options};
   $('tg-mode').value=cfg.mode||'PAPER';$('tg-quantity').value=cfg.quantity||1000;$('tg-timeframe').value=cfg.timeframe||'5 minutes';$('tg-ema-length').value=cfg.ema_exit_length||10;
   $('tg-ema').checked=cfg.ema_exit_enabled!==false;$('tg-st').checked=cfg.supertrend_exit_enabled!==false;$('tg-gold-proxy').checked=cfg.gold_proxy===true;hydrated=true;
  }
  $('tg-capability').textContent=capable()?'One Paper/Live mode governs both Telegram execution and pasted recommendations. Legacy native submission is retired.':'Unified controls are prepared but backend activation is pending. Existing reception and execution continue unchanged; new submissions are disabled here.';
  $('tg-reception').textContent=(s.running?'RECEIVING':'RECEPTION STOPPED')+' · '+s.connection+' · '+(s.authentication||s.route)+' · '+(s.error||s.channel_label||'');
  $('tg-owner').replaceChildren(document.createTextNode('Execution owner: '+(s.workspace_broker||'select an account')+'. '));
  if(s.workspace_broker!=='DELTA_INDIA'&&s.option_workspace_id&&/^[a-f0-9]{32}$/.test(s.option_workspace_id)){const a=document.createElement('a');a.href='/broker-workspace/'+s.option_workspace_id+'/';a.textContent='Open your Delta option-execution workspace';$('tg-owner').append(a);}
  const life=p?.lifecycle;
  $('tg-execution').textContent=(p?.running?'EXECUTION RUNNING':'EXECUTION STOPPED')+' · '+(p?.mode||'PAPER')+' · '+(p?.quantity||1000)+' contracts'+(life?' · '+life.reason+': '+life.message:'')+(life?.heartbeat?' · heartbeat '+Math.max(0,Math.floor(Date.now()/1000-life.heartbeat))+'s ago':'');
  $('tg-outcomes').replaceChildren();
  for(const record of [...(p?.recommendations||[])].reverse()){const line=document.createElement('pre');line.style.whiteSpace='pre-wrap';line.textContent=record.result?resultText(record.result):[record.mode||'Historical Paper',record.status,record.message||''].join(' · ');$('tg-outcomes').append(line);}
  $('tg-queue').replaceChildren();
  for(const row of s.queue||[]){
   const card=document.createElement('article');card.className='ticket-warning';const text=document.createElement('pre');text.style.whiteSpace='pre-wrap';text.textContent=[row.state+(row.missed_review?' · review-only missed post':''),row.text,row.result?resultText(row.result):row.error||''].join('\n');card.append(text);
   if(row.state==='REVIEW'&&!row.expired&&!row.missed_review&&!row.edited_at&&!row.submission_id){const b=document.createElement('button');b.className='button secondary';b.textContent='Preview this recommendation';b.onclick=()=>{selected={queue_id:row.id,revision:row.revision};$('tg-text').value=row.text;doPreview();};card.append(b);}
   if(row.result?.request_id){const b=document.createElement('button');b.className='button secondary';b.textContent='Refresh existing broker order status';b.onclick=()=>action(async()=>{await api('reconcile',{queue_id:row.id});await refresh();});card.append(b);}
   $('tg-queue').append(card);
  }
  controls();
 }
 async function refresh(){render(await api('status'));}
 async function action(fn){if(busy)return;busy=true;controls();try{await fn();}catch(e){$('tg-message').textContent=e.message;}finally{busy=false;controls();}}
 async function save(){if(!capable())throw Error('Backend activation pending; current run was not changed.');execution=await api('execution-settings',{...settings(),config_revision:execution.revision});dirty=false;clearPreview();return execution;}
 function doPreview(){return action(async()=>{
  await save();preview=await api('execution-preview',{text:$('tg-text').value,config_revision:execution.revision,...selected});
  const c=preview.contract;$('tg-preview-result').textContent=[preview.execution_mode+' · '+preview.quantity+' bought option contracts',c.symbol+' · '+c.option_type+' · expiry '+new Date(c.expiry_epoch*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}),'Per contract: '+c.quantity_multiplier+' '+c.underlying_asset,'Bid '+preview.quote.bid+' / ask '+preview.quote.ask,'Immediate option entry; Renko exits. Recommendation levels remain references.'].join('\n');
 });}
 $('tg-save-settings').onclick=()=>action(async()=>{await save();$('tg-message').textContent='Settings saved. Execution was not started.';await refresh();});
 $('tg-run').onclick=()=>action(async()=>{if(!capable())throw Error('Backend activation pending.');execution=await api('execution-start',{...settings(),config_revision:execution.revision,live_confirmed:$('tg-live-consent').checked});dirty=false;clearPreview();await refresh();});
 $('tg-stop').onclick=()=>action(async()=>{await api(capable()?'execution-stop':'paper-stop',{});await refresh();});
 $('tg-connect').onclick=()=>action(async()=>{await api(capable()?'connect':'start',{auto:false});await refresh();});
 $('tg-disconnect').onclick=()=>action(async()=>{await api('disconnect',{});await refresh();});
 $('tg-preview').onclick=doPreview;
 $('tg-submit').onclick=()=>action(async()=>{if(!preview)throw Error('Parse a fresh preview first.');const response=await api('execution-submit',{ticket_id:preview.ticket_id,text:$('tg-text').value,config_revision:execution.revision,entry_confirmed:true,live_confirmed:$('tg-live-consent').checked});$('tg-message').textContent=resultText(response);clearPreview();await refresh();});
 $('tg-text').oninput=()=>{selected=null;clearPreview();controls();};
 for(const id of ['mode','quantity','timeframe','ema-length','ema','st','gold-proxy'])$('tg-'+id).onchange=()=>{dirty=true;$('tg-live-consent').checked=false;clearPreview();controls();};
 $('tg-live-consent').onchange=controls;
 $('tg-source-save').onclick=()=>action(async()=>{const data={route:$('tg-route').value,channel:$('tg-channel').value,channel_label:$('tg-channel-label').value,interval:30};for(const key of ['token','api-id','api-hash']){data[key.replace('-','_')]=$('tg-'+key).value;$('tg-'+key).value='';}await api('config',data);sourceHydrated=false;await refresh();});
 for(const [button,field] of [['login','phone'],['code-submit','code'],['password-submit','password']])$('tg-'+button).onclick=()=>action(async()=>{if(button==='login'&&state?.authentication==='AUTHORIZED'){await refresh();$('tg-message').textContent='Saved Telegram session is authorized and ready to reuse. Use Connect & receive to start reception.';return;}const value=$('tg-'+field).value;$('tg-'+field).value='';await api('login',{[field]:value});await refresh();});
 refresh().catch(e=>{$('tg-message').textContent=e.message;});
 setInterval(()=>{if(!busy&&(host.classList.contains('active')||state?.running||state?.execution?.running||state?.paper_pipeline?.running))refresh().catch(e=>{$('tg-message').textContent=e.message;});},5000);
})();
