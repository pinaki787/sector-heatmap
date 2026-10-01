/* Display forming candles separately from unchanged completed-close signals. */
(function (root) {
  function signals(candles, fast = 10, slow = 30) {
    if (!Number.isInteger(fast) || !Number.isInteger(slow) || fast < 1 || slow <= fast || slow > 100) throw Error('Use whole-number periods: 1 ≤ fast < slow ≤ 100.');
    const unique = new Map();
    for (const c of candles.filter(c => !c.is_forming)) {
      const prior = unique.get(c.timestamp);
      if (prior && ['open','high','low','close','volume'].some(k => prior[k] !== c[k])) throw Error('Conflicting duplicate broker candles; signals blocked.');
      unique.set(c.timestamp, c);
    }
    const rows = [...unique.values()].sort((a,b) => a.timestamp - b.timestamp);
    let f, s;
    return rows.map((c, i) => {
      if (![c.timestamp, c.open, c.high, c.low, c.close].every(Number.isFinite) || (i && c.timestamp <= rows[i - 1].timestamp)) throw Error('Candle data must be finite, unique and chronological.');
      f = i ? f + 2 / (fast + 1) * (c.close - f) : c.close;
      s = i ? s + 2 / (slow + 1) * (c.close - s) : c.close;
      const signal = i >= slow * 3 && c.close > f ? 'CALL' : i >= slow * 3 && c.close < f ? 'PUT' : null;
      return { ...c, fast: f, slow: s, signal };
    });
  }
  function rsiSignals(candles,rsiLength=14,smaLength=14,maType="SMA"){
    const chart=root.EmaCloudChart || (typeof require==='function'?require('./ema-cloud-chart.js'):null);
    const rows=chart.displayRows(candles.filter(c=>!c.is_forming),10,30,rsiLength,smaLength,maType);return rows.map((c,i)=>{const p=rows[i-1];return {...c,signal:p?.rsiMa!=null&&c.rsiMa!=null?(p.rsi<=p.rsiMa&&c.rsi>c.rsiMa?'CALL':p.rsi>=p.rsiMa&&c.rsi<c.rsiMa?'PUT':null):null};});
  }
  function mount(initialView) {
    const active = initialView === 'ema-cross';
    document.querySelector('[data-view="ema-band"]').insertAdjacentHTML('afterend', `<button type="button" data-view="ema-cross" class="${active ? 'active' : ''}" aria-pressed="${active}">RSI based SMA</button>`);
    document.querySelector('.work').insertAdjacentHTML('beforeend', `<section id="ema-cross" class="view ${active ? 'active' : ''}">
      <header class="head"><div><span class="label">RSI MOVING AVERAGE STRATEGY</span><h1>RSI based SMA</h1><small class="muted">RSI 14 · RSI SMA 14 · Completed close</small></div><div class="status">Signals only</div></header>
      <section class="panel"><div class="step-title"><div><span class="label">CONFIGURATION</span><h2>RSI based SMA</h2></div><span class="badge">CANDLE CLOSE</span></div>
      <div class="field-grid" style="margin-top:14px"><label class="field">Underlying search<input id="cross-search" placeholder="NIFTY, SENSEX, RELIANCE…" autocomplete="off"></label><label class="field">Broker-master instrument<select id="cross-symbol"><option value="">Search and select an underlying</option></select></label>
      <label class="field">Signal timeframe<select id="cross-timeframe"><option>1 minute</option><option>2 minutes</option><option>3 minutes</option><option selected>5 minutes</option><option>10 minutes</option><option>15 minutes</option><option>30 minutes</option><option>1 hour</option></select></label><label class="field">RSI length<input id="cross-rsi-length" type="number" value="14" min="1" max="100"></label><label class="field">RSI smoothing<select id="cross-ma-type"><option selected>SMA</option><option>EMA</option></select></label><label class="field">RSI MA length<input id="cross-sma-length" type="number" value="14" min="1" max="100" step="1"></label><label class="field">Signal confirmation<input value="Completed candle only" readonly></label></div>
      <div id="cross-status" class="handoff-status" role="status">Select an instrument to load completed candles.</div>
      <div class="risk-strip"><div><b id="cross-trend">—</b><small>Latest completed-close setup</small></div><div><b id="cross-event">—</b><small>Latest completed bar signal</small></div><div><b id="cross-values">14 / 14</b><small>RSI / selected MA values</small></div><div><b>CANDLE CLOSE</b><small>Execution state</small></div></div></section>
      <section class="panel" style="margin-top:15px"><span class="label">PRICE & MOVING AVERAGES</span><h2>Live market chart</h2><small class="muted">Forming candles · RSI / selected RSI MA · Volume · Optional EMA overlays · Strategy signals remain completed-close only</small><div id="cross-pnl" role="status" style="padding:12px;border-radius:8px;background:#132a27;margin-top:12px;font-weight:600">Position P&amp;L: ₹0.00 · Realized: ₹0.00 · Before fees</div><div id="cross-chart" class="chart-empty">Select an instrument to show the chart.</div></section>
      <section class="panel" style="margin-top:15px"><span class="label">STRATEGY RULES</span><div class="choice-row"><span class="choice">ATM Call: completed RSI crosses above the selected RSI MA.</span><span class="choice">ATM Put: completed RSI crosses below the selected RSI MA.</span><span class="choice">Call exit: later completed RSI crosses below its MA. Put exit: later completed RSI crosses above its MA. Equality holds.</span></div><p class="muted">RSI uses Wilder smoothing; choose SMA or EMA for its moving average. Signals and opposite-cross exits use completed candles only. One owned position at a time.</p><div id="cross-history"></div></section></section>`);
    const el = id => document.getElementById('cross-' + id);
    const stamp = t => new Date(t * 1000).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit' }) + ' IST';
    async function get(url) { const response = await fetch(url); const data = await response.json(); if (!response.ok || data.error) throw Error(data.error || 'Data request failed'); return data; }
    let version = 0, searchVersion = 0, timer, marketChart;
    function clear() { version++; marketChart?.destroy(); marketChart=null; el('chart').classList.add('chart-empty'); el('chart').textContent = 'Select an instrument to show the chart.'; el('history').textContent = ''; ['trend', 'event', 'values'].forEach(id => el(id).textContent = '—'); el('status').textContent = 'Chart updates automatically after selecting an instrument.'; }
    ['symbol','timeframe','rsi-length','sma-length','ma-type'].forEach(id => el(id).addEventListener('change', () => {clear(); if(el('symbol').value)load();}));
    el('search').addEventListener('input', () => {
      clear(); clearTimeout(timer); const seq = ++searchVersion; el('symbol').replaceChildren(new Option('Search and select an underlying', ''));
      const q = el('search').value.trim(); if (q.length < 2) return;
      timer = setTimeout(async () => { try { const data = await get('/api/ema-band/underlying-search?q=' + encodeURIComponent(q)); if (seq !== searchVersion) return; for (const item of data.matches || []) el('symbol').add(new Option(item.underlying + ' · ' + item.symbol, item.symbol)); el('status').textContent = data.matches?.length ? 'Select an instrument to display its chart.' : 'No matching instruments.'; } catch (e) { if (seq === searchVersion) el('status').textContent = e.message; } }, 300);
    });
    let loading = false, nextAttemptAt=0;
    async function load() {
      if(loading || Date.now()<nextAttemptAt || !el('symbol').value)return;
      loading=true; const seq = version;
      try {
        const rsiLength=Number(el('rsi-length').value),smaLength=Number(el('sma-length').value),maType=el('ma-type').value;root.EmaCloudChart.displayRows([],10,30,rsiLength,smaLength,maType);
        if (!el('symbol').value) throw Error('Select a broker-master instrument first.');
        if(!marketChart)el('status').textContent = 'Loading broker candles…';
        const data = await get('/api/ema-band/chart?' + new URLSearchParams({symbol:el('symbol').value, timeframe:el('timeframe').value, ema_length:'30', bars:'500',references:marketChart?.wantsReferences()?'1':'0'}));
        if (seq !== version) return;
        const rows=rsiSignals(data.candles||[],rsiLength,smaLength,maType);if(rows.length<=rsiLength+(maType==='SMA'?smaLength-1:0))throw Error('Insufficient completed candles for RSI/SMA warm-up.');
        const last = rows.at(-1), events = rows.filter((c,i) => c.signal && c.signal !== rows[i-1]?.signal);
        el('trend').textContent = last.rsi > last.rsiMa ? 'BULLISH' : last.rsi < last.rsiMa ? 'BEARISH' : 'NEUTRAL';
        el('event').textContent = last.signal || 'NO FRESH CROSS'; el('values').textContent = last.rsi.toFixed(2) + ' / ' + last.rsiMa.toFixed(2);
        el('status').textContent = `${data.symbol} · ${data.timeframe} · Last completed bar: ${stamp(last.timestamp)} · Forming candle shown; signals use completed closes.`;
        if(!marketChart)marketChart=root.EmaCloudChart.mount(el('chart'));
        marketChart.update(data,10,30,rsiLength,smaLength,maType);if(data.history_error||data.history_gap)marketChart.error(data.history_error||'Latest completed candle awaiting reconciliation');else marketChart.healthy();nextAttemptAt=0;
        const history=el('history');history.replaceChildren();
        const title=document.createElement('p');title.textContent='Recent completed RSI crossover events';title.style.cssText='font-weight:600;margin:20px 0 6px';
        const note=document.createElement('p');note.className='muted';note.textContent='Signal events only — these rows are not executed fills. Actual fills appear in Position history.';note.style.cssText='font-size:12px;line-height:1.6;margin:0 0 12px';history.append(title,note);
        if(!events.length){const empty=document.createElement('p');empty.textContent='No completed crossovers after warm-up in loaded history.';history.append(empty);}
        else {
          const wrap=document.createElement('div');wrap.style.cssText='overflow-x:auto;border:1px solid #29374d;border-radius:8px';
          const table=document.createElement('table');table.style.cssText='width:100%;min-width:360px;border-collapse:collapse;font-size:12px;text-align:left';table.setAttribute('aria-label','Recent RSI crossover signal events');
          const head=table.createTHead().insertRow();for(const name of ['Completed candle · IST','RSI crossover','Underlying close']){const th=document.createElement('th');th.textContent=name;th.style.cssText='padding:12px;border-bottom:1px solid #35465e';head.append(th);}
          const body=table.createTBody();for(const c of events.slice(-8).reverse()){const row=body.insertRow();for(const value of [stamp(c.timestamp),c.signal==='CALL'?'CALL · crossed above RSI MA':'PUT · crossed below RSI MA','₹'+c.close.toFixed(2)]){const cell=row.insertCell();cell.textContent=value;cell.style.cssText='padding:12px;border-bottom:1px solid #26374d;line-height:1.5';}}
          wrap.append(table);history.append(wrap);
        }
      } catch (e) { if (seq === version) {el('status').textContent = 'Chart unavailable: ' + e.message;marketChart?.error(e.message);nextAttemptAt=Date.now()+30000;} } finally { loading = false; if(seq !== version && el('symbol').value)load(); }
    }
    setInterval(() => {if(!document.hidden && sectionVisible())load();},1000);
    function sectionVisible(){return document.getElementById('ema-cross').classList.contains('active');}
  }
  root.EmaCrossover = { signals, rsiSignals, mount };
  if (typeof module !== 'undefined') module.exports = { signals, rsiSignals };
})(typeof window === 'undefined' ? globalThis : window);
