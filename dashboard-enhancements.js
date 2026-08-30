(() => {
  const analysisRefreshMs = 5 * 60 * 1000
  const accountRefreshMs = 10 * 1000
  const periods = ['daily', 'weekly', 'monthly', 'annual']
  const timeframeOrder = ['15m', '1h', 'daily', 'weekly']
  const { filterAndSortSectors } = window.SectorDashboardModel
  const stateClass = value => value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral'
  const scrollBehavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character])
  const money = value => value == null ? '—' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(Number(value))
  const number = (value, suffix = '') => value == null ? '—' : `${Number(value).toFixed(1)}${suffix}`
  const time = value => value ? new Date(value).toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'

  document.body.innerHTML = `<style>
    :root{color-scheme:dark;--bg:#09111f;--surface:#101d31;--surface-2:#0d192a;--border:#233c59;--text:#edf4ff;--muted:#91a7c4;--positive:#60dca9;--negative:#ff92a1;--neutral:#d0b66a;--focus:#a9dcff}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px Inter,system-ui,sans-serif}.desk{min-height:100vh;display:grid;grid-template-columns:250px minmax(0,1fr)}button,select{font:inherit}.side{padding:24px 16px;background:var(--surface-2);border-right:1px solid var(--border);display:flex;flex-direction:column;gap:24px}.brand{padding:4px 10px}.brand b{font-size:18px}.brand small,.label,.muted{display:block;color:var(--muted);font-size:11px}.nav{display:grid;gap:7px}.nav button,.mode-tabs button,.period-tabs button{border:0;border-radius:9px;padding:11px 12px;background:transparent;color:#b3c4da;font-weight:700;cursor:pointer}.nav button{text-align:left}.nav button.active,.nav button:hover,.mode-tabs button.active,.period-tabs button.active{background:#18324e;color:white}.nav button:focus-visible,.button:focus-visible,.mode-tabs button:focus-visible,.period-tabs button:focus-visible,select:focus-visible,.tf-button:focus-visible,.sector-row:focus-visible{outline:3px solid var(--focus);outline-offset:2px}.broker-card{margin-top:auto;padding:15px;border:1px solid #294766;border-radius:12px;background:#102138}.broker-card b{display:block;margin:8px 0}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#f2b74b;margin-right:7px}.dot.ok{background:var(--positive);box-shadow:0 0 10px var(--positive)}.button{border:0;border-radius:8px;background:#2678be;color:white;padding:10px 12px;font-weight:800;cursor:pointer}.work{max-width:1800px;width:100%;margin:auto;padding:28px}.view{display:none}.view.active{display:block}.head,.toolbar,.detail-head{display:flex;justify-content:space-between;align-items:center;gap:16px}.head{margin-bottom:18px}.head h1,.head h2,.panel h2{margin:0}.status,.badge{padding:7px 10px;border:1px solid #294766;border-radius:999px;background:#102138;font-size:11px;font-weight:800}.positive{color:var(--positive)}.negative{color:var(--negative)}.neutral{color:var(--neutral)}.mode-tabs,.period-tabs{display:flex;gap:7px;flex-wrap:wrap}.toolbar{align-items:end;margin:14px 0}.toolbar label{display:grid;gap:5px;color:var(--muted);font-size:11px}.toolbar select{min-width:180px;background:#0c192a;border:1px solid #294766;border-radius:8px;color:var(--text);padding:9px}.overview-grid,.metric-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:14px 0}.metric,.panel{background:var(--surface);border:1px solid var(--border);border-radius:14px}.metric{padding:14px;min-width:0}.metric strong{display:block;font-size:18px;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.metric small{color:var(--muted)}.panel{padding:17px}.table-wrap{overflow:auto;border:1px solid var(--border);border-radius:14px;background:var(--surface)}table{width:100%;border-collapse:collapse;min-width:1520px;font-variant-numeric:tabular-nums}th,td{padding:10px 9px;border-bottom:1px solid #203750;text-align:left;white-space:nowrap;font-size:12px}th{position:sticky;top:0;background:#12223a;color:var(--muted);font-size:10px;text-transform:uppercase;z-index:1}.sector-row{cursor:pointer}.sector-row:hover{background:#142840}.sector-name b,.sector-name small{display:block}.sector-name small{color:var(--muted);margin-top:3px}.tf-button{min-width:46px;border:1px solid #36516f;border-radius:8px;background:#0b1728;color:var(--text);padding:7px;font:900 12px ui-monospace,SFMono-Regular,Consolas,monospace;cursor:pointer}.tf-button.strong-positive{background:#135b47}.tf-button.positive{background:#174437}.tf-button.negative{background:#512430}.tf-button.strong-negative{background:#6a2533}.tf-button.unavailable{color:#70839d}.quality{font-weight:800;font-size:10px}.quality.stale,.quality.insufficient-data{color:var(--neutral)}.quality.unavailable{color:var(--negative)}.rank-change.up{color:var(--positive)}.rank-change.down{color:var(--negative)}.empty{padding:28px;color:var(--muted);text-align:center}.error{color:#ffb1bb}.detail{margin-top:16px}.detail[hidden]{display:none}.detail-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(300px,.8fr);gap:14px;margin-top:14px}.chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.chart-card{border:1px solid var(--border);border-radius:11px;padding:12px;background:#0b1728}.chart-card h3{font-size:12px;margin:0 0 8px}.chart-card svg{width:100%;height:120px;overflow:visible}.chart-empty{height:120px;display:grid;place-items:center;color:var(--muted);font-size:11px}.legend{display:flex;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:10px}.explanation{margin-top:12px;padding:14px;border:1px solid var(--border);border-radius:11px;background:#0b1728}.explanation ul{margin:9px 0 0;padding-left:18px;color:#c7d5e7;line-height:1.6}.components{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.component{padding:11px;border-radius:9px;background:#0b1728;border:1px solid var(--border)}.component span,.component strong{display:block}.component span{font-size:10px;color:var(--muted)}.component strong{margin-top:5px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.movers{display:grid;grid-template-columns:1fr 1fr;gap:12px}.mover-list{margin:0;padding:0;list-style:none}.mover-list li{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:12px}.rotation-list{max-height:190px;overflow:auto;font-size:11px}.rotation-list div{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;padding:7px 0;border-bottom:1px solid var(--border)}.split{display:grid;grid-template-columns:1fr 1fr;gap:15px}.row{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr;gap:12px;padding:11px 0;border-top:1px solid #263c57;font-size:12px}.row.header{border-top:0;color:var(--muted);font-size:10px;font-weight:800;text-transform:uppercase}.last-updated{color:var(--muted);font-size:11px}
    .desk{max-width:100vw;overflow-x:hidden}.work{min-width:0}.table-wrap{max-width:100%}.components{grid-template-columns:repeat(6,1fr)}th:first-child,td:first-child{position:sticky;left:0;background:var(--surface);z-index:2}th:first-child{background:#12223a;z-index:3}.sector-row:hover td:first-child{background:#142840}
    @media(max-width:1200px){.overview-grid{grid-template-columns:repeat(3,1fr)}.components{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:950px){.desk{grid-template-columns:1fr}.side{border-right:0;border-bottom:1px solid var(--border);padding:14px 18px;gap:12px}.brand{padding:0}.nav{grid-template-columns:repeat(2,minmax(0,1fr))}.nav button{text-align:center}.broker-card{margin-top:0}.work{padding:18px}.detail-grid,.split{grid-template-columns:1fr}}
    @media(max-width:620px){.head,.toolbar,.detail-head{align-items:flex-start;flex-direction:column}.overview-grid,.metric-grid,.chart-grid,.components,.movers{grid-template-columns:1fr}.toolbar select{width:100%}}
  </style>
  <main class="desk">
    <aside class="side">
      <div class="brand"><b>◈ Sector Pulse</b><small>Analytical prioritization workspace</small></div>
      <nav class="nav" aria-label="Dashboard views"><button type="button" class="active" data-view="sectors" aria-pressed="true">Sector rotation</button><button type="button" data-view="broker" aria-pressed="false">Live feed & positions</button></nav>
      <div class="broker-card"><span class="label">BROKER CONNECTION</span><b role="status" aria-live="polite"><i id="broker-dot" class="dot" aria-hidden="true"></i><span id="broker-state">Checking FYERS</span></b><button type="button" class="button" id="reauth">Refresh authentication</button></div>
    </aside>
    <section class="work">
      <section id="sectors" class="view active">
        <header class="head"><div><span class="label">MULTI-TIMEFRAME SECTOR ANALYSIS</span><h1>Rotation, relative strength & ranking</h1><small class="muted">Analysis only — sector strength is not a buy or sell signal.</small></div><div id="analysis-status" class="status" role="status">Loading completed-bar analysis</div></header>
        <div class="toolbar">
          <div class="mode-tabs" aria-label="Analysis mode"><button type="button" class="active" data-mode="intraday" aria-pressed="true">Intraday</button><button type="button" data-mode="swing" aria-pressed="false">Swing</button></div>
          <label>Filter<select id="sector-filter"><option value="all">All sectors</option><option value="top3">Top 3</option><option value="top5">Top 5</option><option value="bottom3">Bottom 3</option><option value="bottom5">Bottom 5</option><option value="leading">Leading</option><option value="improving">Improving</option><option value="neutral">Neutral</option><option value="weakening">Weakening</option><option value="lagging">Lagging</option><option value="bullish">Bullish MTF alignment</option><option value="bearish">Bearish MTF alignment</option><option value="strong-outperformer">Strong outperformers</option><option value="strong-underperformer">Strong underperformers</option></select></label>
          <label>Sort by<select id="sector-sort"><option value="rank">Rank</option><option value="score">Score</option><option value="rank-change">Rank change</option><option value="relative-strength">Relative strength</option><option value="momentum">Momentum</option><option value="breadth">Breadth</option><option value="volume">Volume</option><option value="adx">ADX</option></select></label>
        </div>
        <section id="market-overview" class="overview-grid" aria-label="Calculated market overview"></section>
        <div class="table-wrap"><table aria-label="Multi-timeframe sector ranking"><thead><tr><th>Sector</th><th>15m</th><th>1H</th><th>Daily</th><th>Weekly</th><th>MTF alignment</th><th>RS vs NIFTY</th><th>ADX</th><th>Momentum</th><th>Breadth</th><th>Volume</th><th>Rotation</th><th>Score</th><th>Rank</th><th>Rank change</th><th>Last updated</th></tr></thead><tbody id="sector-body"><tr><td colspan="16" class="empty">Loading sector analysis…</td></tr></tbody></table></div>
        <section id="sector-detail" class="panel detail" hidden aria-live="polite"></section>
      </section>
      <section id="broker" class="view">
        <header class="head"><div><span class="label">LIVE FEED & POSITIONS</span><h1>Broker dashboard</h1></div><div id="account-state" class="status" role="status">Loading account</div></header>
        <div class="metric-grid"><article class="metric"><small>Live P&L</small><strong id="live-pnl">—</strong></article><article class="metric"><small>Open positions</small><strong id="open-count">—</strong></article><article class="metric"><small>Available funds</small><strong id="funds">—</strong></article><article class="metric"><small>Closed P&L</small><strong id="closed-pnl">—</strong></article></div>
        <div class="split"><section class="panel"><span class="label">OPEN POSITIONS</span><h2>Current broker positions</h2><div class="row header"><span>Instrument</span><span>Quantity</span><span>Average</span><span>Live P&L</span></div><div id="open-positions"></div></section><section class="panel"><span class="label">CLOSED POSITIONS</span><h2>Realised P&L</h2><div class="period-tabs" aria-label="Realised P and L period">${periods.map((period, index) => `<button type="button" data-period="${period}" class="${index === 0 ? 'active' : ''}" aria-pressed="${index === 0}">${period[0].toUpperCase() + period.slice(1)}</button>`).join('')}</div><div class="row header"><span>Instrument</span><span>Buy / sell</span><span>Quantity</span><span>Realised P&L</span></div><div id="closed-positions"></div></section></div>
      </section>
    </section>
  </main>`

  const $ = id => document.getElementById(id)
  let mode = 'intraday'
  let period = 'daily'
  let analysis = null
  let selectedSector = ''
  let selectedTimeframe = 'daily'

  const fetchJson = async url => {
    const response = await fetch(url, { cache: 'no-store' })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`)
    return data
  }
  const metric = (label, value, title = '') => `<article class="metric" title="${escapeHtml(title)}"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></article>`
  const qualityClass = value => String(value || 'unavailable').toLowerCase().replaceAll(' ', '-')
  const stateButton = (sector, timeframe) => {
    const value = sector.timeframe_states?.[timeframe]
    const state = value?.state
    const cls = state === 2 ? 'strong-positive' : state === 1 ? 'positive' : state === -1 ? 'negative' : state === -2 ? 'strong-negative' : state == null ? 'unavailable' : 'neutral'
    const title = value?.reasons?.join(' · ') || value?.data_quality || 'Unavailable'
    return `<button type="button" class="tf-button ${cls}" data-sector="${escapeHtml(sector.sector_id)}" data-timeframe="${timeframe}" title="${escapeHtml(title)}" aria-label="${escapeHtml(sector.name)} ${timeframe}: ${escapeHtml(value?.label || 'Unavailable')}">${state == null ? '—' : state > 0 ? `+${state}` : state}</button>`
  }
  const applyFilter = sectors => {
    return filterAndSortSectors(sectors, $('sector-filter').value, $('sector-sort').value)
  }
  const renderOverview = overview => {
    $('market-overview').innerHTML = [
      metric('Market regime', overview.market_regime || 'Unavailable'),
      metric('Leading', (overview.leading || []).join(', ') || 'None'),
      metric('Improving', (overview.improving || []).join(', ') || 'None'),
      metric('Weakening / lagging', [...(overview.weakening || []), ...(overview.lagging || [])].join(', ') || 'None'),
      metric('Sector breadth', overview.sector_breadth ? `${overview.sector_breadth.bullish} / ${overview.sector_breadth.total} bullish` : 'Unavailable'),
      metric('Daily + Weekly bullish', overview.daily_weekly_bullish_alignment ? `${overview.daily_weekly_bullish_alignment.count} / ${overview.daily_weekly_bullish_alignment.total}` : 'Unavailable'),
    ].join('')
  }
  const renderTable = () => {
    if (!analysis?.sectors?.length) {
      $('sector-body').innerHTML = `<tr><td colspan="16" class="empty ${analysis?.error ? 'error' : ''}">${escapeHtml(analysis?.error || 'Completed-bar analysis is still loading.')}</td></tr>`
      renderOverview(analysis?.market_overview || {})
      return
    }
    renderOverview(analysis.market_overview || {})
    const rows = applyFilter(analysis.sectors)
    $('sector-body').innerHTML = rows.map(sector => {
      const rankChange = sector.rank_change == null ? '—' : sector.rank_change > 0 ? `+${sector.rank_change}` : String(sector.rank_change)
      return `<tr class="sector-row" tabindex="0" data-detail="${escapeHtml(sector.sector_id)}"><td class="sector-name"><b>${escapeHtml(sector.name)}</b><small class="quality ${qualityClass(sector.data_quality)}">${escapeHtml(sector.data_quality)}</small></td>${timeframeOrder.map(tf => `<td>${stateButton(sector, tf)}</td>`).join('')}<td>${escapeHtml(sector.mtf_alignment)}</td><td class="${stateClass((sector.relative_strength_score ?? 50) - 50)}">${escapeHtml(sector.relative_strength_state)}<br><small>${number(sector.relative_strength_score)}</small></td><td>${number(sector.adx)}</td><td>${number(sector.momentum_score)}</td><td>${number(sector.breadth_score)}</td><td>${number(sector.volume_score)}</td><td>${escapeHtml(sector.rotation_state)}<br><small>${escapeHtml(sector.acceleration_state)}</small></td><td><b>${number(sector.overall_score)}</b></td><td>${sector.rank ? `#${sector.rank}` : '—'}</td><td class="rank-change ${sector.rank_change > 0 ? 'up' : sector.rank_change < 0 ? 'down' : ''}">${rankChange}</td><td>${time(sector.last_updated)}</td></tr>`
    }).join('') || '<tr><td colspan="16" class="empty">No sectors match this filter.</td></tr>'
    document.querySelectorAll('[data-detail]').forEach(row => {
      const open = () => loadDetail(row.dataset.detail, selectedTimeframe)
      row.addEventListener('click', event => { if (!event.target.closest('.tf-button')) open() })
      row.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open() } })
    })
    document.querySelectorAll('.tf-button').forEach(button => button.addEventListener('click', () => loadDetail(button.dataset.sector, button.dataset.timeframe)))
  }
  const coordinates = (values, width = 420, height = 110, invert = false) => {
    const usable = values.map(Number).filter(Number.isFinite)
    if (usable.length < 2) return ''
    const minimum = Math.min(...usable), maximum = Math.max(...usable), spread = maximum - minimum || 1
    return usable.map((value, index) => `${index * width / (usable.length - 1)},${invert ? (value - minimum) * height / spread : height - (value - minimum) * height / spread}`).join(' ')
  }
  const lineChart = (title, points, key, invert = false) => {
    const values = (points || []).map(point => point[key]).filter(value => value != null)
    return `<article class="chart-card"><h3>${escapeHtml(title)}</h3>${values.length > 1 ? `<svg viewBox="0 0 420 110" role="img" aria-label="${escapeHtml(title)} history"><polyline fill="none" stroke="#6fb7ff" stroke-width="3" points="${coordinates(values, 420, 110, invert)}"/></svg>` : '<div class="chart-empty">History becomes available after persisted refresh snapshots.</div>'}</article>`
  }
  const priceChart = state => {
    const rows = state?.series || []
    const lines = [{ key: 'close', color: '#edf4ff' }, { key: 'ema20', color: '#60dca9' }, { key: 'ema50', color: '#f0c85b' }, { key: 'ema200', color: '#ff92a1' }]
    const all = rows.flatMap(row => lines.map(line => row[line.key])).filter(value => value != null).map(Number)
    if (all.length < 2) return '<div class="chart-empty">Price history unavailable.</div>'
    const minimum = Math.min(...all), maximum = Math.max(...all), spread = maximum - minimum || 1
    const points = key => rows.map((row, index) => `${index * 420 / Math.max(1, rows.length - 1)},${110 - (Number(row[key]) - minimum) * 110 / spread}`).join(' ')
    return `<svg viewBox="0 0 420 110" role="img" aria-label="Price with EMA20, EMA50 and EMA200">${lines.map(line => `<polyline fill="none" stroke="${line.color}" stroke-width="${line.key === 'close' ? 2.5 : 1.5}" points="${points(line.key)}"/>`).join('')}</svg><div class="legend"><span>Close</span><span class="positive">EMA20</span><span class="neutral">EMA50</span><span class="negative">EMA200</span></div>`
  }
  const renderDetail = sector => {
    const state = sector.timeframe_states?.[selectedTimeframe] || {}
    const history = sector.history || []
    const movers = [...(sector.constituent_movers || [])].filter(item => item.change != null)
    const strongest = movers.slice().sort((a, b) => (b.contribution ?? -Infinity) - (a.contribution ?? -Infinity)).slice(0, 5)
    const weakest = movers.slice().sort((a, b) => (a.contribution ?? Infinity) - (b.contribution ?? Infinity)).slice(0, 5)
    $('sector-detail').hidden = false
    $('sector-detail').innerHTML = `<div class="detail-head"><div><span class="label">SECTOR DETAIL · ${escapeHtml(mode.toUpperCase())}</span><h2>${escapeHtml(sector.name)}</h2><small class="last-updated">Completed bars · Updated ${time(sector.last_updated)} · ${escapeHtml(sector.data_quality)}</small></div><button type="button" class="button" id="strongest-stocks">View strongest stocks</button></div>
      <div class="components">${[['Overall', sector.overall_score], ['Trend', sector.trend_score], ['RS vs NIFTY', sector.relative_strength_score], ['Momentum', sector.momentum_score], ['Breadth', sector.breadth_score], ['Volume', sector.volume_score]].map(([label, value]) => `<div class="component"><span>${label}</span><strong>${number(value)}</strong></div>`).join('')}</div>
      <div class="mode-tabs" aria-label="Detail timeframe" style="margin-top:12px">${timeframeOrder.map(tf => `<button type="button" data-detail-timeframe="${tf}" class="${selectedTimeframe === tf ? 'active' : ''}" aria-pressed="${selectedTimeframe === tf}">${tf}</button>`).join('')}</div>
      <div class="detail-grid"><div><article class="chart-card"><h3>${escapeHtml(sector.name)} ${escapeHtml(selectedTimeframe)} · Price and EMA structure</h3>${priceChart(state)}</article><div class="explanation"><b>${escapeHtml(state.label || 'Unavailable')} · Trend ${number(state.score)}/100</b><ul>${(state.reasons || []).map(reason => `<li>${escapeHtml(reason)}</li>`).join('') || '<li>No explanation is available because candle data is missing.</li>'}</ul></div><div class="chart-grid" style="margin-top:12px">${lineChart('Sector score history', history, 'overall_score')}${lineChart('Rank history', history, 'rank', true)}${lineChart('Relative strength history', history, 'relative_strength_score')}${lineChart('Momentum history', history, 'momentum_score')}${lineChart('Breadth history', history, 'breadth_score')}</div></div>
      <aside><article class="chart-card"><h3>Multi-timeframe summary</h3>${timeframeOrder.map(tf => { const item = sector.timeframe_states?.[tf] || {}; return `<div class="row" style="grid-template-columns:70px 1fr 70px"><b>${tf}</b><span class="${stateClass(item.state)}">${escapeHtml(item.label || 'Unavailable')}</span><strong>${number(item.score)}</strong></div>` }).join('')}</article><article class="chart-card" style="margin-top:12px"><h3>Rotation history</h3><div class="rotation-list">${history.length ? history.slice().reverse().map(point => `<div><span>${time(point.timestamp)}</span><b>${escapeHtml(point.rotation_state || 'NEUTRAL')}</b><span>${point.rank ? `#${point.rank}` : '—'} · ${number(point.overall_score)}</span></div>`).join('') : '<div class="chart-empty">Waiting for persisted snapshots.</div>'}</div></article><article class="chart-card" style="margin-top:12px"><h3>Data quality</h3><p>${escapeHtml(sector.data_quality)}</p><p class="muted">Missing: ${escapeHtml((sector.missing_components || []).join(', ') || 'none')}</p><p class="muted">Weights: ${escapeHtml(Object.entries(sector.component_weights || {}).map(([key, value]) => `${key} ${value}%`).join(' · '))}</p></article></aside></div>
      <section id="constituent-workflow" class="chart-card" style="margin-top:12px"><h3>Sector → stock prioritization</h3><p class="muted">Current constituent movers support further stock analysis only. They are not trade signals and do not place orders.</p><div class="movers"><div><b>Strongest current contributors</b><ul class="mover-list">${strongest.length ? strongest.map(item => `<li><span>${escapeHtml(item.ticker)}</span><strong class="${stateClass(item.change)}">${number(item.change, '%')}</strong></li>`).join('') : '<li>Live constituent data unavailable</li>'}</ul></div><div><b>Weakest current contributors</b><ul class="mover-list">${weakest.length ? weakest.map(item => `<li><span>${escapeHtml(item.ticker)}</span><strong class="${stateClass(item.change)}">${number(item.change, '%')}</strong></li>`).join('') : '<li>Live constituent data unavailable</li>'}</ul></div></div></section>`
    document.querySelectorAll('[data-detail-timeframe]').forEach(button => button.addEventListener('click', () => loadDetail(sector.sector_id, button.dataset.detailTimeframe)))
    $('strongest-stocks').addEventListener('click', () => $('constituent-workflow').scrollIntoView({ behavior: scrollBehavior, block: 'start' }))
  }
  const loadDetail = async (sectorId, timeframe = 'daily') => {
    selectedSector = sectorId
    selectedTimeframe = timeframe
    $('sector-detail').hidden = false
    $('sector-detail').innerHTML = '<div class="empty">Loading explainable sector detail…</div>'
    try {
      const data = await fetchJson(`/api/sector-analysis/detail?mode=${encodeURIComponent(mode)}&sector=${encodeURIComponent(sectorId)}`)
      renderDetail(data.sector)
      $('sector-detail').scrollIntoView({ behavior: scrollBehavior, block: 'start' })
    } catch (error) {
      $('sector-detail').innerHTML = `<div class="empty error">${escapeHtml(error.message)}</div>`
    }
  }
  const refreshAnalysis = async () => {
    try {
      analysis = await fetchJson(`/api/sector-analysis?mode=${encodeURIComponent(mode)}`)
      $('analysis-status').textContent = analysis.refreshing ? 'Refreshing completed bars' : analysis.updated_at ? `Updated ${time(analysis.updated_at)}` : (analysis.error || 'Analysis loading')
      renderTable()
      if (selectedSector && analysis.sectors?.some(item => item.sector_id === selectedSector)) loadDetail(selectedSector, selectedTimeframe)
    } catch (error) {
      analysis = { sectors: [], error: error.message }
      $('analysis-status').textContent = 'Analysis unavailable'
      renderTable()
    }
  }
  const refreshAccount = async () => {
    try {
      const data = await fetchJson('/api/account')
      const positions = (data.positions || []).filter(item => Number(item.netQty ?? item.net_qty ?? 0) !== 0)
      $('live-pnl').textContent = money(data.pnl); $('live-pnl').className = stateClass(data.pnl)
      $('open-count').textContent = String(positions.length); $('funds').textContent = money(data.available_funds)
      $('open-positions').innerHTML = positions.length ? positions.map(item => { const quantity = item.netQty ?? item.net_qty ?? 0; const pnl = item.pl ?? item.pnl ?? 0; return `<div class="row"><b>${escapeHtml(item.symbol || item.symbol_name || '—')}</b><span>${quantity}</span><span>${money(item.netAvg ?? item.net_avg)}</span><strong class="${stateClass(pnl)}">${money(pnl)}</strong></div>` }).join('') : '<p class="empty">No open broker positions.</p>'
      $('broker-dot').classList.toggle('ok', !!data.connected); $('broker-state').textContent = data.connected ? 'FYERS connected' : (data.error || 'FYERS disconnected'); $('account-state').textContent = data.connected ? 'Broker feed connected' : (data.error || 'Broker feed unavailable')
    } catch (error) { $('account-state').textContent = error.message; $('broker-state').textContent = 'FYERS unavailable' }
  }
  const refreshClosed = async () => {
    try {
      const data = await fetchJson(`/api/realized-pnl?period=${period}`)
      const summary = data.summary || {}; $('closed-pnl').textContent = money(summary.net_pnl); $('closed-pnl').className = stateClass(summary.net_pnl)
      $('closed-positions').innerHTML = data.records?.length ? data.records.map(item => `<div class="row"><b>${escapeHtml(item.symbol)}</b><span>${escapeHtml(item.buy_rate)} / ${escapeHtml(item.sell_rate)}</span><span>${escapeHtml(item.buy_qty)} / ${escapeHtml(item.sell_qty)}</span><strong class="${stateClass(item.pnl)}">${money(item.pnl)}</strong></div>`).join('') : '<p class="empty">No closed positions in this period.</p>'
    } catch (error) { $('closed-positions').innerHTML = `<p class="empty error">${escapeHtml(error.message)}</p>` }
  }

  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => { document.querySelectorAll('[data-view]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)) }); document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === button.dataset.view)) }))
  document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => { mode = button.dataset.mode; document.querySelectorAll('[data-mode]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)) }); selectedSector = ''; $('sector-detail').hidden = true; refreshAnalysis() }))
  document.querySelectorAll('[data-period]').forEach(button => button.addEventListener('click', () => { period = button.dataset.period; document.querySelectorAll('[data-period]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)) }); refreshClosed() }))
  $('sector-filter').addEventListener('change', renderTable)
  $('sector-sort').addEventListener('change', renderTable)
  $('reauth').addEventListener('click', async () => {
    const button = $('reauth'); const loginWindow = window.open('about:blank', 'fyers-oauth'); button.disabled = true; button.textContent = 'Opening FYERS login…'
    try { const data = await fetchJson('/api/auth/start'); if (loginWindow) { loginWindow.opener = null; loginWindow.location.replace(data.url) } else window.location.assign(data.url); $('broker-state').textContent = 'Complete login and 2FA in the browser' } catch (error) { if (loginWindow) loginWindow.close(); $('broker-state').textContent = error.message } finally { button.disabled = false; button.textContent = 'Refresh authentication' }
  })

  refreshAnalysis(); refreshAccount(); refreshClosed()
  setInterval(refreshAnalysis, analysisRefreshMs)
  setInterval(refreshAccount, accountRefreshMs)
})()
