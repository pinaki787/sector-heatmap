/* Read-only broker portfolio review. No order endpoints or strategy mutations. */
(() => {
  'use strict';
  const labels = {HOLD: 'Hold', TRAIL: 'Trail', EXIT: 'Exit', BOOK_PROFIT: 'Book profit', REVIEW_NEEDED: 'Review needed'};
  const priority = {EXIT: 0, REVIEW_NEEDED: 1, BOOK_PROFIT: 2, TRAIL: 3, HOLD: 4};
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const numeric = value => value == null || !Number.isFinite(Number(value)) ? '—' : new Intl.NumberFormat('en-IN', {maximumFractionDigits: 4}).format(Number(value));
  const displayTime = value => value ? new Date(value).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'}) + ' IST' : '—';
  function mount() {
    const work = document.querySelector('.work'), nav = document.querySelector('.nav'), context = window.SectorPulseWorkspace;
    if (!work || !nav || document.getElementById('holdings') || !context?.holdings_review_available || window.self !== window.top) return;
    if (Array.isArray(context?.allowed_features) && context.allowed_features.includes('broker') && !context.allowed_features.includes('holdings')) context.allowed_features = [...context.allowed_features, 'holdings'];
    if (context && !context.admin && Array.isArray(context.allowed_features) && !context.allowed_features.includes('holdings')) return;
    const button = document.createElement('button'); button.type = 'button'; button.dataset.view = 'holdings'; button.textContent = 'Holdings review'; button.setAttribute('aria-pressed', 'false'); nav.append(button);
    const section = document.createElement('section'); section.id = 'holdings'; section.className = 'view';
    section.innerHTML = `<header class="head"><div><span class="label">PORTFOLIO DECISIONS · ADVISORY</span><h1>Holdings review</h1><small class="muted">Review every holding with completed daily and weekly trend evidence.</small></div><span class="status">Swing horizon</span></header>
      <section class="panel holdings-controls"><div class="holdings-toolbar"><label class="field">Broker<select id="holdings-broker"></select></label><div><button type="button" class="button" id="holdings-analyse">Analyse all holdings</button><button type="button" class="button" id="holdings-cancel" hidden>Stop after current batch</button></div><button type="button" class="button" id="holdings-export" disabled>Export review</button></div><p class="muted" id="holdings-scope">Delivery holdings for FYERS; open derivative positions for Delta India. Suggestions do not submit orders or change stops.</p><p id="holdings-status" role="status" aria-live="polite">Choose a broker, then analyse its portfolio.</p><progress id="holdings-progress" max="1" value="0" hidden aria-label="Holdings analysis progress"></progress></section>
      <div id="holdings-counts" class="holdings-counts" aria-label="Filter by suggested action"></div>
      <section class="panel"><div class="holdings-toolbar"><div><span class="label">REVIEW QUEUE</span><h2>Decision and supporting evidence</h2><p id="holdings-coverage" class="muted">No analysis yet.</p></div><label class="field">Show<select id="holdings-filter"><option value="ALL">All holdings</option>${Object.entries(labels).map(([key, text]) => `<option value="${key}">${text}</option>`).join('')}</select></label></div><div class="table-wrap"><table class="holdings-table"><thead><tr><th>Suggested action</th><th>Holding / contract</th><th>Quantity / average</th><th>Reference price / gross P&L</th><th>Candidate protective level</th><th>Rationale and evidence</th></tr></thead><tbody id="holdings-rows"><tr><td colspan="6" class="empty">Your review will appear here. Missing evidence stays visible as Review needed.</td></tr></tbody></table></div></section>
      <details class="panel holdings-method"><summary>How suggestions are made</summary><p>Daily EMA20/EMA50 and the prior completed weekly EMA20 provide trend context. ATR14 measures volatility; RSI14 and the prior 20-session range identify extended profitable holdings.</p><ul><li><b>Hold:</b> aligned daily and weekly trends.</li><li><b>Trail:</b> aligned trends, a gain of at least one ATR and a candidate protective level beyond acquisition cost.</li><li><b>Exit:</b> daily EMA20/EMA50 and weekly trend oppose the holding or position.</li><li><b>Book profit:</b> gross profit, an extreme RSI and price at least two ATR from EMA20 near the range boundary.</li><li><b>Review needed:</b> stale or missing data, mixed trends, unsupported products, options, or an imminent futures expiry.</li></ul><p>Rules are transparent technical hypotheses, not a tested return forecast. They omit fundamental/news analysis and personal tax or risk plans. P&L excludes fees, taxes and funding. Price-return percentages are not returns on margin. Check existing strategy ownership and hedges before acting. A candidate stop is a review level, not a resting order; tighten an existing stop only.</p></details>`;
    work.append(section);
    const style = document.createElement('style'); style.textContent = `
      #holdings .holdings-toolbar{display:flex;align-items:end;justify-content:space-between;gap:18px;flex-wrap:wrap}#holdings .holdings-toolbar .field{min-width:180px}#holdings .holdings-counts{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:18px 0}#holdings .holdings-count{background:#11243a;border:1px solid #36516f;border-top:3px solid var(--decision,#95b4d0);color:inherit;text-align:left;padding:14px;cursor:pointer;border-radius:9px}#holdings .holdings-count strong{display:block;font:700 28px ui-monospace,monospace;margin:8px 0}#holdings .holdings-count[aria-pressed=true]{outline:2px solid #a9dcff;outline-offset:2px}#holdings .holdings-action{display:inline-block;padding:5px 9px;border:1px solid var(--decision);color:var(--decision);border-radius:5px;font-weight:800;white-space:nowrap}#holdings [data-action=EXIT]{--decision:#ff9c8b}#holdings [data-action=REVIEW_NEEDED]{--decision:#d7c2ed}#holdings [data-action=BOOK_PROFIT]{--decision:#f0c77b}#holdings [data-action=TRAIL]{--decision:#89ccef}#holdings [data-action=HOLD]{--decision:#92d2b4}#holdings td{vertical-align:top}#holdings td:first-child{position:static}#holdings td small{display:block;margin-top:6px;color:#aabdd0}#holdings .holdings-table{min-width:1050px}#holdings .holdings-table td:last-child{min-width:320px;white-space:normal}#holdings .holdings-table td:last-child p{margin:0 0 8px}#holdings .holdings-method{margin-top:18px}#holdings .holdings-method summary{cursor:pointer;font-weight:700}#holdings progress{width:100%;height:8px;accent-color:#89ccef}#holdings button:focus-visible,#holdings select:focus-visible{outline:3px solid #a9dcff;outline-offset:3px}@media(max-width:750px){#holdings .holdings-counts{grid-template-columns:repeat(2,minmax(0,1fr))}#holdings .holdings-toolbar{align-items:stretch}#holdings .holdings-toolbar>div{display:flex;gap:8px;flex-wrap:wrap}}`;
    document.head.append(style);
    const $ = id => document.getElementById(id);
    const broker = $('holdings-broker');
    for (const value of ['FYERS', 'DELTA_INDIA']) {
      if (context?.workspace?.broker && context.workspace.broker !== value) continue;
      broker.add(new Option(value === 'FYERS' ? 'FYERS' : 'Delta India', value));
    }
    let rows = [], report = null, busy = false, cancel = false;
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
        return `<tr data-action="${escape(row.action)}"><td><span class="holdings-action">${labels[row.action]}</span><small>${row.kind === 'DELIVERY_EQUITY' ? 'Delivery' : row.quantity < 0 ? 'Short contract' : 'Contract / other'}</small></td><td><b>${escape(row.symbol)}</b><small>${escape(row.holding_type || row.kind.replaceAll('_',' '))}</small>${weight == null ? '' : `<small>${numeric(weight)}% of priced holdings${weight >= 20 ? ' · concentrated' : ''}</small>`}</td><td>${numeric(row.quantity)}<small>Avg ${numeric(row.average_price)} ${escape(row.currency)}</small></td><td>${numeric(row.price)} ${escape(row.currency)}<small>Gross ${numeric(row.gross_pnl)} ${escape(row.currency)}</small><small>${numeric(row.gross_return_pct)}${row.gross_return_pct == null ? '' : '% price return'}</small>${row.broker_unrealized_pnl == null ? '' : `<small>Broker unrealized ${numeric(row.broker_unrealized_pnl)}</small>`}</td><td>${numeric(row.candidate_stop)}${row.candidate_stop == null ? '' : ` ${escape(row.currency)}<small>Candidate only · tighten existing stop</small>`}</td><td>${row.reasons.map(reason => `<p>${escape(reason)}</p>`).join('')}<small>Daily session: ${escape(evidence.completed_session || 'Unavailable')} · ${escape(evidence.price_basis || 'No validated quote')}</small><small>EMA20 ${numeric(evidence.ema20)} · EMA50 ${numeric(evidence.ema50)} · ATR14 ${numeric(evidence.atr14)} · RSI14 ${numeric(evidence.rsi14)}</small><small>Quote: ${escape(displayTime(evidence.quote_timestamp))}</small><details><summary>Limits and assumptions</summary>${row.limitations.map(note => `<p>${escape(note)}</p>`).join('')}</details></td></tr>`;
      }).join('') : `<tr><td colspan="6" class="empty">${report ? 'No holdings match this view.' : 'Choose a broker, then analyse its portfolio. Missing evidence will stay visible.'}</td></tr>`;
      if (report) $('holdings-coverage').textContent = `${rows.length}/${report.total} reviewed · ${report.broker} · account fetched ${displayTime(report.as_of)} · ${report.scope}. ${pricedValue == null ? '' : `Priced delivery subtotal ${numeric(pricedValue)} INR (${report.portfolio.priced_rows} rows). Weights ${report.portfolio.complete ? 'exclude unpriced holdings' : 'are provisional'}.`}`;
    };
    $('holdings-filter').onchange = render;
    broker.onchange = () => {rows = []; report = null; $('holdings-export').disabled = true; $('holdings-coverage').textContent = 'No analysis for the selected broker yet.'; $('holdings-status').textContent = 'Choose Analyse all holdings to load this broker.'; render();};
    $('holdings-cancel').onclick = () => {cancel = true; $('holdings-status').textContent = 'Stopping after the current read-only batch completes…';};
    $('holdings-analyse').onclick = async () => {
      if (busy) return;
      busy = true; cancel = false; rows = []; report = null; $('holdings-coverage').textContent = 'Reading the selected broker portfolio…'; render(); broker.disabled = true; $('holdings-analyse').disabled = true;
      $('holdings-cancel').hidden = false; $('holdings-export').disabled = true; $('holdings-progress').hidden = false; $('holdings-progress').value = 0;
      let offset = 0, capture = null;
      try {
        do {
          $('holdings-status').textContent = `Reading ${broker.value} holdings and completed candles… ${rows.length} reviewed. This may take several seconds per batch.`;
          const query = new URLSearchParams({broker: broker.value, offset, limit: 1}); if (capture) query.set('capture_id', capture); else query.set('inventory_only', '1');
          const response = await fetch('/api/holdings-analysis?' + query, {cache: 'no-store'}), data = await response.json();
          if (!response.ok) throw new Error(data.error || 'Holdings analysis failed.');
          capture = data.capture_id; report = data; rows.push(...data.rows); offset = data.next_offset;
          $('holdings-progress').max = data.total || 1; $('holdings-progress').value = data.analysed;
          render();
          // Keep the entire portfolio visible; continue in small batches without order calls.
          if (offset != null && !cancel) await new Promise(resolve => setTimeout(resolve, 1000));
        } while (offset != null && !cancel);
        $('holdings-status').textContent = report.total === 0 ? 'No holdings or open derivative positions were returned for this broker.' : `${cancel && offset != null ? 'Stopped · partial review' : 'Review complete'} · ${rows.length}/${report.total} reviewed. ${rows.filter(row => row.action === 'REVIEW_NEEDED').length} marked Review needed. Suggestions are advisory.`;
      } catch (error) { $('holdings-status').textContent = `${error.message} ${rows.length ? `Partial review retained: ${rows.length} rows.` : 'No complete portfolio review was produced.'}`; }
      finally {busy = false; broker.disabled = false; $('holdings-analyse').disabled = false; $('holdings-cancel').hidden = true; $('holdings-export').disabled = !report;}
    };
    $('holdings-export').onclick = () => {
      const url = URL.createObjectURL(new Blob([JSON.stringify({...report, rows, complete: rows.length === report.total}, null, 2)], {type:'application/json'}));
      const link = document.createElement('a'); link.href = url; link.download = `holdings-review-${report.broker}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
    };
    render();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
