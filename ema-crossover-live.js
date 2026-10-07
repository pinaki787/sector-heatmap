/* User-activated FYERS execution; activation preview is configuration-bound. */
(function(root) {
  function mount() {
    const section = document.getElementById('ema-cross');
    section.querySelector('.head .status').textContent = 'Checking FYERS execution availability';
    section.querySelector('.choice-row + p').textContent = 'RSI uses Wilder smoothing and the selected SMA or EMA of RSI. Entry: completed RSI crosses above its MA buys ATM Call; crosses below buys ATM Put. Opposite completed crossover exits. Equality holds. One owned position; no re-entry on the exit candle.';
    section.querySelector('.panel').insertAdjacentHTML('afterend', `<section class="panel" style="margin-top:15px"><div class="step-title"><div><span class="label">FYERS EXECUTION</span><h2>RSI based EMA runner</h2></div><span id="cross-live-state" class="badge">STOPPED</span></div>
      <div class="field-grid" style="margin-top:14px"><label class="field">Strategy label<input id="cross-label" maxlength="60" value="RSI based EMA"></label><label class="field">Execution mode<select id="cross-mode"><option value="PAPER">Paper</option><option value="LIVE" selected>Live — real FYERS orders</option></select></label><label class="field">Maximum trades per run<input id="cross-max-trades" type="number" min="1" max="1000" step="1" value="2"><small>Caps entry orders, including uncertain submissions. Exit orders remain allowed. Resets only on a new start while flat.</small></label><label class="field">Virtual Paper capital · INR<input id="cross-paper-capital" type="number" min="1" max="1000000000" value="100000"></label><label class="field">Lots<input id="cross-lots" type="number" min="1" max="100" step="1" value="1"></label><label class="field">Underlying spot target (optional)<input id="cross-spot-target" type="number" min="0.01" step="any" placeholder="Absolute spot price"><small>When either spot level is entered, EMA exit is ignored.</small></label><label class="field">Underlying spot stop-loss (optional)<input id="cross-spot-stop" type="number" min="0.01" step="any" placeholder="Absolute spot price"><small>Completed-close checks. Blank levels are unused.</small></label><label class="field">Quoted premium cap per entry (₹, optional)<input id="cross-premium" type="number" min="1" step="1" placeholder="No per-entry cap"><small>Leave blank for no per-entry cap. Any configured daily budget still applies.</small></label><label class="field">Daily loss budget (₹, optional)<input id="cross-budget" type="number" min="1" step="1" placeholder="No daily budget"><small>Leave blank for no daily budget. When set, realized losses plus new premium must fit; fees are additional.</small></label></div>
      <div class="ticket-warning">Live mode places real FYERS MARKET requests (broker applies MPP): BUY nearest-expiry ATM CE/PE; SELL only the runner’s broker-confirmed quantity. A call exits when a later completed RSI crosses below its selected MA; a put exits when a later completed RSI crosses above its selected MA. Equality holds. All strategy decisions use completed closes. Optional premium step trailing applies only when enabled for a new run. No initial stop exists before its first step; entry-price stop excludes fees. Positions may carry between sessions. Orders require the running server, fresh data and liquidity; fills are not guaranteed. Optional money limits check quoted premium; the actual market fill can differ. Stop Runner cancels unfilled entry quantities and squares off the runner-owned position.</div>
      <div class="packet-actions"><button type="button" class="button" id="cross-runner-start">Start Runner</button></div>
      <div id="cross-live-message" class="handoff-status" role="status">Loading runner status…</div><div class="risk-strip"><div><b id="cross-owned">None</b><small>Runner-owned position</small></div><div><b id="cross-pending">None</b><small>Pending order</small></div><div><b id="cross-runtime">Checking</b><small>FYERS live runtime gate</small></div></div><details style="margin-top:12px"><summary>Execution journal</summary><pre id="cross-journal" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details></section>`);
    const el=id=>document.getElementById('cross-'+id);
    el('live-message').insertAdjacentHTML('afterend',`<section class="cloud-order-summary" aria-label="Order summary"><div class="cloud-order-title"><strong>Order & position</strong><span id="cross-order-phase">No active order</span></div><dl><div><dt>Option contract</dt><dd id="cross-order-contract">—</dd></div><div><dt>Direction / action</dt><dd id="cross-order-action">—</dd></div><div><dt>Confirmed position</dt><dd id="cross-order-quantity">—</dd></div><div><dt>Average entry price</dt><dd id="cross-order-price">—</dd></div><div><dt>Broker order reference</dt><dd id="cross-order-reference">—</dd></div><div><dt>Opened at</dt><dd id="cross-order-time">—</dd></div></dl><small>Only confirmed fills appear as positions. Open profit and loss is shown with the chart.</small></section>`);
    section.querySelector('.cloud-order-summary').insertAdjacentHTML('afterend','<section class="cloud-order-summary"><div class="cloud-order-title"><strong>Order history</strong><span>One row per verified position · all available history</span></div><div id="cross-order-history" style="overflow:auto;margin-top:14px">No orders placed by this runner.</div></section>');
    const executionNote=section.querySelector('.ticket-warning');
    const executionDetails=document.createElement('details');
    executionDetails.style.cssText='margin-top:10px;font-size:12px;line-height:1.65;color:#a5b6ca';
    const executionSummary=document.createElement('summary');executionSummary.textContent='Execution details';
    const executionBody=document.createElement('p');executionBody.textContent=executionNote.textContent;
    executionDetails.append(executionSummary,executionBody);executionNote.after(executionDetails);
    executionNote.textContent='Start Runner trades in the selected mode. Stop Runner cancels pending entries and closes this runner’s positions. Market requests use FYERS price protection.';
    const cloudStyle=document.createElement('style');
    cloudStyle.textContent=`
      #ema-cross .panel{padding:24px;border-color:#29374d}
      #ema-cross .field-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px 24px;align-items:start}
      #ema-cross .field{display:grid;grid-template-rows:auto 44px auto;align-content:start;gap:8px;min-width:0;margin:0}
      #ema-cross .cloud-field-label{display:flex;align-items:flex-end;min-height:34px;font-size:12px;line-height:17px;color:#c6d1df;font-weight:600}
      #ema-cross .field input,#ema-cross .field select{box-sizing:border-box;width:100%;min-width:0;height:44px;margin:0;padding:10px 12px;border:1px solid #36465e;border-radius:8px;background:#0c1626;font-size:14px;font-variant-numeric:tabular-nums}
      #ema-cross .trailing-switch{grid-column:1/-1;display:flex!important;align-items:center;gap:12px!important;padding:14px 16px;border:1px solid #29374d;border-radius:8px;background:#0d1929}
      #ema-cross .trailing-switch input{width:16px!important;height:16px!important;min-width:16px!important;padding:0!important;margin:0!important;accent-color:#6eb7e9}
      #ema-cross .switch-copy{font-size:13px;font-weight:600;line-height:1.5}#ema-cross .switch-copy small{display:block;font-size:11px;font-weight:400}
      #ema-cross .trailing-choice{margin-left:auto;font-size:11px;color:#9aacc2;border:1px solid #35465e;border-radius:20px;padding:3px 9px;white-space:nowrap}
      #ema-cross .field input:focus,#ema-cross .field select:focus{outline:2px solid #6eb7e9;outline-offset:2px}
      #ema-cross .field small{font-size:11px;line-height:16px;color:#94a6bc;max-width:44ch}
      #ema-cross .cloud-group{grid-column:1/-1;margin:6px 0 -10px;padding-top:18px;border-top:1px solid #2b3b51;display:flex;align-items:baseline;gap:12px}
      #ema-cross .cloud-group strong{font-size:12px;color:#dce8f6;letter-spacing:.06em;text-transform:uppercase}
      #ema-cross .cloud-group span{font-size:11px;color:#91a5be}
      #ema-cross .ticket-warning{margin-top:24px;padding:14px 16px;font-size:12px;line-height:1.65;border-radius:8px}
      #ema-cross .packet-actions{margin-top:20px;padding-top:18px;border-top:1px solid #29374d}
      #ema-cross #cross-runner-start{min-height:44px;min-width:164px;font-weight:700}
      #ema-cross .cloud-order-summary{margin-top:18px;padding:18px;background:#0d1929;border:1px solid #2c4059;border-radius:10px}
      #ema-cross .cloud-order-title{display:flex;justify-content:space-between;gap:12px;font-size:13px;color:#dce8f6}
      #ema-cross .cloud-order-title span{font-size:11px;color:#8bc3e9}
      #ema-cross .cloud-order-summary dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:18px 0}
      #ema-cross .cloud-order-summary dt{font-size:11px;color:#91a5be;margin-bottom:6px}
      #ema-cross .cloud-order-summary dd{margin:0;font-size:13px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere;color:#e0eaf6}
      #ema-cross .cloud-order-summary small{font-size:11px;color:#91a5be}
      #ema-cross #cross-owned,#ema-cross #cross-pending{white-space:normal}
      #ema-cross .risk-strip{gap:12px;margin-top:18px}
      @media(max-width:520px){#ema-cross .field-grid{grid-template-columns:1fr;gap:14px}#ema-cross .panel{padding:18px}#ema-cross .cloud-field-label{min-height:0}#ema-cross .cloud-group{flex-wrap:wrap;gap:4px}}
    `;
    section.append(cloudStyle);
    for(const field of section.querySelectorAll('.field')){
      const text=field.firstChild;
      if(text?.nodeType===3){const label=document.createElement('span');label.className='cloud-field-label';label.textContent=text.textContent.trim();text.replaceWith(label);}
    }
    function groupBefore(id,title,hint){
      const group=document.createElement('div');group.className='cloud-group';
      const strong=document.createElement('strong');strong.textContent=title;const note=document.createElement('span');note.textContent=hint;
      group.append(strong,note);el(id).closest('.field').before(group);
    }
    groupBefore('max-trades','Position sizing','Entries per run and contract quantity');
    for(const id of ['spot-target','spot-stop']){el(id).value='';el(id).closest('.field').remove();}
    groupBefore('premium','Money limits','Optional · leave blank to disable');

    el('budget').closest('.field').insertAdjacentHTML('afterend',`<label class="field trailing-switch"><input id="cross-trailing-enabled" type="checkbox"><span class="switch-copy">Trailing stop<small>Option premium · optional</small></span><span id="cross-trailing-choice" class="trailing-choice">Off</span></label><label class="field">Trailing mode<select id="cross-trailing-mode"><option value="PERCENTAGE">Percentage of filled entry</option><option value="POINTS">Premium points</option></select></label><label class="field">Trailing step<input id="cross-trailing-step" type="number" min="0.000001" step="any" value="10"><small>Percentage defaults to 10%. Points require your positive distance. Fixed distance; never compounds.</small></label><div id="cross-trailing-state" style="grid-column:1/-1">Trailing off.</div><div id="cross-trailing-allocation" style="grid-column:1/-1;font-size:12px;line-height:1.6;color:#9aacc2"></div>`);
    const inputs=['paper-capital','trailing-enabled','trailing-mode','trailing-step','symbol','timeframe','rsi-length','sma-length','ma-type','max-trades','mode','lots','premium','budget','label'];
    const display=value=>String(value || '');
    let version=0, busy=false, messagePinned=false, running=false, stopping=false, policyReady=false;
    async function request(path,body) {
      if(path==='preview')await root.PaperCapital?.ensure(body?.mode);
      const response=await fetch('/api/ema-crossover/'+path,body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {});
      const data=await response.json();if(!response.ok || data.error)throw Error(display(data.error || 'Runner request failed'));return data;
    }
    const settingsKey='sector-pulse:rsi-based-ema-settings-v1';
    let savedSettings=null;
    try {savedSettings=JSON.parse(localStorage.getItem(settingsKey) || 'null');}catch{}
    function saveSettings(){
      try {localStorage.setItem(settingsKey,JSON.stringify(Object.fromEntries([...inputs,'search'].map(id=>[id,id==='trailing-enabled'?el(id).checked:el(id).value]))));}catch{}
    }
    function restoreSettings(values){
      if(!values || typeof values!=='object')return;
      if(typeof values.symbol==='string' && values.symbol && ![...el('symbol').options].some(o=>o.value===values.symbol))el('symbol').add(new Option(values.symbol,values.symbol));
      for(const id of [...inputs,'search'])if(typeof values[id]==='string')el(id).value=values[id];
      el('trailing-enabled').checked=values['trailing-enabled']===true;
    }
    restoreSettings(savedSettings);
    function invalidate() { version++; saveSettings(); }
    inputs.forEach(id=>el(id).addEventListener('input',invalidate));
    el('search').addEventListener('input',invalidate);
    function applyLabel() {
      const name='RSI based '+el('ma-type').value;el('label').value=name;el('label').readOnly=true;
      document.querySelector('[data-view="ema-cross"]').textContent=name;
      section.querySelector('h1').textContent=name;section.querySelector('section.panel h2').textContent=name;section.querySelector('.head small').textContent='RSI '+el('rsi-length').value+' · '+el('ma-type').value+' '+el('sma-length').value+' · Completed close';
      el('live-state').closest('.step-title').querySelector('h2').textContent=name+' runner';
      try {localStorage.setItem('sector-pulse:ema-cloud-label',name);} catch {}
    }
    try {if(!savedSettings)el('label').value=localStorage.getItem('sector-pulse:ema-cloud-label') || 'RSI based EMA';} catch {}
    el('label').addEventListener('input',applyLabel);for(const id of ['ma-type','rsi-length','sma-length'])el(id).addEventListener('input',applyLabel);applyLabel();
    el('trailing-mode').addEventListener('change',()=>{el('trailing-step').value=el('trailing-mode').value==='PERCENTAGE'?'10':'';invalidate();});
    function config() { return {paper_capital_inr:Number(el('paper-capital').value),trailing_enabled:el('trailing-enabled').checked,trailing_mode:el('trailing-mode').value,trailing_step:el('trailing-step').value===''?null:Number(el('trailing-step').value),strategy:'RSI_BASED_EMA_V1',underlying:el('symbol').value,timeframe:el('timeframe').value,rsi_length:Number(el('rsi-length').value),ma_length:Number(el('sma-length').value),ma_type:el('ma-type').value,max_trades:Number(el('max-trades').value),mode:el('mode').value,lots:Number(el('lots').value),max_premium:el('premium').value.trim()===''?null:Number(el('premium').value),daily_budget:el('budget').value.trim()===''?null:Number(el('budget').value),spot_target:null,spot_stop:null,label:el('label').value}; }
    function render(s) {
      if(!el('paper-funds'))el('paper-capital').closest('label').insertAdjacentHTML('afterend','<p id="cross-paper-funds"></p>');
      const funds=s.paper_capital;el('paper-funds').textContent=funds?(funds.error||`Virtual INR capital · available ₹${Number(funds.available_inr).toLocaleString('en-IN')} · reserved ₹${Number(funds.reserved_inr).toLocaleString('en-IN')} · fee provision ₹${Number(funds.fee_provision_inr).toLocaleString('en-IN')}`):'Virtual Paper capital applies after backend deployment on the next Paper start.';
      if(s.strategy !== 'RSI_BASED_EMA_V1') {el('runner-start').disabled=true;el('live-message').textContent='RSI based EMA backend update pending. Reload after the update completes.';return;}

      el('live-state').textContent=s.status;
      const history=el('order-history');history.replaceChildren();
      const fmt=v=>v==null?'Unavailable':String(v), price=v=>v==null?'Unavailable':'₹'+Number(v).toFixed(2), when=v=>v?new Date(v*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':'—';
      const positions=s.position_history || root.PositionHistory.project(s);
      if(!positions.length)history.textContent='No position history recorded by this runner.';
      else {
        const table=document.createElement('table');table.style.cssText='width:100%;min-width:2200px;font-size:12px;text-align:left;border-collapse:collapse';
        const header=table.createTHead().insertRow();
        for(const title of ['Contract','Status','Entry order IDs','Exit order IDs','Bought lots','Bought quantity · filled','Invested premium ₹ · before fees','Buy avg.','Sell avg.','Realized P&L ₹','P&L %','Strategy','Entry time','Exit time','Mode','Entry / exit types','Product','Entry reason','Exit reason','Requested entry / exit','Filled entry / exit','Matched qty','Remaining quantity']){const th=document.createElement('th');th.textContent=title;th.style.cssText='padding:10px 12px;border-bottom:1px solid #35465e;white-space:nowrap';header.append(th);}
        for(const p of positions){const mult=p.orders?.find(o=>o.quantity_multiplier>0)?.quantity_multiplier;const invested=p.invested_amount ?? (p.entry_filled>0&&p.entry_price!=null&&mult>0?p.entry_filled*p.entry_price*mult:null);const row=table.insertRow();for(const v of [p.contract,p.status,p.entry_order_ids?.join(', ') || '—',p.exit_order_ids?.join(', ') || '—',fmt(p.lots),fmt(p.entry_filled),price(invested),price(p.entry_price),price(p.exit_price),price(p.realized_pnl),p.pnl_percent==null?'Unavailable':p.pnl_percent.toFixed(2)+'%',p.strategy,when(p.entry_time),p.exit_time_detail || when(p.exit_time),p.mode,(p.entry_types || []).join(', ')+' / '+(p.exit_types || []).join(', '),(p.products || []).join(', '),(p.entry_reasons || []).join(', '),(p.exit_reasons || []).join(', '),p.entry_requested+' / '+p.exit_requested,p.entry_filled+' / '+p.exit_filled,fmt(p.matched_quantity),fmt(p.remaining_quantity ?? (['OPEN','CLOSED','PARTIAL EXIT'].includes(p.status)?p.entry_filled-p.exit_filled:null))]){const c=row.insertCell();c.textContent=fmt(v);c.style.cssText='padding:10px 12px;border-bottom:1px solid #26374d;white-space:nowrap';}}
        history.append(table);
        const note=document.createElement('p');note.textContent='Before fees. P&L uses confirmed matched fills only. Legacy rows without verified lifecycle links remain unpaired; missing history and external exits are not inferred.';history.append(note);
        const detail=document.createElement('details'),summary=document.createElement('summary'),raw=document.createElement('pre');summary.textContent='Raw execution ledger · all available orders';raw.textContent=JSON.stringify(s.order_history || [],null,2);detail.append(summary,raw);history.append(detail);
      }

      const position=s.position,pending=s.pending;
      el('order-phase').textContent=pending?'Awaiting broker fill':position?'Position confirmed':'No active order';
      el('order-contract').textContent=position?.symbol || pending?.order.symbol || '—';
      el('order-action').textContent=pending?(pending.order.side===1?'BUY · entry':'SELL · exit'):position?(position.direction==='BULLISH'?'CALL · bullish':'PUT · bearish'):'—';
      el('order-quantity').textContent=position?`${position.quantity} filled units`:pending?`Awaiting fill · ${pending.order.qty} requested`:'—';
      el('order-price').textContent=position?`₹${Number(position.entry_price).toFixed(2)}`:'—';
      el('order-reference').textContent=pending?.id || position?.entry_order_id || (pending?'Awaiting acknowledgement':'—');
      el('order-time').textContent=position?.opened_at?new Date(position.opened_at*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST':'—';

      const pnl=s.pnl;
      el('pnl').textContent=pnl?.available?`Position P&L: ₹${pnl.unrealized.toFixed(2)} · Realized: ₹${pnl.realized.toFixed(2)} · Before fees · ${s.config?.mode || el('mode').value}`:'Position P&L unavailable — waiting for a fresh option bid';
      el('runtime').textContent=s.live_available?'Enabled':'Disabled';
      section.querySelector('.head .status').textContent=s.live_available?'FYERS live runner available':'FYERS live submission disabled';
      el('owned').textContent=s.position?`${s.position.symbol} · ${s.position.quantity} qty @ ${s.position.entry_price}`:'None';
      el('pending').textContent=s.pending?`${s.pending.order.side===1?'BUY':'SELL'} ${s.pending.order.symbol} · ${s.pending.id || 'Awaiting acknowledgement'}`:'None';
      section.querySelector('.risk-strip > div:last-child b').textContent=s.running ? s.config.mode : s.status;
      policyReady=s.runtime_revision==='rsi-crossover-partial-trailing-v5';
      const legacyStream = s.runtime_revision !== 'rsi-crossover-partial-trailing-v5';
      const streamNote = legacyStream ? ' Saved crossover and optional trailing changes are not loaded. Active runner behavior is unchanged. Controlled deployment requires a separate decision after the position is flat.' : s.stream ? ` Stream: ${s.stream.connected ? 'connected' : 'disconnected'}${s.stream.error ? ' · '+s.stream.error : ''}.` : '';
      if(!messagePinned)el('live-message').textContent=display(s.message || s.error || 'Stopped. Select your settings and click Start Runner.') + streamNote;
      running=!!s.running;stopping=running && !!s.squareoff_requested;
      el('runner-start').textContent=stopping?'Stopping…':running?'Stop Runner':'Start Runner';
      el('runner-start').disabled=busy || stopping;
      el('journal').textContent=(s.events || []).slice(-12).reverse().map(e=>`${new Date(e.at*1000).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})} IST · ${display(e.status)}\n${display(e.message)}`).join('\n\n') || 'No execution events.';
      if(s.running)inputs.forEach(id=>el(id).disabled=true);else inputs.forEach(id=>el(id).disabled=false);
      el('search').disabled=!!s.running;
      el('trailing-mode').disabled=!!s.running || !el('trailing-enabled').checked;el('trailing-step').disabled=!!s.running || !el('trailing-enabled').checked;
      const lots=Number(el('lots').value),split=lots===1?[0,0,1]:lots===2?[1,0,1]:[Math.max(1,Math.floor(lots*.3)),Math.max(1,Math.floor(lots*.3)),lots-2*Math.max(1,Math.floor(lots*.3))];
      el('trailing-allocation').textContent=(el('trailing-enabled').checked?'':'Off · preview only. ')+`Nominal 30% / 30% / 40%. Actual ${lots} lots: ${split.join(' / ')} (${split.map(n=>(n/lots*100).toFixed(1)+'%').join(' / ')}). First step sells first allocation; second sells second; remainder trails. Applied to confirmed whole filled lots.`;
      el('trailing-choice').textContent=el('trailing-enabled').checked?'On for next run':'Off';
      const t=s.position?.trailing;el('trailing-state').textContent=t?`${t.armed?'Armed stop ₹'+t.stop:'Unarmed'} · Next bid ₹${t.next_trigger} · High bid ₹${t.high_water} · ${t.mode} ${t.configured_step} · Fixed premium distance ${t.increment} · Confirmed lot split ${t.allocation?.join(' / ') || 'Unavailable: non-whole filled lots'} · Target fills ${t.target_filled?.['1'] || 0} / ${t.target_filled?.['2'] || 0}`:'Trailing off for this position. No stop has been added.';if(s.position?.trailing_error)el('trailing-state').textContent+=' · '+s.position.trailing_error;
    }
    async function refresh() { if(busy)return;try { render(await request('runner')); } catch(e) { el('live-message').textContent='Runner unavailable: '+e.message; } }
    el('runner-start').addEventListener('click',async()=>{
      if(busy)return;busy=true;const seq=version;messagePinned=true;el('runner-start').disabled=true;
      el('live-message').textContent=running?'Stopping entries and requesting square-off…':'Validating settings and starting the selected execution mode…';
      try {
        if(running){messagePinned=false;render(await request('stop',{}));return;}
        if(!policyReady)throw Error('Saved strategy changes require controlled deployment first.');
        const p=await request('preview',config());
        if(seq!==version)throw Error('Settings changed while starting. Click Start Runner again.');
        const s=await request('start',{preview_id:p.id,confirmation:p.confirmation});
        messagePinned=false;render(s);
      } catch(e){el('live-message').textContent=e.message;}finally{busy=false;await refresh();}
    });
    // Restore owned configuration for explicit recovery after server restart; never auto-start.
    request('runner').then(s=>{
      if(s.config && (s.running || s.position || s.pending || !savedSettings)) {
        const c=s.config;el('trailing-enabled').checked=c.trailing_enabled===true;el('trailing-mode').value=c.trailing_mode || 'PERCENTAGE';el('trailing-step').value=c.trailing_step ?? (el('trailing-mode').value==='PERCENTAGE'?10:'');
        if(![...el('symbol').options].some(o=>o.value===c.underlying))el('symbol').add(new Option(c.underlying,c.underlying));
        for(const [id,key] of Object.entries({symbol:'underlying',timeframe:'timeframe','rsi-length':'rsi_length','sma-length':'ma_length','ma-type':'ma_type','max-trades':'max_trades','paper-capital':'paper_capital_inr',mode:'mode',lots:'lots',premium:'max_premium',budget:'daily_budget',label:'label'}))el(id).value=c[key] == null ? (['premium','budget','spot-target','spot-stop'].includes(id)?'':el(id).value) : c[key];
      }
      applyLabel();render(s);saveSettings();
      if(el('symbol').value)el('symbol').dispatchEvent(new Event('change',{bubbles:true}));
    }).catch(e=>{el('live-message').textContent='Runner unavailable: '+e.message;});
    setInterval(()=>{if(!document.hidden)refresh();},2000);
  }
  root.EmaCrossoverLive={mount};
})(window);
