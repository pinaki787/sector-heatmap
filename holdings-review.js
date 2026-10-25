/* Read-only broker portfolio review. No order endpoints or strategy mutations. */
(() => {
  'use strict';
  const labels = {HOLD: 'Hold', TRAIL: 'Trail', EXIT: 'Exit', BOOK_PROFIT: 'Book profit', REVIEW_NEEDED: 'Review needed'};
  const priority = {EXIT: 0, REVIEW_NEEDED: 1, BOOK_PROFIT: 2, TRAIL: 3, HOLD: 4};
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const numeric = value => value == null || !Number.isFinite(Number(value)) ? '—' : new Intl.NumberFormat('en-IN', {maximumFractionDigits: 2}).format(Number(value));
  const pnlMarkup = row => {
    const finite = value => value != null && value !== '' && typeof value !== 'boolean' && Number.isFinite(Number(value));
    const gross = finite(row.gross_pnl), value = gross ? Number(row.gross_pnl) : finite(row.broker_unrealized_pnl) ? Number(row.broker_unrealized_pnl) : null;
    const rounded = value == null ? null : Number(value.toFixed(2));
    const state = rounded == null ? 'unavailable' : rounded > 0 ? 'profit' : rounded < 0 ? 'loss' : 'flat';
    const label = {profit:'Profit',loss:'Loss',flat:'Break-even',unavailable:'P&L unavailable'}[state];
    const amount = rounded == null ? '—' : (rounded > 0 ? '+' : rounded < 0 ? '−' : '') + numeric(Math.abs(rounded));
    const percent = gross && finite(row.gross_return_pct) ? Number(Number(row.gross_return_pct).toFixed(2)) : null;
    return `<td class="holding-pnl" data-pnl="${state}"><span class="holding-pnl-label">${label}</span><strong>${amount}${rounded == null ? '' : ' '+escape(row.currency)}</strong>${percent == null ? '' : `<small>${percent > 0 ? '+' : ''}${numeric(percent)}% price return</small>`}<small class="holding-pnl-basis">${rounded == null ? 'A validated price or broker P&L is needed' : gross ? 'Gross unrealized · before costs' : 'Broker unrealized P&L'}</small></td>`;
  };
  const displayTime = value => value ? new Date(value).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'}) + ' IST' : '—';
  async function mount() {
    await window.BrokerForms?.ready;
    const work = document.querySelector('.work'), nav = document.querySelector('.nav'), context = window.SectorPulseWorkspace;
    if (!work || !nav || document.getElementById('holdings') || !context?.holdings_review_available || window.self !== window.top) return;
    if (Array.isArray(context?.allowed_features) && context.allowed_features.includes('broker') && !context.allowed_features.includes('holdings')) context.allowed_features = [...context.allowed_features, 'holdings'];
    if (context && !context.admin && Array.isArray(context.allowed_features) && !context.allowed_features.includes('holdings')) return;
    const button = document.createElement('button'); button.type = 'button'; button.dataset.view = 'holdings'; button.textContent = 'Holdings review'; button.setAttribute('aria-pressed', 'false'); nav.append(button);
    const section = document.createElement('section'); section.id = 'holdings'; section.className = 'view';
    section.innerHTML = `<header class="head"><div><span class="label">PORTFOLIO DECISIONS · ADVISORY</span><h1>Holdings review</h1><small class="muted">Review every holding with completed daily and weekly trend evidence.</small></div><span class="status">Swing horizon</span></header>
      <section class="panel holdings-controls"><div class="holdings-toolbar"><label class="field">Broker<select id="holdings-broker"></select></label><label class="field">Analysis mode<select id="holdings-analysis-mode" aria-label="Holdings analysis mode"><option value="RULES_ONLY">Rule-based analysis</option><option value="CODEX_CHATGPT">AI-based · Codex ChatGPT account</option></select></label><div><button type="button" class="button" id="holdings-analyse">Analyse holdings & positions</button><button type="button" class="button" id="holdings-cancel" hidden>Stop after current batch</button></div><button type="button" class="button" id="holdings-export" disabled>Export review</button></div><p class="muted" id="holdings-scope">Delivery holdings for FYERS and Motilal Oswal; delivery holdings and open positions for Dhan; open derivative positions for Delta India. Suggestions do not submit orders or change stops. The mode applies to the next submitted job; saved output keeps its captured mode. Fundamentals appear only in AI-based analysis, using dated public company filings; quantities, acquisition cost and portfolio P&amp;L are excluded from AI evidence.</p><p id="holdings-status" role="status" aria-live="polite">Choose a broker, then analyse its portfolio.</p><progress id="holdings-progress" max="1" value="0" hidden aria-label="Holdings analysis progress"></progress></section>
      <section id="holdings-ai-feedback" class="panel" hidden><span class="label">AI COMPANY CONTEXT · REPORT ONLY</span><h2>Company financial feedback</h2><p class="muted">Financial evidence complements the captured holding recommendation; it does not change any holding, order or stop.</p><div id="holdings-fundamental-cards"></div></section>
      <div id="holdings-counts" class="holdings-counts" aria-label="Filter by suggested action"></div>
      <section class="panel"><div class="holdings-toolbar"><div><span class="label">REVIEW QUEUE</span><h2>Decision and supporting evidence</h2><p id="holdings-coverage" class="muted">No analysis yet.</p></div><label class="field">Show<select id="holdings-filter"><option value="ALL">All holdings</option>${Object.entries(labels).map(([key, text]) => `<option value="${key}">${text}</option>`).join('')}</select></label></div><div class="table-wrap"><table class="holdings-table"><thead><tr><th>Suggested action</th><th>Holding / contract</th><th>Quantity / average</th><th>Reference price</th><th>Profit / loss</th><th>Candidate protective level</th><th>Rationale and evidence</th><th class="holding-actions-heading">Actions</th></tr></thead><tbody id="holdings-rows"><tr><td colspan="8" class="empty">Your review will appear here. Missing evidence stays visible as Review needed.</td></tr></tbody></table></div></section>
      <details class="panel holdings-method"><summary>How suggestions are made</summary><p>Daily EMA20/EMA50 and the prior completed weekly EMA20 provide trend context. ATR14 measures volatility; RSI14 and the prior 20-session range identify extended profitable holdings.</p><ul><li><b>Hold:</b> aligned daily and weekly trends.</li><li><b>Trail:</b> aligned trends, a gain of at least one ATR and a candidate protective level beyond acquisition cost.</li><li><b>Exit:</b> daily EMA20/EMA50 and weekly trend oppose the holding or position.</li><li><b>Book profit:</b> gross profit, an extreme RSI and price at least two ATR from EMA20 near the range boundary.</li><li><b>Review needed:</b> stale or missing data, mixed trends, unsupported products, options, or an imminent futures expiry.</li></ul><p>Rules are transparent technical hypotheses, not a tested return forecast. They omit fundamental/news analysis and personal tax or risk plans. P&L excludes fees, taxes and funding. Price-return percentages are not returns on margin. Check existing strategy ownership and hedges before acting. A candidate stop is a review level, not a resting order; tighten an existing stop only.</p></details>`;
    work.append(section);
    const style = document.createElement('style'); style.textContent = `
      #holdings .holdings-toolbar{display:flex;align-items:end;justify-content:space-between;gap:18px;flex-wrap:wrap}#holdings .holdings-toolbar .field{min-width:180px}#holdings .holdings-counts{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:18px 0}#holdings .holdings-count{background:#11243a;border:1px solid #36516f;border-top:3px solid var(--decision,#95b4d0);color:inherit;text-align:left;padding:14px;cursor:pointer;border-radius:9px}#holdings .holdings-count strong{display:block;font:700 28px ui-monospace,monospace;margin:8px 0}#holdings .holdings-count[aria-pressed=true]{outline:2px solid #a9dcff;outline-offset:2px}#holdings .holdings-action{display:inline-block;padding:5px 9px;border:1px solid var(--decision);color:var(--decision);border-radius:5px;font-weight:800;white-space:nowrap}#holdings [data-action=EXIT]{--decision:#ff9c8b}#holdings [data-action=REVIEW_NEEDED]{--decision:#d7c2ed}#holdings [data-action=BOOK_PROFIT]{--decision:#f0c77b}#holdings [data-action=TRAIL]{--decision:#89ccef}#holdings [data-action=HOLD]{--decision:#92d2b4}#holdings td{vertical-align:top}#holdings td:first-child{position:static}#holdings td small{display:block;margin-top:6px;color:#aabdd0}#holdings .holdings-table{min-width:1050px}#holdings .holdings-table td:nth-child(7){min-width:300px;white-space:normal}#holdings .holdings-table td:last-child{white-space:normal}#holdings .holdings-table td:last-child p{margin:0 0 8px}#holdings .holdings-method{margin-top:18px}#holdings .holdings-method summary{cursor:pointer;font-weight:700}#holdings progress{width:100%;height:8px;accent-color:#89ccef}#holdings button:focus-visible,#holdings select:focus-visible{outline:3px solid #a9dcff;outline-offset:3px}@media(max-width:750px){#holdings .holdings-counts{grid-template-columns:repeat(2,minmax(0,1fr))}#holdings .holdings-toolbar{align-items:stretch}#holdings .holdings-toolbar>div{display:flex;gap:8px;flex-wrap:wrap}}`;
    document.head.append(style);
    const $ = id => document.getElementById(id);
    const broker = $('holdings-broker');
    const brokerNames={FYERS:'FYERS',DHAN:'Dhan',MOTILAL_OSWAL:'Motilal Oswal',DELTA_INDIA:'Delta India'};
    const owned=(window.BrokerForms?.accounts()||[]).filter(a=>brokerNames[a.broker]);
    for(const account of owned){const option=new Option(brokerNames[account.broker]+' · '+account.label,'account:'+account.id);option.dataset.savedBrokerAccount=account.id;option.dataset.broker=account.broker;option.disabled=account.configured===false;broker.add(option);}
    if(!window.BrokerForms)for(const value of ['FYERS','DELTA_INDIA']){if(context?.workspace?.broker&&context.workspace.broker!==value)continue;broker.add(new Option(brokerNames[value],value));}
    const initial=window.BrokerForms?.initial('holdings')||context?.workspace?.id;
    const remembered=initial&&[...broker.options].find(o=>o.dataset.savedBrokerAccount===initial&&!o.disabled);
    if(remembered)broker.value=remembered.value;
    else if([...broker.options].some(o=>!o.disabled))broker.value=[...broker.options].find(o=>!o.disabled).value;
    const selectedAccount=()=>window.BrokerForms?.account('holdings')||owned.find(a=>'account:'+a.id===broker.value)||null;
    const selectedBroker=()=>selectedAccount()?.broker||broker.value;
    const selectedId=()=>selectedAccount()?.id||context?.workspace?.id||'dashboard';
    const mode=$('holdings-analysis-mode'),modeKey=()=> 'sector-pulse:holdings-ai-mode:'+selectedId();
    const restoreMode=()=>{try{mode.value=localStorage.getItem(modeKey())==='CODEX_CHATGPT'?'CODEX_CHATGPT':'RULES_ONLY';}catch{mode.value='RULES_ONLY';}};
    restoreMode();mode.onchange=()=>{try{localStorage.setItem(modeKey(),mode.value);}catch{}};

    let rows = [], report = null, busy = false, cancel = false, activeJob = null, stopSent = false, reviewedJob = null;
    const activate = () => {
      document.querySelectorAll('[data-view]').forEach(item => {const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active));});
      document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
      try {localStorage.setItem('sector-pulse:selected-view', 'holdings');} catch {}
    };
    button.onclick = activate;
    try {if (new URLSearchParams(location.search).get('view') === 'holdings' || localStorage.getItem('sector-pulse:selected-view') === 'holdings') activate();} catch {if (new URLSearchParams(location.search).get('view') === 'holdings') activate();}
    const render = () => {
      const counts = Object.fromEntries(Object.keys(labels).map(action => [action, rows.filter(row => row.action === action).length]));
      $('holdings-counts').replaceChildren();
      for (const [action, text] of Object.entries(labels)) {
        const card = document.createElement('button'); card.type = 'button'; card.className = 'holdings-count'; card.dataset.action = action;
        card.setAttribute('aria-pressed', String($('holdings-filter').value === action)); card.innerHTML = `${text}<strong>${counts[action]}</strong><small>holding${counts[action] === 1 ? '' : 's'} reviewed</small>`;
        card.onclick = () => {$('holdings-filter').value = $('holdings-filter').value === action ? 'ALL' : action; render();}; $('holdings-counts').append(card);
      }
      const filtered = rows.filter(row => $('holdings-filter').value === 'ALL' || row.action === $('holdings-filter').value).sort((a,b) => priority[a.action] - priority[b.action] || a.symbol.localeCompare(b.symbol));
      const pricedValue = report?.portfolio?.priced_holdings_value;
      for (const row of rows) row.priced_holdings_weight_pct = pricedValue > 0 && row.kind === 'DELIVERY_EQUITY' && row.price > 0 && row.quantity > 0 ? +(row.price * row.quantity / pricedValue * 100).toFixed(2) : null;
      $('holdings-rows').innerHTML = filtered.length ? filtered.map(row => {
        const evidence = row.evidence || {}, weight = pricedValue > 0 && row.kind === 'DELIVERY_EQUITY' && row.price > 0 && row.quantity > 0 ? row.price * row.quantity / pricedValue * 100 : null;
        return `<tr data-action="${escape(row.action)}"><td><span class="holdings-action">${labels[row.action]}</span><small>${row.kind === 'DELIVERY_EQUITY' ? 'Delivery' : row.quantity < 0 ? 'Short contract' : 'Contract / other'}</small></td><td><b>${escape(row.symbol)}</b><small>${escape(row.holding_type || row.kind.replaceAll('_',' '))}</small>${weight == null ? '' : `<small>${numeric(weight)}% of priced holdings${weight >= 20 ? ' · concentrated' : ''}</small>`}</td><td>${numeric(row.quantity)}<small>Avg ${numeric(row.average_price)} ${escape(row.currency)}</small></td><td>${numeric(row.price)} ${escape(row.currency)}<small>${escape(evidence.price_basis || 'Broker snapshot')}</small></td>${pnlMarkup(row)}<td>${numeric(row.candidate_stop)}${row.candidate_stop == null ? '' : ` ${escape(row.currency)}<small>Candidate only · tighten existing stop</small>`}</td><td>${row.ai_commentary?.rationale?`<p>${escape(row.ai_commentary.rationale)}</p>`:''}${row.reasons.map(reason => `<p>${escape(reason)}</p>`).join('')}<small>Daily session: ${escape(evidence.completed_session || 'Unavailable')} · ${escape(evidence.price_basis || 'No validated quote')}</small><small>EMA20 ${numeric(evidence.ema20)} · EMA50 ${numeric(evidence.ema50)} · ATR14 ${numeric(evidence.atr14)} · RSI14 ${numeric(evidence.rsi14)}</small><small>Quote: ${escape(displayTime(evidence.quote_timestamp))}</small><details><summary>Limits and assumptions</summary>${row.limitations.map(note => `<p>${escape(note)}</p>`).join('')}</details></td></tr>`;
      }).join('') : `<tr><td colspan="8" class="empty">${report ? 'No holdings or positions in this saved review match this view. Run a fresh analysis to read the current broker inventory.' : 'Choose a broker, then analyse its portfolio. Missing evidence will stay visible.'}</td></tr>`;
      if (report) $('holdings-coverage').textContent = `${report.ai_provider==='CODEX_CHATGPT'?'AI-based saved analysis':'Rule-based saved analysis'} · ${rows.length}/${report.total} reviewed · ${report.broker} · account fetched ${displayTime(report.as_of)} · ${report.scope}. ${pricedValue == null ? '' : `Priced delivery subtotal ${numeric(pricedValue)} INR (${report.portfolio.priced_rows} rows). Weights ${report.portfolio.complete ? 'exclude unpriced holdings' : 'are provisional'}.`}`;
      $('holdings-ai-feedback').hidden=report?.ai_provider!=='CODEX_CHATGPT';
      $('holdings-fundamental-cards').innerHTML=report?.ai_provider==='CODEX_CHATGPT'?filtered.map(row=>`<article><h3>${escape(row.symbol)} · ${escape(labels[row.action]||row.action)}</h3>${window.CompanyFundamentalsReport?.html(row.fundamentals,true)||''}</article>`).join(''):'';
      window.HoldingsReviewTools?.render(section,{report,rows:filtered,job:reviewedJob,broker:selectedBroker(),accountId:selectedId()});
    };
    $('holdings-filter').onchange = render;
    broker.onchange = () => {restoreMode();activeJob=null;stopSent=false;cancel=false;$('holdings-cancel').hidden=true;rows = []; report = null; $('holdings-export').disabled = true; $('holdings-coverage').textContent = 'No analysis for the selected broker yet.'; $('holdings-status').textContent = 'Choose Analyse holdings & positions to load this broker.'; render();if(selectedAccount())window.BrokerForms?.onChange('holdings',selectedAccount());};
    const sameJobScope = job => job?.feature === 'holdings' && job.kind === 'ANALYSIS' && job.request?.account_id === selectedId() && job.request?.payload?.broker === selectedBroker();
    const restoreJob = job => {
      if (!sameJobScope(job)) return;
      if (job.terminal && !Array.isArray(job.output?.rows)) {
        $('holdings-cancel').hidden = true;
        $('holdings-progress').hidden = true;
        $('holdings-status').textContent = `${job.status} · ${job.error || job.message || 'No portfolio output was produced.'} Check the selected broker connection and run a fresh analysis.`;
        $('holdings-coverage').textContent = 'Current portfolio could not be read; no current positions have been verified.';
        return;
      }
      if (!Array.isArray(job.output?.rows)) return;
      reviewedJob = job; report = job.output; rows = report.rows.slice(); render();
      $('holdings-export').disabled = false;
      $('holdings-progress').max = report.total || 1; $('holdings-progress').value = report.analysed || 0;
      if(job.terminal){$('holdings-cancel').hidden=true;}
      const stale = !report.as_of || Date.now() - Date.parse(report.as_of) > 600000;
      $('holdings-status').textContent = `${stale ? 'STALE saved review · run a fresh analysis · ' : ''}${job.status} · ${rows.length}/${report.total} reviewed. Saved advisory output.`;
    };
    const restoreLatest = () => {
      const records = [...(window.SectorPulseJobs?.records?.values() || [])].sort((a,b) => b.job.created-a.job.created);
      const saved = records.find(record => sameJobScope(record.job) && (record.job.output || record.job.terminal));
      if (saved) restoreJob(saved.job);
    };
    const stopAnalysis = async () => {
      if (!activeJob || stopSent) return;
      stopSent = true;
      try {await window.SectorPulseJobs.client.cancel(activeJob.base, activeJob.job.job_id);}
      catch (error) {stopSent = false; $('holdings-status').textContent = error.message;}
    };
    window.addEventListener('sector-pulse-job-submitted', event => {
      if (!busy || !sameJobScope(event.detail.job)) return;
      activeJob = event.detail; if (cancel) stopAnalysis();
    });
    window.addEventListener('sector-pulse-job-update', event => {
      if (activeJob?.job.job_id !== event.detail.job.job_id) return;
      activeJob=event.detail;restoreJob(event.detail.job);
    });
    window.addEventListener('sector-pulse-job-output', event => restoreJob(event.detail.job));
    broker.addEventListener('change', restoreLatest);
    window.addEventListener('sector-pulse-jobs-refreshed', () => {if (!busy && (!activeJob || activeJob.job.terminal)) restoreLatest();});
    if (!section.querySelector('[data-durable-jobs-open]')) {
      const saved = document.createElement('button'); saved.type = 'button'; saved.textContent = 'Saved jobs & outputs'; saved.dataset.durableJobsOpen = '1';
      saved.className = 'button holdings-secondary'; saved.onclick = () => window.SectorPulseJobs?.open(); $('holdings-export').before(saved);
    }
    $('holdings-cancel').onclick = () => {cancel = true; $('holdings-status').textContent = 'Stop requested; saved partial output will be retained.'; stopAnalysis();};
    $('holdings-analyse').onclick = async () => {
      if (busy) return;
      busy = true; cancel = false; activeJob = null; stopSent = false; rows = []; report = null;
      $('holdings-coverage').textContent = 'Reading the selected broker portfolio…'; render(); broker.disabled = true;mode.disabled=true; $('holdings-analyse').disabled = true;
      $('holdings-cancel').hidden = false; $('holdings-export').disabled = true; $('holdings-progress').hidden = false; $('holdings-progress').value = 0;
      try {
        $('holdings-status').textContent = 'Portfolio analysis submitted as a server job. It continues if you leave this page.';
        const headers = {'Content-Type':'application/json','X-Job-Return-Accepted':'1'}; if (context?.csrf) headers['X-CSRF-Token'] = context.csrf;
        const options={method:'POST',headers,body:JSON.stringify({broker:selectedBroker(),ai_provider:mode.value,account_id:selectedId()==='dashboard'?undefined:selectedId(),offset:0,limit:1,inventory_only:1})};
        const response = await (window.BrokerForms?window.BrokerForms.fetch('holdings','/api/holdings-analysis/analyze',options):fetch('/api/holdings-analysis/analyze',options)), data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Holdings analysis failed.');
        if(data.job_accepted){$('holdings-status').textContent='Holdings job accepted. You can continue working; completed and partial output remains saved.';return;}
        report = data; rows = data.rows; render();
        $('holdings-progress').max = data.total || 1; $('holdings-progress').value = data.analysed;
        $('holdings-status').textContent = report.total === 0 ? 'No holdings or open derivative positions were returned for this broker.' : `Review complete · ${rows.length}/${report.total} reviewed. ${rows.filter(row => row.action === 'REVIEW_NEEDED').length} marked Review needed. Suggestions are advisory.`;
      } catch (error) { $('holdings-status').textContent = `${error.message} ${rows.length ? `Partial review retained: ${rows.length} rows.` : 'No complete portfolio review was produced.'}`; }
      finally {busy = false; broker.disabled = false;mode.disabled=false; $('holdings-analyse').disabled = false; $('holdings-cancel').hidden = !activeJob||!!activeJob.job.terminal; $('holdings-export').disabled = !report;}
    };
    restoreLatest();
    $('holdings-export').onclick = () => {
      const url = URL.createObjectURL(new Blob([JSON.stringify({...report, rows, complete: rows.length === report.total}, null, 2)], {type:'application/json'}));
      const link = document.createElement('a'); link.href = url; link.download = `holdings-review-${report.broker}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
    };
    render();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
