(() => {
  const defaultAnalysisReadyPollMs = 5 * 1000
  const analysisLoadingPollMs = 750
  const accountRefreshMs = 10 * 1000
  const straddleRefreshMs = 5 * 1000
  const periods = ['daily', 'weekly', 'monthly', 'annual']
  const timeframeOrder = ['15m', '1h', 'daily', 'weekly']
  const { analysisStatusText, filterAndSortSectors, qualityText, refreshPhaseState, riskPolicyPreview, rotationDisplay, rotationOverviewValue } = window.SectorDashboardModel
  const stateClass = value => value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral'
  const scrollBehavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character])
  const money = value => value == null ? '—' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(Number(value))
  const number = (value, suffix = '') => value == null ? '—' : `${Number(value).toFixed(1)}${suffix}`
  const percent = value => value == null ? '—' : `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}%`
  const percentagePoints = value => value == null ? '—' : `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(3)} pp`
  const time = value => value ? new Date(value).toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'
  const sourceDate = value => value ? new Date(`${value}T00:00:00`).toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' }) : 'unavailable'
  const horizonLegends = item => {
    const states = item?.timeframe_states || {}
    const aligned = (first, second) => {
      const a = Number(states[first]?.state), b = Number(states[second]?.state)
      return Number.isFinite(a) && Number.isFinite(b) && a !== 0 && b !== 0 && Math.sign(a) === Math.sign(b)
    }
    const horizons = [['Intraday', aligned('15m', '1h')], ['Swing', aligned('1h', 'daily')], ['Positional', aligned('daily', 'weekly')]]
    return `<div class="choice-row" style="margin-top:10px">${horizons.map(([label, applicable]) => `<span class="choice ${applicable ? 'positive' : 'neutral'}">${escapeHtml(label)} · ${applicable ? 'Applicable' : 'Not aligned'}</span>`).join('')}</div>`
  }
  const viewStorageKey = 'sector-pulse:selected-view'
  const refreshStorageKey = 'sector-pulse:analysis-refresh-ms'
  const allowedRefreshIntervals = [5, 15, 30, 60, 300, 900, 3600, 14400].map(seconds => seconds * 1000)
  const storedRefreshInterval = (() => {
    try {
      const value = Number(localStorage.getItem(refreshStorageKey))
      return allowedRefreshIntervals.includes(value) ? value : defaultAnalysisReadyPollMs
    } catch { return defaultAnalysisReadyPollMs }
  })()
  const storedView = (() => {
    try { return localStorage.getItem(viewStorageKey) } catch { return null }
  })()
  const storedStraddleMarket = (() => {
    try { return localStorage.getItem('sector-pulse:straddle-market') } catch { return null }
  })()
  const initialStraddleMarket = storedView === 'nifty-straddle' || storedStraddleMarket === 'nifty' ? 'nifty' : 'sensex'
  const initialView = ['sectors', 'handoff', 'broker', 'straddles', 'ema-band', 'ema-cross', 'kama', 'screener', 'settings', 'trade-parser'].includes(storedView)
    ? storedView
    : ['sensex-straddle', 'nifty-straddle'].includes(storedView) ? 'straddles' : 'sectors'
  let straddleRunnerState = { available: false, running: false }
  let niftyStraddleRunnerState = { available: false, running: false }
  const straddleSquareoffPreviews = { sensex: null, nifty: null }

  document.body.innerHTML = `<style>
    :root{color-scheme:dark;--bg:#09111f;--surface:#101d31;--surface-2:#0d192a;--border:#233c59;--text:#edf4ff;--muted:#91a7c4;--positive:#60dca9;--negative:#ff92a1;--neutral:#d0b66a;--focus:#a9dcff}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px Inter,system-ui,sans-serif}.desk{min-height:100vh;display:grid;grid-template-columns:250px minmax(0,1fr)}button,select{font:inherit}.side{padding:24px 16px;background:var(--surface-2);border-right:1px solid var(--border);display:flex;flex-direction:column;gap:24px}.brand{padding:4px 10px}.brand b{font-size:18px}.brand small,.label,.muted{display:block;color:var(--muted);font-size:11px}.nav{display:grid;gap:7px}.nav button,.mode-tabs button,.period-tabs button{border:0;border-radius:9px;padding:11px 12px;background:transparent;color:#b3c4da;font-weight:700;cursor:pointer}.nav button{text-align:left}.nav button.active,.nav button:hover,.mode-tabs button.active,.period-tabs button.active{background:#18324e;color:white}.nav button:focus-visible,.button:focus-visible,.mode-tabs button:focus-visible,.period-tabs button:focus-visible,select:focus-visible,.tf-button:focus-visible,.sector-row:focus-visible{outline:3px solid var(--focus);outline-offset:2px}.broker-card{margin-top:auto;padding:15px;border:1px solid #294766;border-radius:12px;background:#102138}.broker-card b{display:block;margin:8px 0}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#f2b74b;margin-right:7px}.dot.ok{background:var(--positive);box-shadow:0 0 10px var(--positive)}.button{border:0;border-radius:8px;background:#2678be;color:white;padding:10px 12px;font-weight:800;cursor:pointer}.work{max-width:1800px;width:100%;margin:auto;padding:28px}.view{display:none}.view.active{display:block}.head,.toolbar,.detail-head{display:flex;justify-content:space-between;align-items:center;gap:16px}.head{margin-bottom:18px}.head h1,.head h2,.panel h2{margin:0}.status,.badge{padding:7px 10px;border:1px solid #294766;border-radius:999px;background:#102138;font-size:11px;font-weight:800}.status.failed{border-color:#743646;color:#ffb1bb}.positive{color:var(--positive)}.negative{color:var(--negative)}.neutral{color:var(--neutral)}.mode-tabs,.period-tabs{display:flex;gap:7px;flex-wrap:wrap}.toolbar{align-items:end;margin:14px 0}.toolbar label{display:grid;gap:5px;color:var(--muted);font-size:11px}.toolbar select{min-width:180px;background:#0c192a;border:1px solid #294766;border-radius:8px;color:var(--text);padding:9px}.refresh-pipeline{position:relative;overflow:hidden;margin:2px 0 18px;padding:17px 18px 14px;border:1px solid #3979aa;border-radius:14px;background:linear-gradient(110deg,#123a61,#112943);box-shadow:0 10px 26px #02091655,inset 0 1px 0 #ffffff10}.refresh-pipeline.loading{border-color:#63b8f2;background:linear-gradient(110deg,#164e7e,#132d4b)}.refresh-pipeline.ready{border-color:#38745f;background:linear-gradient(110deg,#123c34,#112c32)}.refresh-pipeline.failed{border-color:#8c4354;background:linear-gradient(110deg,#4a2130,#271b2c)}.pipeline-head{display:flex;align-items:center;gap:13px}.refresh-beacon{width:14px;height:14px;border:3px solid #8fd1ff;border-radius:50%;background:#d9f2ff;box-shadow:0 0 0 5px #58b7f333;flex:none}.refresh-pipeline.loading .refresh-beacon{animation:beacon-pulse 1.2s ease-out infinite}.refresh-pipeline.ready .refresh-beacon{border-color:#6ce3b2;background:#6ce3b2;box-shadow:0 0 0 5px #60dca922}.refresh-pipeline.failed .refresh-beacon{border-color:#ff92a1;background:#ff92a1;box-shadow:none}.pipeline-copy{min-width:0}.pipeline-kicker{display:block;color:#b9dcf6;font-size:10px;font-weight:900;letter-spacing:.13em}.pipeline-message{margin:3px 0 0;color:#c6d8e9;font-size:12px;line-height:1.35}.pipeline-message b{display:block;color:#fff;font-size:16px;letter-spacing:-.01em}.pipeline-message span{display:block;margin-top:2px}.pipeline-track{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;margin:15px 0 11px}.pipeline-step{position:relative;display:flex;align-items:center;gap:7px;color:#7892ae;font-size:10px;font-weight:800;letter-spacing:.03em}.pipeline-step:not(:last-child)::after{content:"";height:2px;background:#294d6b;flex:1;margin-right:7px}.pipeline-step i{width:10px;height:10px;border:2px solid #5c7590;border-radius:50%;flex:none}.pipeline-step.active{color:#fff}.pipeline-step.active i{border-color:#8fd1ff;background:#8fd1ff}.pipeline-step.complete{color:#b8d8cc}.pipeline-step.complete i{border-color:var(--positive);background:var(--positive)}.pipeline-step.failed{color:#ffced4}.pipeline-step.failed i{border-color:var(--negative);background:var(--negative)}.refresh-meter{height:5px;overflow:hidden;border-radius:999px;background:#06152399}.refresh-meter span{display:block;height:100%;width:100%;border-radius:inherit;background:#6ce3b2;transform-origin:left}.refresh-pipeline.loading .refresh-meter span{width:34%;background:linear-gradient(90deg,#55aeea,#c4edff,#55aeea);animation:meter-sweep 1.45s ease-in-out infinite}.refresh-pipeline.failed .refresh-meter span{width:100%;background:#ff92a1;animation:none}@keyframes beacon-pulse{0%,100%{box-shadow:0 0 0 5px #58b7f326}50%{box-shadow:0 0 0 12px #8fd1ff08}}@keyframes meter-sweep{0%{transform:translateX(-115%)}100%{transform:translateX(305%)}}@media(prefers-reduced-motion:reduce){.refresh-pipeline.loading .refresh-beacon,.refresh-pipeline.loading .refresh-meter span{animation:none}.refresh-pipeline.loading .refresh-meter span{width:60%;transform:none}}.overview-grid,.metric-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:14px 0}.metric,.panel{background:var(--surface);border:1px solid var(--border);border-radius:14px}.metric{padding:14px;min-width:0}.metric strong{display:block;font-size:18px;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.metric small{color:var(--muted)}.panel{padding:17px}.table-wrap{overflow:auto;border:1px solid var(--border);border-radius:14px;background:var(--surface)}.table-wrap.retained{border-color:#756634;box-shadow:inset 0 3px 0 #d0b66a40}table{width:100%;border-collapse:collapse;min-width:1800px;font-variant-numeric:tabular-nums}th,td{padding:10px 9px;border-bottom:1px solid #203750;text-align:left;white-space:nowrap;font-size:12px}th{position:sticky;top:0;background:#12223a;color:var(--muted);font-size:10px;text-transform:uppercase;z-index:1}.sector-row{cursor:pointer}.sector-row:hover{background:#142840}.sector-name b,.sector-name small{display:block}.sector-name small{color:var(--muted);margin-top:3px}.tf-button{min-width:46px;border:1px solid #36516f;border-radius:8px;background:#0b1728;color:var(--text);padding:7px;font:900 12px ui-monospace,SFMono-Regular,Consolas,monospace;cursor:pointer}.tf-button.strong-positive{background:#135b47}.tf-button.positive{background:#174437}.tf-button.negative{background:#512430}.tf-button.strong-negative{background:#6a2533}.tf-button.unavailable{color:#70839d}.quality{font-weight:800;font-size:10px}.quality.stale,.quality.insufficient-data{color:var(--neutral)}.quality.unavailable{color:var(--negative)}.rank-change.up{color:var(--positive)}.rank-change.down{color:var(--negative)}.contributors{min-width:260px;white-space:normal}.contributor{display:grid;grid-template-columns:72px 54px 68px 74px;gap:5px;padding:2px 0;font-size:10px}.contributor b{overflow:hidden;text-overflow:ellipsis}.source-scope{display:block;color:var(--muted);font-size:9px;margin-top:5px}.source-scope.complete{color:var(--positive)}.source-scope.partial{color:var(--neutral)}.provenance-link{color:#8ecbff}.empty{padding:28px;color:var(--muted);text-align:center}.error{color:#ffb1bb}.detail{margin-top:16px}.detail[hidden]{display:none}.detail-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(300px,.8fr);gap:14px;margin-top:14px}.chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.chart-card{border:1px solid var(--border);border-radius:11px;padding:12px;background:#0b1728}.chart-card h3{font-size:12px;margin:0 0 8px}.chart-card svg{width:100%;height:120px;overflow:visible}.chart-empty{height:120px;display:grid;place-items:center;color:var(--muted);font-size:11px}.legend{display:flex;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:10px}.explanation{margin-top:12px;padding:14px;border:1px solid var(--border);border-radius:11px;background:#0b1728}.explanation ul{margin:9px 0 0;padding-left:18px;color:#c7d5e7;line-height:1.6}.components{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.component{padding:11px;border-radius:9px;background:#0b1728;border:1px solid var(--border)}.component span,.component strong{display:block}.component span{font-size:10px;color:var(--muted)}.component strong{margin-top:5px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.movers{display:grid;grid-template-columns:1fr 1fr;gap:12px}.mover-list{margin:0;padding:0;list-style:none}.mover-list li{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:12px}.rotation-list{max-height:190px;overflow:auto;font-size:11px}.rotation-list div{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;padding:7px 0;border-bottom:1px solid var(--border)}.split{display:grid;grid-template-columns:1fr 1fr;gap:15px}.row{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr;gap:12px;padding:11px 0;border-top:1px solid #263c57;font-size:12px}.row.header{border-top:0;color:var(--muted);font-size:10px;font-weight:800;text-transform:uppercase}.last-updated{color:var(--muted);font-size:11px}
    .desk{max-width:100vw;overflow-x:hidden}.work{min-width:0}.table-wrap{max-width:100%}.components{grid-template-columns:repeat(6,1fr)}th:first-child,td:first-child{position:sticky;left:0;background:var(--surface);z-index:2}th:first-child{background:#12223a;z-index:3}.sector-row:hover td:first-child{background:#142840}
    @media(max-width:1200px){.overview-grid{grid-template-columns:repeat(3,1fr)}.components{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:950px){.desk{grid-template-columns:1fr}.side{border-right:0;border-bottom:1px solid var(--border);padding:14px 18px;gap:12px}.brand{padding:0}.nav{grid-template-columns:repeat(4,minmax(0,1fr))}.nav button{text-align:center}.broker-card{margin-top:0}.work{padding:18px}.detail-grid,.split{grid-template-columns:1fr}}
    .handoff-banner{display:grid;grid-template-columns:auto 1fr;gap:13px;margin:0 0 16px;padding:16px;border:1px solid #3b6588;border-radius:14px;background:linear-gradient(120deg,#102b45,#102237)}.handoff-banner strong,.handoff-banner span{display:block}.handoff-banner span{margin-top:4px;color:#afc3d9;font-size:12px;line-height:1.5}.handoff-mark{width:38px;height:38px;border:1px solid #72b9ed;border-radius:11px;display:grid;place-items:center;color:#bce4ff;font-weight:900}.handoff-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(340px,.85fr);gap:15px}.step-title{display:flex;justify-content:space-between;gap:12px;align-items:start}.step-title h2{font-size:17px}.field-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.field{display:grid;gap:6px;color:var(--muted);font-size:11px}.field input,.field select,.field textarea,.confirmation-input{width:100%;border:1px solid #31506f;border-radius:8px;background:#081525;color:var(--text);padding:10px}.field textarea{min-height:76px;resize:vertical}.choice-row{display:flex;gap:8px;flex-wrap:wrap}.choice{display:flex;align-items:center;gap:7px;padding:9px 10px;border:1px solid #294766;border-radius:9px;background:#0b1728;color:#c4d2e2;font-size:12px}.choice input{accent-color:#60dca9}.candidate-list{display:grid;gap:8px;margin-top:12px;max-height:420px;overflow:auto}.candidate-card{display:grid;grid-template-columns:auto minmax(0,1fr) 150px;gap:10px;align-items:center;padding:11px;border:1px solid #28425f;border-radius:10px;background:#0b1728}.candidate-card b,.candidate-card small{display:block}.candidate-card small{color:var(--muted);margin-top:3px}.candidate-card.bullish{box-shadow:inset 3px 0 0 var(--positive)}.candidate-card.bearish{box-shadow:inset 3px 0 0 var(--negative)}.candidate-card input[type=number]{width:100%;border:1px solid #31506f;border-radius:7px;background:#071322;color:var(--text);padding:8px}.analysis-panel{margin-top:15px}.analysis-board{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:13px;margin-top:13px}.opportunity-card{position:relative;overflow:hidden;border:1px solid #294966;border-radius:14px;background:linear-gradient(145deg,#0d1c2d,#091522);padding:15px 15px 15px 19px}.opportunity-card:before{content:"";position:absolute;inset:0 auto 0 0;width:4px;background:var(--positive)}.opportunity-card.bearish:before{background:var(--negative)}.opportunity-head{display:flex;justify-content:space-between;gap:10px}.opportunity-head small,.proposal-copy{color:var(--muted);font-size:11px;line-height:1.5}.conviction{border:1px solid #42627d;border-radius:999px;padding:4px 8px;height:max-content;font-size:10px;text-transform:uppercase}.decision-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:11px 0}.decision-metrics div{padding:8px;border-radius:8px;background:#071322}.decision-metrics b,.decision-metrics small{display:block}.decision-metrics small{color:var(--muted);font-size:9px;margin-top:2px}.invalidation-picker{display:grid;gap:6px;margin:10px 0}.invalidation-option{display:grid;grid-template-columns:auto 1fr 92px;gap:7px;align-items:center;padding:7px;border:1px solid #29445f;border-radius:8px;font-size:11px}.invalidation-option input[type=number]{width:100%;background:#071322;color:var(--text);border:1px solid #31506f;border-radius:6px;padding:6px}.leg-table{width:100%;font-size:10px;border-collapse:collapse;margin:9px 0}.leg-table td,.leg-table th{padding:5px;border-bottom:1px solid #263d55;text-align:left}.proposal-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.excluded-list{margin-top:10px;color:var(--muted);font-size:11px}.privacy-gate{margin-top:10px;padding:11px;border:1px dashed #4a6b8b;border-radius:10px}.privacy-gate .choice+.choice{margin-top:7px}.packet-panel,.ticket-panel,.automation-panel{margin-top:15px}.packet-actions{display:flex;gap:8px;flex-wrap:wrap}.packet-preview{max-height:520px;overflow:auto;white-space:pre-wrap;word-break:break-word;padding:14px;border:1px solid #263f5c;border-radius:10px;background:#071321;color:#cfe0f1;font:11px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace}.button.secondary{background:#17314a;color:#c9e4f7;border:1px solid #3c6687}.button.danger{background:#8f3142}.button:disabled{cursor:not-allowed;opacity:.45}.handoff-status{margin-top:10px;color:#b7c8d9;font-size:12px}.handoff-status.error{color:#ffb1bb}.risk-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0}.risk-strip div{padding:10px;border:1px solid #2b465f;border-radius:9px;background:#0b1728}.risk-strip b,.risk-strip small{display:block}.risk-strip small{color:var(--muted);margin-top:3px}.ticket-warning{padding:11px;border-left:3px solid var(--neutral);background:#2a2619;color:#e3d6a8;font-size:12px;line-height:1.5}.automation-panel summary{cursor:pointer;font-weight:800;font-size:16px}.automation-panel details[open] summary{margin-bottom:14px}.screen-reader-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
    .screener-source{display:block}.screener-source-head{display:flex;justify-content:space-between;align-items:start;gap:12px}.screener-source-actions{display:flex;align-items:end;gap:7px;flex-wrap:wrap;justify-content:flex-end}.screener-refresh-setting{display:grid;gap:4px;color:var(--muted);font-size:10px}.screener-refresh-setting select{border:1px solid #31506f;border-radius:8px;background:#081525;color:var(--text);padding:9px}.screener-schedule{display:block;margin-top:5px;color:var(--muted);font-size:10px}.screener-schedule.paused{color:var(--neutral)}.screener-results{margin-top:11px;border-top:1px solid #28425f;padding-top:10px}.screener-results summary{cursor:pointer;color:#c9e4f7;font-size:12px;font-weight:800}.screener-visible-count{display:block;padding:9px 0;color:var(--muted);font-size:11px}.screener-result-table{max-height:340px;overflow:auto;margin-top:5px;border:1px solid #28425f;border-radius:9px}.screener-result-table table{min-width:1500px}.screener-result-table th,.screener-result-table td{padding:8px 10px}.screener-result-table th:first-child,.screener-result-table td:first-child{position:static}.screener-sort{border:0;background:transparent;color:inherit;padding:0;font:inherit;font-weight:800;text-transform:uppercase;cursor:pointer}.screener-sort:hover{color:#fff}.screener-header-filter{display:grid;grid-template-columns:repeat(2,minmax(70px,1fr));gap:4px;margin-top:6px;text-transform:none}.screener-header-filter.single{grid-template-columns:minmax(110px,1fr)}.screener-header-filter label{display:grid;gap:2px;color:#8299b5;font-size:8px}.screener-header-filter input,.screener-header-filter select{min-width:0;width:100%;border:1px solid #31506f;border-radius:6px;background:#081525;color:var(--text);padding:5px;font-size:10px}.screener-validation{margin-top:9px;color:var(--neutral);font-size:10px;line-height:1.45}
    @media(max-width:1100px){.handoff-grid{grid-template-columns:1fr}.risk-strip{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:620px){.head,.toolbar,.detail-head{align-items:flex-start;flex-direction:column}.refresh-pipeline{padding:15px}.pipeline-head{align-items:flex-start}.pipeline-track{grid-template-columns:1fr;gap:7px}.pipeline-step:not(:last-child)::after{display:none}.overview-grid,.metric-grid,.chart-grid,.components,.movers,.field-grid,.risk-strip{grid-template-columns:1fr}.toolbar select{width:100%}.candidate-card{grid-template-columns:auto 1fr}.candidate-card label{grid-column:2}}
    .closed-summary{grid-template-columns:1.5fr 1fr 1fr 1fr;align-items:center;gap:12px;font-size:12px;white-space:nowrap}.closed-summary strong{text-align:left}
    .straddle-hero{position:relative;overflow:hidden;border:1px solid #a97435;background:linear-gradient(125deg,#17283b 0%,#14243a 58%,#3d2b1b 100%)}.straddle-hero:after{content:"7 · 3";position:absolute;right:22px;bottom:-18px;color:#f4bc7420;font:900 96px/1 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:-.12em;pointer-events:none}.straddle-switch{display:flex;gap:7px;flex-wrap:wrap}.straddle-switch button{border:1px solid #36516f;border-radius:9px;background:#0b1728;color:#b3c4da;padding:9px 12px;font-weight:800;cursor:pointer}.straddle-switch button.active,.straddle-switch button:hover{border-color:#f0a85c;background:#251d16;color:#fff}.straddle-switch button:focus-visible{outline:3px solid var(--focus);outline-offset:2px}.straddle-pane{display:none}.straddle-pane.active{display:block}.straddle-layout{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr);gap:15px;margin-top:15px}.strategy-contract{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin-top:14px}.strategy-contract div{padding:11px;border:1px solid #2d4865;border-radius:9px;background:#091625}.strategy-contract small,.strategy-contract b{display:block}.strategy-contract small{color:var(--muted);font-size:10px}.strategy-contract b{margin-top:5px}.runner-config{display:grid;gap:12px;margin-top:16px;padding-top:15px;border-top:1px solid #2d4865}.option-set{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.option-set.execution{grid-template-columns:repeat(2,minmax(0,1fr))}.option-card{position:relative;display:block;padding:11px;border:1px solid #2d4865;border-radius:9px;background:#091625;cursor:pointer}.option-card input{position:absolute;opacity:0}.option-card:has(input:checked){border-color:#f0a85c;background:#251d16;box-shadow:inset 0 0 0 1px #f0a85c55}.option-card:has(input:focus-visible){outline:2px solid #8dc6ff;outline-offset:2px}.option-card b,.option-card small{display:block}.option-card small{margin-top:4px;color:var(--muted)}.runner-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.runner-log{min-height:170px;max-height:300px}.premium-chart{margin-bottom:14px}.premium-chart svg{display:block;width:100%;height:auto;min-height:210px}.premium-chart-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:8px}.premium-chart-stats div{padding:8px;border-radius:8px;background:#071322}.premium-chart-stats b,.premium-chart-stats small{display:block}.premium-chart-stats small{color:var(--muted);font-size:9px;margin-top:2px}.straddle-position{margin-top:12px;padding:12px;border-left:3px solid #f0a85c;background:#251d16}.straddle-position.flat{border-color:#46617c;background:#0b1728}@media(max-width:950px){.straddle-layout{grid-template-columns:1fr}}@media(max-width:700px){.nav{grid-template-columns:repeat(2,minmax(0,1fr))}.strategy-contract,.option-set,.option-set.execution,.premium-chart-stats{grid-template-columns:1fr}}
  </style>
  <main class="desk">
    <aside class="side">
      <div class="brand"><b>◈ Sector Pulse</b><small>Analytical prioritization workspace</small></div>
      <nav class="nav" aria-label="Dashboard views"><button type="button" class="${initialView === 'sectors' ? 'active' : ''}" data-view="sectors" aria-pressed="${initialView === 'sectors'}">Sector rotation</button><button type="button" class="${initialView === 'handoff' ? 'active' : ''}" data-view="handoff" aria-pressed="${initialView === 'handoff'}">Analysis handoff</button><button type="button" class="${initialView === 'straddles' ? 'active' : ''}" data-view="straddles" aria-pressed="${initialView === 'straddles'}">Long Straddles</button><button type="button" class="${initialView === 'broker' ? 'active' : ''}" data-view="broker" aria-pressed="${initialView === 'broker'}">Live feed & positions</button></nav>
      <div class="broker-card"><span class="label">BROKER CONNECTION</span><b role="status" aria-live="polite"><i id="broker-dot" class="dot" aria-hidden="true"></i><span id="broker-state">Checking FYERS</span></b><button type="button" class="button" id="reauth" aria-describedby="reauth-help">Refresh authentication</button><span id="reauth-help" class="screen-reader-only">Authentication status is still being checked. Manual refresh remains available.</span></div>
    </aside>
    <section class="work">
      <section id="sectors" class="view ${initialView === 'sectors' ? 'active' : ''}">
        <header class="head"><div><span class="label">MULTI-TIMEFRAME SECTOR ANALYSIS</span><h1>Rotation, relative strength & ranking</h1><small class="muted">Analysis only — sector strength is not a buy or sell signal.</small><small id="weight-source" class="muted">Official constituent weight source loading…</small></div><div id="analysis-status" class="status" role="status">Loading completed-bar analysis</div></header>
        <section id="refresh-pipeline" class="refresh-pipeline loading" role="status" aria-live="polite" aria-label="Sector refresh progress"><div class="pipeline-head"><i class="refresh-beacon" aria-hidden="true"></i><div class="pipeline-copy"><small id="pipeline-kicker" class="pipeline-kicker">REFRESH IN PROGRESS</small><p id="pipeline-message" class="pipeline-message"><b>Connecting to FYERS history</b><span>Preparing the first completed-bar snapshot.</span></p></div></div><div id="pipeline-track" class="pipeline-track"></div><div class="refresh-meter" aria-hidden="true"><span></span></div></section>
        <div class="toolbar">
          <div class="mode-tabs" aria-label="Analysis mode"><button type="button" class="active" data-mode="intraday" aria-pressed="true">Intraday</button><button type="button" data-mode="swing" aria-pressed="false">Swing</button></div>
          <label>Filter<select id="sector-filter"><option value="all">All sectors</option><option value="top3">Top 3</option><option value="top5">Top 5</option><option value="bottom3">Bottom 3</option><option value="bottom5">Bottom 5</option><option value="leading">Leading</option><option value="improving">Improving</option><option value="neutral">Neutral</option><option value="weakening">Weakening</option><option value="lagging">Lagging</option><option value="bullish">Bullish MTF alignment</option><option value="bearish">Bearish MTF alignment</option><option value="strong-outperformer">Strong outperformers</option><option value="strong-underperformer">Strong underperformers</option></select></label>
          <label>Sort by<select id="sector-sort"><option value="rank">Rank</option><option value="score">Score</option><option value="rank-change">Rank change</option><option value="relative-strength">Relative strength</option><option value="momentum">Momentum</option><option value="breadth">Breadth</option><option value="volume">Volume</option><option value="adx">ADX</option></select></label>
          <label>Refresh every<select id="analysis-refresh-interval" aria-label="Sector analysis refresh interval"><option value="5000">5 seconds</option><option value="15000">15 seconds</option><option value="30000">30 seconds</option><option value="60000">1 minute</option><option value="300000">5 minutes</option><option value="900000">15 minutes</option><option value="3600000">1 hour</option><option value="14400000">4 hours</option></select></label>
        </div>
        <section id="market-overview" class="overview-grid" aria-label="Calculated market overview"></section>
        <div class="table-wrap"><table aria-label="Multi-timeframe sector ranking"><thead><tr><th>Sector</th><th>Top 3 official-weight contributors</th><th>15m</th><th>1H</th><th>Daily</th><th>Weekly</th><th>MTF alignment</th><th>RS vs NIFTY</th><th>ADX</th><th>Momentum</th><th>Breadth</th><th>Volume</th><th>Rotation</th><th>Score</th><th>Rank</th><th>Rank change</th><th>Last updated</th></tr></thead><tbody id="sector-body"><tr><td colspan="17" class="empty">Loading sector analysis…</td></tr></tbody></table></div>
        <section id="sector-detail" class="panel detail" hidden aria-live="polite"></section>
      </section>
      <section id="broker" class="view ${initialView === 'broker' ? 'active' : ''}">
        <header class="head"><div><span class="label">LIVE FEED & POSITIONS</span><h1>Broker dashboard</h1></div><div id="account-state" class="status" role="status">Loading account</div></header>
        <div class="metric-grid"><article class="metric"><small>Gross live P&L</small><strong id="live-pnl">—</strong><em class="muted">Before charges</em></article><article class="metric"><small>Estimated charges</small><strong id="estimated-charges">—</strong><em class="muted" id="estimated-charges-note">From executed fills</em></article><article class="metric"><small>Estimated net P&L</small><strong id="estimated-net-pnl">—</strong><em class="muted">Gross less estimated charges</em></article><article class="metric"><small>Open positions</small><strong id="open-count">—</strong></article><article class="metric"><small>Available funds</small><strong id="funds">—</strong></article><article class="metric"><small id="closed-pnl-label">Daily closed P&L</small><strong id="closed-pnl">—</strong></article></div>
        <div class="split"><section class="panel"><span class="label">OPEN POSITIONS</span><h2>Current broker positions</h2><div class="row header"><span>Instrument</span><span>Quantity</span><span>Average</span><span>Live P&L</span></div><div id="open-positions"></div></section><section class="panel"><span class="label">CLOSED POSITIONS</span><h2>Realised P&L</h2><div class="period-tabs" aria-label="Realised P and L period">${periods.map((period, index) => `<button type="button" data-period="${period}" class="${index === 0 ? 'active' : ''}" aria-pressed="${index === 0}">${period[0].toUpperCase() + period.slice(1)}</button>`).join('')}</div><div class="row header"><span>Instrument</span><span>Buy / sell</span><span>Quantity</span><span>Realised P&L</span></div><div id="closed-positions"></div><div id="closed-summary" class="row closed-summary" aria-live="polite">Loading closed-position summary…</div></section></div>
      </section>
      <section id="straddles" class="view ${initialView === 'straddles' ? 'active' : ''}">
        <header class="head straddle-hero panel"><div><span class="label">MANAGED STRATEGIES · INDEPENDENT RUNNERS</span><h1>Long Straddles</h1><small class="muted">Choose a market to inspect its own controls, position state, premium chart, runner output and journal.</small></div><div class="straddle-switch" role="tablist" aria-label="Long straddle market"><button type="button" role="tab" id="sensex-straddle-tab" aria-controls="sensex-straddle" aria-selected="${initialStraddleMarket === 'sensex'}" class="${initialStraddleMarket === 'sensex' ? 'active' : ''}" data-straddle-market="sensex">SENSEX</button><button type="button" role="tab" id="nifty-straddle-tab" aria-controls="nifty-straddle" aria-selected="${initialStraddleMarket === 'nifty'}" class="${initialStraddleMarket === 'nifty' ? 'active' : ''}" data-straddle-market="nifty">NIFTY</button></div></header>
      <section id="sensex-straddle" class="straddle-pane ${initialStraddleMarket === 'sensex' ? 'active' : ''}" role="tabpanel" aria-labelledby="sensex-straddle-tab">
        <header class="head straddle-hero panel"><div><span class="label">SENSEX · LONG VOLATILITY</span><h1>Sensex Long Straddle</h1><small class="muted">Completed-candle runner stitched to the external SENSEX strategy.</small></div><div id="straddle-runner-state" class="status" role="status" aria-live="polite">Checking runner</div></header>
        <div class="metric-grid"><article class="metric"><small>Execution default</small><strong>Live</strong></article><article class="metric"><small>Entry regime</small><strong>Low vol · P50</strong></article><article class="metric"><small>Profit activation</small><strong>+10 pts</strong></article><article class="metric"><small>Default exit</small><strong>ST 7 · 3</strong></article><article class="metric"><small>Default hard stop</small><strong>None</strong></article><article class="metric"><small>Square-off</small><strong>15:20 IST</strong></article></div>
        <div class="straddle-layout"><section class="panel"><div class="step-title"><div><span class="label">RUNNER CONTROL</span><h2>Strategy process</h2><small class="muted">Choose exactly the same execution and exit options exposed by the Python script.</small></div><span class="badge">FYERS</span></div><div id="straddle-contract" class="strategy-contract"></div><form id="straddle-options" class="runner-config"><div><span class="label">POSITION SIZE</span><label class="field">Lots per leg<input id="straddle-lots" type="number" min="1" max="20" step="1" value="1" inputmode="numeric"><small>Buys this many lots of both the ATM call and put. Confirm available funds before live use.</small></label></div><div><span class="label">NEW-ENTRY WINDOW · IST</span><div class="field-grid"><label class="field">Start time<input id="straddle-entry-start" type="time" value="09:15" required></label><label class="field">End time<input id="straddle-entry-end" type="time" value="11:30" required></label></div><small class="muted">New entries and one permitted re-entry are blocked outside this window. Existing positions keep their normal stop, trail and EOD square-off management.</small></div><div><span class="label">EXECUTION OPTION</span><div class="option-set execution"><label class="option-card"><input type="radio" name="straddle-mode" value="live" checked><b>Live · <code>--live</code></b><small>Places real FYERS orders after one start confirmation.</small></label><label class="option-card"><input type="radio" name="straddle-mode" value="paper"><b>Paper · script default</b><small>Simulates entries and exits using live prices.</small></label></div></div><div><span class="label">EXIT OPTION</span><div class="option-set"><label class="option-card"><input type="radio" name="straddle-exit" value="supertrend" checked><b>Supertrend trail</b><small><code>--supertrend-trail</code> · 7,3 after +10 · no stop.</small></label><label class="option-card"><input type="radio" name="straddle-exit" value="fixed"><b>Fixed target</b><small><code>--fixed-target</code> · 30 target · no stop.</small></label><label class="option-card"><input type="radio" name="straddle-exit" value="trail"><b>Profit trail</b><small><code>--trail-profit</code> · trail 10 after +30 · no stop.</small></label></div></div></form><div class="runner-actions"><button type="button" class="button" id="start-straddle">Start live runner</button><button type="button" class="button secondary" id="stop-straddle">Stop runner</button></div><div id="straddle-action-status" class="handoff-status" role="status" aria-live="polite">No runner action requested.</div><div id="straddle-position" class="straddle-position flat"></div></section><section class="panel"><div class="step-title"><div><span class="label">COMBINED PREMIUM</span><h2>CE + PE live chart</h2></div><small id="premium-chart-updated" class="muted"></small></div><div id="premium-chart" class="chart-card premium-chart"><div class="chart-empty">Chart starts when the strategy opens a position.</div></div><span class="label">RUNNER OUTPUT</span><h2>Recent activity</h2><pre id="straddle-output" class="packet-preview runner-log">Waiting for runner status…</pre></section></div>
        <section class="panel" style="margin-top:15px"><div class="step-title"><div><span class="label">RECENT COMPLETED TRADES</span><h2>Local strategy journal</h2></div><small id="straddle-updated" class="muted"></small></div><div class="row header"><span>Exit</span><span>Strike</span><span>P&amp;L points</span><span>Reason</span></div><div id="straddle-trades"><p class="empty">No completed paper trades recorded.</p></div></section>
      </section>
      <section id="nifty-straddle" class="straddle-pane ${initialStraddleMarket === 'nifty' ? 'active' : ''}" role="tabpanel" aria-labelledby="nifty-straddle-tab">
        <header class="head straddle-hero panel"><div><span class="label">NIFTY · LONG VOLATILITY</span><h1>NIFTY Long Straddle</h1><small class="muted">Volatility-compression runner stitched to the external NIFTY strategy.</small></div><div id="nifty-straddle-runner-state" class="status" role="status" aria-live="polite">Checking runner</div></header>
        <div class="metric-grid"><article class="metric"><small>Execution default</small><strong>Live</strong></article><article class="metric"><small>Entry regime</small><strong>Low vol · P50</strong></article><article class="metric"><small>Hard stop</small><strong>15 pts</strong></article><article class="metric"><small>Target</small><strong>30 pts</strong></article><article class="metric"><small>Expiry</small><strong>Nearest weekly</strong></article><article class="metric"><small>Square-off</small><strong>15:20 IST</strong></article></div>
        <div class="straddle-layout"><section class="panel"><div class="step-title"><div><span class="label">RUNNER CONTROL</span><h2>Strategy process</h2><small class="muted">Options match <code>nifty_straddle.py</code>; no unsupported exit modes are added.</small></div><span class="badge">FYERS</span></div><div id="nifty-straddle-contract" class="strategy-contract"></div><form id="nifty-straddle-options" class="runner-config"><div class="field-grid"><label class="field">Lots per leg<input id="nifty-straddle-lots" type="number" min="1" max="20" step="1" value="1" inputmode="numeric"></label><label class="field">Hard stop (premium points)<input id="nifty-straddle-stoploss" type="number" min="0.05" step="0.05" value="15"></label><label class="field">Target (premium points)<input id="nifty-straddle-target" type="number" min="0.05" step="0.05" value="30"></label><label class="field">Entry start (IST)<input id="nifty-straddle-entry-start" type="time" value="09:15" required></label><label class="field">Entry end (IST)<input id="nifty-straddle-entry-end" type="time" value="11:30" required></label></div><small class="muted">New entries and one permitted re-entry are blocked outside this window. Existing positions keep their normal stop, trail and EOD square-off management.</small><div><span class="label">EXECUTION OPTION</span><div class="option-set execution"><label class="option-card"><input type="radio" name="nifty-straddle-mode" value="live" checked><b>Live · <code>--live</code></b><small>Can place real FYERS orders after an explicit start confirmation.</small></label><label class="option-card"><input type="radio" name="nifty-straddle-mode" value="paper"><b>Paper · script default</b><small>Forward-tests entries and exits without broker orders.</small></label></div></div></form><div class="runner-actions"><button type="button" class="button" id="start-nifty-straddle">Start live runner</button><button type="button" class="button secondary" id="stop-nifty-straddle">Stop runner</button></div><div id="nifty-straddle-action-status" class="handoff-status" role="status" aria-live="polite">No runner action requested.</div><div id="nifty-straddle-position" class="straddle-position flat"></div></section><section class="panel"><div class="step-title"><div><span class="label">COMBINED PREMIUM</span><h2>CE + PE status</h2></div></div><div id="nifty-premium-chart" class="chart-card premium-chart"><div class="chart-empty">The current NIFTY script does not emit chart history. Position premium updates remain visible in runner output.</div></div><span class="label">RUNNER OUTPUT</span><h2>Recent activity</h2><pre id="nifty-straddle-output" class="packet-preview runner-log">Waiting for runner status…</pre></section></div>
        <section class="panel" style="margin-top:15px"><div class="step-title"><div><span class="label">RECENT COMPLETED TRADES</span><h2>Local strategy journal</h2></div><small id="nifty-straddle-updated" class="muted"></small></div><div class="row header"><span>Exit</span><span>Strike</span><span>P&amp;L points</span><span>Reason</span></div><div id="nifty-straddle-trades"><p class="empty">No completed paper trades recorded.</p></div></section>
      </section>
      </section>
      <section id="handoff" class="view ${initialView === 'handoff' ? 'active' : ''}">
        <header class="head"><div><span class="label">FULL ALIGNMENT · USER-CONTROLLED HANDOFF</span><h1>From market evidence to a reviewable packet</h1><small class="muted">Collect, inspect and export locally. Nothing is sent to an AI recipient or broker automatically.</small></div><div class="status">FYERS data · FYERS execution selected</div></header>
        <div class="handoff-banner"><div class="handoff-mark">↗</div><div><strong>Preview and transmission are separate actions</strong><span>Choosing ChatGPT or Codex only labels the local packet. Preview, copy and download remain on this device. Account funds enter a packet only after both inclusion and confirmation are checked.</span></div></div>
        <div class="handoff-grid">
          <section class="panel"><div class="step-title"><div><span class="label">1 · CHOOSE ROUTE & COLLECT</span><h2>Full-alignment stock candidates</h2><small class="muted">Completed 15m, 1H, Daily and Weekly evidence only.</small></div><button type="button" class="button" id="collect-candidates">Collect cash equity matches</button></div><span class="label" style="margin-top:14px">INSTRUMENT ROUTE — REQUIRED</span><div class="option-set execution route-set"><label class="option-card"><input type="radio" name="instrument-route" value="cash_equity" checked><b>Cash equity</b><small>Entry, structural stop, target, shares and cash-risk sizing only. No calls, puts or spreads.</small></label><label class="option-card"><input type="radio" name="instrument-route" value="stock_options"><b>Stock options</b><small>Validated stock-option contracts and defined-risk spreads only. No cash-share plan.</small></label></div><div id="candidate-status" class="handoff-status">Choose one route, then collect matches.</div><div id="candidate-list" class="candidate-list"></div><div id="candidate-batch-actions" class="packet-actions" hidden style="margin-top:12px"><button type="button" class="button secondary" id="select-all-candidates">Select all eligible</button><button type="button" class="button secondary" id="clear-candidate-selection">Clear selection</button><button type="button" class="button" id="prepare-handoff-batch">Prepare selected FYERS batch</button></div></section>
          <section class="panel"><span class="label">2 · OPTIONAL PLANNING PREFERENCES</span><h2>Your sizing and reward preferences</h2><label class="field" style="margin-top:12px"><input id="enforce-risk-controls" type="checkbox"> Apply these capital limits to analysis and ticket sizing</label><div class="field-grid" style="margin-top:12px"><label class="field">Planning capital (₹)<input id="planning-capital" type="number" min="1" step="1000" value="100000"></label><label class="field">Maximum daily loss (₹)<input id="daily-loss-limit" type="number" min="1" step="100" value="5000"></label><label class="field">Per-idea risk allocation (₹)<input id="idea-risk-limit" type="number" min="1" step="100" value="2000"></label><label class="field">Reserved risk buffer (₹)<input id="risk-reserve" type="number" min="0" step="100" value="1000"></label><label class="field">Maximum simultaneous positions<input id="max-positions" type="number" min="1" step="1" value="3"></label><label class="field">Optional minimum reward:risk (0 = no gate)<input id="minimum-rr" type="number" min="0" step="0.1" value="0"></label><label class="field">Stop / invalidation basis<select id="stop-basis"><option value="price">Exact price level</option><option value="percent">Percent from entry / spot</option></select></label><label class="field">Order-type preference<select id="order-type"><option value="LIMIT">Limit (default, live eligible)</option><option value="MARKET">Market (preview only)</option></select></label></div><div id="policy-impact" class="risk-strip" aria-live="polite"></div><div id="policy-validation" class="handoff-status" role="status"></div><p class="muted">Capital values are used only if you enable capital controls. A reward:risk value is considered only when you enter one above zero. Validated spreads default to one lot and cash ideas to one share; choose a larger quantity in the ticket. Fresh FYERS contract, quote, liquidity, funds/margin and confirmation checks always apply.</p>
          <span class="label" style="margin-top:14px">RECIPIENT — REQUIRED</span><div class="choice-row"><label class="choice"><input type="radio" name="recipient" value="chatgpt"> ChatGPT</label><label class="choice"><input type="radio" name="recipient" value="codex" checked> Codex</label></div>
          <span class="label" style="margin-top:14px">LOCAL ACTION — REQUIRED</span><div class="choice-row"><label class="choice"><input type="radio" name="handoff-action" value="preview"> Preview only</label><label class="choice"><input type="radio" name="handoff-action" value="export"> Prepare export</label></div>
          <div class="privacy-gate"><label class="choice"><input id="include-funds" type="checkbox"> Include freshly read FYERS available funds</label><label class="choice"><input id="confirm-funds" type="checkbox" disabled> I confirm funds may be included in this local packet</label></div>
          <button type="button" class="button" id="prepare-packet" style="margin-top:12px">Prepare local preview</button><div id="packet-status" class="handoff-status" role="status" aria-live="polite"></div></section>
        </div>
        <section id="analysis-panel" class="panel analysis-panel" hidden><div class="step-title"><div><span class="label">3 · REVIEW PROPOSALS</span><h2>Evidence-backed opportunity plans</h2><small id="ai-review-state" class="muted"></small></div><div class="status">Decision support only</div></div><div id="analysis-board" class="analysis-board"></div><div id="analysis-exclusions" class="excluded-list"></div></section>
        <section id="packet-panel" class="panel packet-panel" hidden><div class="step-title"><div><span class="label">3 · REVIEW</span><h2>Analysis packet</h2><small class="muted">No transmission has occurred.</small></div><div class="packet-actions"><button type="button" class="button secondary" id="copy-packet">Copy JSON</button><button type="button" class="button" id="download-packet" hidden>Download JSON</button></div></div><pre id="packet-preview" class="packet-preview"></pre></section>
        <section id="ticket-panel" class="panel ticket-panel" hidden><div class="step-title"><div><span class="label">OPTIONAL · SEPARATE BROKER ACTION</span><h2>Exact FYERS trade ticket</h2><small class="muted">A packet never authorizes this workflow.</small></div><div id="ticket-capability" class="status">Checking FYERS capability</div></div><p class="ticket-warning">FYERS is the user-selected route. Preparing a ticket refreshes token/profile, exact master contract, chain and Greeks, bid/ask, lot/tick, funds, margin coverage, positions and order state. Only debit spreads with fully funded protection-first premium can become submit-eligible; credit spreads remain blocked when exact basket margin is unavailable. Submission still requires an explicitly enabled runtime and the exact current confirmation phrase.</p><div class="field-grid" style="margin-top:12px"><label class="field">Broker<input id="ticket-broker" value="fyers" readonly></label><label class="field">Defined-risk proposal<select id="ticket-proposal"><option value="">Choose a packet proposal</option></select></label><label class="field">Lots<input id="ticket-lots" type="number" min="1" step="1" value="1"></label><label class="field">Declared external open risk (₹)<input id="external-open-risk" type="number" min="0" step="100" placeholder="Required if FYERS has other open positions"></label></div><button type="button" class="button" id="prepare-ticket" style="margin-top:12px">Refresh FYERS and prepare exact preview</button><div id="ticket-status" class="handoff-status" role="status" aria-live="polite"></div><div id="ticket-review" hidden><div id="risk-strip" class="risk-strip"></div><pre id="ticket-preview" class="packet-preview"></pre><label class="field" style="margin-top:10px">Exact confirmation phrase<input id="ticket-confirmation" class="confirmation-input" autocomplete="off" spellcheck="false"></label><button type="button" class="button danger" id="submit-ticket" disabled style="margin-top:10px">Submit confirmed FYERS basket</button></div></section>
        <section class="panel automation-panel"><details><summary>Optional unattended FYERS policy · disabled by default</summary><p class="ticket-warning">This is separate from per-order approval. It authors a bounded FYERS policy only; this dashboard contains no automatic signal runner. PAPER is the default. A LIVE profile also requires a separate runtime gate, a released kill switch, fresh FYERS preflight for every order, and all policy checks.</p><div class="choice-row"><label class="choice"><input id="auto-enabled" type="checkbox"> Enable policy after acknowledgement</label><label class="choice"><input id="auto-kill" type="checkbox" checked> Kill switch engaged</label><label class="choice"><input id="auto-uncertain" type="checkbox" checked disabled> Halt on uncertain order status</label><label class="choice"><input id="auto-completed" type="checkbox" checked disabled> Completed candles required</label><label class="choice"><input id="auto-option-evidence" type="checkbox" checked disabled> Full option chain/master/liquidity/Greeks/lot/tick evidence required</label><label class="choice"><input id="auto-risk-defined" type="checkbox" checked disabled> Stop or defined-risk spread required</label><label class="choice"><input id="auto-target" type="checkbox" checked disabled> Target required</label></div><div class="field-grid" style="margin-top:12px"><label class="field">Execution mode<select id="auto-mode"><option value="PAPER">Paper / dry-run</option><option value="LIVE">Live (extra runtime gate)</option></select></label><label class="field">Universe<select id="auto-universe"><option value="ALIGNED_EQUITIES_AND_OPTIONS">Aligned equities + index and stock options</option><option value="ALIGNED_EQUITIES">Aligned equities only</option><option value="ALIGNED_OPTIONS">Aligned options only</option></select></label><label class="field">Exact allowed FYERS underlyings, comma-separated<input id="auto-symbols" value="NSE:RELIANCE-EQ,NSE:NIFTY50-INDEX"></label><label class="field">Supported index underlyings<input id="auto-index-underlyings" value="NSE:NIFTY50-INDEX"></label><label class="field">Allowed segments, comma-separated<input id="auto-segments" value="NSE_CM,NSE_FO"></label><label class="field">Allowed strategies, comma-separated<input id="auto-strategies" value="EQUITY_LONG,EQUITY_SHORT,BULL_CALL_DEBIT,BEAR_PUT_DEBIT"></label><label class="field" style="grid-column:1/-1">Completed-candle signal conditions, one per line<textarea id="auto-signals">15m, 1h, Daily and Weekly completed candles must all be fresh
Every timeframe must agree as exact FULL BULLISH ALIGNMENT or FULL BEARISH ALIGNMENT</textarea></label><label class="field">Planning capital (₹)<input id="auto-planning-capital" type="number" min="1" value="100000"></label><label class="field">Maximum daily loss (₹)<input id="auto-daily-loss" type="number" min="1" max="5000" value="5000"></label><label class="field">Per-idea risk (₹)<input id="auto-idea-risk" type="number" min="1" value="2000"></label><label class="field">Reserved risk buffer (₹)<input id="auto-risk-reserve" type="number" min="0" value="1000"></label><label class="field">Maximum concurrent positions<input id="auto-max-positions" type="number" min="1" max="20" value="3"></label><label class="field">Maximum concurrent orders<input id="auto-max-orders" type="number" min="1" max="20" value="2"></label><label class="field">Minimum reward:risk<input id="auto-min-rr" type="number" min="1" max="10" step="0.1" value="1.5"></label><label class="field">Order type<select id="auto-order-type"><option value="LIMIT">Limit only</option></select></label><label class="field">Maximum limit buffer (%)<input id="auto-limit-buffer" type="number" min="0" max="5" step="0.1" value="0.5"></label><label class="field">Maximum bid/ask spread (%)<input id="auto-max-spread" type="number" min="0.1" max="20" step="0.1" value="8"></label><label class="field">Trading start (IST)<input id="auto-start" type="time" value="09:30"></label><label class="field">Trading end (IST)<input id="auto-end" type="time" value="15:00"></label><label class="field">Minimum DTE<input id="auto-min-dte" type="number" min="0" max="365" value="1"></label><label class="field">Maximum DTE<input id="auto-max-dte" type="number" min="0" max="365" value="14"></label><label class="field">Cooldown (minutes)<input id="auto-cooldown" type="number" min="1" max="1440" value="30"></label><label class="field">Stale-data veto (seconds)<input id="auto-stale" type="number" min="1" max="300" value="15"></label></div><div class="packet-actions" style="margin-top:12px"><button type="button" class="button secondary" id="save-auto-draft">Save disabled PAPER draft</button><button type="button" class="button secondary" id="preview-auto-policy">Preview complete policy</button></div><div id="auto-status" class="handoff-status" role="status" aria-live="polite"></div><div id="auto-review" hidden><pre id="auto-preview" class="packet-preview"></pre><label class="field" style="margin-top:10px">Exact policy acknowledgement<input id="auto-ack" class="confirmation-input" autocomplete="off" spellcheck="false"></label><button type="button" class="button" id="save-auto-policy" disabled style="margin-top:10px">Save acknowledged policy</button></div></details></section>
      </section>
    </section>
  </main>`

  const $ = id => document.getElementById(id)
  let mode = 'intraday'
  let period = 'daily'
  let analysis = null
  let selectedSector = ''
  let selectedTimeframe = 'daily'
  let analysisRefreshTimer = null
  let analysisReadyPollMs = storedRefreshInterval
  let candidateCollection = null
  let analysisRun = null
  let handoffPacket = null
  let ticketProposals = []
  let ticketPreview = null
  let handoffBatchPreview = null
  let ticketCapabilities = null
  let automationPreview = null
  $('ticket-panel').insertAdjacentHTML('afterend', '<section id="handoff-batch-panel" class="panel ticket-panel" hidden><div class="step-title"><div><span class="label">MULTI-PLAN PREVIEW · FYERS</span><h2>Selected recommendation batch</h2><small class="muted">Every selected symbol is revalidated together; an invalid item blocks the whole batch.</small></div><div class="status">No partial submission</div></div><label class="field">Declared external open risk (₹)<input id="handoff-batch-external-risk" type="number" min="0" step="100" placeholder="Required when other FYERS positions are open"></label><div id="handoff-batch-status" class="handoff-status" role="status" aria-live="polite"></div><div id="handoff-batch-review" hidden><pre id="handoff-batch-preview" class="packet-preview"></pre><label class="field" style="margin-top:10px">Exact confirmation phrase<input id="handoff-batch-confirmation" class="confirmation-input" autocomplete="off" spellcheck="false"></label><button type="button" class="button danger" id="submit-handoff-batch" disabled style="margin-top:10px">Submit all selected</button></div></section>')
  $('minimum-rr').value = '1'
  document.querySelector('.nav').insertAdjacentHTML('beforeend', `<button type="button" class="${initialView === 'screener' ? 'active' : ''}" data-view="screener" aria-pressed="${initialView === 'screener'}">Screener</button>`)
  document.querySelector('.nav').insertAdjacentHTML('beforeend', `<button type="button" class="${initialView === 'settings' ? 'active' : ''}" data-view="settings" aria-pressed="${initialView === 'settings'}">Risk Guardrails</button>`)
  document.querySelector('.nav').insertAdjacentHTML('beforeend', `<button type="button" class="${initialView === 'ema-band' ? 'active' : ''}" data-view="ema-band" aria-pressed="${initialView === 'ema-band'}">EMA Band</button>`)
  document.querySelector('.nav').insertAdjacentHTML('beforeend', `<button type="button" class="${initialView === 'kama' ? 'active' : ''}" data-view="kama" aria-pressed="${initialView === 'kama'}">KAMA Strategy</button>`)
  document.querySelector('.nav').insertAdjacentHTML('beforeend', `<button type="button" class="${initialView === 'trade-parser' ? 'active' : ''}" data-view="trade-parser" aria-pressed="${initialView === 'trade-parser'}">Trade Parser</button>`)
  document.querySelector('.work').insertAdjacentHTML('beforeend', `<section id="trade-parser" class="view ${initialView === 'trade-parser' ? 'active' : ''}"><header class="head"><div><span class="label">FYERS CONTRACT RESOLUTION · CONFIRMATION-GATED</span><h1>Trade Recommendation Parser</h1><small class="muted">Paste a message, map it to the official FYERS master, then prepare and submit an exact limit-order ticket.</small></div><div class="status">FYERS order route</div></header><section class="panel"><div class="step-title"><div><span class="label">PASTE RECOMMENDATION</span><h2>Review a text-based trade call</h2><small class="muted">Recognizes BUY/SELL, C/P or CE/PE, expiry, entry, stop loss, and targets. An exact contract is required for an order preview.</small></div><span class="badge">FYERS ONLY</span></div><label class="field" style="margin-top:14px">Recommendation text<textarea id="trade-parser-input" rows="8" placeholder="Example: BUY MCX CRUDEOIL 17-SEP CE 9100 AT 253.30 SL 235 TGT 285"></textarea><small>Verify the source independently. The ticket uses the FYERS master and a fresh FYERS quote.</small></label><div class="packet-actions" style="margin-top:12px"><button type="button" class="button" id="trade-parser-run">Parse recommendation</button><button type="button" class="button secondary" id="trade-parser-clear">Clear</button></div><div id="trade-parser-status" class="handoff-status" role="status">Paste a recommendation to begin.</div><div id="trade-parser-result" class="packet-preview" hidden style="margin-top:12px"></div><section id="trade-parser-order" class="ticket-warning" hidden style="margin-top:12px"><b>FYERS order route</b><div class="field-grid" style="margin-top:10px"><label class="field">Lots<input id="trade-parser-lots" type="number" min="1" step="1" value="1"></label></div><div class="packet-actions" style="margin-top:10px"><button type="button" class="button secondary" id="trade-parser-prepare-order">Prepare FYERS order</button><button type="button" class="button danger" id="trade-parser-submit-order" disabled>Submit confirmed order</button></div><div id="trade-parser-order-status" class="handoff-status">An exact contract match is required before an FYERS order preview can be prepared.</div></section></section></section>`)
  $('trade-parser-result').insertAdjacentHTML('afterend', '<div id="trade-parser-ai-result" class="ticket-warning" hidden style="margin-top:12px"></div>')
  $('trade-parser-lots').closest('.field-grid').insertAdjacentHTML('beforeend', '<label class="field">Entry type<select id="trade-parser-entry-mode"><option value="LIMIT">Limit</option><option value="STOP_LIMIT">Stop-limit</option></select><small id="trade-parser-entry-help">Limit buys at or below the stated price.</small></label><label class="field">Trigger price<input id="trade-parser-trigger-price" type="number" step="any"></label><label class="field">Limit price<input id="trade-parser-limit-price" type="number" step="any"></label>')
  $('trade-parser-prepare-order').textContent = 'Submit FYERS order'
  $('trade-parser-submit-order').hidden = true
  document.querySelector('.work').insertAdjacentHTML('beforeend', `<section id="ema-band" class="view ${initialView === 'ema-band' ? 'active' : ''}"><header class="head"><div><span class="label">RESEARCH WORKBENCH · PAPER ONLY</span><h1>EMA Band</h1><small class="muted">Independent completed-candle research panel. It does not connect to or control either Long Straddles runner.</small></div><div class="status">Paper default · optional live auto-trading</div></header><section class="panel"><div class="step-title"><div><span class="label">CONFIGURATION</span><h2>Trend-following EMA band</h2><small class="muted">Use the band as a directional research framework, not a profitability claim or an order instruction.</small></div><span class="badge">PAPER DEFAULT · LIVE OPTIONAL</span></div><div class="field-grid" style="margin-top:14px"><label class="field">Segment<select id="ema-band-segment"><option value="index">Cash / index</option><option value="fno">F&amp;O</option><option value="commodity">Commodities</option><option value="stock-option">Stock options</option></select></label><label class="field">Broker-master instrument<select id="ema-band-underlying" disabled><option>Refresh the official cache to search instruments</option></select></label><label class="field" style="grid-column:1/-1">Broker-supported symbol or option search<input id="ema-band-search" autocomplete="off" placeholder="Search exact broker/master instrument; option symbols are never constructed here"><small>For stock options, enter the underlying or exact master search. Expiry, strike, call/put, lot size and tick must be returned by broker metadata before research is enabled.</small></label><div id="ema-band-contract" class="ticket-warning" style="grid-column:1/-1"><b>Contract context: not validated.</b> Metadata and quotes are unavailable until an explicit, fresh broker/master validation. The EMA Band stays paper-only and fail-closed.</div><div class="packet-actions" style="grid-column:1/-1"><button type="button" class="button secondary" id="ema-band-master-refresh">Refresh official FYERS master cache</button><span id="ema-band-master-status" class="handoff-status">Cache status loading…</span></div><label class="field">Research timeframe<select id="ema-band-timeframe"><option>5 minutes</option><option>15 minutes</option><option>1 hour</option></select></label><label class="field">EMA band length (High / Low)<input id="ema-band-length" type="number" value="21" min="1" max="500"><small>Applies separately to High and Low, exactly as the Pine source.</small></label><label class="field">Chart timeframe<select id="ema-band-chart-timeframe"><option>5 minutes</option><option>15 minutes</option><option>1 hour</option></select><small>Display only; this never changes the runner’s timeframe or trade logic.</small></label><label class="field">Chart history<select id="ema-band-chart-bars"><option value="80">80 candles</option><option value="160">160 candles</option><option value="240">240 candles</option><option value="320" selected>320 candles</option><option value="500">500 candles</option></select><small>Controls the displayed FYERS history only.</small></label><label class="field">Same-direction re-entry cooldown (bars)<input id="ema-band-cooldown" type="number" value="0" min="0"></label><label class="field">Entry session (IST)<input id="ema-band-session" type="text" value="0915-1515"><small>Optional Pine entry filter; exits remain active outside it.</small></label><label class="field">Signal confirmation<select id="ema-band-confirmation"><option>Completed candle only</option></select></label></div><div class="risk-strip" style="margin-top:14px"><div><b id="ema-band-direction">WATCH</b><small>Current research direction</small></div><div><b>EMA 21 High / Low</b><small>Band inputs</small></div><div><b>Completed close</b><small>Signal confirmation</small></div><div><b>PAPER</b><small>Execution state</small></div></div><div class="ticket-warning">Paper mode has no broker or order route. Live mode (selected below) adds Start/Stop controls that automatically submit real FYERS BUY/SELL orders on validated signals; a valid paper study still requires completed candles, explicit transaction costs, and out-of-sample validation.</div><div id="ema-band-status" class="handoff-status" role="status"><b>Python strategy: READY · PAPER ONLY</b><br>Completed 5-minute candles only: a prior candle crosses EMA-21 High or Low; the following candle's completed close must be beyond that signal candle's midpoint—above for long, below for short—regardless of candle color. Paper fills use next-bar open; EMA-band exits and 15:20 IST square-off remain required. Backtest waits for a fresh, validated FYERS instrument and historical response. No market data or broker request has been made.</div></section><section class="panel" style="margin-top:15px"><span class="label">RESEARCH CHECKLIST</span><h2>Interpretation guardrails</h2><div class="choice-row" style="margin-top:12px"><span class="choice">Long: prior completed body crosses EMA High; following completed candle closes above that signal candle's midpoint, regardless of color.</span><span class="choice">Short: prior completed body crosses EMA Low; following completed candle closes below that signal candle's midpoint, regardless of color.</span><span class="choice">Exit: completed close inside the EMA High/Low band.</span></div></section></section>`)
  document.querySelector('.work').insertAdjacentHTML('beforeend', `<section id="kama" class="view ${initialView === 'kama' ? 'active' : ''}"><header class="head"><div><span class="label">INDEPENDENT STRATEGY · PAPER DEFAULT</span><h1>KAMA Strategy</h1><small class="muted">A separate completed-candle KAMA V6 lifecycle. EMA only screens the broker-master symbol; it never authorizes a KAMA trade.</small></div><div class="status" id="kama-capability">Loading policy…</div></header><section class="panel"><div class="step-title"><div><span class="label">RUNNER CONFIGURATION</span><h2>Kaufman Adaptive Moving Average</h2><small class="muted">KAMA direction, efficiency, breakout/reclaim and KAMA exits alone decide position state.</small></div><span class="badge">NO MANUAL TICKETS</span></div><div class="field-grid" style="margin-top:14px"><label class="field">Exact broker-master underlying<input id="kama-underlying" autocomplete="off" placeholder="NSE:RELIANCE-EQ"><small>Screened against the current master only.</small></label><label class="field">Timeframe<select id="kama-timeframe"><option>5 minutes</option><option>15 minutes</option><option>1 hour</option></select></label><label class="field">KAMA efficiency length<input id="kama-length" type="number" value="10" min="1"></label><label class="field">Fast / slow lengths<div class="choice-row"><input id="kama-fast" type="number" value="2" min="1"><input id="kama-slow" type="number" value="30" min="2"></div></label><label class="field">Minimum efficiency ratio<input id="kama-efficiency" type="number" value="0.35" min="0" max="1" step="0.05"></label><label class="field">Breakout / cooldown bars<div class="choice-row"><input id="kama-breakout" type="number" value="5" min="2"><input id="kama-cooldown" type="number" value="2" min="0"></div></label><label class="choice"><input id="kama-reclaims" type="checkbox" checked> Allow KAMA reclaim entries</label><label class="field">Mode<select id="kama-mode"><option value="PAPER">Paper</option><option value="LIVE" disabled>Live — operator-gated</option></select></label><label class="field kama-live-setting" hidden>Quantity<input id="kama-quantity" type="number" min="1" step="1" placeholder="Whole units"></label><label class="field kama-live-setting" hidden>Invalidation / stop price<input id="kama-invalidation" type="number" min="0.01" step="0.05" placeholder="Required for live"></label><label class="field kama-live-setting" hidden>Maximum idea risk (₹)<input id="kama-idea-risk" type="number" min="1" step="1" value="2000"></label></div><div class="risk-strip"><div><b>ENTRY</b><small>Completed KAMA V6 only</small></div><div><b>HOLD</b><small>KAMA position state only</small></div><div><b>EXIT</b><small>Reversal or 15:15 square-off</small></div><div><b>RISK</b><small>Fresh preflight, broker confirmation and reconciliation</small></div></div><div class="packet-actions"><button type="button" class="button secondary" id="kama-runner-toggle">Start paper runner</button></div><div id="kama-runner-status" class="handoff-status" role="status">Runner stopped. No broker order route is active.</div></section><section class="panel" style="margin-top:15px"><span class="label">OBSERVABILITY</span><h2>Current KAMA runner</h2><div id="kama-policy" class="ticket-warning">Policy loads from the KAMA-only API.</div><section id="kama-chart" class="chart-card premium-chart" style="margin-top:12px"><div class="chart-empty">Chart starts only after completed KAMA candles are received.</div></section><pre id="kama-state" class="packet-preview">No current runner state.</pre><h3>Lifecycle events</h3><pre id="kama-events" class="packet-preview runner-log">No KAMA events.</pre></section></section>`)
  $('kama-underlying').closest('label').outerHTML = '<label class="field">Execution instrument<select id="kama-execution-mode"><option value="EQUITY">Equity / Futures</option><option value="OPTIONS">Options — automatic ATM Call / Put</option></select><small>Options mode uses the KAMA direction on the selected underlying.</small></label><label class="field" style="grid-column:1/-1">Search underlying<input id="kama-underlying-search" autocomplete="off" placeholder="Search RELIANCE, NIFTY, SENSEX, CRUDEOIL…"><small>Searches current NSE, BSE, and MCX FYERS masters; exact symbol formatting is not required.</small></label><label class="field">FYERS underlying<select id="kama-underlying" disabled><option value="">Type at least two characters to search</option></select><small id="kama-underlying-status">Choose Equity / Futures or Options, then search.</small></label>'
  $('kama-quantity').closest('label').id = 'kama-size-field'
  $('kama-quantity').insertAdjacentHTML('afterend', '<small id="kama-size-help">Shares for equities; lots for MCX futures.</small>')
  $('kama-invalidation').insertAdjacentHTML('afterend', '<small id="kama-invalidation-help">Price invalidation for the directly traded instrument.</small>')
  document.querySelector('#kama .risk-strip div:nth-child(3) small').id = 'kama-exit-session'
  $('ema-band-length').closest('label').insertAdjacentHTML('afterend', '<label class="field">EMA slope lookback (completed bars)<input id="ema-band-slope-lookback" type="number" value="8" min="2" max="100"><small>Measures the EMA-band midpoint; this blocks flat conditions only.</small></label><label class="field">Minimum slope (ATR per bar)<input id="ema-band-minimum-slope-atr" type="number" value="0.10" min="0" step="0.01" max="2"><small>0.10 is the default; raise it to reject more sideways conditions.</small></label>')
  $('ema-band-slope-lookback').closest('label').insertAdjacentHTML('afterend', '<label class="field"><input id="ema-band-resistance-volume-exit" type="checkbox"> Protect a profitable long at weak resistance</label><label class="field">Resistance breakout volume<input id="ema-band-resistance-volume-multiple" type="number" value="1.5" min="0" step="0.1" max="10"><small>Required multiple of the prior average volume.</small></label><label class="field">Resistance volume lookback<input id="ema-band-resistance-volume-lookback" type="number" value="20" min="2" max="100"><small>Completed candles used for the volume average.</small></label>')
  document.querySelector('.work').insertAdjacentHTML('beforeend', `<section id="screener" class="view ${initialView === 'screener' ? 'active' : ''}"><header class="head"><div><span class="label">CHARTINK · SOURCE ONLY</span><h1>Screener</h1><small class="muted">A dedicated source view for user-provided Chartink screeners.</small></div><div class="status">Awaiting screener URLs</div></header><section class="panel"><span class="label">NO SOURCES CONFIGURED</span><h2>Chartink candidates will appear here</h2><p class="muted">Provide the exact Chartink screener URLs you want to use. This view will not invent URLs, scrape pages, or refresh automatically.</p><div class="ticket-warning">Imported results will remain source-only and separate from Analysis Handoff and broker order planning until you explicitly review and select them.</div></section></section>`)
  const chartinkSourceUrl = 'https://chartink.com/screener/independent-indicator-signals-daily-or'
  document.querySelector('#screener .status').textContent = '1 source configured'
  document.querySelector('#screener .panel').innerHTML = `<span class="label">MANAGED SOURCES · LOCAL ONLY</span><h2>Chartink screeners</h2><div class="field-grid"><label class="field">Friendly label (optional)<input id="screener-label" placeholder="My daily scan"></label><label class="field">Chartink screener URL<input id="screener-url" type="url" placeholder="https://chartink.com/screener/..."></label></div><div class="packet-actions" style="margin-top:10px"><button type="button" class="button" id="add-screener">Add source</button><button type="button" class="button secondary" id="refresh-screeners">Refresh all</button><button type="button" class="button secondary" id="analyze-screeners" disabled>Analyze selected symbols (0)</button></div><div id="screener-status" class="handoff-status"></div><div id="screener-sources" class="candidate-list"></div><section id="screener-analysis" class="analysis-panel" hidden><div class="step-title"><div><span class="label">READ-ONLY ADVISORY</span><h2>Screener candidate analysis</h2></div></div><div id="screener-analysis-status" class="handoff-status"></div><div id="screener-bulk-selection" class="packet-actions" style="margin:12px 0"><button type="button" class="button secondary" id="screener-select-all">Select all high-conviction equities</button><button type="button" class="button secondary" id="screener-clear-selection">Clear selection</button><span id="screener-selected-count" class="status" aria-live="polite">0 selected</span></div><div id="screener-analysis-results" class="analysis-board"></div><div class="packet-actions"><button type="button" class="button secondary" id="screener-analysis-next" hidden>Analyze next 12</button></div></section><div class="ticket-warning">Source auto-refresh can only update Chartink membership and read-only quote fields; it never analyzes, selects, prepares, or submits an order. Select source candidates first: analysis uses only those selected symbols.</div>`
  document.querySelector('#screener .panel').insertAdjacentHTML('beforeend', `<section id="screener-order" class="panel ticket-panel" hidden><div class="step-title"><div><span class="label">MULTI-PLAN PREVIEW · FYERS</span><h2>Consolidated FYERS batch preview</h2><small class="muted">Selected High-Conviction plans and the aggregate batch must pass fresh validation.</small></div><div class="status">FYERS is the default broker</div></div><div class="field-grid" style="margin-top:12px"><label class="field">Broker<input value="FYERS" readonly></label><label class="field">Cash product<select id="screener-order-product"><option value="INTRADAY">Intraday</option><option value="CNC">Delivery (CNC)</option></select></label><label class="field">Declared external open risk (₹)<input id="screener-order-external-risk" type="number" min="0" step="100" placeholder="Required when FYERS has open positions"></label></div><div id="screener-batch-selection" class="handoff-status" style="margin-top:12px">No High-Conviction plans selected.</div><button type="button" class="button" id="prepare-screener-order" style="margin-top:12px">Prepare FYERS batch preview</button><div id="screener-order-status" class="handoff-status" role="status" aria-live="polite">No plans selected. No broker action has occurred.</div><div id="screener-order-review" hidden><pre id="screener-order-preview" class="packet-preview"></pre><label class="field" style="margin-top:10px">Exact fresh confirmation phrase<input id="screener-order-confirmation" class="confirmation-input" autocomplete="off" spellcheck="false"></label><button type="button" class="button danger" id="submit-screener-order" disabled style="margin-top:10px">Submit confirmed FYERS batch</button></div></section>`)
  $('stop-straddle').insertAdjacentHTML('afterend', '<button type="button" class="button danger" id="squareoff-straddle">Stop &amp; square off</button>')
  $('straddle-action-status').insertAdjacentHTML('afterend', '<section id="straddle-squareoff-review" class="automation-panel" hidden><pre id="straddle-squareoff-preview" class="packet-preview"></pre><label class="field">Exact exit confirmation<input id="straddle-squareoff-confirmation" autocomplete="off" spellcheck="false"></label><button type="button" class="button danger" id="confirm-straddle-squareoff" disabled>Confirm stop &amp; square off</button></section>')
  $('stop-nifty-straddle').insertAdjacentHTML('afterend', '<button type="button" class="button danger" id="squareoff-nifty-straddle">Stop &amp; square off</button>')
  $('nifty-straddle-action-status').insertAdjacentHTML('afterend', '<section id="nifty-straddle-squareoff-review" class="automation-panel" hidden><pre id="nifty-straddle-squareoff-preview" class="packet-preview"></pre><label class="field">Exact exit confirmation<input id="nifty-straddle-squareoff-confirmation" autocomplete="off" spellcheck="false"></label><button type="button" class="button danger" id="confirm-nifty-straddle-squareoff" disabled>Confirm stop &amp; square off</button></section>')
  document.querySelector('#nifty-straddle-options .field-grid').insertAdjacentHTML('afterend', '<div><span class="label">EXIT OPTION</span><div class="option-set execution"><label class="option-card"><input type="radio" name="nifty-straddle-exit" value="supertrend" checked><b>Supertrend trail</b><small><code>--supertrend-trail</code> · 7,3 after +10 · configured hard stop remains active.</small></label><label class="option-card"><input type="radio" name="nifty-straddle-exit" value="fixed"><b>Fixed target + stop</b><small><code>--fixed-target</code> · uses the configured target and hard stop.</small></label></div></div>')
  const niftyMetrics = document.querySelectorAll('#nifty-straddle .metric strong')
  niftyMetrics[2].textContent = '15 pts'
  niftyMetrics[3].textContent = 'ST 7 · 3'
  document.querySelectorAll('#sensex-straddle .metric strong')[4].textContent = '15 pts'
  document.querySelector('input[name="straddle-exit"][value="supertrend"]').closest('.option-card').querySelector('small').innerHTML = '<code>--supertrend-trail</code> · 7,3 after +10 · 15-point hard stop.'
  document.querySelector('input[name="straddle-exit"][value="fixed"]').closest('.option-card').querySelector('small').innerHTML = '<code>--fixed-target</code> · 30 target · 15-point hard stop.'
  document.querySelector('input[name="straddle-exit"][value="trail"]').closest('.option-card').querySelector('small').innerHTML = '<code>--trail-profit</code> · trail 10 after +30 · 15-point hard stop.'
  $('screener-analysis-next').textContent = 'Cancel analysis'
  $('screener-analysis-results').insertAdjacentHTML('afterend', `<section id="screener-watchlist" style="margin-top:18px"><div class="step-title"><div><span class="label">SECONDARY · NON-ACTIONABLE</span><h3>Watchlist</h3><small class="muted">Candidates needing stronger alignment or evidence. No live-order path is available here.</small></div><span class="status">Advisory only</span></div><div id="screener-watchlist-results" class="analysis-board"></div></section>`)
  $('screener-analysis-results').insertAdjacentHTML('afterend', `<section id="screener-options" style="margin-top:18px"><div class="step-title"><div><span class="label">STOCK OPTIONS · DEFINED RISK</span><h3>High-Conviction option spreads</h3><small class="muted">Built only from the High-Conviction equity underlyings using fresh FYERS chain, contract and liquidity evidence.</small></div><button type="button" class="button secondary" id="analyze-screener-options">Refresh option spreads</button></div><div id="screener-options-status" class="handoff-status">Complete the equity analysis to screen stock options.</div><div id="screener-options-results" class="analysis-board"></div></section>`)
  document.querySelector('.work').insertAdjacentHTML('beforeend', `<section id="settings" class="view ${initialView === 'settings' ? 'active' : ''}"><header class="head"><div><span class="label">OPTIONAL PREFERENCES</span><h1>Risk Guardrails</h1><small class="muted">Safe defaults apply automatically. Adjustments refresh and recalculate the next plan.</small></div></header><div id="settings-content"></div></section>`)
  document.querySelector('.route-set').insertAdjacentHTML('afterend', `<div id="cash-product-choice"><span class="label" style="margin-top:14px">CASH PRODUCT</span><div class="choice-row"><label class="choice"><input type="radio" name="cash-product" value="INTRADAY" checked> Intraday <small>Same-day position.</small></label><label class="choice"><input type="radio" name="cash-product" value="CNC"> Delivery <small>Fully funded holding.</small></label></div><span class="label" style="margin-top:14px">EXIT PLAN · OPTIONAL</span><div class="choice-row"><label class="choice"><input type="radio" name="cash-exit-plan" value="FIXED_TARGET" checked> Fixed full target <small>Default: exit the full quantity at target.</small></label><label class="choice"><input type="radio" name="cash-exit-plan" value="TARGET_ACTIVATED_SUPERTREND_7_2"> Target trigger + Supertrend 7,2 exit <small>Planning only; completed candles.</small></label></div></div>`)
  const trailingExitChoice = document.querySelector('input[name="cash-exit-plan"][value="TARGET_ACTIVATED_SUPERTREND_7_2"]')
  trailingExitChoice.value = 'PARTIAL_TARGET_SUPERTREND_7_2'
  trailingExitChoice.nextSibling.textContent = ' 50% target + Supertrend 7,2 trail '
  const riskPanel = document.querySelector('.handoff-grid > section:nth-child(2)')
  const riskControls = document.createElement('details')
  riskControls.className = 'automation-panel'
  riskControls.innerHTML = '<summary>Settings · risk limits</summary>'
  while (riskPanel.firstChild) riskControls.appendChild(riskPanel.firstChild)
  riskPanel.appendChild(riskControls)
  riskPanel.insertAdjacentHTML('afterbegin', '<span class="label">SETTINGS</span><h2>Risk guardrails</h2><p class="muted">Defaults: ₹2,000 per idea · ₹5,000 daily loss · ₹1,000 reserve · maximum 3 positions. Changes recalculate the automatic plan.</p>')
  $('settings-content').appendChild(riskPanel)
  const unattendedPolicyPanel = document.querySelector('#handoff > .automation-panel')
  if (unattendedPolicyPanel) $('settings-content').appendChild(unattendedPolicyPanel)
  document.querySelector('#handoff .handoff-grid').style.gridTemplateColumns = '1fr'
  const recipientControls = document.querySelector('input[name="recipient"]')?.closest('.choice-row')
  const actionControls = document.querySelector('input[name="handoff-action"]')?.closest('.choice-row')
  ;[recipientControls, recipientControls?.previousElementSibling, actionControls, actionControls?.previousElementSibling, $('include-funds')?.closest('.privacy-gate')].forEach(element => { if (element) element.style.display = 'none' })
  $('prepare-packet').hidden = true
  $('packet-status').hidden = true
  document.querySelector('#handoff header h1').textContent = 'From completed-candle signal to order review'
  document.querySelector('#handoff header .muted').textContent = 'Choose a route and candidate; the strategy fills the plan using safe defaults.'
  document.querySelector('#handoff .handoff-banner strong').textContent = 'Automatic plan first, explicit confirmation last'
  document.querySelector('#handoff .handoff-banner span').textContent = 'Place order refreshes the quote, contract, product, quantity, funds or margin, risk limits and ticket state. Nothing is submitted until you review the exact preview and type its confirmation phrase.'

  const fetchJson = async url => {
    const response = await fetch(url, { cache: 'no-store' })
    const contentType = response.headers.get('content-type') || ''
    let data
    if (contentType.includes('application/json')) {
      data = await response.json()
    } else {
      const body = await response.text()
      throw new Error(response.ok ? 'The server returned an unreadable response.' : `Request failed (${response.status})${body ? ' — the server did not return JSON' : ''}`)
    }
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`)
    return data
  }
  const postJson = async (url, payload) => {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    const contentType = response.headers.get('content-type') || ''
    const data = contentType.includes('application/json')
      ? await response.json().catch(() => ({ error: `The server returned invalid JSON (HTTP ${response.status}).` }))
      : { error: response.status === 501 ? 'The running dashboard does not support policy POST requests yet. Restart it from this checkout and retry.' : `The server returned a non-JSON response (HTTP ${response.status}).` }
    if (!response.ok) {
      const error = new Error(data.error || `Request failed (${response.status})`)
      error.payload = data
      throw error
    }
    return data
  }
  // KAMA has no ticket/confirmation controls: its completed-candle runner owns
  // every paper lifecycle transition.  This UI intentionally never invokes a
  // broker order endpoint.
  const renderKamaRunner = state => {
    $('kama-runner-toggle').textContent = state.running ? 'Stop runner' : `Start ${$('kama-mode').value.toLowerCase()} runner`
    $('kama-runner-status').textContent = `${state.status || 'STOPPED'}${state.last_event?.signal?.message ? ` · ${state.last_event.signal.message}` : state.last_event?.error ? ` · ${state.last_event.error}` : ''}`
    $('kama-state').textContent = JSON.stringify(state, null, 2)
    $('kama-policy').textContent = state.config
      ? `${state.policy?.signal_authority || 'KAMA completed candles only'} · ${state.policy?.risk_policy || 'policy unavailable'}`
      : 'No active KAMA runner. Historical events are a journal, never an active position.'
    const candles = state.chart?.candles || []
    const signal = state.chart?.signal || state.last_event?.signal
    $('kama-chart').innerHTML = candles.length
      ? `<b>${escapeHtml(state.chart.symbol)} · ${escapeHtml(state.chart.timeframe)}</b><small class="muted">Completed-candle KAMA: ${escapeHtml(signal?.action || 'WAIT')} · ${escapeHtml(signal?.message || '')}</small><div class="premium-chart-stats"><div><small>Candles</small><b>${candles.length}</b></div><div><small>KAMA</small><b>${signal?.kama ?? '—'}</b></div><div><small>Efficiency</small><b>${signal?.efficiency ?? '—'}</b></div></div><div class="chart-empty">KAMA chart state is sourced from completed candles only.</div>`
      : '<div class="chart-empty">Chart starts only after completed KAMA candles are received.</div>'
    $('kama-events').textContent = state.events?.length
      ? state.events.map(event => `${event.at}  ${event.lifecycle || event.status || 'WATCH'}  ${event.signal?.action || event.error || ''}`).join('\n')
      : 'No KAMA events.'
  }
  const loadKamaRunner = async () => {
    try { renderKamaRunner(await fetchJson('/api/kama/runner')) }
    catch (error) { $('kama-runner-status').textContent = `KAMA state unavailable: ${error.message}` }
  }
  const loadKamaCapability = async () => {
    try {
      const capability = await fetchJson('/api/kama/live-capability')
      $('kama-capability').textContent = capability.live_submission_enabled ? 'Live runner available' : 'Paper default · live gated off'
      $('kama-mode').querySelector('option[value="LIVE"]').disabled = !capability.live_submission_enabled
      $('kama-policy').textContent = capability.message
    } catch (error) { $('kama-capability').textContent = 'Policy unavailable' }
  }
  const updateKamaMode = () => {
    const live = $('kama-mode').value === 'LIVE'
    document.querySelectorAll('.kama-live-setting').forEach(field => { field.hidden = !live })
    if (!$('kama-runner-toggle').disabled) $('kama-runner-toggle').textContent = `Start ${live ? 'live' : 'paper'} runner`
  }
  let kamaUnderlyingSearchGeneration = 0
  const searchKamaUnderlyings = async () => {
    const query = $('kama-underlying-search').value.trim()
    const picker = $('kama-underlying')
    const executionMode = $('kama-execution-mode').value
    const generation = ++kamaUnderlyingSearchGeneration
    if (query.length < 2) {
      picker.innerHTML = '<option value="">Type at least two characters to search</option>'
      picker.disabled = true
      $('kama-underlying-status').textContent = 'Type at least two characters to search the selected route.'
      return
    }
    $('kama-underlying-status').textContent = 'Searching the current FYERS master…'
    try {
      const data = await fetchJson(`/api/kama/underlying-search?q=${encodeURIComponent(query)}&execution_mode=${encodeURIComponent(executionMode)}`)
      if (generation !== kamaUnderlyingSearchGeneration) return
      picker.innerHTML = '<option value="">Choose a FYERS underlying</option>' + data.matches.map(item => `<option value="${escapeHtml(item.symbol)}" data-underlying="${escapeHtml(JSON.stringify(item))}">${escapeHtml(item.underlying_kind.replaceAll('_', ' '))} · ${escapeHtml(item.description)} · ${escapeHtml(item.symbol)}</option>`).join('')
      picker.disabled = !data.status?.usable || !data.matches.length
      $('kama-underlying-status').textContent = data.matches.length ? `${data.matches.length} current master match${data.matches.length === 1 ? '' : 'es'}. Select one.` : 'No eligible current FYERS underlying matched that route and search.'
    } catch (error) {
      picker.innerHTML = '<option value="">KAMA equity search unavailable</option>'
      picker.disabled = true
      $('kama-underlying-status').textContent = `Search blocked: ${error.message}`
    }
  }
  $('kama-underlying-search').addEventListener('input', searchKamaUnderlyings)
  const syncKamaSelectedUnderlying = () => {
    const selected = JSON.parse($('kama-underlying').selectedOptions[0]?.dataset.underlying || 'null')
    $('kama-exit-session').textContent = selected?.underlying_kind === 'COMMODITY_FUTURE' ? 'Reversal or 23:30 square-off' : 'Reversal or 15:15 square-off'
  }
  $('kama-underlying').addEventListener('change', syncKamaSelectedUnderlying)
  const syncKamaExecutionMode = () => {
    const options = $('kama-execution-mode').value === 'OPTIONS'
    $('kama-size-field').childNodes[0].textContent = options ? 'Option lots' : 'Quantity / lots'
    $('kama-size-help').textContent = options ? 'The exact quantity is calculated from the selected ATM contract lot size.' : 'Shares for NSE/BSE equities; lots for MCX futures.'
    $('kama-invalidation-help').textContent = options ? 'Required live stop price for the selected option premium.' : 'Required live stop price for the directly traded instrument.'
    $('kama-underlying').innerHTML = '<option value="">Search and select for this route</option>'
    $('kama-underlying').disabled = true
    syncKamaSelectedUnderlying()
    searchKamaUnderlyings()
  }
  $('kama-execution-mode').addEventListener('change', syncKamaExecutionMode)
  $('kama-mode').addEventListener('change', updateKamaMode)
  $('kama-runner-toggle').addEventListener('click', async () => {
    const button = $('kama-runner-toggle')
    button.disabled = true
    try {
      const current = await fetchJson('/api/kama/runner')
      const state = current.running ? await postJson('/api/kama/runner/stop', {}) : await postJson('/api/kama/runner/start', {
        mode: $('kama-mode').value, execution_mode: $('kama-execution-mode').value,
        underlying: $('kama-underlying').value, timeframe: $('kama-timeframe').value,
        kama_length: $('kama-length').value, fast_length: $('kama-fast').value, slow_length: $('kama-slow').value,
        minimum_efficiency: $('kama-efficiency').value, breakout_bars: $('kama-breakout').value,
        cooldown_bars: $('kama-cooldown').value, allow_reclaims: $('kama-reclaims').checked,
        quantity: $('kama-quantity').value, invalidation: $('kama-invalidation').value,
        idea_risk_limit: $('kama-idea-risk').value,
      })
      renderKamaRunner(state)
    } catch (error) { $('kama-runner-status').textContent = `Runner action blocked: ${error.message}` }
    finally { button.disabled = false }
  })
  syncKamaExecutionMode(); updateKamaMode(); loadKamaCapability(); loadKamaRunner(); setInterval(() => { if (!document.hidden) loadKamaRunner() }, 5000)
  const renderTradeRecommendation = data => {
    const parsed = data.parsed || {}
    const mapping = data.mapping || {}
    const output = $('trade-parser-result')
    const fields = [
      ['Action', parsed.action || 'not found'],
      ['Underlying', parsed.underlying || 'not found'],
      ['Option', parsed.option_type ? `${parsed.strike ?? '—'} ${parsed.option_type}` : 'cash / futures not identified'],
      ['Entry', parsed.entry ?? 'not found'],
      ['Entry type', parsed.entry_instruction === 'STOP_LIMIT' ? 'stop-limit trigger' : 'limit'],
      ['Stop loss', parsed.stop_loss ?? 'not found'],
      ['Targets', (parsed.targets || []).length ? parsed.targets.join(' → ') : 'none found'],
    ]
    const contract = mapping.contract
    const candidateLines = (mapping.candidates || []).map(item => `${item.symbol} · ${item.description} · expiry ${item.expiry || 'n/a'} · lot ${item.lot_size}`).join('\n')
    const stages = (data.trailing_plan || []).map((stage, index) => `T${index + 1} ${stage.target}: ${stage.action}`).join('\n')
    output.textContent = [
      'REVIEW-ONLY PARSED TICKET',
      ...fields.map(([label, value]) => `${label}: ${value}`),
      '',
      `FYERS mapping: ${mapping.status || 'UNRESOLVED'}`,
      contract ? `${contract.symbol} · ${contract.description} · expiry ${contract.expiry || 'n/a'} · lot ${contract.lot_size} · tick ${contract.tick_size}` : (mapping.message || 'No exact broker contract found.'),
      candidateLines ? `\nPossible FYERS contracts — add expiry to your text to make this exact:\n${candidateLines}` : '',
      stages ? `\nSuggested staged stop plan (review only):\n${stages}` : '',
      parsed.missing?.length ? `\nMissing fields: ${parsed.missing.join(', ')}` : '',
      '\nNo order, stop, or trailing instruction has been sent to FYERS.'
    ].filter(Boolean).join('\n')
    output.hidden = false
    $('trade-parser-order').hidden = mapping.status !== 'EXACT'
    $('trade-parser-submit-order').disabled = true
    const inferredStopLimit = parsed.entry_instruction === 'STOP_LIMIT'
    const tickSize = Number(contract?.tick_size) || 0
    const isBuy = (parsed.action || 'BUY') === 'BUY'
    $('trade-parser-entry-mode').value = inferredStopLimit ? 'STOP_LIMIT' : 'LIMIT'
    $('trade-parser-trigger-price').value = parsed.entry ?? ''
    $('trade-parser-limit-price').value = parsed.entry == null ? '' : (inferredStopLimit && tickSize > 0 ? Number(parsed.entry) + (isBuy ? tickSize : -tickSize) : parsed.entry)
    const updateEntryHelp = () => {
      const stopLimit = $('trade-parser-entry-mode').value === 'STOP_LIMIT'
      $('trade-parser-entry-help').textContent = stopLimit
        ? `FYERS stop-limit: trigger first, then submit a ${parsed.action || 'BUY'} limit price. For BUY, limit must be above trigger; SELL, below.`
        : `FYERS limit: ${parsed.action === 'SELL' ? 'sell at or above' : 'buy at or below'} the stated price.`
    }
    updateEntryHelp()
    $('trade-parser-order-status').textContent = mapping.status === 'EXACT'
      ? 'Exact FYERS contract found. Choose lots and prepare a fresh limit-order preview.'
      : 'Order preparation is blocked until the recommendation maps to exactly one active FYERS contract.'
  }
  $('trade-parser-run').addEventListener('click', async () => {
    const button = $('trade-parser-run')
    const status = $('trade-parser-status')
    const text = $('trade-parser-input').value.trim()
    if (!text) { status.textContent = 'Paste a trade recommendation first.'; return }
    button.disabled = true; status.textContent = 'Parsing text and checking the FYERS master cache…'
    try {
      const data = await postJson('/api/trade-recommendation/parse', { text })
      renderTradeRecommendation(data)
      if (data.mapping?.status === 'EXACT') {
        const ai = await postJson('/api/trade-recommendation/ai-analysis', { text })
        renderTradeRecommendationAi(ai)
        status.textContent = 'Parsed ticket and AI analysis are ready. Review them before preparing an order.'
      } else status.textContent = 'Parser result needs review; AI analysis requires one exact active FYERS contract.'
    } catch (error) { status.textContent = `Parser blocked: ${error.message}` }
    finally { button.disabled = false }
  })
  $('trade-parser-clear').addEventListener('click', () => {
    $('trade-parser-input').value = ''; $('trade-parser-result').hidden = true; $('trade-parser-result').textContent = ''; $('trade-parser-ai-result').hidden = true; $('trade-parser-ai-result').textContent = ''; $('trade-parser-order').hidden = true; $('trade-parser-status').textContent = 'Paste a recommendation to begin.'
  })
  const renderTradeRecommendationAi = data => {
      const output = $('trade-parser-ai-result')
      const evidence = data.evidence || {}; const trend = evidence.trend || {}
      output.textContent = [
        `AI FEEDBACK: ${data.verdict === 'FAVOURABLE' ? 'FAVOURABLE — PROCEED' : 'NOT FAVOURABLE'}${data.verdict === 'WAIT_FOR_TRIGGER' ? ' — WAIT FOR TRIGGER' : data.verdict === 'MIXED' ? ' — WAIT FOR ALIGNMENT' : data.verdict === 'NOT_FAVOURABLE' ? ' — DO NOT PROCEED' : ''}`,
        `Trend: ${trend.state || 'unavailable'} · ${trend.normalized_slope ?? '—'} ATR per candle`,
        `Latest completed option close: ${evidence.last_completed_close ?? '—'}`,
        `Entry instruction: ${evidence.entry_instruction === 'STOP_LIMIT' ? 'stop-limit' : 'limit'} · ${String(evidence.entry_state || 'unavailable').replaceAll('_', ' ')}`,
        `Entry distance: ${evidence.entry_gap_pct ?? '—'}%`,
        `First target distance: ${evidence.target_distance_atr ?? '—'} ATR`,
        ...(data.reasons || []),
        'No capital, lot-sizing, or reward-to-risk rule was applied. This is completed-candle evidence, not a target guarantee.'
      ].join('\n')
      const favourable = data.verdict === 'FAVOURABLE'
      output.style.borderColor = favourable ? '#35b878' : '#df5b67'
      output.style.background = favourable ? 'linear-gradient(135deg,#102d24,#0a1f19)' : 'linear-gradient(135deg,#351920,#241116)'
      output.style.color = favourable ? '#b9f4d2' : '#ffc2c8'
      output.hidden = false
  }
  let tradeParserOrderPreview = null
  $('trade-parser-prepare-order').addEventListener('click', async () => {
    const status = $('trade-parser-order-status'); const button = $('trade-parser-prepare-order')
    button.disabled = true; status.textContent = 'Refreshing FYERS contract and quote, then submitting the exact order…'
    try {
      const result = await postJson('/api/trade-recommendation/submit-direct', { text: $('trade-parser-input').value.trim(), lots: $('trade-parser-lots').value, entry_mode: $('trade-parser-entry-mode').value, trigger_price: $('trade-parser-trigger-price').value, limit_price: $('trade-parser-limit-price').value })
      tradeParserOrderPreview = null
      status.textContent = result.message || 'FYERS received the order; reconcile its status in the broker.'
    } catch (error) { tradeParserOrderPreview = null; status.textContent = `Order preparation blocked: ${error.message}` }
    finally { button.disabled = false }
  })
  $('trade-parser-submit-order').addEventListener('click', async () => {
    const status = $('trade-parser-order-status'); const button = $('trade-parser-submit-order')
    if (!tradeParserOrderPreview) { status.textContent = 'Prepare a fresh order ticket first.'; return }
    button.disabled = true; status.textContent = 'Submitting the reviewed FYERS limit order…'
    try {
      const result = await postJson('/api/trade-recommendation/submit-order', { preview_id: tradeParserOrderPreview.preview_id, confirmation: tradeParserOrderPreview.confirmation_phrase })
      status.textContent = result.message || 'FYERS received the order; reconcile its status in the broker.'
      tradeParserOrderPreview = null
    } catch (error) {
      const replacement = error.payload?.replacement_preview
      if (replacement) { tradeParserOrderPreview = replacement; $('trade-parser-submit-order').disabled = !replacement.live_submission_enabled; status.textContent = 'FYERS state changed. Review the replacement ticket, then submit it directly.' }
      else status.textContent = `Submission blocked: ${error.message}`
    }
  })
  $('trade-parser-entry-mode').addEventListener('change', () => {
    const stopLimit = $('trade-parser-entry-mode').value === 'STOP_LIMIT'
    const action = ($('trade-parser-result').textContent.match(/Action: (BUY|SELL)/) || [])[1] || 'BUY'
    $('trade-parser-entry-help').textContent = stopLimit
      ? `FYERS stop-limit: trigger first, then submit a ${action} limit price. For BUY, limit must be above trigger; SELL, below.`
      : `FYERS limit: ${action === 'SELL' ? 'sell at or above' : 'buy at or below'} the stated price.`
  })
  const screenerStorageKey = 'sector-pulse:chartink-sources'
  const screenerRefreshIntervals = [0, 5, 15, 30, 60].map(minutes => minutes * 60 * 1000)
  const defaultScreenerRefreshMs = 15 * 60 * 1000
  const defaultScreenerSources = [{ id: 'independent-indicator-signals-daily-or', label: 'Pinaki - Bollinger Band Squeeze', url: chartinkSourceUrl, refresh_interval_ms: defaultScreenerRefreshMs, refresh_interval_explicit: false, result: null }]
  let screenerSources = (() => {
    try {
      const stored = JSON.parse(localStorage.getItem(screenerStorageKey) || 'null')
      return Array.isArray(stored) && stored.length ? stored : defaultScreenerSources
    } catch { return defaultScreenerSources }
  })()
  screenerSources = screenerSources.map(source => {
    const saved = Number(source.refresh_interval_ms)
    const migrated = source.refresh_interval_explicit == null ? defaultScreenerRefreshMs : saved
    const valid = Number.isFinite(migrated) && (migrated === 0 || (migrated >= 5 * 60 * 1000 && migrated <= 24 * 60 * 60 * 1000)) ? migrated : defaultScreenerRefreshMs
    return { ...source, refresh_interval_ms: valid, refresh_interval_explicit: source.refresh_interval_explicit === true, refresh_interval_custom: source.refresh_interval_custom === true }
  })
  screenerSources = screenerSources.map(source => source.result?.status === 'EMPTY' && source.result?.fetch_schema !== 2
    ? { ...source, result: { status: 'REFRESH_REQUIRED', count: null, fetched_at: new Date().toISOString(), error: 'The earlier empty result came from a page-shell parser and is invalid. Refresh this source to run the corrected Chartink scan.' } }
    : source)
  screenerSources = screenerSources.map(source => source.result?.status === 'READY' && source.result?.market_data_schema !== 1
    ? { ...source, result: { ...source.result, market_data: {}, market_data_as_of: null, market_data_available: 0, market_data_error: 'This saved result predates FYERS quote enrichment. Refresh this source manually to load current prices.' } }
    : source)
  const saveScreenerSources = () => { try { localStorage.setItem(screenerStorageKey, JSON.stringify(screenerSources)) } catch {} }
  const screenerSortState = new Map()
  const screenerFilterState = new Map()
  const screenerRefreshInFlight = new Set()
  let screenerAnalysisOffset = 0
  let screenerAnalysisSymbols = []
  let screenerAnalysisResults = []
  let screenerWatchlistResults = []
  let screenerAnalysisDiagnostics = { analyzed: 0, watchlist: 0, rejected: 0 }
  const screenerSelectedPlans = new Map()
  let screenerOrderPreview = null
  let screenerAnalysisRunning = false
  let screenerAnalysisCancelled = false
  let screenerSchedulerTimer = null
  const screenerReadySymbols = () => new Set(screenerSources.flatMap(source => source.result?.status === 'READY' && Array.isArray(source.result.candidates) ? source.result.candidates : []).map(symbol => String(symbol).trim()).filter(Boolean))
  const screenerCandidateSelections = new Set()
  const pruneScreenerCandidateSelections = () => {
    const ready = screenerReadySymbols()
    screenerCandidateSelections.forEach(symbol => { if (!ready.has(symbol)) screenerCandidateSelections.delete(symbol) })
  }
  const syncScreenerCandidateSelectionUi = () => {
    pruneScreenerCandidateSelections()
    const count = screenerCandidateSelections.size
    const button = $('analyze-screeners')
    button.disabled = !count || screenerAnalysisRunning
    button.textContent = screenerAnalysisRunning ? `Analyzing ${screenerAnalysisSymbols.length} selected symbol${screenerAnalysisSymbols.length === 1 ? '' : 's'}…` : `Analyze selected symbols (${count})`
    document.querySelectorAll('.screener-candidate-select').forEach(control => { control.checked = screenerCandidateSelections.has(control.value) })
    document.querySelectorAll('.screener-source-select-all').forEach(control => {
      const sourceSymbols = (screenerSources.find(source => source.id === control.dataset.sourceId)?.result?.candidates || []).map(symbol => String(symbol).trim()).filter(Boolean)
      control.disabled = sourceSymbols.length === 0 || sourceSymbols.every(symbol => screenerCandidateSelections.has(symbol))
    })
    document.querySelectorAll('.screener-source-clear-selection').forEach(control => {
      const sourceSymbols = (screenerSources.find(source => source.id === control.dataset.sourceId)?.result?.candidates || []).map(symbol => String(symbol).trim()).filter(Boolean)
      control.disabled = !sourceSymbols.some(symbol => screenerCandidateSelections.has(symbol))
    })
    document.querySelectorAll('.screener-source-selected-count').forEach(node => {
      const sourceSymbols = (screenerSources.find(source => source.id === node.dataset.sourceId)?.result?.candidates || []).map(symbol => String(symbol).trim()).filter(Boolean)
      node.textContent = `${sourceSymbols.filter(symbol => screenerCandidateSelections.has(symbol)).length} selected`
    })
  }
  const screenerBlockedReason = source => {
    const status = String(source.result?.status || '').toUpperCase()
    const error = String(source.result?.error || '')
    if (status === 'ACCESS_REQUIRED') return error || 'Chartink access is required.'
    if (status === 'RATE_LIMITED' || /rate.?limit|too many requests|\b429\b/i.test(error)) return error || 'The source is rate-limited.'
    if (status === 'ERROR' || status === 'AUTH_REQUIRED' || /auth|sign.?in|login|access required/i.test(error)) return error || 'The source needs attention.'
    return ''
  }
  const screenerNextRefreshAt = source => {
    const interval = Number(source.refresh_interval_ms || 0)
    if (!interval || screenerBlockedReason(source)) return null
    const fetchedAt = Date.parse(source.result?.fetched_at || '')
    return (Number.isFinite(fetchedAt) ? fetchedAt : Date.now()) + interval
  }
  const refreshIntervalLabel = interval => interval ? `${interval / 60000}m` : 'Off'
  const scheduleText = source => {
    if (!source.refresh_interval_ms) return 'Auto-refresh off · last refresh shown above'
    const blocked = screenerBlockedReason(source)
    if (blocked) return `Auto-refresh every ${source.refresh_interval_ms / 60000} minutes · paused: ${blocked}`
    if (screenerRefreshInFlight.has(source.id) || source.result?.status === 'LOADING') return 'Auto-refresh in progress…'
    if (document.hidden) return 'Auto-refresh paused while this page is hidden'
    const next = screenerNextRefreshAt(source)
    const seconds = Math.max(0, Math.ceil((next - Date.now()) / 1000))
    const minutes = Math.floor(seconds / 60)
    return `Auto-refresh every ${source.refresh_interval_ms / 60000} minutes · next read-only refresh in ${minutes}:${String(seconds % 60).padStart(2, '0')}`
  }
  const screenerSortValue = (symbol, key, marketData) => {
    if (key === 'symbol') return symbol
    const quote = marketData[symbol]
    if (!quote) return null
    if (key === 'sector') return quote.display_sector
    if (key === 'price') return Number(quote.last_price)
    if (key === 'change') return Number(quote.day_change)
    if (key === 'change_pct') return Number(quote.day_change_pct)
    if (key === 'timestamp') { const value = Date.parse(quote.provider_timestamp); return Number.isFinite(value) ? value : null }
    if (key === 'volume') return Number(quote.display_volume)
    if (key === 'market_cap') return Number(quote.display_market_cap)
    if (key.startsWith('dynamic:')) return quote.dynamic_fields?.[key.slice(8)]
    return null
  }
  const dynamicFilterPass = (symbol, schema, values, filter) => schema.every(field => {
    const rule = filter.dynamic?.[field.key]
    if (!rule) return true
    const raw = values[symbol]?.[field.key]
    if (raw == null) return false
    if (field.type === 'number') {
      const value = Number(String(raw).replaceAll(',', '').replace('%', ''))
      return (!rule.min || value >= Number(rule.min)) && (!rule.max || value <= Number(rule.max))
    }
    if (field.type === 'datetime') return !rule.value || Date.parse(raw) >= Date.parse(`${rule.value}T00:00:00`)
    if (field.type === 'boolean') return rule.value === '' || String(raw) === rule.value
    return !rule.value || String(raw).toLowerCase().includes(rule.value.toLowerCase())
  })
  const sortScreenerSymbols = (symbols, sort, marketData) => [...symbols].sort((left, right) => {
    const a = screenerSortValue(left, sort.key, marketData), b = screenerSortValue(right, sort.key, marketData)
    const aMissing = a == null || (typeof a === 'number' && !Number.isFinite(a)), bMissing = b == null || (typeof b === 'number' && !Number.isFinite(b))
    if (aMissing !== bMissing) return aMissing ? 1 : -1
    if (aMissing) return left.localeCompare(right)
    const comparison = typeof a === 'string' ? a.localeCompare(b) : a - b
    return (sort.direction === 'asc' ? comparison : -comparison) || left.localeCompare(right)
  })
  const screenerSortHeader = (sourceId, key, label, sort) => {
    const active = sort.key === key
    const indicator = active ? (sort.direction === 'asc' ? ' ▲' : ' ▼') : ''
    return `<th aria-sort="${active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}"><button type="button" class="screener-sort" data-source-id="${escapeHtml(sourceId)}" data-sort-key="${key}">${label}${indicator}</button></th>`
  }
  saveScreenerSources()
  const validChartinkUrl = value => {
    const parsed = new URL(value)
    if (!['http:', 'https:'].includes(parsed.protocol) || !['chartink.com', 'www.chartink.com'].includes(parsed.hostname) || !parsed.pathname.startsWith('/screener/')) throw new Error('Enter a valid Chartink screener URL.')
    parsed.hash = ''
    return parsed.toString().replace(/\/$/, '')
  }
  const renderScreenerSources = () => {
    document.querySelector('#screener .status').textContent = `${screenerSources.length} source${screenerSources.length === 1 ? '' : 's'} configured`
    $('screener-sources').innerHTML = screenerSources.length ? screenerSources.map(source => {
      const result = source.result || {}
      const state = result.status || 'NOT_FETCHED'
      const detail = state === 'READY' ? `${result.count} source candidate(s)` : state === 'EMPTY' ? 'No candidates returned' : result.error || 'Not refreshed yet'
      const sourceSymbols = Array.isArray(result.candidates) ? [...new Set(result.candidates.map(value => String(value).trim()).filter(Boolean))] : []
      const marketData = result.market_data && typeof result.market_data === 'object' ? result.market_data : {}
      const sort = screenerSortState.get(source.id) || { key: 'symbol', direction: 'asc' }
      const sectorData = result.sectors && typeof result.sectors === 'object' ? result.sectors : {}
      const sectorOrigins = result.sector_origins && typeof result.sector_origins === 'object' ? result.sector_origins : {}
      const sourceVolumes = result.source_volumes && typeof result.source_volumes === 'object' ? result.source_volumes : {}
      const sourceMarketCaps = result.source_market_caps && typeof result.source_market_caps === 'object' ? result.source_market_caps : {}
      const sourceFields = result.source_fields && typeof result.source_fields === 'object' ? result.source_fields : {}
      const sourceFieldSchema = Array.isArray(result.source_field_schema) ? result.source_field_schema : []
      const sortData = Object.fromEntries(sourceSymbols.map(symbol => [symbol, { ...(marketData[symbol] || {}), display_sector: sectorData[symbol], display_volume: sourceVolumes[symbol] ?? marketData[symbol]?.volume, display_market_cap: sourceMarketCaps[symbol], dynamic_fields: sourceFields[symbol] || {} }]))
      const filter = screenerFilterState.get(source.id) || { search: '', sector: '', minMarketCap: '', maxMarketCap: '', minVolume: '', maxVolume: '', minPrice: '', maxPrice: '', minChange: '', maxChange: '', minChangePct: '', maxChangePct: '', priceAsOf: '', dynamic: {} }
      const sectorOptions = [...new Set(sourceSymbols.map(symbol => sectorData[symbol]).filter(Boolean))].sort((a, b) => a.localeCompare(b))
      const filteredSymbols = sourceSymbols.filter(symbol => {
        const marketCap = sourceMarketCaps[symbol]
        const quote = marketData[symbol]
        const quoteTime = Date.parse(quote?.provider_timestamp || '')
        const minimumDate = filter.priceAsOf ? Date.parse(`${filter.priceAsOf}T00:00:00`) : null
        const volume = sourceVolumes[symbol] ?? quote?.volume
        return symbol.toLowerCase().includes(filter.search.toLowerCase()) && (!filter.sector || sectorData[symbol] === filter.sector) && (!filter.minMarketCap || (marketCap != null && Number(marketCap) >= Number(filter.minMarketCap))) && (!filter.maxMarketCap || (marketCap != null && Number(marketCap) <= Number(filter.maxMarketCap))) && (!filter.minVolume || (volume != null && Number(volume) >= Number(filter.minVolume))) && (!filter.maxVolume || (volume != null && Number(volume) <= Number(filter.maxVolume))) && (!filter.minPrice || (quote && Number(quote.last_price) >= Number(filter.minPrice))) && (!filter.maxPrice || (quote && Number(quote.last_price) <= Number(filter.maxPrice))) && (!filter.minChange || (quote && Number(quote.day_change) >= Number(filter.minChange))) && (!filter.maxChange || (quote && Number(quote.day_change) <= Number(filter.maxChange))) && (!filter.minChangePct || (quote && Number(quote.day_change_pct) >= Number(filter.minChangePct))) && (!filter.maxChangePct || (quote && Number(quote.day_change_pct) <= Number(filter.maxChangePct))) && (!filter.priceAsOf || (Number.isFinite(quoteTime) && quoteTime >= minimumDate)) && dynamicFilterPass(symbol, sourceFieldSchema, sourceFields, filter)
      })
      const symbols = sortScreenerSymbols(filteredSymbols, sort, sortData)
      const marketDataNote = result.market_data_as_of
        ? `${escapeHtml(result.market_data_provider || 'Market data')} · ${escapeHtml(result.market_data_available || 0)} of ${escapeHtml(result.count)} rows · as of ${escapeHtml(time(result.market_data_as_of))}`
        : escapeHtml(result.market_data_error || 'FYERS price enrichment unavailable for this refresh.')
      const results = state === 'READY'
        ? `<details class="screener-results"><summary>View ${escapeHtml(result.count)} candidates</summary><small>${marketDataNote}</small><small>Sector, volume and market cap: Chartink source when returned. Market cap is ₹ crore as of ${escapeHtml(time(result.fetched_at))}; unavailable values are not estimated.</small><div class="packet-actions" style="margin-top:10px"><button type="button" class="button secondary screener-source-select-all" data-source-id="${escapeHtml(source.id)}">Select all symbols</button><button type="button" class="button secondary screener-source-clear-selection" data-source-id="${escapeHtml(source.id)}">Clear source selection</button><span class="status screener-source-selected-count" data-source-id="${escapeHtml(source.id)}">${sourceSymbols.filter(symbol => screenerCandidateSelections.has(symbol)).length} selected</span></div><div class="screener-filters"><label class="field">Symbol search<input class="screener-symbol-filter" data-source-id="${escapeHtml(source.id)}" value="${escapeHtml(filter.search)}" placeholder="Filter symbols"></label><label class="field">Sector<select class="screener-sector-filter" data-source-id="${escapeHtml(source.id)}"><option value="">All sectors</option>${sectorOptions.map(sector => `<option value="${escapeHtml(sector)}" ${filter.sector === sector ? 'selected' : ''}>${escapeHtml(sector)}</option>`).join('')}</select></label><label class="field">Minimum market cap (₹ cr)<input type="number" min="0" step="1" class="screener-market-cap-min" data-source-id="${escapeHtml(source.id)}" value="${escapeHtml(filter.minMarketCap)}" placeholder="Any"></label><label class="field">Maximum market cap (₹ cr)<input type="number" min="0" step="1" class="screener-market-cap-max" data-source-id="${escapeHtml(source.id)}" value="${escapeHtml(filter.maxMarketCap)}" placeholder="Any"></label><label class="field">Minimum volume<input type="number" min="0" step="1" class="screener-volume-filter" data-source-id="${escapeHtml(source.id)}" value="${escapeHtml(filter.minVolume)}" placeholder="Any volume"></label><span class="screener-visible-count">${symbols.length} of ${sourceSymbols.length} visible</span></div><div class="screener-result-table"><table><thead><tr>${screenerSortHeader(source.id, 'sector', 'Sector', sort)}${screenerSortHeader(source.id, 'symbol', 'Symbol', sort)}${screenerSortHeader(source.id, 'market_cap', 'Market Cap (₹ cr)', sort)}${screenerSortHeader(source.id, 'price', 'Last price', sort)}${screenerSortHeader(source.id, 'change', 'Day change', sort)}${screenerSortHeader(source.id, 'change_pct', 'Day change %', sort)}${screenerSortHeader(source.id, 'volume', 'Volume', sort)}${screenerSortHeader(source.id, 'timestamp', 'Price as of', sort)}<th>Select</th></tr></thead><tbody>${symbols.map(symbol => { const quote = marketData[symbol]; const sectorOrigin = sectorOrigins[symbol] === 'CHARTINK_SOURCE' ? 'Chartink source' : sectorOrigins[symbol] === 'NSE_INDEX_FALLBACK' ? 'NSE index fallback' : ''; const volume = sourceVolumes[symbol] ?? quote?.volume; const volumeOrigin = sourceVolumes[symbol] != null ? 'Chartink source' : quote?.volume != null ? 'FYERS quote' : ''; const marketCap = sourceMarketCaps[symbol]; return `<tr><td>${escapeHtml(sectorData[symbol] || 'Unavailable')}${sectorOrigin ? `<small>${escapeHtml(sectorOrigin)}</small>` : ''}</td><td><b>${escapeHtml(symbol)}</b></td><td>${marketCap == null ? 'Unavailable' : `₹${escapeHtml(Number(marketCap).toLocaleString('en-IN', { maximumFractionDigits: 2 }))} cr<small>Chartink · ${escapeHtml(time(result.fetched_at))}</small>`}</td><td>${quote ? money(quote.last_price) : 'Unavailable'}</td><td class="${quote ? stateClass(quote.day_change) : ''}">${quote ? money(quote.day_change) : 'Unavailable'}</td><td class="${quote ? stateClass(quote.day_change_pct) : ''}">${quote ? percent(quote.day_change_pct) : 'Unavailable'}</td><td>${volume == null ? 'Unavailable' : escapeHtml(Number(volume).toLocaleString('en-IN'))}${volumeOrigin ? `<small>${escapeHtml(volumeOrigin)}</small>` : ''}</td><td>${quote?.provider_timestamp ? escapeHtml(time(quote.provider_timestamp)) : 'Unavailable'}</td><td><input type="checkbox" class="screener-candidate-select" value="${escapeHtml(symbol)}" aria-label="Select ${escapeHtml(symbol)} for analysis" ${screenerCandidateSelections.has(symbol) ? 'checked' : ''}></td></tr>` }).join('')}</tbody></table></div><div class="screener-validation">Select one or more symbols, or use Select all symbols, then analyze only that selection. Filtering and sorting change display order only; they do not change an existing selection. Completed-candle and fresh-market-data validation is required before analysis.</div></details>`
        : state === 'EMPTY'
          ? '<div class="screener-results muted">The source executed successfully and returned exactly 0 candidates.</div>'
          : state !== 'NOT_REFRESHED' && state !== 'LOADING'
            ? `<div class="screener-results error">${escapeHtml(result.error || 'The source result is unavailable.')}</div>`
            : ''
      const blocked = screenerBlockedReason(source)
      return `<article class="candidate-card screener-source"><div class="screener-source-head"><span><b>${escapeHtml(source.label || 'Chartink screener')}</b><small><a class="provenance-link" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.url)}</a></small><small>${escapeHtml(state)} · ${escapeHtml(detail)}${result.fetched_at ? ` · refreshed ${escapeHtml(time(result.fetched_at))}` : ''}</small><small class="screener-schedule ${blocked ? 'paused' : ''}" data-schedule-source-id="${escapeHtml(source.id)}">${escapeHtml(scheduleText(source))}</small></span><div class="screener-source-actions"><label class="screener-refresh-setting">Auto-refresh<select class="screener-refresh-interval" data-source-id="${escapeHtml(source.id)}" aria-label="Auto-refresh interval for ${escapeHtml(source.label || 'Chartink screener')}">${screenerRefreshIntervals.map(interval => `<option value="${interval}" ${Number(source.refresh_interval_ms) === interval ? 'selected' : ''}>${refreshIntervalLabel(interval)}</option>`).join('')}</select></label>${source.refresh_interval_ms ? `<button type="button" class="button secondary stop-screener-refresh" data-source-id="${escapeHtml(source.id)}">Stop</button>` : ''}<button type="button" class="button secondary refresh-screener" data-source-id="${escapeHtml(source.id)}" ${screenerRefreshInFlight.has(source.id) ? 'disabled' : ''}>Refresh</button><button type="button" class="button secondary remove-screener" data-source-id="${escapeHtml(source.id)}">Remove</button></div></div>${results}</article>`
    }).join('') : '<div class="empty">No Chartink sources configured.</div>'
    syncScreenerCandidateSelectionUi()
    screenerSources.forEach(source => {
      const intervalSelect = document.querySelector(`.screener-refresh-interval[data-source-id="${CSS.escape(source.id)}"]`)
      if (intervalSelect) {
        intervalSelect.insertAdjacentHTML('beforeend', `<option value="custom" ${source.refresh_interval_custom ? 'selected' : ''}>Custom…</option>`)
        if (source.refresh_interval_custom) intervalSelect.insertAdjacentHTML('afterend', `<input type="number" class="screener-custom-refresh-minutes" data-source-id="${escapeHtml(source.id)}" min="5" max="1440" step="1" value="${escapeHtml(source.refresh_interval_ms / 60000)}" aria-label="Custom auto-refresh interval in minutes"><small class="screener-custom-refresh-help">5–1440 minutes</small>`)
      }
      const filters = document.querySelector(`.screener-symbol-filter[data-source-id="${CSS.escape(source.id)}"]`)?.closest('.screener-filters')
      if (filters) {
        const filter = screenerFilterState.get(source.id) || {}
        const count = filters.querySelector('.screener-visible-count')
        const fields = [
          ['Maximum volume', 'number', 'screener-volume-max', 'maxVolume', '1'],
          ['Minimum price (₹)', 'number', 'screener-price-min', 'minPrice', '0.05'],
          ['Maximum price (₹)', 'number', 'screener-price-max', 'maxPrice', '0.05'],
          ['Minimum day change (₹)', 'number', 'screener-change-min', 'minChange', '0.05'],
          ['Maximum day change (₹)', 'number', 'screener-change-max', 'maxChange', '0.05'],
          ['Minimum day change (%)', 'number', 'screener-change-pct-min', 'minChangePct', '0.01'],
          ['Maximum day change (%)', 'number', 'screener-change-pct-max', 'maxChangePct', '0.01'],
          ['Price as of (on or after)', 'date', 'screener-price-as-of', 'priceAsOf', ''],
        ]
        fields.forEach(([label, type, className, key, step]) => count.insertAdjacentHTML('beforebegin', `<label class="field">${label}<input type="${type}" ${step ? `step="${step}"` : ''} class="${className}" data-source-id="${escapeHtml(source.id)}" value="${escapeHtml(filter[key] || '')}" placeholder="Any"></label>`))
      }
      const table = filters?.nextElementSibling?.querySelector('table')
      if (table) {
        const header = table.tHead.rows[0]
        header.insertBefore(header.cells[6], header.cells[3])
        Array.from(table.tBodies[0].rows).forEach(row => row.insertBefore(row.cells[6], row.cells[3]))
        const headerFilters = [
          [0, ['.screener-sector-filter']], [1, ['.screener-symbol-filter']],
          [2, ['.screener-market-cap-min', '.screener-market-cap-max']], [3, ['.screener-volume-filter', '.screener-volume-max']],
          [4, ['.screener-price-min', '.screener-price-max']], [5, ['.screener-change-min', '.screener-change-max']],
          [6, ['.screener-change-pct-min', '.screener-change-pct-max']], [7, ['.screener-price-as-of']],
        ]
        headerFilters.forEach(([index, selectors]) => {
          const wrapper = document.createElement('span')
          wrapper.className = `screener-header-filter${selectors.length === 1 ? ' single' : ''}`
          selectors.forEach(selector => { const control = filters.querySelector(selector); if (control) wrapper.appendChild(control.closest('label')) })
          header.cells[index].appendChild(wrapper)
        })
        const dynamicSchema = Array.isArray(source.result?.source_field_schema) ? source.result.source_field_schema : []
        const dynamicValues = source.result?.source_fields || {}
        dynamicSchema.forEach(field => {
          const dynamicRule = screenerFilterState.get(source.id)?.dynamic?.[field.key] || {}
          const th = document.createElement('th')
          const currentSort = screenerSortState.get(source.id) || { key: 'symbol', direction: 'asc' }
          const sortKey = `dynamic:${field.key}`
          const active = currentSort.key === sortKey
          th.setAttribute('aria-sort', active ? (currentSort.direction === 'asc' ? 'ascending' : 'descending') : 'none')
          th.innerHTML = `<button type="button" class="screener-sort" data-source-id="${escapeHtml(source.id)}" data-sort-key="${escapeHtml(sortKey)}">${escapeHtml(field.label)}${active ? (currentSort.direction === 'asc' ? ' ▲' : ' ▼') : ''}</button>`
          const wrapper = document.createElement('span'); wrapper.className = `screener-header-filter${field.type === 'number' ? '' : ' single'}`
          wrapper.innerHTML = field.type === 'number'
            ? `<label>Min<input type="number" class="screener-dynamic-filter" data-source-id="${escapeHtml(source.id)}" data-field="${escapeHtml(field.key)}" data-filter-part="min" value="${escapeHtml(dynamicRule.min || '')}"></label><label>Max<input type="number" class="screener-dynamic-filter" data-source-id="${escapeHtml(source.id)}" data-field="${escapeHtml(field.key)}" data-filter-part="max" value="${escapeHtml(dynamicRule.max || '')}"></label>`
            : field.type === 'datetime'
              ? `<label>On or after<input type="date" class="screener-dynamic-filter" data-source-id="${escapeHtml(source.id)}" data-field="${escapeHtml(field.key)}" data-filter-part="value" value="${escapeHtml(dynamicRule.value || '')}"></label>`
              : field.type === 'boolean'
                ? `<label>Value<select class="screener-dynamic-filter" data-source-id="${escapeHtml(source.id)}" data-field="${escapeHtml(field.key)}" data-filter-part="value"><option value="" ${!dynamicRule.value ? 'selected' : ''}>Any</option><option value="true" ${dynamicRule.value === 'true' ? 'selected' : ''}>True</option><option value="false" ${dynamicRule.value === 'false' ? 'selected' : ''}>False</option></select></label>`
                : `<label>Contains<input class="screener-dynamic-filter" data-source-id="${escapeHtml(source.id)}" data-field="${escapeHtml(field.key)}" data-filter-part="value" value="${escapeHtml(dynamicRule.value || '')}"></label>`
          th.appendChild(wrapper); header.appendChild(th)
          Array.from(table.tBodies[0].rows).forEach(row => {
            const symbol = row.cells[1]?.innerText.trim()
            const value = dynamicValues[symbol]?.[field.key]
            const td = document.createElement('td')
            td.textContent = value == null ? 'Unavailable' : field.type === 'number' ? Number(String(value).replaceAll(',', '').replace('%', '')).toLocaleString('en-IN') : String(value)
            row.appendChild(td)
          })
        })
        const count = filters.querySelector('.screener-visible-count')
        table.closest('.screener-result-table').insertAdjacentElement('beforebegin', count)
        filters.remove()
      }
    })
  }
  const refreshScreenerSource = async (id, origin = 'manual') => {
    const source = screenerSources.find(item => item.id === id)
    if (!source || screenerRefreshInFlight.has(id)) return
    if (origin === 'auto') {
      const blocked = screenerBlockedReason(source)
      if (blocked || document.hidden) return
    }
    screenerRefreshInFlight.add(id)
    source.result = { status: 'LOADING', fetched_at: new Date().toISOString() }; renderScreenerSources()
    try { source.result = await postJson('/api/chartink/refresh', { url: source.url }) }
    catch (error) { source.result = { status: 'ERROR', count: null, fetched_at: new Date().toISOString(), error: error.message } }
    screenerRefreshInFlight.delete(id)
    saveScreenerSources(); renderScreenerSources()
  }
  const updateScreenerScheduleLabels = () => {
    screenerSources.forEach(source => {
      const label = document.querySelector(`[data-schedule-source-id="${CSS.escape(source.id)}"]`)
      if (label) label.textContent = scheduleText(source)
    })
  }
  const runScreenerScheduler = () => {
    clearTimeout(screenerSchedulerTimer)
    if (!document.hidden) {
      screenerSources.forEach(source => {
        const next = screenerNextRefreshAt(source)
        if (next != null && next <= Date.now() && !screenerRefreshInFlight.has(source.id)) refreshScreenerSource(source.id, 'auto')
      })
    }
    updateScreenerScheduleLabels()
    screenerSchedulerTimer = setTimeout(runScreenerScheduler, 1000)
  }
  const analyzeScreenerCandidates = async reset => {
    const readySources = screenerSources.filter(item => item.result?.status === 'READY')
    if (!readySources.length) { $('screener-status').textContent = 'Refresh a Chartink source before analysis.'; return }
    if (reset) {
      if (screenerAnalysisRunning) return
      pruneScreenerCandidateSelections()
      screenerAnalysisSymbols = [...screenerCandidateSelections]
      if (!screenerAnalysisSymbols.length) { $('screener-status').textContent = 'Select at least one screener symbol before analysis.'; syncScreenerCandidateSelectionUi(); return }
      screenerAnalysisRunning = true
      screenerAnalysisCancelled = false
      syncScreenerCandidateSelectionUi()
      screenerAnalysisOffset = 0
      screenerSelectedPlans.clear()
      screenerAnalysisResults = []
      screenerWatchlistResults = []
      screenerAnalysisDiagnostics = { analyzed: 0, watchlist: 0, rejected: 0 }
      syncScreenerSelectionUi('A fresh read-only analysis is starting; any earlier preview was cleared.')
    }
    $('screener-analysis').hidden = false
    $('screener-analysis-status').textContent = `Analyzing only your ${screenerAnalysisSymbols.length} selected symbol${screenerAnalysisSymbols.length === 1 ? '' : 's'} with completed 15m, 1h, Daily and Weekly candles · ${screenerAnalysisOffset}/${screenerAnalysisSymbols.length} complete · next ${screenerAnalysisOffset + 1}–${Math.min(screenerAnalysisOffset + 12, screenerAnalysisSymbols.length)}…`
    $('screener-analysis-next').hidden = false
    try {
      const prices = Object.fromEntries(readySources.flatMap(source => Object.entries(source.result.market_data || {})).map(([symbol, quote]) => [symbol, quote.last_price]))
      const data = await postJson('/api/chartink/analyze', { symbols: screenerAnalysisSymbols, prices, offset: screenerAnalysisOffset, limit: 12 })
      const qualified = data.results.filter(item => item.decision === 'PASS' && item.conviction?.rating === 'High')
      const watchlist = data.results.filter(item => item.decision === 'WATCHLIST')
      screenerAnalysisResults = reset ? qualified : screenerAnalysisResults.concat(qualified)
      screenerWatchlistResults = reset ? watchlist : screenerWatchlistResults.concat(watchlist)
      screenerAnalysisDiagnostics.analyzed += data.analyzed
      screenerAnalysisDiagnostics.watchlist += data.results.filter(item => item.decision === 'WATCHLIST').length
      screenerAnalysisDiagnostics.rejected += data.results.filter(item => item.decision === 'REJECT' || (item.decision === 'PASS' && item.conviction?.rating !== 'High')).length
      $('screener-analysis-status').textContent = `${screenerAnalysisResults.length} high-conviction recommendation(s) shown first · ${screenerAnalysisDiagnostics.analyzed} analyzed of ${data.total} · ${screenerAnalysisDiagnostics.watchlist} watchlist shown separately · ${screenerAnalysisDiagnostics.rejected} rejected/deferred hidden.`
      const cards = qualified.map(item => { const projectedPoints = Math.abs(Number(item.target) - Number(item.entry)); const projectedPct = Number(item.entry) > 0 ? projectedPoints / Number(item.entry) * 100 : null; return `<article class="opportunity-card ${item.direction === 'BEARISH' ? 'bearish' : ''}"><div class="opportunity-head"><div><b>${escapeHtml(item.symbol)}</b><small>${escapeHtml(item.alignment)}</small></div><span class="conviction">HIGH CONVICTION</span></div>${horizonLegends(item)}<p class="proposal-copy">${escapeHtml(item.reason)}</p><div class="decision-metrics"><div><small>Entry</small><b>${money(item.entry)}</b></div><div><small>Stop</small><b>${money(item.stop)}</b></div><div><small>Target</small><b>${money(item.target)}</b></div><div><small>R:R</small><b>1:${escapeHtml(item.reward_to_risk)}</b></div></div><p class="proposal-copy"><b>Rule-based evidence:</b> ${escapeHtml(item.conviction?.rationale)}</p><p class="proposal-copy"><b>Projection if target is reached:</b> ${money(projectedPoints)} per share${projectedPct == null ? '' : ` · ${percent(projectedPct)}`}. This is conditional, not guaranteed.</p><small class="muted">Completed candles only · read-only advisory · no automatic selection or order authority.</small></article>` }).join('')
      if (reset) $('screener-analysis-results').innerHTML = cards || '<div class="empty">No candidate currently clears the established high-conviction gates. No recommendation is shown.</div>'; else if (cards) { const empty = $('screener-analysis-results').querySelector('.empty'); if (empty) empty.remove(); $('screener-analysis-results').insertAdjacentHTML('beforeend', cards) }
      const watchCards = watchlist.map(item => `<article class="opportunity-card"><div class="opportunity-head"><div><b>${escapeHtml(item.symbol)}</b><small>${escapeHtml(item.alignment)}</small></div><span class="conviction">WATCHLIST · ADVISORY</span></div>${horizonLegends(item)}<p class="proposal-copy">${escapeHtml(item.reason)}</p><small class="muted">Non-actionable · no selection, ticket, or live-order path.</small></article>`).join('')
      if (reset) $('screener-watchlist-results').innerHTML = watchCards || '<div class="empty">No watchlist candidates in the analyzed batch.</div>'; else if (watchCards) { const empty = $('screener-watchlist-results').querySelector('.empty'); if (empty) empty.remove(); $('screener-watchlist-results').insertAdjacentHTML('beforeend', watchCards) }
      document.querySelectorAll('#screener-analysis-results .opportunity-card').forEach((card, index) => {
        const plan = screenerAnalysisResults[index]
        if (plan?.decision !== 'PASS' || card.querySelector('.screener-plan-select')) return
        card.insertAdjacentHTML('beforeend', `<label class="choice"><input type="checkbox" class="screener-plan-select" value="${escapeHtml(plan.symbol)}" ${screenerSelectedPlans.has(plan.symbol) ? 'checked' : ''}> Select for FYERS batch</label>`)
        card.querySelector('.screener-plan-select').addEventListener('change', event => selectScreenerOrderPlan(plan, event.target.checked, event.target))
      })
      $('screener-selected-count').textContent = `${screenerSelectedPlans.size} selected`
      $('screener-clear-selection').disabled = screenerSelectedPlans.size === 0
      $('screener-select-all').disabled = screenerAnalysisResults.length === 0 || screenerSelectedPlans.size === screenerAnalysisResults.length
      screenerAnalysisOffset += data.analyzed
      if (data.has_more && !screenerAnalysisCancelled) {
        $('screener-analysis-status').textContent = `${screenerAnalysisOffset}/${data.total} complete · queuing the next safe batch of up to ${data.operational_limits.batch_size}…`
        await analyzeScreenerCandidates(false)
      } else {
        screenerAnalysisRunning = false
        syncScreenerCandidateSelectionUi()
        $('screener-analysis-next').hidden = true
        $('screener-analysis-next').disabled = false
        $('screener-analysis-status').textContent = screenerAnalysisCancelled
          ? `Analysis cancelled after ${screenerAnalysisOffset}/${data.total} candidates. Existing results remain read-only.`
          : `Complete · ${screenerAnalysisOffset}/${data.total} analyzed · ${screenerAnalysisResults.length} high-conviction shown first · ${screenerWatchlistResults.length} watchlist shown separately · ${screenerAnalysisDiagnostics.rejected} rejected/deferred hidden.`
        if (screenerAnalysisResults.length) await analyzeScreenerOptionPlans()
      }
    } catch (error) {
      screenerAnalysisRunning = false
      syncScreenerCandidateSelectionUi()
      $('screener-analysis-next').hidden = true
      $('screener-analysis-next').disabled = false
      $('screener-analysis-status').className = 'handoff-status error'; $('screener-analysis-status').textContent = `Analysis stopped after ${screenerAnalysisOffset}/${screenerAnalysisSymbols.length}: ${error.message}`
    }
  }
  const analyzeScreenerOptionPlans = async () => {
    const button = $('analyze-screener-options')
    if (!screenerAnalysisResults.length) { $('screener-options-status').textContent = 'No High-Conviction equity underlyings are available for option screening.'; return }
    button.disabled = true
    $('screener-options-status').className = 'handoff-status'
    $('screener-options-status').textContent = 'Refreshing FYERS option chains, exact contracts, two-sided quotes, Greeks, open interest, volume and spread liquidity…'
    try {
      const data = await postJson('/api/chartink/analyze-options', { candidates: screenerAnalysisResults.slice(0, 12) })
      $('screener-options-status').textContent = data.message
      $('screener-options-results').innerHTML = (data.plans || []).map(item => {
        const proposal = item.proposal || {}, sizing = proposal.sizing || {}, legs = proposal.legs || []
        const legRows = legs.map(leg => `<tr><td>${escapeHtml(leg.action)}</td><td>${escapeHtml(leg.symbol)}</td><td>${money(leg.bid)} / ${money(leg.ask)}</td><td>${escapeHtml(leg.open_interest ?? '—')}</td><td>${escapeHtml(leg.volume ?? '—')}</td></tr>`).join('')
        return `<article class="opportunity-card ${item.direction === 'BEARISH' ? 'bearish' : ''}"><div class="opportunity-head"><div><b>${escapeHtml(item.symbol)}</b><small>${escapeHtml(proposal.label || 'Defined-risk spread')} · expiry ${escapeHtml(item.expiry || '—')}</small></div><span class="conviction">HIGH CONVICTION · OPTIONS</span></div>${horizonLegends(item)}<div class="decision-metrics"><div><small>Entry</small><b>${number(proposal.entry_points, ' pts')}</b></div><div><small>Max loss / lot</small><b>${money(proposal.max_loss_per_lot)}</b></div><div><small>R:R</small><b>1:${number(proposal.reward_to_risk)}</b></div><div><small>Supported size</small><b>${escapeHtml(sizing.lots || 0)} lot(s)</b></div></div><table class="leg-table"><thead><tr><th>Side</th><th>Contract</th><th>Bid / ask</th><th>OI</th><th>Volume</th></tr></thead><tbody>${legRows}</tbody></table><p class="proposal-copy"><b>Rule-based evidence:</b> ${escapeHtml(item.conviction?.rationale)}</p><small class="muted">Fresh FYERS evidence · defined risk · decision support only · not selected for the cash-equity batch.</small></article>`
      }).join('') || `<div class="empty">No stock-option spread currently passes every contract, liquidity, sizing and conviction gate.</div>`
      if ((data.excluded || []).length) $('screener-options-results').insertAdjacentHTML('beforeend', `<details class="excluded-list"><summary>${data.excluded.length} option candidate(s) excluded</summary>${data.excluded.map(item => `<p><b>${escapeHtml(item.symbol)}</b> · ${escapeHtml(item.reason)}</p>`).join('')}</details>`)
    } catch (error) {
      $('screener-options-status').className = 'handoff-status error'
      $('screener-options-status').textContent = error.message
    } finally { button.disabled = false }
  }
  const invalidateScreenerOrderPreview = message => {
    screenerOrderPreview = null
    $('screener-order-review').hidden = true
    $('screener-order-confirmation').value = ''
    $('submit-screener-order').disabled = true
    if (message) $('screener-order-status').textContent = message
  }
  const syncScreenerSelectionUi = (message, scroll = false) => {
    const count = screenerSelectedPlans.size
    $('screener-selected-count').textContent = `${count} selected`
    $('screener-clear-selection').disabled = count === 0
    $('screener-select-all').disabled = screenerAnalysisResults.length === 0 || count === screenerAnalysisResults.length
    $('screener-order').hidden = count === 0
    const allocation = [...screenerSelectedPlans.values()].map(plan => `${plan.symbol} × ${plan.suggested_quantity || 1}`).join(', ')
    $('screener-batch-selection').textContent = `${count} plan(s) selected: ${allocation || 'none'}. Quantities are allocated from fresh FYERS funds and conviction, then remain editable in the reviewed ticket.`
    document.querySelectorAll('#screener-analysis-results .screener-plan-select').forEach(control => { control.checked = screenerSelectedPlans.has(control.value) })
    invalidateScreenerOrderPreview(message || 'Selection changed. Prepare a new consolidated FYERS preview; no broker action has occurred.')
    if (scroll && count) $('screener-order').scrollIntoView({ behavior: scrollBehavior, block: 'start' })
  }
  const selectScreenerOrderPlan = (plan, selected, control) => {
    if (selected) screenerSelectedPlans.set(plan.symbol, plan); else screenerSelectedPlans.delete(plan.symbol)
    syncScreenerSelectionUi(null, true)
  }
  const allocateScreenerPlansByFunds = async () => {
    const account = await fetchJson('/api/account')
    if (!account?.connected || !Number.isFinite(Number(account.available_funds))) throw new Error(account?.error || 'FYERS available funds are unavailable for allocation.')
    let remaining = Number(account.available_funds)
    const ranked = [...screenerAnalysisResults].filter(plan => plan.decision === 'PASS' && Number(plan.entry) > 0).sort((left, right) => {
      const a = Number(left.conviction?.score || 0); const b = Number(right.conviction?.score || 0)
      return b - a || Number(left.entry) - Number(right.entry) || String(left.symbol).localeCompare(String(right.symbol))
    })
    for (const plan of ranked) {
      const entry = Number(plan.entry)
      const score = Math.max(1, Number(plan.conviction?.score || 1))
      plan.suggested_quantity = remaining >= entry ? 1 : 0
      plan.allocation_notional = plan.suggested_quantity * entry
      plan.allocation_weight = score
      if (plan.suggested_quantity) remaining -= entry
    }
    const funded = ranked.filter(plan => plan.suggested_quantity > 0)
    const totalWeight = funded.reduce((sum, plan) => sum + plan.allocation_weight, 0)
    for (const plan of funded) {
      const extra = Math.floor((remaining * plan.allocation_weight / totalWeight) / Number(plan.entry))
      if (extra > 0) {
        plan.suggested_quantity += extra
        plan.allocation_notional += extra * Number(plan.entry)
        remaining -= extra * Number(plan.entry)
      }
    }
    screenerSelectedPlans.clear()
    funded.forEach(plan => screenerSelectedPlans.set(plan.symbol, plan))
    syncScreenerSelectionUi(`Allocated from fresh FYERS available funds of ${money(account.available_funds)} by conviction. Higher-conviction plans receive priority; suggested quantities remain editable.`)
  }
  const prepareScreenerOrder = async () => {
    const button = $('prepare-screener-order')
    try {
      if (!screenerSelectedPlans.size) throw new Error('Select at least one High-Conviction plan before requesting a FYERS batch preview.')
      const policy = riskPolicyInputs()
      button.disabled = true; button.textContent = 'Refreshing FYERS preflight…'
      $('screener-order-status').className = 'handoff-status'
      $('screener-order-status').textContent = 'Validating FYERS auth, security master, live two-sided quote, market state, product, side, quantity, funds, positions, orders and risk ledger.'
      const external = $('screener-order-external-risk').value
      const items = [...screenerSelectedPlans.values()].map(plan => {
        const quantity = Math.max(1, Math.floor(Number(plan.suggested_quantity || 1)))
        return {
        broker: 'fyers', underlying: `NSE:${plan.symbol}-EQ`, proposal: { kind: 'EQUITY', label: `Screener ${plan.direction === 'BULLISH' ? 'long' : 'short'} limit`, direction: plan.direction, quantity, entry: plan.entry, target: plan.target },
        invalidation: Number(plan.stop), quantity, cash_product: $('screener-order-product').value,
        daily_loss_limit: policy.dailyLossLimit, idea_risk_limit: policy.ideaRiskLimit, risk_reserve: policy.riskReserve,
        max_simultaneous_positions: policy.maxPositions, minimum_reward_to_risk: policy.minimumRewardToRisk,
        enforce_risk_controls: policy.enforceRiskControls, enforce_minimum_reward_to_risk: policy.minimumRewardToRisk > 0, order_type: policy.orderType,
        external_open_risk: external === '' ? null : Number(external), require_market_open: true,
      }})
      const preview = await postJson('/api/trade-ticket/prepare-batch', { items })
      screenerOrderPreview = preview
      $('screener-order-preview').textContent = JSON.stringify(preview, null, 2)
      $('screener-order-review').hidden = false
      $('screener-order-confirmation').value = ''
      $('submit-screener-order').disabled = true
      $('screener-order-status').textContent = `Exact FYERS batch preview ${preview.preview_id} prepared · ${preview.aggregate.order_count} orders · ${money(preview.aggregate.total_worst_case_risk)} total risk · ${money(preview.aggregate.cash_reserved)} cash reserved. Review every item and exclusion.`
    } catch (error) { $('screener-order-status').className = 'handoff-status error'; $('screener-order-status').textContent = error.message }
    finally { button.disabled = false; button.textContent = 'Prepare FYERS batch preview' }
  }
  const submitScreenerOrder = async () => {
    if (!screenerOrderPreview) return
    const button = $('submit-screener-order'); button.disabled = true
    try {
      const result = await postJson('/api/trade-ticket/submit-batch', { preview_id: screenerOrderPreview.preview_id, confirmation: $('screener-order-confirmation').value })
      $('screener-order-preview').textContent = JSON.stringify(result, null, 2)
      $('screener-order-status').textContent = `${result.status}: ${result.message}`
      screenerOrderPreview = null
    } catch (error) { $('screener-order-status').className = 'handoff-status error'; $('screener-order-status').textContent = error.message }
  }
  renderScreenerSources()
  const metric = (label, value, title = '') => `<article class="metric" title="${escapeHtml(title)}"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></article>`
  const qualityClass = value => String(value || 'unavailable').toLowerCase().replaceAll(' ', '-')
  const stateButton = (sector, timeframe) => {
    const value = sector.timeframe_states?.[timeframe]
    const state = value?.state
    const cls = state === 2 ? 'strong-positive' : state === 1 ? 'positive' : state === -1 ? 'negative' : state === -2 ? 'strong-negative' : state == null ? 'unavailable' : 'neutral'
    const title = value?.reasons?.join(' · ') || value?.data_quality || 'Unavailable'
    return `<button type="button" class="tf-button ${cls}" data-sector="${escapeHtml(sector.sector_id)}" data-timeframe="${timeframe}" title="${escapeHtml(title)}" aria-label="${escapeHtml(sector.name)} ${timeframe}: ${escapeHtml(value?.label || 'Unavailable')} · ${escapeHtml(qualityText(value?.data_quality || 'Unavailable'))}">${state == null ? '—' : state > 0 ? `+${state}` : state}</button>`
  }
  const applyFilter = sectors => {
    return filterAndSortSectors(sectors, $('sector-filter').value, $('sector-sort').value)
  }
  const renderTopContributors = sector => {
    const attribution = sector.attribution || {}
    const rows = sector.top_contributors || []
    const scopeClass = attribution.status === 'OFFICIAL_COMPLETE' ? 'complete' : attribution.status === 'OFFICIAL_PARTIAL' ? 'partial' : ''
    const scope = attribution.status === 'OFFICIAL_COMPLETE'
      ? `Official complete · as of ${sourceDate(attribution.source_as_of)}`
      : attribution.status === 'OFFICIAL_PARTIAL'
        ? `Official top ${attribution.published_constituents} · ${number(attribution.weight_coverage_pct, '%')} coverage · as of ${sourceDate(attribution.source_as_of)}`
        : 'Authoritative weights unavailable'
    return `<td class="contributors">${rows.length ? rows.map(item => `<div class="contributor" title="Provider tick ${escapeHtml(item.provider_tick_timestamp_iso || item.provider_tick_timestamp || 'unavailable')}"><b>${escapeHtml(item.ticker)}</b><span>${number(item.weight, '%')}</span><span class="${stateClass(item.change)}">${percent(item.change)}</span><strong class="${stateClass(item.contribution)}">${percentagePoints(item.contribution)}</strong></div>`).join('') : '<span class="muted">Live constituent moves unavailable</span>'}<small class="source-scope ${scopeClass}">${escapeHtml(scope)}</small></td>`
  }
  const renderOverview = overview => {
    const pending = analysis?.refreshing && !analysis?.sectors?.length ? 'Waiting for first snapshot' : 'Unavailable'
    $('market-overview').innerHTML = [
      metric('Market regime', overview.market_regime || pending),
      metric('Leading', rotationOverviewValue(overview, ['leading'])),
      metric('Improving', rotationOverviewValue(overview, ['improving'])),
      metric('Weakening / lagging', rotationOverviewValue(overview, ['weakening', 'lagging'])),
      metric('Sector breadth', overview.sector_breadth ? `${overview.sector_breadth.bullish} / ${overview.sector_breadth.total} bullish` : pending),
      metric('Daily + Weekly bullish', overview.daily_weekly_bullish_alignment ? `${overview.daily_weekly_bullish_alignment.count} / ${overview.daily_weekly_bullish_alignment.total}` : pending),
    ].join('')
  }
  const renderRefreshState = () => {
    const labels = { CONNECTING: 'Connecting', LOADING_BARS: 'Completed bars', CALCULATING_INDICATORS: 'Indicators', READY: 'Ready' }
    const steps = refreshPhaseState(analysis)
    $('pipeline-track').innerHTML = steps.map(step => `<span class="pipeline-step ${step.state}"><i aria-hidden="true"></i>${labels[step.id]}</span>`).join('')
    const refresh = analysis?.refresh_state || {}
    const retained = !!analysis?.sectors?.length && (analysis?.refreshing || refresh.phase === 'FAILED')
    const progress = refresh.phase === 'LOADING_BARS' && refresh.total ? ` · ${refresh.completed || 0}/${refresh.total}` : ''
    const isFailed = refresh.phase === 'FAILED'
    const isLoading = !!analysis?.refreshing && !isFailed
    const lastRefresh = analysis?.updated_at ? `Last refresh ${time(analysis.updated_at)}` : 'Waiting for the first completed-bar snapshot.'
    const supportingCopy = retained
      ? isFailed ? `Refresh failed. Last valid metrics remain visible · ${lastRefresh}` : `Refreshing safely while the prior valid table stays visible · ${lastRefresh}`
      : isLoading ? 'Building the first completed-bar snapshot. Metrics will appear when calculation finishes.' : lastRefresh
    $('pipeline-kicker').textContent = isFailed ? 'REFRESH NEEDS ATTENTION' : isLoading ? 'REFRESH IN PROGRESS' : 'SECTOR DATA READY'
    $('pipeline-message').innerHTML = `<b>${escapeHtml(refresh.message || (analysis?.error ? 'Analysis unavailable' : 'Sector rotation is ready'))}${escapeHtml(progress)}</b><span>${escapeHtml(supportingCopy)}</span>`
    $('refresh-pipeline').classList.toggle('loading', isLoading)
    $('refresh-pipeline').classList.toggle('ready', !isLoading && !isFailed)
    $('refresh-pipeline').classList.toggle('failed', isFailed)
    document.querySelector('.table-wrap').classList.toggle('retained', retained)
    $('analysis-status').classList.toggle('failed', refresh.phase === 'FAILED' || !!analysis?.error)
  }
  const renderTable = () => {
    if (!analysis?.sectors?.length) {
      $('sector-body').innerHTML = `<tr><td colspan="17" class="empty ${analysis?.error ? 'error' : ''}">${escapeHtml(analysis?.error || 'Completed-bar analysis is still loading.')}</td></tr>`
      renderOverview(analysis?.market_overview || {})
      return
    }
    renderOverview(analysis.market_overview || {})
    const rows = applyFilter(analysis.sectors)
    $('sector-body').innerHTML = rows.map(sector => {
      const rankChange = sector.rank_change == null ? '—' : sector.rank_change > 0 ? `+${sector.rank_change}` : String(sector.rank_change)
      const rotation = rotationDisplay(sector)
      return `<tr class="sector-row" tabindex="0" data-detail="${escapeHtml(sector.sector_id)}"><td class="sector-name"><b>${escapeHtml(sector.name)}</b><small class="quality ${qualityClass(sector.data_quality)}">${escapeHtml(qualityText(sector.data_quality))}</small></td>${renderTopContributors(sector)}${timeframeOrder.map(tf => `<td>${stateButton(sector, tf)}</td>`).join('')}<td>${escapeHtml(sector.mtf_alignment)}</td><td class="${stateClass((sector.relative_strength_score ?? 50) - 50)}">${escapeHtml(sector.relative_strength_state)}<br><small>${number(sector.relative_strength_score)}</small></td><td>${number(sector.adx)}</td><td>${number(sector.momentum_score)}</td><td>${number(sector.breadth_score)}</td><td>${number(sector.volume_score)}</td><td class="${sector.rotation_readiness === 'READY' ? '' : 'neutral'}">${escapeHtml(rotation)}</td><td><b>${number(sector.overall_score)}</b></td><td>${sector.rank ? `#${sector.rank}` : '—'}</td><td class="rank-change ${sector.rank_change > 0 ? 'up' : sector.rank_change < 0 ? 'down' : ''}">${rankChange}</td><td>${time(sector.last_updated)}</td></tr>`
    }).join('') || '<tr><td colspan="17" class="empty">No sectors match this filter.</td></tr>'
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
    const attribution = sector.attribution || {}
    const attributionScope = attribution.status === 'OFFICIAL_COMPLETE' ? 'Complete official-weight coverage' : attribution.status === 'OFFICIAL_PARTIAL' ? `Partial official top-${attribution.published_constituents} coverage (${number(attribution.weight_coverage_pct, '%')})` : 'Authoritative weights unavailable'
    $('sector-detail').innerHTML = `<div class="detail-head"><div><span class="label">SECTOR DETAIL · ${escapeHtml(mode.toUpperCase())}</span><h2>${escapeHtml(sector.name)}</h2><small class="last-updated">Completed bars · Updated ${time(sector.last_updated)} · ${escapeHtml(qualityText(sector.data_quality))}</small><small class="last-updated">${escapeHtml(attributionScope)} · NSE source as of ${sourceDate(attribution.source_as_of)}${attribution.factsheet_url ? ` · <a class="provenance-link" href="${escapeHtml(attribution.factsheet_url)}" target="_blank" rel="noopener noreferrer">Official factsheet</a>` : ''}</small></div><button type="button" class="button" id="strongest-stocks">View strongest stocks</button></div>
      <div class="components">${[['Overall', sector.overall_score], ['Trend', sector.trend_score], ['RS vs NIFTY', sector.relative_strength_score], ['Momentum', sector.momentum_score], ['Breadth', sector.breadth_score], ['Volume', sector.volume_score]].map(([label, value]) => `<div class="component"><span>${label}</span><strong>${number(value)}</strong></div>`).join('')}</div>
      <div class="mode-tabs" aria-label="Detail timeframe" style="margin-top:12px">${timeframeOrder.map(tf => `<button type="button" data-detail-timeframe="${tf}" class="${selectedTimeframe === tf ? 'active' : ''}" aria-pressed="${selectedTimeframe === tf}">${tf}</button>`).join('')}</div>
      <div class="detail-grid"><div><article class="chart-card"><h3>${escapeHtml(sector.name)} ${escapeHtml(selectedTimeframe)} · Price and EMA structure</h3>${priceChart(state)}</article><div class="explanation"><b>${escapeHtml(state.label || 'Unavailable')} · Trend ${number(state.score)}/100</b><ul>${(state.reasons || []).map(reason => `<li>${escapeHtml(reason)}</li>`).join('') || '<li>No explanation is available because candle data is missing.</li>'}</ul></div><div class="chart-grid" style="margin-top:12px">${lineChart('Sector score history', history, 'overall_score')}${lineChart('Rank history', history, 'rank', true)}${lineChart('Relative strength history', history, 'relative_strength_score')}${lineChart('Momentum history', history, 'momentum_score')}${lineChart('Breadth history', history, 'breadth_score')}</div></div>
      <aside><article class="chart-card"><h3>Multi-timeframe summary</h3>${timeframeOrder.map(tf => { const item = sector.timeframe_states?.[tf] || {}; return `<div class="row" style="grid-template-columns:70px 1fr 70px"><b>${tf}</b><span class="${stateClass(item.state)}" title="${escapeHtml(qualityText(item.data_quality || 'Unavailable'))}">${escapeHtml(item.label || 'Unavailable')}</span><strong>${number(item.score)}</strong></div>` }).join('')}</article><article class="chart-card" style="margin-top:12px"><h3>Rotation history</h3><div class="rotation-list">${history.length ? history.slice().reverse().map(point => `<div><span>${time(point.timestamp)}</span><b>${escapeHtml(point.rotation_state || 'NEUTRAL')}</b><span>${point.rank ? `#${point.rank}` : '—'} · ${number(point.overall_score)}</span></div>`).join('') : '<div class="chart-empty">Waiting for persisted snapshots.</div>'}</div></article><article class="chart-card" style="margin-top:12px"><h3>Data quality</h3><p>${escapeHtml(qualityText(sector.data_quality))}</p><p class="muted">Latest completed bar: ${time(sector.last_updated)}</p><p class="muted">Missing: ${escapeHtml((sector.missing_components || []).join(', ') || 'none')}</p><p class="muted">Weights: ${escapeHtml(Object.entries(sector.component_weights || {}).map(([key, value]) => `${key} ${value}%`).join(' · '))}</p></article></aside></div>
      <section id="constituent-workflow" class="chart-card" style="margin-top:12px"><h3>Sector → stock prioritization</h3><p class="muted">Contributions use unrounded FYERS stock moves multiplied by the official published weight. They are analytical only and do not place orders. ${escapeHtml(attributionScope)}.</p><div class="movers"><div><b>Strongest current contributors</b><ul class="mover-list">${strongest.length ? strongest.map(item => `<li><span>${escapeHtml(item.ticker)} · ${number(item.weight, '%')} · ${percent(item.change)}</span><strong class="${stateClass(item.contribution)}">${percentagePoints(item.contribution)}</strong></li>`).join('') : '<li>Live constituent data unavailable</li>'}</ul></div><div><b>Weakest current contributors</b><ul class="mover-list">${weakest.length ? weakest.map(item => `<li><span>${escapeHtml(item.ticker)} · ${number(item.weight, '%')} · ${percent(item.change)}</span><strong class="${stateClass(item.contribution)}">${percentagePoints(item.contribution)}</strong></li>`).join('') : '<li>Live constituent data unavailable</li>'}</ul></div></div></section>`
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
      $('analysis-status').textContent = analysisStatusText(analysis, time)
      $('weight-source').textContent = `Official NSE constituent weights as of ${sourceDate(analysis.weight_source?.source_as_of)} · ${analysis.weight_source?.complete_indices ?? 0} complete, ${analysis.weight_source?.partial_indices ?? 0} partial indices`
      renderTable()
      if (selectedSector && analysis.sectors?.some(item => item.sector_id === selectedSector)) loadDetail(selectedSector, selectedTimeframe)
    } catch (error) {
      const retained = analysis?.sectors?.length ? analysis : null
      analysis = retained
        ? { ...retained, refreshing: false, refresh_error: error.message, refresh_state: { ...(retained.refresh_state || {}), phase: 'FAILED', last_phase: retained.refresh_state?.phase || 'CONNECTING', message: error.message } }
        : { status: 'UNAVAILABLE', sectors: [], error: error.message, refreshing: false, refresh_state: { phase: 'FAILED', last_phase: 'CONNECTING', message: error.message } }
      $('analysis-status').textContent = analysisStatusText(analysis, time)
      renderTable()
    } finally {
      renderRefreshState()
      clearTimeout(analysisRefreshTimer)
      analysisRefreshTimer = setTimeout(refreshAnalysis, analysis?.refreshing ? analysisLoadingPollMs : analysisReadyPollMs)
    }
  }
  const refreshAccount = async () => {
    const setAuthenticationControl = connected => {
      const button = $('reauth')
      const help = $('reauth-help')
      button.disabled = connected === true
      button.setAttribute('aria-disabled', connected === true ? 'true' : 'false')
      button.title = connected === true ? 'FYERS is connected; authentication refresh is unnecessary while this session remains valid.' : 'Refresh FYERS authentication'
      help.textContent = connected === true
        ? 'FYERS is connected. Authentication refresh is unnecessary while this session remains valid.'
        : 'FYERS is disconnected, expired, unavailable, or its status is unknown. Manual authentication refresh is available.'
    }
    try {
      const data = await fetchJson('/api/account')
      const positions = (data.positions || []).filter(item => Number(item.netQty ?? item.net_qty ?? 0) !== 0)
      const charges = data.estimated_charges || {}; const chargeTotal = Number(charges.total)
      const estimatedNet = Number(data.estimated_net_pnl)
      $('live-pnl').textContent = data.connected ? money(data.pnl) : '—'; $('live-pnl').className = data.connected ? stateClass(data.pnl) : 'neutral'
      $('estimated-charges').textContent = data.connected && Number.isFinite(chargeTotal) ? `−${money(chargeTotal)}` : '—'; $('estimated-charges').className = data.connected && Number.isFinite(chargeTotal) ? 'negative' : 'neutral'
      $('estimated-charges-note').textContent = charges.available ? `Estimate · ${charges.orders || 0} executed orders` : (charges.disclaimer || 'Awaiting FYERS tradebook')
      $('estimated-net-pnl').textContent = data.connected && Number.isFinite(estimatedNet) ? money(estimatedNet) : '—'; $('estimated-net-pnl').className = data.connected && Number.isFinite(estimatedNet) ? stateClass(estimatedNet) : 'neutral'
      $('open-count').textContent = data.connected ? String(positions.length) : '—'; $('funds').textContent = data.connected ? money(data.available_funds) : '—'
      $('open-positions').innerHTML = !data.connected ? `<p class="empty error">${escapeHtml(data.error || 'Connect FYERS to load positions.')}</p>` : positions.length ? positions.map(item => { const quantity = item.netQty ?? item.net_qty ?? 0; const pnl = item.pl ?? item.pnl ?? 0; return `<div class="row"><b>${escapeHtml(item.symbol || item.symbol_name || '—')}</b><span>${quantity}</span><span>${money(item.netAvg ?? item.net_avg)}</span><strong class="${stateClass(pnl)}">${money(pnl)}</strong></div>` }).join('') : '<p class="empty">No open broker positions.</p>'
      $('broker-dot').classList.toggle('ok', data.connected === true); $('broker-state').textContent = data.connected === true ? 'FYERS connected' : (data.error || 'FYERS disconnected'); $('account-state').textContent = data.connected === true ? 'Broker feed connected' : (data.error || 'Broker feed unavailable'); setAuthenticationControl(data.connected === true)
    } catch (error) { $('account-state').textContent = error.message; $('broker-state').textContent = 'FYERS unavailable'; $('broker-dot').classList.remove('ok'); setAuthenticationControl(false) }
  }
  const refreshClosed = async () => {
    try {
      const data = await fetchJson(`/api/realized-pnl?period=${period}`)
      const summary = data.summary || {}; const records = data.records || []; const reportedTotal = Number(summary.net_pnl); const total = Number.isFinite(reportedTotal) ? reportedTotal : records.reduce((sum, item) => sum + Number(item.pnl || 0), 0)
      $('closed-pnl').textContent = data.supported === false ? '—' : money(total); $('closed-pnl').className = data.supported === false ? 'neutral' : stateClass(total)
      const periodName = `${period[0].toUpperCase() + period.slice(1)}`; $('closed-pnl-label').textContent = `${periodName} net P&L`
      $('closed-summary').innerHTML = data.supported === false ? `<span class="muted">${escapeHtml(data.message || 'Realised P&L history is unavailable from FYERS.')}</span>` : `<b>${periodName} net P&L</b><span aria-hidden="true"></span><span aria-hidden="true"></span><strong class="${stateClass(total)}">${money(total)}</strong>`
      $('closed-positions').innerHTML = data.supported === false ? `<p class="empty">${escapeHtml(data.message || 'Realised P&L history is unavailable from FYERS.')}</p>` : records.length ? records.map(item => `<div class="row"><b>${escapeHtml(item.symbol)}</b><span>${escapeHtml(item.buy_rate)} / ${escapeHtml(item.sell_rate)}</span><span>${escapeHtml(item.buy_qty)} / ${escapeHtml(item.sell_qty)}</span><strong class="${stateClass(item.pnl)}">${money(item.pnl)}</strong></div>`).join('') : '<p class="empty">No closed positions in this period.</p>'
    } catch (error) { $('closed-pnl-label').textContent = 'Closed P&L'; $('closed-summary').textContent = 'Closed-position summary unavailable.'; $('closed-positions').innerHTML = `<p class="empty error">${escapeHtml(error.message)}</p>` }
  }

  const renderPremiumChart = (chart, chartId = 'premium-chart', updatedId = 'premium-chart-updated') => {
    if (!chart) {
      $(chartId).innerHTML = '<div class="chart-empty">Chart starts when the strategy opens a position.</div>'
      if ($(updatedId)) $(updatedId).textContent = ''
      return
    }
    const candles = (chart.candles || []).filter(item => Number.isFinite(Number(item.close)))
    const points = candles.map(item => Number(item.close))
    if (Number.isFinite(Number(chart.premium_now))) points.push(Number(chart.premium_now))
    const stValues = candles.map(item => item.supertrend == null ? null : Number(item.supertrend))
    const rangeValues = points.concat(stValues.filter(Number.isFinite), [Number(chart.premium_entry), Number(chart.activation_premium)].filter(Number.isFinite))
    if (!rangeValues.length) {
      $(chartId).innerHTML = `<div class="chart-empty">${escapeHtml(chart.error || 'Waiting for combined-premium candles.')}</div>`
      if ($(updatedId)) $(updatedId).textContent = chart.updated_at ? `Updated ${time(chart.updated_at)}` : ''
      return
    }
    const width = 640, height = 240, left = 44, right = 12, top = 12, bottom = 28
    const low = Math.min(...rangeValues), high = Math.max(...rangeValues), padding = Math.max((high - low) * .12, 2)
    const minY = low - padding, maxY = high + padding
    const x = index => left + index * ((width - left - right) / Math.max(points.length - 1, 1))
    const y = value => top + (maxY - value) * ((height - top - bottom) / (maxY - minY))
    const pathFor = values => {
      let started = false
      return values.map((value, index) => {
        if (!Number.isFinite(value)) { started = false; return '' }
        const command = started ? 'L' : 'M'
        started = true
        return `${command}${x(index).toFixed(1)},${y(value).toFixed(1)}`
      }).join(' ')
    }
    const reference = (value, label, color) => Number.isFinite(Number(value)) ? `<line x1="${left}" x2="${width - right}" y1="${y(Number(value))}" y2="${y(Number(value))}" stroke="${color}" stroke-width="1" stroke-dasharray="5 5"/><text x="${left + 4}" y="${y(Number(value)) - 5}" fill="${color}" font-size="10">${escapeHtml(label)} ${number(value)}</text>` : ''
    const currentIndex = points.length - 1
    const pnlClass = Number(chart.pnl_points) >= 0 ? 'positive' : 'negative'
    $(chartId).innerHTML = `<div class="premium-chart-stats"><div><b>${number(chart.premium_now)}</b><small>Combined premium</small></div><div><b class="${pnlClass}">${Number(chart.pnl_points) >= 0 ? '+' : ''}${number(chart.pnl_points)} pts</b><small>${money(chart.pnl_rupees)}</small></div><div><b>${chart.supertrend_armed ? 'Armed' : 'Waiting'}</b><small>Supertrend 7,3</small></div></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Live combined call and put premium chart"><line x1="${left}" x2="${left}" y1="${top}" y2="${height - bottom}" stroke="#294766"/><line x1="${left}" x2="${width - right}" y1="${height - bottom}" y2="${height - bottom}" stroke="#294766"/>${reference(chart.premium_entry, 'Entry', '#91a7c4')}${reference(chart.activation_premium, 'Arm', '#f0a85c')}<path d="${pathFor(candles.map(item => Number(item.close)))}" fill="none" stroke="#72c7ff" stroke-width="3" stroke-linejoin="round"/><path d="${pathFor(stValues)}" fill="none" stroke="#60dca9" stroke-width="2" stroke-linejoin="round"/><circle cx="${x(currentIndex)}" cy="${y(points[currentIndex])}" r="5" fill="#edf4ff" stroke="#2678be" stroke-width="3"/><text x="4" y="${top + 8}" fill="#91a7c4" font-size="10">${maxY.toFixed(1)}</text><text x="4" y="${height - bottom}" fill="#91a7c4" font-size="10">${minY.toFixed(1)}</text><text x="${left}" y="${height - 7}" fill="#91a7c4" font-size="10">Completed 5-minute closes</text><text x="${width - right}" y="${height - 7}" text-anchor="end" fill="#edf4ff" font-size="10">LIVE</text></svg>${chart.error ? `<p class="muted">Candles delayed: ${escapeHtml(chart.error)}</p>` : ''}`
    if ($(updatedId)) $(updatedId).textContent = chart.updated_at ? `Updated ${time(chart.updated_at)}` : ''
  }

  const tradesForMode = (trades, mode) => (trades || []).filter(trade => {
    const marker = String(trade.dry_run ?? '').trim().toLowerCase()
    if (mode === 'paper') return ['true', '1', 'yes'].includes(marker)
    return ['false', '0', 'no'].includes(marker)
  })

  const renderStraddle = data => {
    straddleRunnerState = data
    const strategy = data.strategy || {}
    const position = data.position
    $('straddle-runner-state').textContent = !data.available ? 'Runner unavailable' : data.running ? `${data.mode} running · PID ${data.pid}` : 'Runner stopped'
    $('straddle-runner-state').classList.toggle('failed', !data.available)
    $('start-straddle').disabled = !data.available || data.running
    $('stop-straddle').disabled = !data.running
    ;['straddle-lots', 'straddle-entry-start', 'straddle-entry-end'].forEach(id => {
      const control = $(id)
      if (control) control.disabled = data.running
    })
    const lotsControl = $('straddle-lots')
    if (lotsControl && (!lotsControl.dataset.initialized || data.running)) {
      lotsControl.value = String(strategy.selected_lots || strategy.default_lots || 1)
      const entryStartControl = $('straddle-entry-start')
      const entryEndControl = $('straddle-entry-end')
      if (entryStartControl) entryStartControl.value = strategy.entry_window_start || '09:15'
      if (entryEndControl) entryEndControl.value = strategy.entry_window_end || '11:30'
      lotsControl.dataset.initialized = 'true'
    }
    $('straddle-contract').innerHTML = [
      ['Entry', strategy.entry], ['Instrument', strategy.instrument], ['Exit', strategy.exit],
      ['Hard stop', strategy.hard_stop], ['New-entry window', `${strategy.entry_window_start || '09:15'}–${strategy.entry_window_end || '11:30'} IST`], ['Re-entry limit', `${strategy.daily_reentry_limit ?? 1} per day`], ['EOD square-off', strategy.eod ? `${strategy.eod} IST` : '—'],
    ].map(([label, value]) => `<div><small>${escapeHtml(label)}</small><b>${escapeHtml(value || '—')}</b></div>`).join('')
    $('straddle-position').classList.toggle('flat', !position)
    $('straddle-position').innerHTML = position
      ? `<span class="label">OPEN ${escapeHtml(data.mode || '')} POSITION</span><b>${escapeHtml(position.ce_symbol || 'CE')} + ${escapeHtml(position.pe_symbol || 'PE')}</b><p class="muted">Strike ${escapeHtml(position.strike || '—')} · entry premium ${number(position.premium_entry)} · entered ${time(position.entry_time)}${position.supertrend_armed ? ' · Supertrend armed' : ''}</p>`
      : '<span class="label">POSITION STATE</span><b>Flat</b><p class="muted">No persisted strategy position.</p>'
    renderPremiumChart(data.premium_chart)
    const output = data.output || []
    $('straddle-output').textContent = output.length ? output.join('\n') : data.running ? 'Runner active. Waiting for output…' : 'Runner stopped. Choose options, then start it to stream activity here.'
    const selectedMode = document.querySelector('input[name="straddle-mode"]:checked')?.value || 'live'
    const trades = tradesForMode(data.recent_trades, selectedMode)
    $('straddle-trades').innerHTML = trades.length ? trades.map(trade => `<div class="row"><b>${time(trade.exit_time)}</b><span>${escapeHtml(trade.strike || '—')}</span><strong class="${stateClass(Number(trade.pnl_points))}">${number(trade.pnl_points)}</strong><span>${escapeHtml(trade.exit_reason || '—')}</span></div>`).join('') : '<p class="empty">No completed paper trades recorded.</p>'
    if (!trades.length) $('straddle-trades').innerHTML = `<p class="empty">No completed ${selectedMode} trades recorded.</p>`
    $('straddle-updated').textContent = `Status checked ${time(data.updated_at)}`
  }

  const refreshStraddle = async () => {
    try {
      renderStraddle(await fetchJson('/api/sensex-straddle'))
    } catch (error) {
      $('straddle-runner-state').classList.add('failed')
      $('straddle-runner-state').textContent = 'Runner status unavailable'
      $('straddle-action-status').className = 'handoff-status error'
      $('straddle-action-status').textContent = error.message
    }
  }

  const selectedStraddleMode = () => document.querySelector('input[name="straddle-mode"]:checked')?.value || 'live'
  const selectedStraddleExit = () => document.querySelector('input[name="straddle-exit"]:checked')?.value || 'supertrend'
  const selectedStraddleLots = () => {
    const raw = Number($('straddle-lots').value)
    if (!Number.isInteger(raw) || raw < 1 || raw > 20) throw new Error('Lots must be a whole number between 1 and 20.')
    return raw
  }
  const straddleEntryWindow = (startId, endId) => {
    const entryStart = $(startId).value
    const entryEnd = $(endId).value
    if (!/^\d{2}:\d{2}$/.test(entryStart) || !/^\d{2}:\d{2}$/.test(entryEnd)) throw new Error('Entry-window times must use HH:MM IST.')
    if (entryStart > entryEnd) throw new Error('Entry-window start must be no later than entry-window end.')
    return { entryStart, entryEnd }
  }
  const syncStraddleOptions = () => {
    const live = selectedStraddleMode() === 'live'
    $('start-straddle').textContent = live ? 'Start live runner' : 'Start paper runner'
    $('start-straddle').disabled = !straddleRunnerState.available || straddleRunnerState.running
  }
  const controlStraddle = async action => {
    const start = action === 'start'
    const button = $(start ? 'start-straddle' : 'stop-straddle')
    button.disabled = true
    $('straddle-action-status').className = 'handoff-status'
    const mode = selectedStraddleMode()
    const exitMode = selectedStraddleExit()
    let lots, entryWindow
    try { lots = start ? selectedStraddleLots() : undefined; entryWindow = start ? straddleEntryWindow('straddle-entry-start', 'straddle-entry-end') : undefined } catch (error) {
      $('straddle-action-status').className = 'handoff-status error'
      $('straddle-action-status').textContent = error.message
      syncStraddleOptions()
      return
    }
    if (start && mode === 'live' && !window.confirm('Start the LIVE SENSEX straddle runner? This can place real FYERS orders with real money.')) {
      $('straddle-action-status').textContent = 'Live runner start cancelled.'
      syncStraddleOptions()
      return
    }
    $('straddle-action-status').textContent = start ? `Starting ${mode} runner with ${exitMode} exit using ${lots} lot(s) in the ${entryWindow.entryStart}-${entryWindow.entryEnd} IST entry window…` : 'Stopping the managed runner…'
    try {
      const result = await postJson(`/api/sensex-straddle/${action}`, start ? { mode, exit_mode: exitMode, lots, entry_start: entryWindow.entryStart, entry_end: entryWindow.entryEnd, confirmation: mode === 'live' ? 'YES' : '' } : {})
      $('straddle-action-status').textContent = result.message
      await refreshStraddle()
    } catch (error) {
      $('straddle-action-status').className = 'handoff-status error'
      $('straddle-action-status').textContent = error.message
    } finally { syncStraddleOptions() }
  }

  const renderNiftyStraddle = data => {
    niftyStraddleRunnerState = data
    const strategy = data.strategy || {}
    const position = data.position
    $('nifty-straddle-runner-state').textContent = !data.available ? 'Runner unavailable' : data.running ? `${data.mode} running · PID ${data.pid}` : 'Runner stopped'
    $('nifty-straddle-runner-state').classList.toggle('failed', !data.available)
    $('start-nifty-straddle').disabled = !data.available || data.running
    $('stop-nifty-straddle').disabled = !data.running
    ;['nifty-straddle-lots', 'nifty-straddle-stoploss', 'nifty-straddle-target', 'nifty-straddle-entry-start', 'nifty-straddle-entry-end'].forEach(id => {
      const control = $(id)
      if (control) control.disabled = data.running
    })
    const niftyLotsControl = $('nifty-straddle-lots')
    if (niftyLotsControl && (!niftyLotsControl.dataset.initialized || data.running)) {
      niftyLotsControl.value = String(strategy.selected_lots || strategy.default_lots || 1)
      const stoplossControl = $('nifty-straddle-stoploss')
      const targetControl = $('nifty-straddle-target')
      const entryStartControl = $('nifty-straddle-entry-start')
      const entryEndControl = $('nifty-straddle-entry-end')
      if (stoplossControl) stoplossControl.value = String(strategy.stoploss_points || 15)
      if (targetControl) targetControl.value = String(strategy.target_points || 30)
      if (entryStartControl) entryStartControl.value = strategy.entry_window_start || '09:15'
      if (entryEndControl) entryEndControl.value = strategy.entry_window_end || '11:30'
      niftyLotsControl.dataset.initialized = 'true'
    }
    $('nifty-straddle-contract').innerHTML = [
      ['Entry', strategy.entry], ['Instrument', strategy.instrument], ['Exit', strategy.exit],
      ['Hard stop', strategy.hard_stop], ['New-entry window', `${strategy.entry_window_start || '09:15'}–${strategy.entry_window_end || '11:30'} IST`], ['Re-entry limit', `${strategy.daily_reentry_limit ?? 1} per day`], ['EOD square-off', strategy.eod ? `${strategy.eod} IST` : '—'],
    ].map(([label, value]) => `<div><small>${escapeHtml(label)}</small><b>${escapeHtml(value || '—')}</b></div>`).join('')
    $('nifty-straddle-position').classList.toggle('flat', !position)
    $('nifty-straddle-position').innerHTML = position
      ? `<span class="label">OPEN ${escapeHtml(data.mode || '')} POSITION</span><b>${escapeHtml(position.ce_symbol || 'CE')} + ${escapeHtml(position.pe_symbol || 'PE')}</b><p class="muted">Strike ${escapeHtml(position.strike || '—')} · entry premium ${number(position.premium_entry)} · entered ${time(position.entry_time)}</p>`
      : '<span class="label">POSITION STATE</span><b>Flat</b><p class="muted">No persisted NIFTY strategy position.</p>'
    renderPremiumChart(data.premium_chart, 'nifty-premium-chart', 'nifty-premium-chart-updated')
    const output = data.output || []
    $('nifty-straddle-output').textContent = output.length ? output.join('\n') : data.running ? 'Runner active. Waiting for output…' : 'Runner stopped. Choose options, then start it to stream activity here.'
    const selectedMode = document.querySelector('input[name="nifty-straddle-mode"]:checked')?.value || 'live'
    const trades = tradesForMode(data.recent_trades, selectedMode)
    $('nifty-straddle-trades').innerHTML = trades.length ? trades.map(trade => `<div class="row"><b>${time(trade.exit_time)}</b><span>${escapeHtml(trade.strike || '—')}</span><strong class="${stateClass(Number(trade.pnl_points))}">${number(trade.pnl_points)}</strong><span>${escapeHtml(trade.exit_reason || '—')}</span></div>`).join('') : '<p class="empty">No completed paper trades recorded.</p>'
    if (!trades.length) $('nifty-straddle-trades').innerHTML = `<p class="empty">No completed ${selectedMode} trades recorded.</p>`
    $('nifty-straddle-updated').textContent = `Status checked ${time(data.updated_at)}`
  }

  const refreshNiftyStraddle = async () => {
    try { renderNiftyStraddle(await fetchJson('/api/nifty-straddle')) }
    catch (error) {
      $('nifty-straddle-runner-state').classList.add('failed')
      $('nifty-straddle-runner-state').textContent = 'Runner status unavailable'
      $('nifty-straddle-action-status').className = 'handoff-status error'
      $('nifty-straddle-action-status').textContent = error.message
    }
  }

  const selectedNiftyStraddleMode = () => document.querySelector('input[name="nifty-straddle-mode"]:checked')?.value || 'live'
  const selectedNiftyStraddleExit = () => document.querySelector('input[name="nifty-straddle-exit"]:checked')?.value || 'supertrend'
  const syncNiftyStraddleOptions = () => {
    const live = selectedNiftyStraddleMode() === 'live'
    const fixed = selectedNiftyStraddleExit() === 'fixed'
    $('start-nifty-straddle').textContent = live ? 'Start live runner' : 'Start paper runner'
    $('start-nifty-straddle').disabled = !niftyStraddleRunnerState.available || niftyStraddleRunnerState.running
    $('nifty-straddle-stoploss').disabled = niftyStraddleRunnerState.running
    $('nifty-straddle-target').disabled = niftyStraddleRunnerState.running || !fixed
  }
  const niftyNumber = (id, label, whole = false) => {
    const value = Number($(id).value)
    if (!Number.isFinite(value) || value <= 0 || (whole && !Number.isInteger(value))) throw new Error(`${label} must be ${whole ? 'a positive whole number' : 'greater than zero'}.`)
    if (whole && value > 20) throw new Error('Lots must be between 1 and 20.')
    return value
  }
  const controlNiftyStraddle = async action => {
    const start = action === 'start'
    const mode = selectedNiftyStraddleMode()
    const exitMode = selectedNiftyStraddleExit()
    let lots, stoploss, target, entryWindow
    try {
      if (start) {
        lots = niftyNumber('nifty-straddle-lots', 'Lots', true)
        stoploss = niftyNumber('nifty-straddle-stoploss', 'Stoploss')
        target = niftyNumber('nifty-straddle-target', 'Target')
        entryWindow = straddleEntryWindow('nifty-straddle-entry-start', 'nifty-straddle-entry-end')
      }
    } catch (error) {
      $('nifty-straddle-action-status').className = 'handoff-status error'
      $('nifty-straddle-action-status').textContent = error.message
      return
    }
    if (start && mode === 'live' && !window.confirm('Start the LIVE NIFTY straddle runner? This can place real FYERS orders with real money.')) {
      $('nifty-straddle-action-status').textContent = 'Live runner start cancelled.'
      return
    }
    const button = $(start ? 'start-nifty-straddle' : 'stop-nifty-straddle')
    button.disabled = true
    $('nifty-straddle-action-status').className = 'handoff-status'
    $('nifty-straddle-action-status').textContent = start ? `Starting ${mode} runner with ${lots} lot(s), ${stoploss}-point stop and ${target}-point target in the ${entryWindow.entryStart}-${entryWindow.entryEnd} IST entry window…` : 'Stopping the managed NIFTY runner…'
    try {
      const result = await postJson(`/api/nifty-straddle/${action}`, start ? { mode, exit_mode: exitMode, lots, stoploss, target, entry_start: entryWindow.entryStart, entry_end: entryWindow.entryEnd, confirmation: mode === 'live' ? 'YES' : '' } : {})
      $('nifty-straddle-action-status').textContent = result.message
      await refreshNiftyStraddle()
    } catch (error) {
      $('nifty-straddle-action-status').className = 'handoff-status error'
      $('nifty-straddle-action-status').textContent = error.message
    } finally { syncNiftyStraddleOptions() }
  }

  const squareoffIds = runner => runner === 'sensex'
    ? { status: 'straddle-action-status', review: 'straddle-squareoff-review', preview: 'straddle-squareoff-preview', input: 'straddle-squareoff-confirmation', confirm: 'confirm-straddle-squareoff' }
    : { status: 'nifty-straddle-action-status', review: 'nifty-straddle-squareoff-review', preview: 'nifty-straddle-squareoff-preview', input: 'nifty-straddle-squareoff-confirmation', confirm: 'confirm-nifty-straddle-squareoff' }
  const prepareStraddleSquareoff = async runner => {
    const ids = squareoffIds(runner)
    $(ids.review).hidden = true
    $(ids.confirm).disabled = true
    $(ids.status).className = 'handoff-status'
    $(ids.status).textContent = 'Refreshing FYERS positions and orders for the exact runner-owned CE and PE legs…'
    try {
      const preview = await postJson('/api/straddle-squareoff/prepare', { runner })
      straddleSquareoffPreviews[runner] = preview
      $(ids.preview).textContent = JSON.stringify(preview, null, 2)
      $(ids.input).value = ''
      $(ids.review).hidden = false
      $(ids.status).textContent = 'Review the exact two-leg exit preview. No order has been sent and the runner remains active.'
    } catch (error) {
      straddleSquareoffPreviews[runner] = null
      $(ids.status).className = 'handoff-status error'
      $(ids.status).textContent = error.message
    }
  }
  const submitStraddleSquareoff = async runner => {
    const ids = squareoffIds(runner)
    const preview = straddleSquareoffPreviews[runner]
    if (!preview) return
    $(ids.confirm).disabled = true
    $(ids.status).textContent = 'Revalidating both FYERS legs before stopping the runner and sending the exit basket…'
    try {
      const result = await postJson('/api/straddle-squareoff/submit', { preview_id: preview.preview_id, confirmation: $(ids.input).value })
      straddleSquareoffPreviews[runner] = null
      $(ids.review).hidden = true
      $(ids.status).textContent = result.message
      await (runner === 'sensex' ? refreshStraddle() : refreshNiftyStraddle())
    } catch (error) {
      $(ids.status).className = 'handoff-status error'
      $(ids.status).textContent = error.message
    }
  }

  const riskPolicyInputs = () => {
    const values = {
      planningCapital: Number($('planning-capital').value),
      dailyLossLimit: Number($('daily-loss-limit').value),
      ideaRiskLimit: Number($('idea-risk-limit').value),
      riskReserve: Number($('risk-reserve').value),
      maxPositions: Number($('max-positions').value),
      minimumRewardToRisk: Number($('minimum-rr').value),
      enforceRiskControls: $('enforce-risk-controls').checked,
      stopBasis: $('stop-basis').value,
      orderType: $('order-type').value,
    }
    const preview = riskPolicyPreview(values)
    if (!preview.valid) throw new Error(preview.errors[0])
    return { ...values, preview }
  }
  const renderPolicyImpact = () => {
    const values = {
      planningCapital: Number($('planning-capital').value), dailyLossLimit: Number($('daily-loss-limit').value),
      ideaRiskLimit: Number($('idea-risk-limit').value), riskReserve: Number($('risk-reserve').value),
      maxPositions: Number($('max-positions').value), minimumRewardToRisk: Number($('minimum-rr').value),
      enforceRiskControls: $('enforce-risk-controls').checked,
      stopBasis: $('stop-basis').value, orderType: $('order-type').value,
    }
    const preview = riskPolicyPreview(values)
    $('policy-impact').innerHTML = [
      ['Capital sizing', values.enforceRiskControls ? money(preview.availableNewIdeaRisk) : 'User-controlled'],
      ['Capital cap / position', values.enforceRiskControls ? money(preview.perPositionCapitalCap) : 'Not applied'],
      ['Concurrent slots', values.enforceRiskControls && Number.isFinite(preview.positionSlots) ? String(preview.positionSlots) : 'Not applied'],
      ['Minimum R:R', values.minimumRewardToRisk > 0 ? `1:${values.minimumRewardToRisk}` : 'Not applied'],
    ].map(([label, value]) => `<div><b>${escapeHtml(value)}</b><small>${escapeHtml(label)}</small></div>`).join('')
    $('policy-validation').className = `handoff-status${preview.valid ? '' : ' error'}`
    $('policy-validation').textContent = preview.valid
      ? `${preview.orderType === 'LIMIT' ? 'Limit orders are eligible for final preflight.' : 'Market preference is preview-only; live submission will be blocked.'} Capital controls are ${values.enforceRiskControls ? 'enabled' : 'not applied'}. Stops use ${preview.stopBasis === 'price' ? 'exact prices' : 'percent distance from entry or spot'}.`
      : preview.errors.join(' ')
  }
  const renderCandidates = () => {
    const candidates = candidateCollection?.candidates || []
    $('candidate-list').innerHTML = candidates.length ? candidates.map(candidate => {
      const derived = candidate.derived_invalidation || {}
      const derivedReady = derived.status === 'READY' && Number(derived.price) > 0
      const detail = candidate.kind === 'stock'
        ? `${candidate.parent_sector} · ${percent(candidate.market_change_pct)} · ${money(candidate.price)}`
        : `Sector rank ${candidate.rank ? `#${candidate.rank}` : '—'} · score ${number(candidate.overall_score)}`
      const stopCopy = derivedReady
        ? `Auto · ${escapeHtml(derived.basis || 'completed-candle structure')}`
        : `Blocked · ${escapeHtml(derived.reason || 'no completed-candle structural stop')}`
      const suggestedQuantity = Number(candidate.allocation?.suggested_quantity)
      const allocationCopy = Number.isInteger(suggestedQuantity) && suggestedQuantity > 0
        ? `Funds-weighted suggestion: ${suggestedQuantity} ${candidate.kind === 'stock' ? 'shares' : 'lots'} · ₹${number(candidate.allocation.estimated_notional)}`
        : candidate.allocation?.reason || 'Quantity is set when you rank selected candidates by FYERS funds.'
      return `<div class="candidate-card ${candidate.direction.toLowerCase()}"><input class="candidate-select" aria-label="Select ${escapeHtml(candidate.name)}" type="checkbox" value="${escapeHtml(candidate.key)}" ${derivedReady ? '' : 'disabled'}><span><b>${escapeHtml(candidate.name)}</b><small>${escapeHtml(candidate.kind.toUpperCase())} · ${escapeHtml(candidate.mtf_alignment)}</small><small>${escapeHtml(detail)} · ${escapeHtml(qualityText(candidate.data_quality))}</small><small>${escapeHtml(allocationCopy)}</small></span><label class="field">Stop / thesis invalidation<input class="candidate-invalidation" data-candidate-key="${escapeHtml(candidate.key)}" data-derived="${derivedReady ? 'true' : 'false'}" type="number" min="0.01" step="0.05" ${derivedReady ? `value="${escapeHtml(derived.price)}"` : 'disabled placeholder="Unavailable"'}><small>${stopCopy}</small></label></div>`
    }).join('') : '<div class="empty">No sectors or scanned stocks currently meet exact full alignment.</div>'
    document.querySelectorAll('.candidate-select').forEach(input => {
      input.addEventListener('change', () => {
        const selected = [...document.querySelectorAll('.candidate-select:checked')].map(item => item.value)
        document.querySelectorAll('.opportunity-card').forEach(card => { card.hidden = !selected.includes(card.dataset.candidateKey) })
        $('candidate-batch-actions').hidden = selected.length === 0 || selectedInstrumentRoute() !== 'cash_equity'
        $('candidate-status').textContent = `${selected.length} recommendation(s) selected. A batch preview revalidates all of them together before any confirmation is possible.`
        $('analysis-panel').hidden = false
      })
    })
    document.querySelectorAll('.candidate-invalidation').forEach(input => { input.readOnly = true })
  }
  const policyPayload = policy => ({
    planning_capital: policy.planningCapital, daily_loss_limit: policy.dailyLossLimit,
    idea_risk_limit: policy.ideaRiskLimit, risk_reserve: policy.riskReserve,
    max_simultaneous_positions: policy.maxPositions, minimum_reward_to_risk: policy.minimumRewardToRisk,
    enforce_risk_controls: policy.enforceRiskControls,
    enforce_minimum_reward_to_risk: policy.minimumRewardToRisk > 0,
    stop_basis: policy.stopBasis, order_type: policy.orderType,
  })
  const selectedInstrumentRoute = () => document.querySelector('input[name="instrument-route"]:checked')?.value || ''
  const rankCandidatesForSelection = async () => {
    if (!candidateCollection || !analysisRun) throw new Error('Collect fresh candidates before ranking them.')
    const account = await fetchJson('/api/account')
    if (!account?.connected || !Number.isFinite(Number(account.available_funds))) throw new Error(account?.error || 'FYERS available funds are unavailable for ranking.')
    const availableFunds = Number(account.available_funds)
    const byKey = new Map((analysisRun.cards || []).map(card => [card.candidate_key, card]))
    const route = selectedInstrumentRoute()
    const ranked = [...candidateCollection.candidates].sort((left, right) => {
      const meta = candidate => {
        const card = byKey.get(candidate.key)
        const conviction = Number(card?.analysis?.conviction?.score || 0)
        const proposal = card?.analysis?.proposal
        const required = route === 'stock_options'
          ? Number(proposal?.minimum_cash_required || proposal?.max_loss_per_lot || Infinity)
          : Number(candidate.price || Infinity)
        return { conviction, required, affordable: Number.isFinite(required) && required <= availableFunds }
      }
      const a = meta(left); const b = meta(right)
      return Number(b.affordable) - Number(a.affordable) || b.conviction - a.conviction || a.required - b.required || String(left.name).localeCompare(String(right.name))
    })
    if (route === 'cash_equity') {
      let remaining = availableFunds
      const fundable = ranked.filter(candidate => Number(candidate.price) > 0 && candidate.derived_invalidation?.status === 'READY')
      // Give each ranked candidate one share first, then distribute the rest
      // by conviction. This uses actual available funds, not a risk-cap proxy.
      for (const candidate of fundable) {
        const price = Number(candidate.price)
        candidate.allocation = remaining >= price
          ? { suggested_quantity: 1, estimated_notional: price, conviction_weight: Number(byKey.get(candidate.key)?.analysis?.conviction?.score || 1) }
          : { suggested_quantity: 0, estimated_notional: 0, reason: 'No available FYERS funds remain after higher-conviction allocations.' }
        if (candidate.allocation.suggested_quantity) remaining -= price
      }
      const allocated = fundable.filter(candidate => candidate.allocation?.suggested_quantity > 0)
      const totalWeight = allocated.reduce((sum, candidate) => sum + Math.max(1, Number(candidate.allocation.conviction_weight || 1)), 0)
      for (const candidate of allocated) {
        const price = Number(candidate.price)
        const weight = Math.max(1, Number(candidate.allocation.conviction_weight || 1))
        const additional = Math.floor((remaining * weight / totalWeight) / price)
        if (additional > 0) {
          candidate.allocation.suggested_quantity += additional
          candidate.allocation.estimated_notional += additional * price
          remaining -= additional * price
        }
      }
    }
    candidateCollection.candidates = ranked
    renderCandidates()
    document.querySelectorAll('.candidate-select:not(:disabled)').forEach(input => {
      const candidate = ranked.find(item => item.key === input.value)
      input.checked = route !== 'cash_equity' || Number(candidate?.allocation?.suggested_quantity) > 0
    })
    document.querySelector('.candidate-select:not(:disabled)')?.dispatchEvent(new Event('change'))
    const top = ranked.filter(candidate => candidate.derived_invalidation?.status === 'READY').slice(0, 3).map((candidate, index) => {
      const card = byKey.get(candidate.key); const score = card?.analysis?.conviction?.score ?? 0
      return `#${index + 1} ${candidate.name} (conviction ${score})`
    })
    const allocatedTotal = route === 'cash_equity' ? ranked.reduce((sum, candidate) => sum + Number(candidate.allocation?.estimated_notional || 0), 0) : 0
    $('candidate-status').textContent = `Ranked using fresh FYERS available funds of ${money(availableFunds)} and conviction. Take first: ${top.join(' · ')}. ${route === 'cash_equity' ? `Suggested allocation totals ${money(allocatedTotal)} and remains editable.` : 'Each validated spread starts at one editable lot.'} All selections still require their own fresh ticket preview.`
  }
  const selectedCashProduct = () => document.querySelector('input[name="cash-product"]:checked')?.value || 'INTRADAY'
  const selectedCashExitPlan = () => document.querySelector('input[name="cash-exit-plan"]:checked')?.value || 'FIXED_TARGET'
  const instrumentRouteLabel = route => route === 'stock_options' ? 'Stock options' : 'Cash equity'
  const resetInstrumentRouteResults = () => {
    const route = selectedInstrumentRoute()
    $('cash-product-choice').hidden = route !== 'cash_equity'
    candidateCollection = null; analysisRun = null; handoffPacket = null; ticketProposals = []
    $('candidate-list').innerHTML = ''
    $('candidate-batch-actions').hidden = true; $('handoff-batch-panel').hidden = true; handoffBatchPreview = null
    $('analysis-panel').hidden = true; $('packet-panel').hidden = true; $('ticket-panel').hidden = true
    $('candidate-status').className = 'handoff-status'
    $('candidate-status').textContent = `${instrumentRouteLabel(route)} selected. Collect fresh completed-candle matches.`
    $('collect-candidates').textContent = `Collect ${route === 'stock_options' ? 'stock option' : 'cash equity'} matches`
    invalidateTicketPreview('Instrument route changed. Any prior proposal or ticket preview was cleared.')
  }
  const invalidateTicketPreview = message => {
    ticketPreview = null
    $('ticket-review').hidden = true
    $('ticket-confirmation').value = ''
    $('submit-ticket').disabled = true
    if (message) { $('ticket-status').className = 'handoff-status'; $('ticket-status').textContent = message }
  }
  const invalidationRows = card => {
    const choices = card.analysis.invalidation_choices || {}
    const recommended = card.analysis.recommended_invalidation || { method: 'structure' }
    return ['structure', 'percent', 'atr', 'custom'].map(method => {
      const choice = choices[method] || {}
      const value = method === 'structure' ? choice.suggested_price : method === 'percent' || method === 'atr' ? choice.default_value : ''
      const suffix = method === 'atr' ? ` · ATR ${number(choice.atr)}` : method === 'structure' ? ` · ₹${number(choice.suggested_price)}` : ''
      return `<label class="invalidation-option"><input type="radio" name="stop-${escapeHtml(card.card_id)}" value="${method}" ${method === recommended.method ? 'checked' : ''}><span>${escapeHtml(choice.label || method)}${escapeHtml(suffix)}${method === recommended.method ? ' · proposed' : ''}</span>${method === 'structure' ? '<span></span>' : `<input type="number" data-stop-value="${method}" min="0.01" step="0.05" value="${escapeHtml(value)}" placeholder="${method === 'custom' ? 'Price' : 'Value'}">`}</label>`
    }).join('')
  }
  const renderAnalysisCards = () => {
    if (!analysisRun) return
    $('analysis-panel').hidden = false
    $('ai-review-state').textContent = analysisRun.ai_review?.message || 'External AI review is unavailable; local evidence proposals are shown.'
    $('analysis-board').innerHTML = (analysisRun.cards || []).map(card => {
      const a = card.analysis; const c = card.candidate; const p = a.proposal; const proposed = a.proposed_sizing || p?.sizing || {}
      const legs = p?.legs?.length ? `<table class="leg-table"><thead><tr><th>Action</th><th>Contract</th><th>Strike</th><th>Bid / ask</th><th>OI · volume</th><th>Lot · tick</th><th>Delta · IV</th></tr></thead><tbody>${p.legs.map(leg => `<tr><td>${escapeHtml(leg.action)}</td><td>${escapeHtml(leg.symbol)}</td><td>${number(leg.strike)}</td><td>${number(leg.bid)} / ${number(leg.ask)}</td><td>${number(leg.open_interest)} · ${number(leg.volume)}</td><td>${number(leg.lot_size)} · ${number(leg.tick_size)}</td><td>${number(leg.greeks?.delta)} · ${number(leg.greeks?.iv)}</td></tr>`).join('')}</tbody></table>` : ''
      const optionGate = p ? '<p class="proposal-copy"><b>Option gates passed:</b> exact FYERS contract and expiry, master lot/tick, two-sided quote, spread, OI, volume, complete Greeks and defined maximum loss.</p>' : ''
      const target = p ? p.target_exit_points : proposed.target || a.target
      const quantity = p ? `${proposed.lots || '—'} lot · ${proposed.quantity || '—'}` : proposed.quantity || '—'
      const maxLoss = p ? proposed.estimated_max_loss || p.max_loss_per_lot : proposed.estimated_max_loss
      const entry = p ? `${p.entry_points} pts ${p.structure}` : money(a.entry)
      return `<article class="opportunity-card ${String(c.direction).toLowerCase()}" data-card-id="${escapeHtml(card.card_id)}"><div class="opportunity-head"><div><span class="label">${escapeHtml(p ? 'STOCK OPTIONS' : 'CASH EQUITY')} · ${escapeHtml(c.direction)}</span><h3>${escapeHtml(c.name)}</h3><small>${escapeHtml(a.thesis || p?.scenario || '')}</small></div><span class="conviction">${escapeHtml(a.conviction?.rating || 'Low')} conviction</span></div><p class="proposal-copy"><b>Why:</b> ${escapeHtml(a.conviction?.rationale || 'Insufficient evidence')} ${escapeHtml(a.conviction?.advisory || '')}</p><div class="decision-metrics"><div><b>${escapeHtml(entry)}</b><small>Entry / trigger</small></div><div><b>${a.recommended_invalidation?.price ? money(a.recommended_invalidation.price) : '—'}</b><small>Proposed stop</small></div><div><b>${target != null ? number(target) : '—'}</b><small>Target / exit</small></div><div><b>1:${number(p?.reward_to_risk || a.reward_to_risk)}</b><small>Reward:risk</small></div><div><b>${escapeHtml(quantity)}</b><small>${p ? 'Lots · quantity' : 'Shares'}</small></div><div><b>${money(maxLoss)}</b><small>Max loss</small></div><div><b>${p ? escapeHtml(p.expiry || '—') : money(proposed.estimated_notional)}</b><small>${p ? 'Expiry' : 'Cash notional'}</small></div><div><b>${p ? escapeHtml(p.label) : escapeHtml(a.market_status || 'WATCH')}</b><small>Plan</small></div></div>${legs}${optionGate}<p class="proposal-copy"><b>Proposed invalidation:</b> ${escapeHtml(a.recommended_invalidation?.rationale || '')}</p><div class="invalidation-picker">${invalidationRows(card)}</div><div class="proposal-actions"><button type="button" class="button accept-analysis">Accept / recompute</button><button type="button" class="button secondary reject-analysis">Reject</button><button type="button" class="button prepare-analysis-ticket" disabled>Prepare FYERS order</button></div><div class="handoff-status card-status">Proposal not accepted. Sizing shown is advisory and has no order authority.</div></article>`
    }).join('') || '<div class="empty">No fresh opportunity passed the alignment and evidence gates.</div>'
    const optionExclusions = (analysisRun.exclusions || []).filter(item => item.kind === 'OPTIONS')
    const optionDecision = optionExclusions.length ? `<div class="ticket-warning"><b>No option strategy recommended</b><br>${optionExclusions.map(item => `${escapeHtml(item.name || 'Option candidate')}: ${escapeHtml(item.reason)}`).join('<br>')}</div>` : ''
    $('analysis-exclusions').innerHTML = optionDecision + (analysisRun.exclusions?.length ? `<details ${optionExclusions.length ? 'open' : ''}><summary>${analysisRun.exclusions.length} excluded or deferred opportunities</summary>${analysisRun.exclusions.map(item => `<p>${escapeHtml(item.name || item.kind || 'Opportunity')}: ${escapeHtml(item.reason)}</p>`).join('')}</details>` : '')
    document.querySelectorAll('.opportunity-card').forEach(element => {
      const card = analysisRun.cards.find(item => item.card_id === element.dataset.cardId)
      element.dataset.candidateKey = card.candidate.key
      element.hidden = true
      const evidence = card.analysis.evidence || {}
      const dailyAdx = evidence.daily?.adx
      const relativeStrength = card.analysis.conviction?.rationale?.match(/relative strength[^;]*/i)?.[0] || 'relative strength is included in the evidence grade'
      const stop = card.analysis.recommended_invalidation?.price
      const target = card.analysis.proposal?.target_exit_points ?? card.analysis.proposed_sizing?.target ?? card.analysis.target
      const rr = card.analysis.proposal?.reward_to_risk ?? card.analysis.reward_to_risk
      const why = element.querySelector('.proposal-copy')
      why.innerHTML = `<b>Why ${escapeHtml(String(card.analysis.conviction?.rating || 'this').toLowerCase())} conviction?</b> ${escapeHtml(card.candidate.mtf_alignment)} across completed 15m, 1H, Daily and Weekly candles; ${dailyAdx != null ? `Daily ADX ${number(dailyAdx)}; ` : ''}${escapeHtml(relativeStrength)}; data quality ${escapeHtml(qualityText(card.candidate.data_quality))}; structural stop ${stop != null ? money(stop) : 'unavailable'}, target ${target != null ? number(target) : 'unavailable'}, reward:risk ${rr != null ? `1:${number(rr)}` : 'unavailable'}. This is a rule-based evidence grade, not a profit guarantee.`
      if (!card.analysis.proposal) {
        const plannedQuantity = Number(card.analysis.proposed_sizing?.quantity || card.analysis.quantity || 0)
        const plannedEntry = Number(card.analysis.entry)
        const plannedTarget = Number(target)
        const tentativeProfit = plannedQuantity > 0 && Number.isFinite(plannedEntry) && Number.isFinite(plannedTarget) ? Math.abs(plannedTarget - plannedEntry) * plannedQuantity : null
        const maxLossMetric = [...element.querySelectorAll('.decision-metrics small')].find(item => item.textContent === 'Max loss')?.parentElement
        maxLossMetric?.insertAdjacentHTML('afterend', `<div><b>${money(tentativeProfit)}</b><small>Tentative profit at target</small></div>`)
        why.insertAdjacentHTML('beforeend', `<br><b>Cash products for ${escapeHtml(card.candidate.name)}:</b> Intraday / Delivery eligibility unavailable from the FYERS cash master; the selected product needs exact final broker validation. No support is assumed.<br><small>Tentative profit is gross, conditional on reaching the target, excludes unmodelled charges/slippage, and is not guaranteed.</small>`)
        if (selectedCashExitPlan() === 'PARTIAL_TARGET_SUPERTREND_7_2') {
          const targetQuantity = Math.floor(plannedQuantity * 0.5)
          const runnerQuantity = plannedQuantity - targetQuantity
          why.insertAdjacentHTML('beforeend', `<br><b>50% target + Supertrend 7,2 trail:</b> Keep the structural stop active until ${targetQuantity} share(s) exit at the target and that partial fill is confirmed. Then evaluate Supertrend 7,2 on completed candles only for the remaining ${runnerQuantity} share(s), exiting on a confirmed ${card.candidate.direction === 'BULLISH' ? 'bearish' : 'bullish'} flip. Partial fills, gaps and slippage can increase risk. Live exit execution is not implemented.`)
          if (targetQuantity < 1 || runnerQuantity < 1) { element.querySelector('.accept-analysis').disabled = true; element.querySelector('.accept-analysis').textContent = 'Partial exit unavailable'; why.insertAdjacentHTML('beforeend', '<br><b>Blocked:</b> at least two whole shares are required.') }
        }
      }
      element.querySelector('.invalidation-picker').hidden = true
      element.querySelector('.invalidation-picker').style.display = 'none'
      element.querySelector('.reject-analysis').hidden = true
      element.querySelector('.prepare-analysis-ticket').hidden = true
      element.querySelector('.accept-analysis').textContent = 'Place order'
      element.querySelectorAll('input').forEach(input => input.addEventListener('change', () => {
        invalidateTicketPreview('Stop inputs changed. Any earlier ticket preview and confirmation were invalidated.')
        element.querySelector('.prepare-analysis-ticket').disabled = true
        element.querySelector('.card-status').textContent = 'Edited proposal requires fresh FYERS recomputation.'
      }))
      element.querySelector('.reject-analysis').addEventListener('click', () => {
        element.classList.add('rejected'); element.querySelectorAll('button,input').forEach(control => { control.disabled = true })
        element.querySelector('.card-status').textContent = 'Rejected locally. No broker action occurred.'
        invalidateTicketPreview('Proposal rejected. No broker action occurred.')
      })
      element.querySelector('.accept-analysis').addEventListener('click', () => acceptAnalysisCard(card, element))
      element.querySelector('.prepare-analysis-ticket').addEventListener('click', () => prepareAnalysisTicket(card, element))
    })
    $('ai-review-state').textContent = 'Select one candidate above to see its automatically populated plan.'
  }
  const acceptAnalysisCard = async (card, element) => {
    const method = element.querySelector(`input[name="stop-${CSS.escape(card.card_id)}"]:checked`)?.value
    const value = element.querySelector(`[data-stop-value="${method}"]`)?.value
    const button = element.querySelector('.accept-analysis'); const status = element.querySelector('.card-status')
    try {
      button.disabled = true; status.textContent = 'Refreshing FYERS quote, tick and dependent risk values…'
      const policy = riskPolicyInputs()
      const result = await postJson('/api/analysis-handoff/size', { analysis_id: analysisRun.analysis_id, card_id: card.card_id, selection: { method, value: value === '' || value == null ? null : Number(value) }, risk_policy: policyPayload(policy) })
      card.analysis.active_invalidation = result.active_invalidation
      if (card.analysis.proposal) card.analysis.proposal.sizing = { status: 'SIZED', lots: result.active_invalidation.lots, quantity: result.active_invalidation.quantity, estimated_max_loss: result.active_invalidation.estimated_max_loss, underlying_invalidation: result.active_invalidation.price }
      status.textContent = `Accepted · fresh ₹${number(result.fresh_quote.price)} · stop ₹${number(result.active_invalidation.price)} · target ${number(result.active_invalidation.target)} · size ${result.active_invalidation.quantity}. Ticket confirmation remains empty.`
      element.querySelector('.prepare-analysis-ticket').disabled = false
      invalidateTicketPreview('Accepted values are fresh; prepare a separate exact FYERS preview to continue.')
      prepareAnalysisTicket(card, element)
      await prepareTicket()
    } catch (error) { status.className = 'handoff-status card-status error'; status.textContent = error.message }
    finally { button.disabled = false; button.textContent = 'Place order' }
  }
  const prepareAnalysisTicket = (card, element) => {
    if (!card.analysis.active_invalidation) return
    const proposal = card.analysis.proposal || {
      kind: 'EQUITY', label: `Equity ${card.candidate.direction === 'BULLISH' ? 'long' : 'short'} limit`,
      direction: card.candidate.direction, quantity: card.analysis.active_invalidation.quantity,
      entry: card.analysis.active_invalidation.entry, target: card.analysis.active_invalidation.target,
      exit_plan_mode: selectedCashExitPlan(),
    }
    const ticket = { candidate: { ...card.candidate, risk_input: { invalidation: card.analysis.active_invalidation.price } }, options: { expiry: proposal.expiry, expiry_iso: proposal.expiry_iso }, proposal }
    const ticketKey = `${ticket.candidate.symbol}|${ticket.proposal.label}|${ticket.options.expiry_iso || ''}`
    let index = ticketProposals.findIndex(item => `${item.candidate.symbol}|${item.proposal.label}|${item.options.expiry_iso || ''}` === ticketKey)
    if (index < 0) index = ticketProposals.push(ticket) - 1
    else ticketProposals[index] = ticket
    $('ticket-proposal').innerHTML = '<option value="">Choose a packet proposal</option>' + ticketProposals.map((item, itemIndex) => `<option value="${itemIndex}">${escapeHtml(item.candidate.name)} · ${escapeHtml(item.proposal.label)}</option>`).join('')
    $('ticket-proposal').value = String(index); $('ticket-lots').value = String(card.analysis.active_invalidation.lots || 1)
    $('ticket-panel').hidden = false; invalidateTicketPreview('Proposal loaded. Refresh FYERS to create the exact ticket preview.')
    $('ticket-panel').scrollIntoView({ behavior: scrollBehavior, block: 'start' })
  }
  const collectCandidates = async () => {
    const button = $('collect-candidates')
    button.disabled = true; button.textContent = 'Scanning completed bars…'
    $('candidate-status').className = 'handoff-status'; $('candidate-status').textContent = 'Scanning fully aligned sectors and their direction-matching official-weight contributors.'
    try {
      const recipient = document.querySelector('input[name="recipient"]:checked')?.value
      if (!recipient) throw new Error('Choose ChatGPT or Codex before collecting AI analysis.')
      const instrumentRoute = selectedInstrumentRoute()
      if (!instrumentRoute) throw new Error('Choose Cash equity or Stock options before collecting matches.')
      const policy = riskPolicyInputs()
      analysisRun = await postJson('/api/analysis-handoff/analyze', { mode, recipient, instrument_route: instrumentRoute, risk_policy: policyPayload(policy) })
      candidateCollection = { candidates: analysisRun.candidates || [], scope: analysisRun.scope, updated_at: analysisRun.source?.analysis_updated_at }
      renderCandidates()
      renderAnalysisCards()
      const stocks = candidateCollection.candidates.filter(item => item.kind === 'stock').length
      const autoStops = candidateCollection.candidates.filter(item => item.derived_invalidation?.status === 'READY').length
      $('candidate-status').textContent = `${instrumentRouteLabel(instrumentRoute)} · ${stocks} fully aligned stocks · ${autoStops} completed-candle stops populated · ${analysisRun.cards.length} route-specific proposals. ${analysisRun.ai_review.message}`
    } catch (error) {
      candidateCollection = null
      $('candidate-list').innerHTML = ''
      $('candidate-status').className = 'handoff-status error'; $('candidate-status').textContent = error.message
    } finally {
      const route = selectedInstrumentRoute()
      button.disabled = false
      button.textContent = `Collect ${route === 'stock_options' ? 'stock option' : 'cash equity'} matches`
    }
  }
  const selectedCandidatePayload = () => {
    if (!candidateCollection) throw new Error('Collect the current full-alignment candidates first.')
    const policy = riskPolicyInputs()
    const selected = [...document.querySelectorAll('.candidate-select:checked')].map(input => input.value)
    if (!selected.length) throw new Error('Select at least one candidate.')
    const riskInputs = {}
    for (const key of selected) {
      const invalidation = document.querySelector(`.candidate-invalidation[data-candidate-key="${CSS.escape(key)}"]`)?.value
      riskInputs[key] = {
        planning_capital: policy.planningCapital,
        max_loss_value: policy.ideaRiskLimit,
        max_loss_unit: 'rupees',
        invalidation: invalidation ? Number(invalidation) : null,
        stop_basis: 'price',
        daily_loss_limit: policy.dailyLossLimit,
        protected_daily_buffer: policy.riskReserve,
        max_simultaneous_positions: policy.maxPositions,
        minimum_reward_to_risk: policy.minimumRewardToRisk,
        enforce_risk_controls: policy.enforceRiskControls,
        enforce_minimum_reward_to_risk: policy.minimumRewardToRisk > 0,
        order_type: policy.orderType,
      }
    }
    return { selected, riskInputs, policy }
  }
  const prepareHandoffBatch = async () => {
    const button = $('prepare-handoff-batch')
    try {
      if (selectedInstrumentRoute() !== 'cash_equity') throw new Error('Multi-symbol submission is currently available for cash-equity recommendations only.')
      const { selected, riskInputs, policy } = selectedCandidatePayload()
      const cards = selected.map(key => analysisRun?.cards?.find(card => card.candidate_key === key)).filter(Boolean)
      if (cards.length !== selected.length) throw new Error('Refresh the recommendations before preparing the batch.')
      button.disabled = true; button.textContent = 'Refreshing FYERS batch preflight…'
      $('handoff-batch-status').className = 'handoff-status'
      $('handoff-batch-status').textContent = 'Refreshing every symbol, quote, stop, funds, positions, orders and aggregate risk. Any failed item blocks the full batch.'
      const external = $('handoff-batch-external-risk').value
      const items = cards.map(card => {
        const candidate = card.candidate; const plan = card.analysis
        const invalidation = Number(riskInputs[candidate.key]?.invalidation)
        return {
          broker: 'fyers', underlying: candidate.symbol,
          proposal: { kind: 'EQUITY', label: `Analysis Handoff ${candidate.direction === 'BULLISH' ? 'long' : 'short'} limit`, direction: candidate.direction, quantity: 1, entry: plan.entry, target: plan.target },
          invalidation, quantity: 1, cash_product: selectedCashProduct(),
          daily_loss_limit: policy.dailyLossLimit, idea_risk_limit: policy.ideaRiskLimit, risk_reserve: policy.riskReserve,
          max_simultaneous_positions: policy.maxPositions, minimum_reward_to_risk: policy.minimumRewardToRisk,
          enforce_risk_controls: policy.enforceRiskControls, enforce_minimum_reward_to_risk: policy.minimumRewardToRisk > 0, order_type: policy.orderType,
          external_open_risk: external === '' ? null : Number(external), require_market_open: true,
        }
      })
      const preview = await postJson('/api/trade-ticket/prepare-batch', { items })
      handoffBatchPreview = preview
      $('handoff-batch-preview').textContent = JSON.stringify(preview, null, 2)
      $('handoff-batch-panel').hidden = false; $('handoff-batch-review').hidden = false
      $('handoff-batch-confirmation').value = ''; $('submit-handoff-batch').disabled = true
      $('handoff-batch-status').textContent = `Batch preview ${preview.preview_id}: ${preview.aggregate.order_count} orders · ${money(preview.aggregate.total_worst_case_risk)} total risk. Review every item, then enter the exact phrase to enable Submit all selected.`
      $('handoff-batch-panel').scrollIntoView({ behavior: scrollBehavior, block: 'start' })
    } catch (error) { $('handoff-batch-status').className = 'handoff-status error'; $('handoff-batch-status').textContent = error.message }
    finally { button.disabled = false; button.textContent = 'Prepare selected FYERS batch' }
  }
  const submitHandoffBatch = async () => {
    if (!handoffBatchPreview) return
    const button = $('submit-handoff-batch'); button.disabled = true
    try {
      const result = await postJson('/api/trade-ticket/submit-batch', { preview_id: handoffBatchPreview.preview_id, confirmation: $('handoff-batch-confirmation').value })
      $('handoff-batch-preview').textContent = JSON.stringify(result, null, 2)
      $('handoff-batch-status').textContent = `${result.status}: ${result.message}`
      handoffBatchPreview = null
    } catch (error) { $('handoff-batch-status').className = 'handoff-status error'; $('handoff-batch-status').textContent = error.message }
  }
  const renderPacket = packet => {
    handoffPacket = packet
    $('packet-panel').hidden = false
    $('packet-preview').textContent = JSON.stringify(packet, null, 2)
    $('download-packet').hidden = packet.requested_action !== 'export'
    ticketProposals = packet.candidates.flatMap(candidate => (candidate.options?.proposals || []).map(proposal => ({ candidate, options: candidate.options, proposal })))
    $('ticket-proposal').innerHTML = '<option value="">Choose a packet proposal</option>' + ticketProposals.map((item, index) => `<option value="${index}">${escapeHtml(item.candidate.name)} · ${escapeHtml(item.proposal.label)} · R:R 1:${escapeHtml(item.proposal.reward_to_risk)} · ${escapeHtml(item.options.expiry || 'expiry unavailable')}</option>`).join('')
    $('ticket-panel').hidden = !ticketProposals.length
    $('packet-panel').scrollIntoView({ behavior: scrollBehavior, block: 'start' })
  }
  const preparePacket = async () => {
    const recipient = document.querySelector('input[name="recipient"]:checked')?.value
    const action = document.querySelector('input[name="handoff-action"]:checked')?.value
    const button = $('prepare-packet')
    try {
      if (!recipient) throw new Error('Choose ChatGPT or Codex as the packet recipient.')
      if (!action) throw new Error('Choose local preview or local export.')
      const { selected, riskInputs, policy } = selectedCandidatePayload()
      const includeFunds = $('include-funds').checked
      if (includeFunds && !$('confirm-funds').checked) throw new Error('Confirm current funds inclusion before preparing the packet.')
      button.disabled = true; button.textContent = 'Refreshing evidence…'
      $('packet-status').className = 'handoff-status'; $('packet-status').textContent = 'Rechecking alignment and current option-chain evidence. No data is being sent to the selected recipient.'
      const packet = await postJson('/api/analysis-handoff/preview', {
        mode, recipient, action, instrument_route: selectedInstrumentRoute(), candidate_keys: selected, risk_inputs: riskInputs,
        risk_policy: {
          planning_capital: policy.planningCapital,
          daily_loss_limit: policy.dailyLossLimit,
          idea_risk_limit: policy.ideaRiskLimit,
          risk_reserve: policy.riskReserve,
          max_simultaneous_positions: policy.maxPositions,
          minimum_reward_to_risk: policy.minimumRewardToRisk,
          enforce_risk_controls: policy.enforceRiskControls,
          enforce_minimum_reward_to_risk: policy.minimumRewardToRisk > 0,
          stop_basis: policy.stopBasis,
          order_type: policy.orderType,
        },
        include_funds: includeFunds, funds_confirmed: includeFunds && $('confirm-funds').checked,
      })
      renderPacket(packet)
      $('packet-status').textContent = `Local ${action} ready · ${packet.candidates.length} candidates · transmitted: no.`
    } catch (error) {
      $('packet-status').className = 'handoff-status error'; $('packet-status').textContent = error.message
    } finally { button.disabled = false; button.textContent = 'Prepare local preview' }
  }
  const copyPacket = async () => {
    if (!handoffPacket) return
    try { await navigator.clipboard.writeText(JSON.stringify(handoffPacket, null, 2)); $('packet-status').textContent = 'Packet copied locally. Nothing was transmitted.' }
    catch { $('packet-status').className = 'handoff-status error'; $('packet-status').textContent = 'Clipboard access was unavailable; use Download JSON instead.' }
  }
  const downloadPacket = () => {
    if (!handoffPacket) return
    const blob = new Blob([JSON.stringify(handoffPacket, null, 2)], { type: 'application/json' })
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `sector-pulse-${handoffPacket.recipient}-${new Date().toISOString().replaceAll(':', '-')}.json`; link.click(); URL.revokeObjectURL(link.href)
    $('packet-status').textContent = 'Packet downloaded locally. Nothing was transmitted.'
  }
  const refreshTicketCapabilities = async () => {
    try {
      ticketCapabilities = await fetchJson('/api/trade-ticket/capabilities')
      $('ticket-capability').textContent = ticketCapabilities.live_submission_enabled ? 'FYERS live path enabled · confirmation required' : ticketCapabilities.fyers_configured ? 'FYERS preview ready · live path disabled' : 'FYERS setup required'
    } catch (error) { $('ticket-capability').textContent = error.message }
  }
  const selectedTicketProposal = () => {
    const index = Number($('ticket-proposal').value)
    return Number.isInteger(index) && ticketProposals[index] ? ticketProposals[index] : null
  }
  const renderTicketPreview = preview => {
    ticketPreview = preview
    $('ticket-review').hidden = false
    $('ticket-preview').textContent = JSON.stringify(preview, null, 2)
    const ledger = preview.daily_risk_ledger || {}
    $('risk-strip').innerHTML = [
      ['Daily limit', money(ledger.hard_daily_loss_limit)],
      ['Used risk', money((ledger.realized_loss || 0) + (ledger.app_open_worst_case_risk || 0) + (ledger.declared_external_open_risk || 0))],
      ['Protected buffer', money(ledger.protected_reserve)],
      ['After proposal', money(ledger.remaining_after_proposal)],
    ].map(([label, value]) => `<div><b>${escapeHtml(value)}</b><small>${escapeHtml(label)}</small></div>`).join('')
    $('ticket-confirmation').value = ''
    $('submit-ticket').disabled = true
    $('submit-ticket').textContent = preview.live_submission_enabled && preview.submission_eligible ? 'Place confirmed order' : preview.submission_eligible ? 'Live submission disabled in runtime' : 'Submission blocked by margin policy'
    $('ticket-review').scrollIntoView({ behavior: scrollBehavior, block: 'start' })
  }
  const prepareTicket = async () => {
    const selected = selectedTicketProposal()
    const button = $('prepare-ticket')
    try {
      if (!selected) throw new Error('Choose one defined-risk packet proposal.')
      const policy = riskPolicyInputs()
      const invalidation = selected.proposal.sizing?.underlying_invalidation ?? selected.candidate.risk_input?.invalidation
      if (!(Number(invalidation) > 0)) throw new Error('The selected candidate needs an explicit invalidation in the packet inputs.')
      const externalValue = $('external-open-risk').value
      button.disabled = true; button.textContent = 'Refreshing FYERS preflight…'
      $('ticket-status').className = 'handoff-status'; $('ticket-status').textContent = 'Refreshing FYERS profile, exact contracts, chain, quotes, lot/tick, funds, margin coverage, positions and orders.'
      const preview = await postJson('/api/trade-ticket/prepare', {
        broker: $('ticket-broker').value,
        underlying: selected.candidate.symbol,
        expiry: selected.options?.expiry_iso,
        proposal: selected.proposal,
        invalidation: Number(invalidation),
        lots: Number($('ticket-lots').value),
        quantity: selected.proposal.kind === 'EQUITY' ? Number(selected.proposal.quantity) : undefined,
        daily_loss_limit: policy.dailyLossLimit,
        idea_risk_limit: policy.ideaRiskLimit,
        risk_reserve: policy.riskReserve,
        max_simultaneous_positions: policy.maxPositions,
        minimum_reward_to_risk: policy.minimumRewardToRisk,
        enforce_risk_controls: policy.enforceRiskControls,
        enforce_minimum_reward_to_risk: policy.minimumRewardToRisk > 0,
        order_type: policy.orderType,
        external_open_risk: externalValue === '' ? null : Number(externalValue),
        cash_product: selectedInstrumentRoute() === 'cash_equity' ? selectedCashProduct() : undefined,
        exit_plan_mode: selectedInstrumentRoute() === 'cash_equity' ? selectedCashExitPlan() : undefined,
      })
      renderTicketPreview(preview)
      $('ticket-status').textContent = `Exact preview ${preview.preview_id} prepared. Review the refreshed ledger and every leg.`
    } catch (error) {
      $('ticket-status').className = 'handoff-status error'; $('ticket-status').textContent = error.message
    } finally { button.disabled = false; button.textContent = 'Refresh FYERS and prepare exact preview' }
  }
  const submitTicket = async () => {
    if (!ticketPreview) return
    const button = $('submit-ticket'); button.disabled = true; button.textContent = 'Refreshing once more…'
    try {
      const result = await postJson('/api/trade-ticket/submit', { preview_id: ticketPreview.preview_id, confirmation: $('ticket-confirmation').value })
      $('ticket-status').className = 'handoff-status'; $('ticket-status').textContent = `${result.status}: ${result.message}`
      $('ticket-preview').textContent = JSON.stringify(result, null, 2)
      ticketPreview = null
    } catch (error) {
      if (error.payload?.replacement_preview) {
        renderTicketPreview(error.payload.replacement_preview)
        $('ticket-status').className = 'handoff-status error'; $('ticket-status').textContent = 'Broker state changed. A replacement preview is shown; review it and type its new confirmation phrase.'
      } else {
        $('ticket-status').className = 'handoff-status error'; $('ticket-status').textContent = error.message
      }
    } finally { if (ticketPreview) button.textContent = ticketPreview.live_submission_enabled && ticketPreview.submission_eligible ? 'Place confirmed order' : ticketPreview.submission_eligible ? 'Live submission disabled in runtime' : 'Submission blocked by margin policy' }
  }
  const commaValues = id => $(id).value.split(',').map(value => value.trim()).filter(Boolean)
  const automationPayload = () => ({
    enabled: $('auto-enabled').checked, execution_mode: $('auto-mode').value,
    universe_mode: $('auto-universe').value, option_universe: 'INDEX_AND_STOCK_OPTIONS',
    allow_stock_options_for_aligned_equities: true,
    allowed_symbols: commaValues('auto-symbols'), allowed_segments: commaValues('auto-segments'),
    supported_index_underlyings: commaValues('auto-index-underlyings'),
    allowed_strategies: commaValues('auto-strategies'),
    completed_candle_conditions: $('auto-signals').value.split('\n').map(value => value.trim()).filter(Boolean),
    require_completed_candle: $('auto-completed').checked,
    required_alignment_values: ['FULL BULLISH ALIGNMENT', 'FULL BEARISH ALIGNMENT'],
    require_validated_contract: $('auto-option-evidence').checked, require_active_expiry: $('auto-option-evidence').checked,
    require_two_sided_liquidity: $('auto-option-evidence').checked, require_complete_greeks_oi_volume: $('auto-option-evidence').checked,
    require_valid_lot_tick: $('auto-option-evidence').checked, require_defined_maximum_loss: $('auto-option-evidence').checked,
    planning_capital: Number($('auto-planning-capital').value), max_daily_loss: Number($('auto-daily-loss').value),
    per_idea_risk: Number($('auto-idea-risk').value), risk_reserve: Number($('auto-risk-reserve').value),
    max_concurrent_positions: Number($('auto-max-positions').value), max_concurrent_orders: Number($('auto-max-orders').value),
    minimum_reward_to_risk: Number($('auto-min-rr').value), order_type: $('auto-order-type').value,
    max_limit_buffer_pct: Number($('auto-limit-buffer').value), max_bid_ask_spread_pct: Number($('auto-max-spread').value),
    trading_start: $('auto-start').value, trading_end: $('auto-end').value,
    min_dte: Number($('auto-min-dte').value), max_dte: Number($('auto-max-dte').value),
    require_stop_or_defined_risk: $('auto-risk-defined').checked, require_target: $('auto-target').checked,
    cooldown_minutes: Number($('auto-cooldown').value), stale_data_seconds: Number($('auto-stale').value),
    kill_switch_engaged: $('auto-kill').checked, halt_on_uncertain_status: $('auto-uncertain').checked,
  })
  const showSavedAutomationPolicy = state => {
    const profile = state?.profile
    if (!profile) return
    $('auto-mode').value = profile.execution_mode || 'PAPER'; $('auto-enabled').checked = !!profile.enabled; $('auto-kill').checked = profile.kill_switch_engaged !== false
    $('auto-universe').value = profile.universe_mode || 'ALIGNED_EQUITIES_AND_OPTIONS'
    $('auto-symbols').value = (profile.allowed_symbols || []).join(','); $('auto-index-underlyings').value = (profile.supported_index_underlyings || []).join(',')
    $('auto-segments').value = (profile.allowed_segments || []).join(','); $('auto-strategies').value = (profile.allowed_strategies || []).join(',')
    $('auto-signals').value = (profile.completed_candle_conditions || []).join('\n')
    $('auto-planning-capital').value = profile.planning_capital ?? 100000; $('auto-daily-loss').value = profile.max_daily_loss ?? 5000
    $('auto-idea-risk').value = profile.per_idea_risk ?? 2000; $('auto-risk-reserve').value = profile.risk_reserve ?? 1000
    $('auto-max-positions').value = profile.max_concurrent_positions ?? 3; $('auto-max-orders').value = profile.max_concurrent_orders ?? 2
    $('auto-min-rr').value = profile.minimum_reward_to_risk ?? 1; $('auto-limit-buffer').value = profile.max_limit_buffer_pct ?? 0.5
    $('auto-max-spread').value = profile.max_bid_ask_spread_pct ?? 8; $('auto-start').value = profile.trading_start || '09:30'; $('auto-end').value = profile.trading_end || '15:00'
    $('auto-min-dte').value = profile.min_dte ?? 1; $('auto-max-dte').value = profile.max_dte ?? 14; $('auto-cooldown').value = profile.cooldown_minutes ?? 30; $('auto-stale').value = profile.stale_data_seconds ?? 15
    $('auto-review').hidden = false
    $('auto-preview').textContent = `${(state.human_readable_policy || []).join('\n\n')}\n\nSaved policy defaults and assumptions:\n${JSON.stringify(profile, null, 2)}`
    $('auto-status').className = 'handoff-status'
    $('auto-status').textContent = `${profile.approval_mode === 'PAPER_DRAFT' ? 'Saved disabled PAPER draft' : 'Saved policy'} · digest ${state.profile_digest_valid ? 'valid' : 'INVALID'} · audit ${state.audit_chain_valid ? 'valid' : 'INVALID'}. No order was placed.`
  }
  const loadAutomationPolicy = async () => {
    try { showSavedAutomationPolicy(await fetchJson('/api/automation/profile')) } catch (error) { $('auto-status').className = 'handoff-status error'; $('auto-status').textContent = error.message }
  }
  const saveAutomationDraft = async () => {
    const button = $('save-auto-draft'); button.disabled = true
    try {
      const result = await postJson('/api/automation/profile/draft', automationPayload())
      showSavedAutomationPolicy({ profile: result.profile, human_readable_policy: result.human_readable_policy, profile_digest_valid: result.profile_digest_valid, audit_chain_valid: result.audit_chain_valid })
    } catch (error) { $('auto-status').className = 'handoff-status error'; $('auto-status').textContent = error.message }
    finally { button.disabled = false }
  }
  const previewAutomationPolicy = async () => {
    const button = $('preview-auto-policy'); button.disabled = true
    try {
      automationPreview = await postJson('/api/automation/profile/preview', automationPayload())
      $('auto-review').hidden = false
      $('auto-preview').textContent = `${automationPreview.human_readable_policy.join('\n\n')}\n\nPolicy digest: ${automationPreview.policy_digest}\nRequired acknowledgement: ${automationPreview.acknowledgement_phrase}\nNo order was placed or transmitted.`
      $('auto-ack').value = ''; $('save-auto-policy').disabled = true
      $('auto-status').className = 'handoff-status'; $('auto-status').textContent = 'Policy preview ready. Review every bound and type the exact acknowledgement to save it.'
    } catch (error) { $('auto-status').className = 'handoff-status error'; $('auto-status').textContent = error.message }
    finally { button.disabled = false }
  }
  const saveAutomationPolicy = async () => {
    if (!automationPreview) return
    const button = $('save-auto-policy'); button.disabled = true
    try {
      const result = await postJson('/api/automation/profile/save', { preview_id: automationPreview.preview_id, acknowledgement: $('auto-ack').value })
      $('auto-status').className = 'handoff-status'; $('auto-status').textContent = `${result.profile.execution_mode} policy saved · ${result.profile.enabled ? 'enabled' : 'disabled'} · audit chain ${result.audit_chain_valid ? 'valid' : 'INVALID'}. No order was placed.`
      automationPreview = null
    } catch (error) { $('auto-status').className = 'handoff-status error'; $('auto-status').textContent = error.message }
  }

  // The master search remains the validation source, but its raw segment and
  // contract controls are deliberately not part of the user workflow.
  ;[$('ema-band-segment').closest('label'), $('ema-band-underlying').closest('label'), $('ema-band-search').closest('label')].forEach(control => { control.hidden = true; control.style.display = 'none' })
  $('ema-band-underlying').closest('.field-grid').insertAdjacentHTML('afterbegin', `<label class="field" style="grid-column:1/-1">Underlying<input id="ema-band-underlying-search" autocomplete="off" placeholder="Search an underlying, for example NIFTY, RELIANCE, CRUDEOIL"><small>Only current FYERS cash/index or commodity-future underlyings with listed options are shown.</small></label><label class="field">Underlying<select id="ema-band-underlying-picker" disabled><option value="">Type at least two characters to search</option></select><small id="ema-band-strategy-direction">Choose an underlying; the completed EMA Band signal chooses Call (CE) or Put (PE).</small></label><label class="field">Mode<select id="ema-band-mode"><option value="PAPER" selected>Paper / forward test</option><option value="LIVE">Live (auto order submission)</option></select><small id="ema-band-mode-status">Paper/forward testing is active. No broker order route exists in this mode.</small></label><label class="field">Lots<input id="ema-band-lots" type="number" value="1" min="1" step="1"><small>Quantity for the automatic BUY entry order.</small></label><label class="field">Stop-loss (%) <span class="muted">(optional)</span><input id="ema-band-stop-pct" type="number" min="0.1" max="99.9" step="0.1" placeholder="Optional; blank = indicator exit only"><small>Optional extra safety net: auto-exit SELL is submitted early if the option price falls this % below entry. Leave blank to exit purely on the EMA Band indicator signal.</small></label><label class="field">Target (%) <span class="muted">(optional)</span><input id="ema-band-target-pct" type="number" min="0.1" step="0.1" placeholder="Optional; blank = indicator exit only"><small>Optional extra safety net: auto-exit SELL is submitted early if the option price rises this % above entry. Leave blank to exit purely on the EMA Band indicator signal. If both are set, target must be at least the stop-loss percentage.</small></label><div class="field" style="grid-column:1/-1"><button type="button" class="button secondary" id="ema-band-runner-toggle">Start Runner</button><div id="ema-band-runner-status" class="handoff-status">Runner stopped. Paper mode records only local paper entries; Live mode automatically submits a real BUY order after a validated signal and auto-exits on the EMA Band indicator signal (plus any stop-loss/target % you set).</div><div id="ema-band-ticket-preview" class="ticket-warning" hidden style="margin-top:10px"></div><div id="ema-band-pnl-chart" class="chart-card premium-chart" style="margin-top:14px"><div class="chart-empty">Live P&amp;L chart starts once the runner opens a position.</div></div></div>`)
  document.querySelector('#ema-band .panel').insertAdjacentHTML('afterend', '<section class="panel" style="margin-top:15px"><span class="label">EXECUTION LOG</span><h2>Paper and live entries/exits</h2><small class="muted">Newest first. Paper rows are local forward-test records; Live rows are real FYERS order submissions.</small><pre id="ema-band-execution-log" class="packet-preview runner-log" style="margin-top:10px">Waiting for runner activity…</pre></section>')
  $('ema-band-target-pct').closest('label').insertAdjacentHTML('afterend', '<label class="field">Profit-protection risk unit (%)<input id="ema-band-profit-protection-pct" type="number" min="0.1" max="99.9" step="0.1" value="20"><small>Initial 1R loss cap; breakeven at +1R, lock +0.5R at +1.5R, then a 40% giveback trail.</small></label>')
  $('ema-band-runner-toggle').parentElement.insertAdjacentHTML('beforebegin', '<section id="ema-band-broker-chart" class="chart-card premium-chart" style="grid-column:1/-1; margin:14px 0"><div class="chart-empty">Broker chart will load from the selected FYERS contract.</div></section><div class="ticket-warning" style="grid-column:1/-1"><b>Live mode places real FYERS orders with real money.</b> The runner submits a BUY entry for the chosen lots on a fresh completed-candle signal, then automatically submits a SELL exit once the EMA Band indicator signals an exit (a completed candle closing back inside the band), or once your optional stop-loss/target percentage is hit, whichever comes first. A SELL is only ever sent after FYERS confirms the matching BUY position is open. There is no per-order manual confirmation.</div>')
  $('ema-band-pnl-chart').insertAdjacentHTML('afterend', '<section id="ema-band-tracked-positions" class="panel" style="margin-top:14px"><div class="step-title"><div><span class="label">POSITION REGISTRY · READ ONLY</span><h3>Tracked paper and FYERS positions</h3><small class="muted">Each card has its own symbol, entry reference and current P&amp;L. Only an explicitly configured EMA worker may manage its own exit.</small></div></div><div id="ema-band-position-cards" class="analysis-board"><div class="empty">Loading retained paper and broker positions…</div></div></section>')
  document.querySelector('#ema-band .head .status').textContent = 'Paper default · optional live auto-trading'
  const showEmaMasterStatus = status => {
    const ready = status?.fresh === true
    const usable = status?.usable === true || status?.fresh === true
    const cachedAt = status?.segments?.map(item => item.cached_at).filter(Boolean).sort().at(-1)
    const lastSuccess = cachedAt ? new Date(cachedAt).toLocaleString([], { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'no successful refresh yet'
    $('ema-band-master-status').textContent = ready ? `Official FYERS cache fresh · last successful refresh ${lastSuccess} local time · next automatic refresh within 24 hours` : usable ? `Using validated stale cache (up to 72h) while automatic daily refresh retries · last successful refresh ${lastSuccess} local time · next automatic refresh within 24 hours` : 'Official FYERS cache missing or older than 72h · no successful refresh yet or cache expired · selection is blocked until refresh succeeds.'
    $('ema-band-underlying').disabled = !usable
    const underlyingPicker = $('ema-band-underlying-picker'); if (underlyingPicker && !underlyingPicker.value) underlyingPicker.disabled = !usable
    $('ema-band-contract').innerHTML = usable ? '<b>Contract context: cached master usable.</b> Automatic refresh runs daily; a transient failure retains this cache for up to 72 hours. Exact selected contract still requires fresh validation before any future action.' : '<b>Contract context: not validated.</b> No usable cache exists; contract selection is fail-closed.'
  }
  const loadEmaMasterStatus = async () => { try { const status = await fetchJson('/api/ema-band/master-status'); showEmaMasterStatus(status); if (status?.usable || status?.fresh) { const select = $('ema-band-underlying'); select.disabled = false; select.innerHTML = '<option value="">Type at least two characters to search the fresh official FYERS cache</option>' } } catch { showEmaMasterStatus(null) } }
  $('ema-band-master-refresh').addEventListener('click', async () => {
    const button = $('ema-band-master-refresh'); button.disabled = true; $('ema-band-master-status').textContent = 'Downloading official FYERS master files into the local cache…'
    try { showEmaMasterStatus(await postJson('/api/ema-band/master-refresh', {})) } catch (error) { $('ema-band-master-status').textContent = `Cache refresh failed; selection remains blocked: ${error.message}` } finally { button.disabled = false }
  })
  const clearEmaMasterSelection = () => {
    const select = $('ema-band-underlying')
    select.innerHTML = '<option value="">Search for a broker-supported contract</option>'
    select.disabled = true
    $('ema-band-contract').innerHTML = '<b>Contract context: not validated.</b> Search and select an exact broker-master contract for the chosen segment.'
  }
  const searchEmaMaster = async () => {
    const query = $('ema-band-search').value.trim()
    if (query.length < 2) { clearEmaMasterSelection(); return }
    try {
      const segment = $('ema-band-segment').value
      const data = await fetchJson(`/api/ema-band/master-search?q=${encodeURIComponent(query)}&segment=${encodeURIComponent(segment)}`)
      const select = $('ema-band-underlying')
      select.innerHTML = '<option value="">Choose exact cached contract</option>' + data.matches.map(item => `<option value="${escapeHtml(item.symbol)}" data-contract="${escapeHtml(JSON.stringify(item))}">${escapeHtml(item.segment)} · ${escapeHtml(item.underlying || '—')} · ${escapeHtml(item.symbol)} · ${escapeHtml(item.description || '')}</option>`).join('')
      select.disabled = !data.status?.usable || !data.matches.length
      select.onchange = () => {
        const item = JSON.parse(select.selectedOptions[0]?.dataset.contract || 'null')
        if (item) {
          const cash = /_CM$/.test(item.segment)
          $('ema-band-contract').textContent = `${item.segment} · underlying ${item.underlying || 'not available'} · ${item.symbol} · ${item.description} · expiry ${cash ? 'not applicable' : item.expiry || 'not available'} · strike ${cash ? 'not applicable' : item.strike || 'not available'} · option side ${cash ? 'not applicable' : item.option_type || 'not available'} · lot ${item.lot_size} · tick ${item.tick_size}`
        }
      }
    } catch (error) { $('ema-band-contract').textContent = `Contract search blocked: ${error.message}` }
  }
  $('ema-band-search').addEventListener('input', searchEmaMaster)
  $('ema-band-segment').addEventListener('change', () => { clearEmaMasterSelection(); searchEmaMaster() })
  const clearEmaAtmContract = message => {
    $('ema-band-contract').innerHTML = `<b>Contract context: not validated.</b> ${message || 'Choose an underlying and a bullish/bearish direction.'}`
  }
  const resolveEmaAtmContract = async () => {
    const picker = $('ema-band-underlying-picker')
    const underlying = JSON.parse(picker.selectedOptions[0]?.dataset.underlying || 'null')
    if (!underlying) { clearEmaAtmContract(); return }
    const mode = $('ema-band-mode').value
    $('ema-band-contract').textContent = 'Resolving the nearest valid ATM contract from FYERS…'
    try {
      const data = await fetchJson(`/api/ema-band/atm-option?underlying=${encodeURIComponent(underlying.symbol)}&timeframe=${encodeURIComponent($('ema-band-timeframe').value)}&ema_length=${encodeURIComponent($('ema-band-length').value)}&slope_lookback=${encodeURIComponent($('ema-band-slope-lookback').value)}&minimum_slope_atr=${encodeURIComponent($('ema-band-minimum-slope-atr').value)}&mode=${encodeURIComponent(mode)}`)
      const contract = data.contract
      const expiry = new Date(contract.expiry_epoch * 1000).toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' })
      const choice = data.direction === 'BULLISH' ? 'Bullish EMA Band signal → Call (CE)' : 'Bearish EMA Band signal → Put (PE)'
      $('ema-band-strategy-direction').textContent = choice
      $('ema-band-contract').textContent = `${choice} · ${underlying.underlying} spot ${data.spot} · automatically selected nearest expiry ${expiry}, nearest ATM strike ${contract.strike} · ${contract.description} · lot ${contract.lot_size} · tick ${contract.tick_size}. ${data.mode_status.message}`
    } catch (error) { $('ema-band-strategy-direction').textContent = 'No completed EMA Band entry signal; contract selection remains blocked.'; clearEmaAtmContract(`ATM contract resolution blocked: ${error.message}`) }
  }
  let emaUnderlyingSearchGeneration = 0
  const searchEmaOptionUnderlyings = async () => {
    const query = $('ema-band-underlying-search').value.trim()
    const picker = $('ema-band-underlying-picker')
    const generation = ++emaUnderlyingSearchGeneration
    if (query.length < 2) { picker.innerHTML = '<option value="">Type at least two characters to search</option>'; picker.disabled = true; clearEmaAtmContract('Search and select an underlying with listed FYERS options.'); return }
    try {
      const data = await fetchJson(`/api/ema-band/underlying-search?q=${encodeURIComponent(query)}`)
      if (generation !== emaUnderlyingSearchGeneration) return
      picker.innerHTML = '<option value="">Choose an underlying</option>' + data.matches.map(item => `<option data-underlying="${escapeHtml(JSON.stringify(item))}">${escapeHtml(item.underlying)} · ${escapeHtml(item.description)} · ${escapeHtml(item.market_kind === 'COMMODITY_FUTURE' ? 'MCX commodity future' : 'cash/index')}</option>`).join('')
      picker.disabled = !data.status?.usable || !data.matches.length
      if (!data.matches.length) clearEmaAtmContract('No current FYERS option-eligible underlying matched that search.')
    } catch (error) { picker.innerHTML = '<option value="">Underlying search unavailable</option>'; picker.disabled = true; clearEmaAtmContract(`Underlying search blocked: ${error.message}`) }
  }
  $('ema-band-underlying-search').addEventListener('input', searchEmaOptionUnderlyings)
  const syncEmaEntrySession = () => {
    const selected = JSON.parse($('ema-band-underlying-picker').selectedOptions[0]?.dataset.underlying || 'null')
    const isMcx = selected?.market_kind === 'COMMODITY_FUTURE' || String(selected?.symbol || '').startsWith('MCX:')
    $('ema-band-session').value = isMcx ? '0915-2330' : '0915-1515'
    $('ema-band-session').readOnly = true
    $('ema-band-session').closest('label').querySelector('small').textContent = isMcx ? 'MCX entries: 09:15–23:30 IST. Exits remain active after the entry window.' : 'Non-MCX entries: 09:15–15:15 IST. Exits remain active after the entry window.'
  }
  $('ema-band-underlying-picker').addEventListener('change', () => { syncEmaEntrySession(); resolveEmaAtmContract() })
  const loadEmaModeCapability = async () => {
    try {
      const data = await fetchJson(`/api/ema-band/mode-capability?mode=${encodeURIComponent($('ema-band-mode').value)}`)
      $('ema-band-mode-status').textContent = data.message
    } catch (error) { $('ema-band-mode-status').textContent = `Mode validation blocked: ${error.message}` }
  }
  $('ema-band-mode').addEventListener('change', async () => { await loadEmaModeCapability(); resolveEmaAtmContract() })
  $('ema-band-timeframe').addEventListener('change', resolveEmaAtmContract)
  $('ema-band-length').addEventListener('change', resolveEmaAtmContract)
  ;['ema-band-slope-lookback', 'ema-band-minimum-slope-atr'].forEach(id => $(id).addEventListener('change', resolveEmaAtmContract))
  const renderEmaBandChart = chart => {
    const el = $('ema-band-pnl-chart')
    if (!el) return
    const ticks = (chart?.ticks || []).filter(point => Number.isFinite(Number(point.ltp)))
    if (!chart || !ticks.length) {
      el.innerHTML = '<div class="chart-empty">Live P&amp;L chart starts once the runner opens a position.</div>'
      return
    }
    const points = ticks.map(point => Number(point.ltp))
    const refs = [chart.entry_price, chart.stop_price, chart.target_price].map(Number).filter(Number.isFinite)
    const rangeValues = points.concat(refs)
    const width = 640, height = 220, left = 48, right = 12, top = 12, bottom = 26
    const low = Math.min(...rangeValues), high = Math.max(...rangeValues), padding = Math.max((high - low) * .12, 0.5)
    const minY = low - padding, maxY = high + padding
    const x = index => left + index * ((width - left - right) / Math.max(points.length - 1, 1))
    const y = value => top + (maxY - value) * ((height - top - bottom) / (maxY - minY))
    const pathFor = values => values.map((value, index) => `${index === 0 ? 'M' : 'L'}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(' ')
    const reference = (value, label, color) => Number.isFinite(Number(value)) ? `<line x1="${left}" x2="${width - right}" y1="${y(Number(value))}" y2="${y(Number(value))}" stroke="${color}" stroke-width="1" stroke-dasharray="5 5"/><text x="${left + 4}" y="${y(Number(value)) - 5}" fill="${color}" font-size="10">${escapeHtml(label)} ${number(value)}</text>` : ''
    const currentIndex = points.length - 1
    const closed = chart.closed === true
    const pnlRupees = closed ? chart.realized_pnl_rupees : chart.unrealized_pnl_rupees
    const pnlPct = closed ? null : chart.unrealized_pnl_pct
    const pnlClass = Number(pnlRupees) >= 0 ? 'positive' : 'negative'
    const statusLabel = closed ? `Closed · ${chart.exit_reason || ''}` : 'Open'
    el.innerHTML = `<div class="premium-chart-stats"><div><b>${number(chart.ltp ?? points[currentIndex])}</b><small>${closed ? 'Exit price' : 'Live price'}</small></div><div><b class="${pnlClass}">${Number(pnlRupees) >= 0 ? '+' : ''}${money(pnlRupees)}</b><small>${pnlPct != null ? `${pnlPct >= 0 ? '+' : ''}${number(pnlPct)}%` : statusLabel}</small></div><div><b>${statusLabel}</b><small>${chart.symbol || ''}</small></div></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Live EMA Band option P&amp;L chart"><line x1="${left}" x2="${left}" y1="${top}" y2="${height - bottom}" stroke="#294766"/><line x1="${left}" x2="${width - right}" y1="${height - bottom}" y2="${height - bottom}" stroke="#294766"/>${reference(chart.entry_price, 'Entry', '#91a7c4')}${reference(chart.stop_price, 'Stop', '#e2685a')}${reference(chart.target_price, 'Target', '#60dca9')}<path d="${pathFor(points)}" fill="none" stroke="#72c7ff" stroke-width="3" stroke-linejoin="round"/><circle cx="${x(currentIndex)}" cy="${y(points[currentIndex])}" r="5" fill="#edf4ff" stroke="#2678be" stroke-width="3"/><text x="4" y="${top + 8}" fill="#91a7c4" font-size="10">${maxY.toFixed(2)}</text><text x="4" y="${height - bottom}" fill="#91a7c4" font-size="10">${minY.toFixed(2)}</text><text x="${width - right}" y="${height - 7}" text-anchor="end" fill="#edf4ff" font-size="10">${closed ? 'CLOSED' : 'LIVE'}</text></svg>`
  }
  const renderEmaTrackedPositions = snapshot => {
    const el = $('ema-band-position-cards')
    if (!el) return
    const positions = snapshot?.positions || []
    if (!positions.length) { el.innerHTML = '<div class="empty">No retained paper or open FYERS positions.</div>'; return }
    el.innerHTML = positions.map(position => {
      const pnl = Number(position.pnl)
      const hasPnl = Number.isFinite(pnl)
      const direction = Number(position.quantity) > 0 ? 'Long' : 'Short'
      const management = position.managed_by_ema ? 'EMA-managed independently' : 'Displayed only · no EMA exit authority'
      return `<article class="opportunity-card"><div class="opportunity-head"><div><b>${escapeHtml(position.description || position.symbol)}</b><small>${escapeHtml(position.source)} · ${direction} ${escapeHtml(Math.abs(Number(position.quantity) || 0))}</small></div><span class="conviction">${escapeHtml(management)}</span></div><div class="decision-metrics"><div><small>Entry</small><b>${number(position.entry_price)}</b></div><div><small>Latest price</small><b>${number(position.ltp)}</b></div><div><small>Current P&amp;L</small><b class="${hasPnl ? stateClass(pnl) : 'neutral'}">${hasPnl ? money(pnl) : 'Unavailable'}</b></div><div><small>Opened</small><b>${position.opened_at ? escapeHtml(time(position.opened_at)) : 'FYERS position'}</b></div></div><small class="muted">A detailed price chart is retained for a position while its own EMA worker is running. Historical paper entries remain visible after a dashboard restart.</small></article>`
    }).join('')
  }
  // The live quote refreshes every second.  Do not replace the SVG while the
  // user is inspecting it: replacing the DOM would make the crosshair and
  // tooltip disappear even though the pointer never left the chart.
  let emaBrokerHoverActive = false
  let pendingEmaBrokerSnapshot = null
  let emaBrokerHistoryStart = null
  const renderEmaBrokerChart = snapshot => {
    if (emaBrokerHoverActive) {
      pendingEmaBrokerSnapshot = snapshot
      return
    }
    const el = $('ema-band-broker-chart')
    const allCandles = snapshot?.candles || []
    if (!el || !allCandles.length) { if (el) el.innerHTML = '<div class="chart-empty">Broker chart unavailable until FYERS returns completed candles.</div>'; return }
    // Keep a readable fixed-width viewport and expose the rest through the
    // history scrollbar.  A full 160–500 bar series in the same SVG is too
    // compressed to inspect like a broker chart.
    const visibleCandleCount = Math.min(80, allCandles.length)
    const latestStart = Math.max(0, allCandles.length - visibleCandleCount)
    const historyStart = Math.max(0, Math.min(emaBrokerHistoryStart == null ? latestStart : emaBrokerHistoryStart, latestStart))
    const candles = allCandles.slice(historyStart, historyStart + visibleCandleCount)
    // Keep volume in its own time-based panel.  FYERS' OI Profile is instead
    // price-anchored, so reserve the right edge for horizontal OI build-up /
    // unwind bars by price zone.
    // Give the OI profile enough dedicated room to be read at a glance.  The
    // price plot remains wider than the old chart even after reserving this
    // larger right-hand panel.
    const width = 1160, height = 400, left = 54, right = 18, top = 56, bottom = 74, oiProfileWidth = 276
    const levels = snapshot?.levels || []
    const values = candles.flatMap(c => [Number(c.high), Number(c.low), Number(c.ema_high), Number(c.ema_low)]).concat(levels.map(level => Number(level.price))).filter(Number.isFinite)
    const low = Math.min(...values), high = Math.max(...values), pad = Math.max((high - low) * .08, 1)
    const minY = low - pad, maxY = high + pad, priceRight = width - right - oiProfileWidth, plotW = priceRight - left, plotH = height - top - bottom
    const x = i => left + (i + .5) * (plotW / candles.length)
    const y = price => top + (maxY - price) * plotH / (maxY - minY)
    const candleW = Math.max(2, Math.min(10, plotW / candles.length * .62))
    const path = field => candles.map((c, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(Number(c[field])).toFixed(1)}`).join(' ')
    const grid = [0, .25, .5, .75, 1].map(t => { const price = maxY - t * (maxY - minY), yy = y(price); return `<line x1="${left}" x2="${priceRight}" y1="${yy}" y2="${yy}" stroke="#21334a" stroke-dasharray="3 5"/><text x="4" y="${yy+4}" fill="#91a7c4" font-size="10">${price.toFixed(1)}</text>` }).join('')
    const levelLines = levels.map(level => { const support = level.label === 'SUPPORT'; const color = support ? '#48c78e' : '#ef6b73'; const yy = y(Number(level.price)); return `<line x1="${left}" x2="${priceRight}" y1="${yy}" y2="${yy}" stroke="${color}" stroke-width="1.5" stroke-dasharray="7 4"/><rect x="2" y="${yy-12}" width="${left-4}" height="14" rx="3" fill="#102035"/><text x="${left-4}" y="${yy-2}" text-anchor="end" fill="${color}" font-size="9" font-weight="700">${support ? 'S' : 'R'} ${number(level.price)}</text>` }).join('')
    const sticks = candles.map((c, i) => { const open=Number(c.open), close=Number(c.close), hi=Number(c.high), lo=Number(c.low), up=close>=open, color=up?'#48c78e':'#ef6b73', xx=x(i), bodyY=y(Math.max(open,close)), bodyH=Math.max(1,y(Math.min(open,close))-bodyY), forming=Boolean(c.is_forming); return `<line x1="${xx}" x2="${xx}" y1="${y(hi)}" y2="${y(lo)}" stroke="${color}"${forming?' stroke-dasharray="3 2"':''}/><rect x="${xx-candleW/2}" y="${bodyY}" width="${candleW}" height="${bodyH}" fill="${forming?'none':color}" stroke="${color}" stroke-width="${forming?'2':'0'}"/>` }).join('')
    const maxVolume = Math.max(...candles.map(c => Number(c.volume) || 0), 1), volumeBase = height - 26, volumeTop = height - bottom + 8, volumeHeight = volumeBase - volumeTop
    const volumeBars = candles.map((c, i) => { const up = Number(c.close) >= Number(c.open), color = up ? '#48c78e' : '#ef6b73', barH = Math.max(1, (Number(c.volume) || 0) / maxVolume * volumeHeight), xx = x(i); return `<rect x="${xx-candleW/2}" y="${volumeBase-barH}" width="${candleW}" height="${barH}" fill="${color}" opacity="${c.is_forming ? '.35' : '.65'}"/>` }).join('')
    const oiValues = candles.map(c => Number(c.open_interest)).filter(Number.isFinite)
    const oiBucketCount = 12
    const oiProfile = Array.from({ length: oiBucketCount }, () => ({ longBuildup: 0, shortBuildup: 0, shortCovering: 0, longUnwinding: 0 }))
    const oiStateEvents = []
    for (let i = 1; i < candles.length; i += 1) {
      const oi = Number(candles[i].open_interest), priorOi = Number(candles[i - 1].open_interest)
      if (!Number.isFinite(oi) || !Number.isFinite(priorOi)) continue
      const typicalPrice = (Number(candles[i].high) + Number(candles[i].low) + Number(candles[i].close)) / 3
      const bucket = Math.max(0, Math.min(oiBucketCount - 1, Math.floor((typicalPrice - minY) / (maxY - minY) * oiBucketCount)))
      const delta = oi - priorOi
      const priceUp = Number(candles[i].close) >= Number(candles[i - 1].close)
      const state = delta >= 0 && priceUp ? 'longBuildup' : delta >= 0 ? 'shortBuildup' : priceUp ? 'shortCovering' : 'longUnwinding'
      const magnitude = Math.abs(delta)
      oiProfile[bucket][state] += magnitude
      oiStateEvents.push({ state, magnitude })
    }
    const oiStateKeys = ['longBuildup', 'shortBuildup', 'shortCovering', 'longUnwinding']
    const oiStateLabels = { longBuildup: 'LB long buildup', shortBuildup: 'SB short buildup', shortCovering: 'SC short covering', longUnwinding: 'LU long unwinding' }
    const oiStateColors = { longBuildup: '#48c78e', shortBuildup: '#ef6b73', shortCovering: '#72c7ff', longUnwinding: '#f0b44d' }
    const oiTrendWindow = Math.min(12, Math.floor(oiStateEvents.length / 2))
    const oiStateMomentum = Object.fromEntries(oiStateKeys.map(state => {
      const recent = oiStateEvents.slice(-oiTrendWindow).filter(event => event.state === state).reduce((sum, event) => sum + event.magnitude, 0)
      const previous = oiStateEvents.slice(-oiTrendWindow * 2, -oiTrendWindow).filter(event => event.state === state).reduce((sum, event) => sum + event.magnitude, 0)
      const change = recent - previous, tolerance = Math.max(1, previous * .05)
      return [state, { recent, previous, change, direction: change > tolerance ? '↑ Increasing' : change < -tolerance ? '↓ Decreasing' : '→ Stable' }]
    }))
    const maxOiProfile = Math.max(...oiProfile.flatMap(bin => [bin.longBuildup, bin.shortBuildup, bin.shortCovering, bin.longUnwinding]), 1)
    const oiProfileBars = oiValues.length ? oiProfile.map((bin, index) => {
      const bucketPrice = minY + (index + .5) * (maxY - minY) / oiBucketCount
      const yy = y(bucketPrice), rowH = Math.max(18, plotH / oiBucketCount - 3), maxBar = oiProfileWidth - 88
      const bar = (value, offset, color) => `<rect x="${priceRight + 78}" y="${yy + offset}" width="${Math.max(0, value / maxOiProfile * maxBar)}" height="5" rx="2" fill="${color}" opacity=".98"/>`
      const zoneLow = minY + index * (maxY - minY) / oiBucketCount, zoneHigh = minY + (index + 1) * (maxY - minY) / oiBucketCount
      return `<g data-oi-profile-zone="${index}"><rect x="${priceRight + 7}" y="${yy-rowH/2}" width="${oiProfileWidth-14}" height="${rowH}" rx="3" fill="${index % 2 ? '#0d1d30' : '#10243a'}" stroke="#28445f" stroke-width=".6"/><text x="${priceRight + 13}" y="${yy-3}" fill="#d8e7f7" font-size="9" font-weight="700">${number(zoneLow)}–${number(zoneHigh)}</text><text x="${priceRight + 13}" y="${yy+8}" fill="#91a7c4" font-size="8">LB  SB  SC  LU</text>${bar(bin.longBuildup, -10, '#48c78e')}${bar(bin.shortBuildup, -3, '#ef6b73')}${bar(bin.shortCovering, 4, '#72c7ff')}${bar(bin.longUnwinding, 11, '#f0b44d')}</g>`
    }).join('') : ''
    const markers = candles.map((c, i) => { if (!c.marker) return ''; const buy=c.marker==='BUY', exit=c.marker.startsWith('EXIT'), yy=buy?y(Number(c.low))+15:y(Number(c.high))-8, color=buy?'#48c78e':exit?'#f0b44d':'#ef6b73'; return `<text x="${x(i)}" y="${yy}" text-anchor="middle" fill="${color}" font-size="9" font-weight="700">${c.marker}</text>` }).join('')
    const first = new Date(Number(candles[0].timestamp) * 1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}), last = new Date(Number(candles.at(-1).timestamp) * 1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})
    const forming = candles.at(-1)?.is_forming
    const rsiLength = Number(snapshot.rsi_length) || 14, rsiValues = candles.map(c => Number(c.rsi_14))
    const rsiTop = 34, rsiHeight = 244, rsiBottom = 36, rsiPlotHeight = rsiHeight - rsiTop - rsiBottom
    const rsiY = value => rsiTop + (100 - value) * rsiPlotHeight / 100
    let rsiStarted = false
    const rsiPath = rsiValues.map((value, index) => {
      if (!Number.isFinite(value)) { rsiStarted = false; return '' }
      const point = `${x(index).toFixed(1)},${rsiY(value).toFixed(1)}`
      const command = rsiStarted ? 'L' : 'M'; rsiStarted = true
      return `${command}${point}`
    }).join(' ')
    const latestRsi = [...rsiValues].reverse().find(Number.isFinite)
    const rsiPanel = `<svg viewBox="0 0 ${width} ${rsiHeight}" role="img" aria-label="RSI ${rsiLength} on FYERS fixed-contract closes"><rect x="${left}" y="${rsiTop}" width="${priceRight-left}" height="${rsiPlotHeight}" rx="5" fill="#091625" stroke="#4a7296" stroke-width="1.2"/><rect x="${left}" y="${rsiTop}" width="${priceRight-left}" height="${rsiY(60)-rsiTop}" fill="#512430" opacity=".5"/><rect x="${left}" y="${rsiY(60)}" width="${priceRight-left}" height="${rsiY(40)-rsiY(60)}" fill="#123451" opacity=".68"/><rect x="${left}" y="${rsiY(40)}" width="${priceRight-left}" height="${rsiTop+rsiPlotHeight-rsiY(40)}" fill="#174437" opacity=".48"/>${[100, 80, 60, 40, 0].map(level => `<line x1="${left}" x2="${priceRight}" y1="${rsiY(level)}" y2="${rsiY(level)}" stroke="${level === 60 || level === 40 ? '#d3b56a' : '#536d88'}" stroke-width="${level === 60 || level === 40 ? '1.4' : '1'}" stroke-dasharray="${level === 60 || level === 40 ? '7 4' : '2 3'}"/><text x="8" y="${rsiY(level)+4}" fill="#e1edf8" font-size="12" font-weight="700">${level}</text>`).join('')}<path d="${rsiPath}" fill="none" stroke="#f2d16c" stroke-width="3.4"/><circle cx="${x(candles.length-1)}" cy="${Number.isFinite(latestRsi) ? rsiY(latestRsi) : rsiY(50)}" r="4.5" fill="#f2d16c" stroke="#fff3bd" stroke-width="1.3"/><text x="${left+12}" y="${rsiTop+20}" fill="#f2d16c" font-size="14" font-weight="700">RSI ${rsiLength}</text><text x="${priceRight-12}" y="${rsiTop+20}" text-anchor="end" fill="#f2d16c" font-size="14" font-weight="700">${Number.isFinite(latestRsi) ? latestRsi.toFixed(1) : 'Warming up'}</text><text x="${left+12}" y="${rsiTop+39}" fill="#ffb1bb" font-size="10" font-weight="700">UPPER ZONE</text><text x="${left+12}" y="${rsiTop+rsiPlotHeight-9}" fill="#93e1bd" font-size="10" font-weight="700">LOWER ZONE</text><text x="${left}" y="${rsiHeight-11}" fill="#91a7c4" font-size="11">${first}</text><text x="${priceRight}" y="${rsiHeight-11}" text-anchor="end" fill="#91a7c4" font-size="11">${last}</text></svg>`
    const oiDetailHeight = 334, oiDetailTop = 82, oiDetailRowH = 19, oiDetailBarX = 210, oiDetailBarW = width - oiDetailBarX - right - 12
    const oiDetailRows = oiValues.length ? oiProfile.map((bin, index) => {
      const yy = oiDetailTop + index * oiDetailRowH
      const zoneLow = minY + index * (maxY - minY) / oiBucketCount, zoneHigh = minY + (index + 1) * (maxY - minY) / oiBucketCount
      const bar = (value, offset, color) => `<rect x="${oiDetailBarX}" y="${yy + offset}" width="${Math.max(0, value / maxOiProfile * oiDetailBarW)}" height="3.5" rx="1.75" fill="${color}"/>`
      return `<g data-oi-detail-zone="${index}"><rect x="${left}" y="${yy-4}" width="${width-left-right}" height="${oiDetailRowH-1}" rx="3" fill="${index % 2 ? '#0b192a' : '#102138'}"/><text x="${left+8}" y="${yy+8}" fill="#e1edf8" font-size="10" font-weight="700">${number(zoneLow)}–${number(zoneHigh)}</text>${bar(bin.longBuildup, 0, '#48c78e')}${bar(bin.shortBuildup, 4.5, '#ef6b73')}${bar(bin.shortCovering, 9, '#72c7ff')}${bar(bin.longUnwinding, 13.5, '#f0b44d')}</g>`
    }).join('') : `<text x="${left+10}" y="${oiDetailTop+20}" fill="#91a7c4" font-size="12">FYERS did not return historical open interest for this contract.</text>`
    const oiMomentumLegend = oiStateKeys.map((state, index) => `<text x="${520 + (index % 2) * 300}" y="${index < 2 ? '25' : '43'}" fill="${oiStateColors[state]}" font-size="10" font-weight="700">${oiStateLabels[state]}: ${oiStateMomentum[state].direction}</text>`).join('')
    const oiDetailPanel = `<svg viewBox="0 0 ${width} ${oiDetailHeight}" role="img" aria-label="Expanded open interest profile by price zone"><rect x="${left}" y="8" width="${width-left-right}" height="${oiDetailHeight-18}" rx="5" fill="#081524" stroke="#4a7296" stroke-width="1.2"/><text x="${left+10}" y="25" fill="#e5c68b" font-size="14" font-weight="700">EXPANDED OPEN INTEREST PROFILE</text><text x="${left+10}" y="43" fill="#91a7c4" font-size="9">Latest ${oiTrendWindow || 0} updates vs prior ${oiTrendWindow || 0}</text>${oiMomentumLegend}${oiDetailRows}</svg>`
    el.innerHTML = `<div class="premium-chart-stats"><div><b>${escapeHtml(snapshot.symbol)}</b><small>FYERS fixed contract · ${escapeHtml(snapshot.timeframe)}</small></div><div><b>EMA ${snapshot.ema_length} High / Low</b><small>Signals use completed candles only</small></div><div><b>${number(snapshot.live_price ?? candles.at(-1).close)}</b><small>${forming ? 'Live quote · refreshed each second' : 'Last completed close'}</small></div></div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="FYERS candlestick chart with EMA high and low bands, volume, and classified price-anchored open interest profile">${grid}${levelLines}<path d="${path('ema_high')}" fill="none" stroke="#ef6b73" stroke-width="2"/><path d="${path('ema_low')}" fill="none" stroke="#48c78e" stroke-width="2"/>${sticks}${markers}<line x1="${left}" x2="${priceRight}" y1="${volumeBase}" y2="${volumeBase}" stroke="#294766"/><text x="4" y="${volumeTop+9}" fill="#91a7c4" font-size="10">VOL</text><text x="${left}" y="${volumeTop+9}" fill="#91a7c4" font-size="10">${Math.round(maxVolume)}</text>${volumeBars}<rect x="${priceRight+4}" y="${top-46}" width="${oiProfileWidth-7}" height="${plotH+46}" rx="5" fill="#091625" stroke="#4a7296" stroke-width="1.2"/><text x="${priceRight+11}" y="${top-31}" fill="#e5c68b" font-size="13" font-weight="700">OPEN INTEREST PROFILE</text><text x="${priceRight+11}" y="${top-18}" fill="#48c78e" font-size="9" font-weight="700">LB long build</text><text x="${priceRight+98}" y="${top-18}" fill="#ef6b73" font-size="9" font-weight="700">SB short build</text><text x="${priceRight+11}" y="${top-6}" fill="#72c7ff" font-size="9" font-weight="700">SC short cover</text><text x="${priceRight+98}" y="${top-6}" fill="#f0b44d" font-size="9" font-weight="700">LU long unwind</text>${oiProfileBars}<text x="${left}" y="${height-9}" fill="#91a7c4" font-size="10">${first}</text><text x="${priceRight}" y="${height-9}" text-anchor="end" fill="#91a7c4" font-size="10">${last}</text></svg>${rsiPanel}${oiDetailPanel}<small class="muted">RSI ${rsiLength} uses the same FYERS fixed-contract closes and is display-only; EMA signals still use completed candles. Volume remains time-based below the candles. The OI Profile at right groups historical OI change by price zone: green long buildup, red short buildup, blue short covering, and amber long unwinding. It is unavailable when FYERS does not provide historical OI.</small>`
    const fullscreenButton = document.createElement('button')
    fullscreenButton.type = 'button'
    fullscreenButton.className = 'button secondary'
    fullscreenButton.textContent = '⛶ Full-screen chart'
    fullscreenButton.title = 'Open the EMA chart, RSI and OI Profile in full screen'
    fullscreenButton.style.margin = '0 0 10px auto'
    fullscreenButton.style.display = 'block'
    fullscreenButton.addEventListener('click', async () => {
      try {
        if (document.fullscreenElement === el) await document.exitFullscreen()
        else if (el.requestFullscreen) await el.requestFullscreen()
      } catch (_) {
        fullscreenButton.textContent = 'Full screen unavailable in this browser'
      }
    })
    document.addEventListener('fullscreenchange', () => {
      const active = document.fullscreenElement === el
      fullscreenButton.textContent = active ? '⤢ Exit full screen' : '⛶ Full-screen chart'
      el.style.background = active ? '#071322' : ''
      el.style.padding = active ? '24px' : ''
      el.style.overflowY = active ? 'auto' : ''
    }, { once: false })
    el.prepend(fullscreenButton)
    const historyNavigation = document.createElement('div')
    historyNavigation.className = 'field'
    historyNavigation.style.cssText = 'display:block;margin:0 0 12px;max-width:none;padding:9px 12px;border:1px solid #4a7296;border-radius:7px;background:#0b1a2b'
    historyNavigation.innerHTML = `<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px"><b style="letter-spacing:.08em;color:#d9f2ff">HISTORY NAVIGATOR</b><button type="button" class="button secondary" data-history-older style="padding:3px 9px">◀ Older</button><button type="button" class="button secondary" data-history-latest style="padding:3px 9px">Latest ▶</button><small style="margin-left:auto">${historyStart + 1}–${historyStart + candles.length} of ${allCandles.length} candles</small></div><input type="range" min="0" max="${latestStart}" value="${historyStart}" step="1" aria-label="Chart history scrollbar: drag left for older candles and right for latest candles" style="width:100%;height:18px;accent-color:#72c7ff"><small>Drag the blue handle left for older candles; drag right to return to the latest candles.</small>`
    const historySlider = historyNavigation.querySelector('input')
    const navigateHistory = start => {
      // Navigation is an explicit user action.  It must take precedence over
      // the hover lock that protects the inspection tooltip from live refresh.
      emaBrokerHistoryStart = start
      emaBrokerHoverActive = false
      pendingEmaBrokerSnapshot = null
      renderEmaBrokerChart(snapshot)
    }
    historySlider.addEventListener('input', () => {
      navigateHistory(Number(historySlider.value))
    })
    historyNavigation.querySelector('[data-history-older]').addEventListener('click', () => {
      navigateHistory(Math.max(0, historyStart - 20))
    })
    historyNavigation.querySelector('[data-history-latest]').addEventListener('click', () => {
      navigateHistory(latestStart)
    })
    fullscreenButton.insertAdjacentElement('afterend', historyNavigation)
    const svg = el.querySelector('svg')
    const rsiSvg = [...el.querySelectorAll('svg')].find(node => node.getAttribute('aria-label') === `RSI ${rsiLength} on FYERS fixed-contract closes`)
    const guide = document.createElementNS('http://www.w3.org/2000/svg', 'line')
    guide.setAttribute('x1', left); guide.setAttribute('x2', priceRight); guide.setAttribute('stroke', '#d9f2ff'); guide.setAttribute('stroke-width', '1'); guide.setAttribute('stroke-dasharray', '4 3'); guide.setAttribute('opacity', '0')
    svg.appendChild(guide)
    const candleGuide = document.createElementNS('http://www.w3.org/2000/svg', 'line')
    candleGuide.setAttribute('y1', top); candleGuide.setAttribute('y2', top + plotH); candleGuide.setAttribute('stroke', '#d9f2ff'); candleGuide.setAttribute('stroke-width', '1'); candleGuide.setAttribute('stroke-dasharray', '4 3'); candleGuide.setAttribute('opacity', '0')
    svg.appendChild(candleGuide)
    const candleTimeLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text')
    candleTimeLabel.setAttribute('y', height - 9); candleTimeLabel.setAttribute('text-anchor', 'middle'); candleTimeLabel.setAttribute('fill', '#d9f2ff'); candleTimeLabel.setAttribute('font-size', '11'); candleTimeLabel.setAttribute('font-weight', '700'); candleTimeLabel.setAttribute('opacity', '0')
    svg.appendChild(candleTimeLabel)
    const rsiGuide = document.createElementNS('http://www.w3.org/2000/svg', 'line')
    const rsiDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
    if (rsiSvg) {
      rsiGuide.setAttribute('y1', rsiTop); rsiGuide.setAttribute('y2', rsiTop + rsiPlotHeight); rsiGuide.setAttribute('stroke', '#d9f2ff'); rsiGuide.setAttribute('stroke-width', '1'); rsiGuide.setAttribute('stroke-dasharray', '4 3'); rsiGuide.setAttribute('opacity', '0')
      rsiDot.setAttribute('r', '5'); rsiDot.setAttribute('fill', '#f2d16c'); rsiDot.setAttribute('stroke', '#fff3bd'); rsiDot.setAttribute('stroke-width', '1.3'); rsiDot.setAttribute('opacity', '0')
      rsiSvg.append(rsiGuide, rsiDot)
    }
    let highlightedOiZone = null
    const hover = document.createElement('div')
    hover.className = 'handoff-status'
    hover.style.marginTop = '8px'
    hover.textContent = 'Hover over a candle or an OI Profile row to inspect the matching FYERS values.'
    el.appendChild(hover)
    el.style.position = 'relative'
    const crosshairCard = document.createElement('div')
    crosshairCard.style.cssText = 'display:none;position:absolute;z-index:3;left:14px;top:142px;max-width:410px;padding:9px 11px;border:1px solid #7ba8ca;border-radius:7px;background:#071322ee;color:#edf4ff;font-size:12px;line-height:1.55;box-shadow:0 8px 24px #0008;pointer-events:none;white-space:pre-line'
    el.appendChild(crosshairCard)
    const showCandleDetails = (candle, index) => {
      const time = new Date(Number(candle.timestamp) * 1000).toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
      const shortTime = new Date(Number(candle.timestamp) * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      const priorOi = index ? Number(candles[index - 1].open_interest) : null
      const oi = Number(candle.open_interest)
      const oiText = Number.isFinite(oi) ? `OI ${number(oi)}${Number.isFinite(priorOi) ? ` · ΔOI ${number(oi - priorOi)}` : ''}` : 'OI unavailable'
      const detail = `${time} · O ${number(candle.open)} · H ${number(candle.high)} · L ${number(candle.low)} · C ${number(candle.close)} · RSI ${number(candle.rsi_14)} · EMA High ${number(candle.ema_high)} · EMA Low ${number(candle.ema_low)} · ${oiText}${candle.marker ? ` · ${candle.marker}` : ''}`
      hover.textContent = detail
      crosshairCard.textContent = `${time}\nO ${number(candle.open)}  H ${number(candle.high)}  L ${number(candle.low)}  C ${number(candle.close)}\nRSI ${number(candle.rsi_14)}  ·  EMA High ${number(candle.ema_high)}  ·  EMA Low ${number(candle.ema_low)}\n${oiText}${candle.marker ? `  ·  ${candle.marker}` : ''}`
      crosshairCard.style.display = 'block'
      candleTimeLabel.setAttribute('x', x(index)); candleTimeLabel.textContent = shortTime; candleTimeLabel.setAttribute('opacity', '1')
    }
    const hideCandleDetails = () => {
      crosshairCard.style.display = 'none'
      candleTimeLabel.setAttribute('opacity', '0')
      hover.textContent = 'Hover over a candle or an OI Profile row to inspect the matching FYERS values.'
    }
    el.addEventListener('mouseenter', () => { emaBrokerHoverActive = true })
    el.addEventListener('mouseleave', () => {
      emaBrokerHoverActive = false
      guide.setAttribute('opacity', '0')
      candleGuide.setAttribute('opacity', '0')
      rsiGuide.setAttribute('opacity', '0')
      rsiDot.setAttribute('opacity', '0')
      svg.querySelectorAll('[data-oi-profile-zone]').forEach(node => node.setAttribute('opacity', '1'))
      highlightedOiZone = null
      hideCandleDetails()
      if (pendingEmaBrokerSnapshot) {
        const pending = pendingEmaBrokerSnapshot
        pendingEmaBrokerSnapshot = null
        renderEmaBrokerChart(pending)
      }
    })
    svg.addEventListener('mousemove', event => {
      const box = svg.getBoundingClientRect()
      const pointer = (event.clientX - box.left) * width / box.width
      const pointerY = (event.clientY - box.top) * height / box.height
      const inOiProfile = pointer >= priceRight + 4 && pointer <= width - right && pointerY >= top && pointerY <= top + plotH
      if (inOiProfile && oiValues.length) {
        const hoveredPrice = maxY - (pointerY - top) * (maxY - minY) / plotH
        const zone = Math.max(0, Math.min(oiBucketCount - 1, Math.floor((hoveredPrice - minY) / (maxY - minY) * oiBucketCount)))
        const zoneLow = minY + zone * (maxY - minY) / oiBucketCount, zoneHigh = minY + (zone + 1) * (maxY - minY) / oiBucketCount
        const zonePrice = (zoneLow + zoneHigh) / 2, bin = oiProfile[zone]
        guide.setAttribute('y1', y(zonePrice)); guide.setAttribute('y2', y(zonePrice)); guide.setAttribute('opacity', '1')
        if (highlightedOiZone !== zone) {
          svg.querySelectorAll('[data-oi-profile-zone]').forEach(node => node.setAttribute('opacity', node.dataset.oiProfileZone === String(zone) ? '1' : '.28'))
          highlightedOiZone = zone
        }
        hover.textContent = `OI Profile ${number(zoneLow)}–${number(zoneHigh)} · Long buildup ${number(bin.longBuildup)} · Short buildup ${number(bin.shortBuildup)} · Short covering ${number(bin.shortCovering)} · Long unwinding ${number(bin.longUnwinding)}`
        return
      }
      guide.setAttribute('opacity', '0')
      const index = Math.max(0, Math.min(candles.length - 1, Math.floor((pointer - left) / plotW * candles.length)))
      const candle = candles[index]
      candleGuide.setAttribute('x1', x(index)); candleGuide.setAttribute('x2', x(index)); candleGuide.setAttribute('opacity', '1')
      if (rsiSvg && Number.isFinite(Number(candle.rsi_14))) {
        rsiGuide.setAttribute('x1', x(index)); rsiGuide.setAttribute('x2', x(index)); rsiGuide.setAttribute('opacity', '1')
        rsiDot.setAttribute('cx', x(index)); rsiDot.setAttribute('cy', rsiY(Number(candle.rsi_14))); rsiDot.setAttribute('opacity', '1')
      }
      if (highlightedOiZone !== null) { svg.querySelectorAll('[data-oi-profile-zone]').forEach(node => node.setAttribute('opacity', '1')); highlightedOiZone = null }
      showCandleDetails(candle, index)
    })
    if (rsiSvg) {
      rsiSvg.addEventListener('mousemove', event => {
        const box = rsiSvg.getBoundingClientRect()
        const pointer = (event.clientX - box.left) * width / box.width
        const index = Math.max(0, Math.min(candles.length - 1, Math.floor((pointer - left) / plotW * candles.length)))
        const candle = candles[index]
        const rsiValue = Number(candle.rsi_14)
        candleGuide.setAttribute('x1', x(index)); candleGuide.setAttribute('x2', x(index)); candleGuide.setAttribute('opacity', '1')
        rsiGuide.setAttribute('x1', x(index)); rsiGuide.setAttribute('x2', x(index)); rsiGuide.setAttribute('opacity', '1')
        if (Number.isFinite(rsiValue)) {
          rsiDot.setAttribute('cx', x(index)); rsiDot.setAttribute('cy', rsiY(rsiValue)); rsiDot.setAttribute('opacity', '1')
        } else rsiDot.setAttribute('opacity', '0')
        showCandleDetails(candle, index)
      })
    }
  }
  const loadEmaBrokerChart = async state => {
    const config = state?.config
    const chartTimeframe = $('ema-band-chart-timeframe')?.value || config?.timeframe || '5 minutes'
    const chartBars = $('ema-band-chart-bars')?.value || '320'
    const symbol = config?.underlying || $('ema-band-underlying-picker')?.selectedOptions?.[0]?.value || ''
    const emaLength = config?.ema_length || $('ema-band-length')?.value || 21
    const params = new URLSearchParams({ timeframe: chartTimeframe, ema_length: String(emaLength), bars: String(chartBars) })
    if (symbol) params.set('symbol', symbol)
    const query = `?${params.toString()}`
    try { renderEmaBrokerChart(await fetchJson(`/api/ema-band/chart${query}`)) }
    catch (error) { const el = $('ema-band-broker-chart'); if (el) el.innerHTML = `<div class="chart-empty">Broker chart unavailable: ${escapeHtml(error.message)}</div>` }
  }
  ;['ema-band-chart-timeframe', 'ema-band-chart-bars'].forEach(id => {
    $(id).addEventListener('change', () => loadEmaBrokerChart(currentEmaRunnerState))
  })
  let currentEmaRunnerState = null
  const emaChecklistText = checklist => {
    if (!checklist?.checks) return ''
    const labels = {
      sufficient_completed_history: 'history', current_candle_completed: 'completed', flat_no_runner_position: 'flat', session_gate: 'session', same_direction_cooldown: 'cooldown',
      ema_slope_regime: 'EMA slope regime',
      prior_body_crosses_ema_high_long: 'long EMA High cross', prior_body_crosses_ema_low_short: 'short EMA Low cross',
      current_close_above_midpoint_long: 'long close above midpoint', current_close_below_midpoint_short: 'short close below midpoint'
    }
    return Object.entries(checklist.checks).map(([key, item]) => `${item.pass ? 'PASS' : 'FAIL'} ${labels[key] || key}${item.value ? ` (${item.value})` : ''}`).join(' · ')
  }
  const renderEmaRunner = state => {
    currentEmaRunnerState = state
    const running = state?.running === true
    $('ema-band-runner-toggle').textContent = running ? 'Stop Runner' : 'Start Runner'
    // A stopped runner has no current position or ticket context. Historical
    // entries/exits remain available in the separate execution journal.
    const event = running ? state?.last_event || {} : {}
    const status = running ? state?.status || 'MONITORING' : 'STOPPED'
    const detail = event.contract ? `${event.signal?.direction || 'Signal'} → ${event.contract.option_type} ${event.contract.strike} · ${event.contract.description}` : event.message || ''
    const ticket = event.ticket
    const ticketPreview = $('ema-band-ticket-preview')
    ticketPreview.hidden = !ticket
    ticketPreview.textContent = ticket ? `Review ticket only · ${ticket.action} ${ticket.quantity} × ${ticket.symbol} at limit ${ticket.limit_price}; EMA completed-candle exit, emergency review stop ${ticket.emergency_stop}, maximum loss cap ₹${ticket.maximum_loss_cap}, maximum premium at risk ₹${ticket.maximum_premium_at_risk}. Expires ${new Date(ticket.expires_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}. No order has been submitted.` : ''
    const checklist = running ? emaChecklistText(event.checklist) : ''
    $('ema-band-runner-status').textContent = `${status}${detail ? ` · ${detail}` : ''}${checklist ? ` · ${checklist}` : ''}${status === 'LIVE_ENTRY_SUBMITTED' ? ' · Real BUY order submitted to FYERS.' : status === 'LIVE_EXIT_SUBMITTED' ? ' · Real SELL exit order submitted to FYERS.' : status === 'LIVE_POSITION_OPEN' ? ' · Monitoring open live position for stop-loss/target.' : ''}`
    renderEmaBandChart(running ? state?.chart : null)
  }
  const loadEmaRunner = async () => { try { renderEmaRunner(await fetchJson('/api/ema-band/runner')) } catch (error) { $('ema-band-runner-status').textContent = `Runner status unavailable: ${error.message}` } }
  const loadEmaTrackedPositions = async () => {
    try { renderEmaTrackedPositions(await fetchJson('/api/ema-band/tracked-positions')) }
    catch (error) { const el = $('ema-band-position-cards'); if (el) el.innerHTML = `<div class="empty error">Tracked positions unavailable: ${escapeHtml(error.message)}</div>` }
  }
  const renderEmaExecutionLog = entries => {
    const el = $('ema-band-execution-log')
    if (!el) return
    const active = currentEmaRunnerState?.running === true
    const currentChecklist = active ? emaChecklistText(currentEmaRunnerState?.last_event?.checklist) : ''
    const current = active ? `CURRENT RUNNER\n${currentEmaRunnerState.status || 'MONITORING'}${currentChecklist ? `\n${currentChecklist}` : ''}\n\nHISTORICAL JOURNAL (previous activity, not current state)\n` : 'HISTORICAL JOURNAL (runner stopped; entries below are not current state)\n'
    if (!entries || !entries.length) { el.textContent = `${current}No paper or live EMA Band activity recorded yet.`; return }
    el.textContent = current + entries.map(entry => {
      const when = entry.at ? time(entry.at) : ''
      const tag = `[${entry.source || entry.mode || ''}]`
      const status = entry.status || ''
      let detail = ''
      if (entry.ticket) detail = `${entry.ticket.action} ${entry.ticket.quantity} × ${entry.ticket.symbol} @ ${entry.ticket.limit_price}`
      else if (entry.exit_order_id) detail = `SELL ${entry.position?.symbol || ''} @ ${entry.exit_ltp ?? ''} (${entry.exit_reason || ''})${entry.realized_pnl_rupees != null ? ` · P&L ${money(entry.realized_pnl_rupees)}` : ''}`
      else if (entry.contract) detail = `${entry.signal?.direction || ''} ${entry.contract.option_type || ''} ${entry.contract.strike || ''} ${entry.contract.description || ''}`
      else if (entry.checklist) detail = emaChecklistText(entry.checklist)
      else if (entry.message) detail = entry.message
      return `${when}  ${tag} ${status}${detail ? ' — ' + detail : ''}`
    }).join('\n')
  }
  const loadEmaExecutionLog = async () => { try { renderEmaExecutionLog((await fetchJson('/api/ema-band/execution-log?limit=100')).entries) } catch (error) { const el = $('ema-band-execution-log'); if (el) el.textContent = `Execution log unavailable: ${error.message}` } }
  $('ema-band-runner-toggle').addEventListener('click', async () => {
    const picker = $('ema-band-underlying-picker')
    const selected = JSON.parse(picker.selectedOptions[0]?.dataset.underlying || 'null')
    const startingLive = $('ema-band-mode').value === 'LIVE'
    const alreadyRunning = (await fetchJson('/api/ema-band/runner')).running
    if (!alreadyRunning && startingLive && !window.confirm('Start the LIVE EMA Band runner? This automatically places real FYERS orders with real money on every completed-candle signal, with no per-order confirmation.')) return
    const button = $('ema-band-runner-toggle'); button.disabled = true
    try {
      const current = await fetchJson('/api/ema-band/runner')
      const state = current.running
        ? await postJson('/api/ema-band/runner/stop', {})
        : await postJson('/api/ema-band/runner/start', (() => {
            const mode = $('ema-band-mode').value
            const body = { underlying: selected?.symbol, timeframe: $('ema-band-timeframe').value, ema_length: $('ema-band-length').value, slope_lookback: $('ema-band-slope-lookback').value, minimum_slope_atr: $('ema-band-minimum-slope-atr').value, resistance_volume_exit: $('ema-band-resistance-volume-exit').checked, resistance_volume_multiple: $('ema-band-resistance-volume-multiple').value, resistance_volume_lookback: $('ema-band-resistance-volume-lookback').value, entry_session: $('ema-band-session').value, mode }
            const protectionPct = $('ema-band-profit-protection-pct').value.trim()
            Object.assign(body, { lots: $('ema-band-lots').value })
            if (protectionPct !== '') body.profit_protection_pct = protectionPct
            if (mode === 'LIVE') {
              const stopPct = $('ema-band-stop-pct').value.trim()
              const targetPct = $('ema-band-target-pct').value.trim()
              if (stopPct !== '') body.stop_loss_pct = stopPct
              if (targetPct !== '') body.target_profit_pct = targetPct
            }
            return body
          })())
      renderEmaRunner(state)
    } catch (error) { $('ema-band-runner-status').textContent = `Runner action blocked: ${error.message}` } finally { button.disabled = false }
  })
  loadEmaMasterStatus()
  loadEmaModeCapability()
  loadEmaRunner()
  loadEmaTrackedPositions()
  loadEmaExecutionLog()
  setTimeout(() => loadEmaBrokerChart(currentEmaRunnerState), 600)
  setInterval(loadEmaRunner, 5000)
  setInterval(() => { if (!document.hidden) loadEmaTrackedPositions() }, 15000)
  setInterval(loadEmaExecutionLog, 15000)
  setInterval(() => { if (!document.hidden) loadEmaBrokerChart(currentEmaRunnerState) }, 1000)
  window.EmaCrossover.mount(initialView)
  window.EmaCrossoverLive.mount()
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => { document.querySelectorAll('[data-view]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)) }); document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === button.dataset.view)); try { localStorage.setItem(viewStorageKey, button.dataset.view) } catch {} }))
  document.querySelectorAll('[data-straddle-market]').forEach(button => button.addEventListener('click', () => {
    const market = button.dataset.straddleMarket
    document.querySelectorAll('[data-straddle-market]').forEach(item => {
      const active = item === button
      item.classList.toggle('active', active)
      item.setAttribute('aria-selected', String(active))
    })
    document.querySelectorAll('.straddle-pane').forEach(pane => pane.classList.toggle('active', pane.id === `${market}-straddle`))
    try { localStorage.setItem('sector-pulse:straddle-market', market) } catch {}
  }))
  document.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => { mode = button.dataset.mode; document.querySelectorAll('[data-mode]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)) }); selectedSector = ''; $('sector-detail').hidden = true; clearTimeout(analysisRefreshTimer); refreshAnalysis() }))
  $('analysis-refresh-interval').value = String(analysisReadyPollMs)
  $('analysis-refresh-interval').addEventListener('change', event => {
    const requested = Number(event.target.value)
    analysisReadyPollMs = allowedRefreshIntervals.includes(requested) ? requested : defaultAnalysisReadyPollMs
    event.target.value = String(analysisReadyPollMs)
    try { localStorage.setItem(refreshStorageKey, String(analysisReadyPollMs)) } catch {}
    clearTimeout(analysisRefreshTimer)
    analysisRefreshTimer = setTimeout(refreshAnalysis, analysis?.refreshing ? analysisLoadingPollMs : analysisReadyPollMs)
  })
  document.querySelectorAll('[data-period]').forEach(button => button.addEventListener('click', () => { period = button.dataset.period; document.querySelectorAll('[data-period]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)) }); refreshClosed() }))
  $('sector-filter').addEventListener('change', renderTable)
  $('sector-sort').addEventListener('change', renderTable)
  $('collect-candidates').addEventListener('click', collectCandidates)
  $('select-all-candidates').addEventListener('click', async () => {
    const button = $('select-all-candidates')
    try {
      button.disabled = true; button.textContent = 'Ranking with FYERS funds…'
      await rankCandidatesForSelection()
    } catch (error) {
      $('candidate-status').className = 'handoff-status error'; $('candidate-status').textContent = error.message
    } finally { button.disabled = false; button.textContent = 'Select all eligible' }
  })
  $('clear-candidate-selection').addEventListener('click', () => {
    document.querySelectorAll('.candidate-select').forEach(input => { input.checked = false })
    document.querySelectorAll('.opportunity-card').forEach(card => { card.hidden = true })
    $('candidate-batch-actions').hidden = true; $('candidate-status').textContent = 'Selection cleared. No broker action occurred.'
  })
  $('prepare-handoff-batch').addEventListener('click', prepareHandoffBatch)
  $('handoff-batch-confirmation').addEventListener('input', event => {
    $('submit-handoff-batch').disabled = !handoffBatchPreview?.live_submission_enabled || !handoffBatchPreview?.submission_eligible || event.target.value !== handoffBatchPreview?.confirmation_phrase
  })
  $('submit-handoff-batch').addEventListener('click', submitHandoffBatch)
  document.querySelectorAll('input[name="instrument-route"]').forEach(input => input.addEventListener('change', resetInstrumentRouteResults))
  document.querySelectorAll('input[name="cash-product"]').forEach(input => input.addEventListener('change', () => invalidateTicketPreview('Cash product changed. Select the candidate and refresh the exact preview.')))
  document.querySelectorAll('input[name="cash-exit-plan"]').forEach(input => input.addEventListener('change', () => {
    invalidateTicketPreview('Exit plan changed. The automatic plan must be reviewed again.')
    const selectedKey = document.querySelector('.candidate-select:checked')?.value
    if (analysisRun) { renderAnalysisCards(); if (selectedKey) document.querySelector(`.candidate-select[value="${CSS.escape(selectedKey)}"]`)?.dispatchEvent(new Event('change')) }
  }))
  $('prepare-packet').addEventListener('click', preparePacket)
  $('include-funds').addEventListener('change', event => { $('confirm-funds').disabled = !event.target.checked; if (!event.target.checked) $('confirm-funds').checked = false })
  $('copy-packet').addEventListener('click', copyPacket)
  $('download-packet').addEventListener('click', downloadPacket)
  $('prepare-ticket').addEventListener('click', prepareTicket)
  $('ticket-confirmation').addEventListener('input', event => {
    $('submit-ticket').disabled = !ticketPreview?.live_submission_enabled || !ticketPreview?.submission_eligible || event.target.value !== ticketPreview?.confirmation_phrase
  })
  $('submit-ticket').addEventListener('click', submitTicket)
  $('add-screener').addEventListener('click', () => {
    try {
      const url = validChartinkUrl($('screener-url').value.trim())
      if (screenerSources.some(source => source.url === url)) throw new Error('That Chartink screener is already configured.')
      screenerSources.push({ id: `chartink-${Date.now()}`, label: $('screener-label').value.trim() || 'Chartink screener', url, refresh_interval_ms: defaultScreenerRefreshMs, refresh_interval_explicit: false, result: null })
      saveScreenerSources(); renderScreenerSources(); $('screener-url').value = ''; $('screener-label').value = ''; $('screener-status').textContent = 'Source added locally. Refresh it manually when needed.'
    } catch (error) { $('screener-status').className = 'handoff-status error'; $('screener-status').textContent = error.message }
  })
  $('refresh-screeners').addEventListener('click', async () => { for (const source of [...screenerSources]) await refreshScreenerSource(source.id) })
  $('analyze-screeners').addEventListener('click', () => analyzeScreenerCandidates(true))
  $('screener-analysis-next').addEventListener('click', () => {
    screenerAnalysisCancelled = true
    $('screener-analysis-next').disabled = true
    $('screener-analysis-status').textContent = `Cancellation requested · finishing the current safe batch (${screenerAnalysisOffset} complete).`
  })
  $('prepare-screener-order').addEventListener('click', prepareScreenerOrder)
  $('analyze-screener-options').addEventListener('click', analyzeScreenerOptionPlans)
  $('submit-screener-order').addEventListener('click', submitScreenerOrder)
  $('screener-select-all').addEventListener('click', async () => {
    const button = $('screener-select-all')
    try {
      button.disabled = true; button.textContent = 'Allocating with FYERS funds…'
      await allocateScreenerPlansByFunds()
    } catch (error) { $('screener-analysis-status').className = 'handoff-status error'; $('screener-analysis-status').textContent = error.message }
    finally { button.disabled = false; button.textContent = 'Select all eligible' }
  })
  $('screener-clear-selection').addEventListener('click', () => {
    screenerSelectedPlans.clear()
    syncScreenerSelectionUi('Selection cleared. No analysis or broker action has occurred.')
  })
  ;['screener-order-product', 'screener-order-external-risk'].forEach(id => $(id).addEventListener('input', () => invalidateScreenerOrderPreview('Order input changed. Request a new exact FYERS preview.')))
  $('screener-order-confirmation').addEventListener('input', event => {
    $('submit-screener-order').disabled = !screenerOrderPreview?.live_submission_enabled || !screenerOrderPreview?.submission_eligible || event.target.value !== screenerOrderPreview?.confirmation_phrase
  })
  $('screener-sources').addEventListener('click', event => {
    const refresh = event.target.closest('.refresh-screener')
    const stop = event.target.closest('.stop-screener-refresh')
    const remove = event.target.closest('.remove-screener')
    const sortButton = event.target.closest('.screener-sort')
    const selectAll = event.target.closest('.screener-source-select-all')
    const clearSelection = event.target.closest('.screener-source-clear-selection')
    if (refresh) refreshScreenerSource(refresh.dataset.sourceId)
    if (stop) {
      const source = screenerSources.find(item => item.id === stop.dataset.sourceId)
      if (source) { source.refresh_interval_ms = 0; source.refresh_interval_explicit = true; source.refresh_interval_custom = false; saveScreenerSources(); renderScreenerSources() }
    }
    if (remove) { screenerSources = screenerSources.filter(source => source.id !== remove.dataset.sourceId); saveScreenerSources(); renderScreenerSources() }
    if (sortButton) {
      const current = screenerSortState.get(sortButton.dataset.sourceId) || { key: 'symbol', direction: 'asc' }
      screenerSortState.set(sortButton.dataset.sourceId, { key: sortButton.dataset.sortKey, direction: current.key === sortButton.dataset.sortKey && current.direction === 'asc' ? 'desc' : 'asc' })
      renderScreenerSources()
      document.querySelector(`.screener-sort[data-source-id="${CSS.escape(sortButton.dataset.sourceId)}"]`)?.closest('details')?.setAttribute('open', '')
    }
    if (selectAll) {
      const source = screenerSources.find(item => item.id === selectAll.dataset.sourceId)
      ;(source?.result?.candidates || []).map(symbol => String(symbol).trim()).filter(Boolean).forEach(symbol => screenerCandidateSelections.add(symbol))
      syncScreenerCandidateSelectionUi()
    }
    if (clearSelection) {
      const source = screenerSources.find(item => item.id === clearSelection.dataset.sourceId)
      ;(source?.result?.candidates || []).map(symbol => String(symbol).trim()).filter(Boolean).forEach(symbol => screenerCandidateSelections.delete(symbol))
      syncScreenerCandidateSelectionUi()
    }
  })
  $('screener-sources').addEventListener('input', event => {
    const customInterval = event.target.closest('.screener-custom-refresh-minutes')
    if (customInterval) {
      const source = screenerSources.find(item => item.id === customInterval.dataset.sourceId)
      const minutes = Number(customInterval.value)
      if (!source || !Number.isInteger(minutes) || minutes < 5 || minutes > 1440) {
        $('screener-status').className = 'handoff-status error'; $('screener-status').textContent = 'Custom auto-refresh must be a whole number from 5 to 1440 minutes.'
        return
      }
      source.refresh_interval_ms = minutes * 60 * 1000; source.refresh_interval_explicit = true; source.refresh_interval_custom = true
      $('screener-status').className = 'handoff-status'; $('screener-status').textContent = `Custom read-only auto-refresh set to ${minutes} minutes.`
      saveScreenerSources(); updateScreenerScheduleLabels()
      return
    }
    const dynamic = event.target.closest('.screener-dynamic-filter')
    if (dynamic) {
      const current = screenerFilterState.get(dynamic.dataset.sourceId) || { dynamic: {} }
      const rules = { ...(current.dynamic || {}) }
      rules[dynamic.dataset.field] = { ...(rules[dynamic.dataset.field] || {}), [dynamic.dataset.filterPart]: dynamic.value }
      screenerFilterState.set(dynamic.dataset.sourceId, { ...current, dynamic: rules })
      renderScreenerSources()
      const replacement = document.querySelector(`.screener-dynamic-filter[data-source-id="${CSS.escape(dynamic.dataset.sourceId)}"][data-field="${CSS.escape(dynamic.dataset.field)}"][data-filter-part="${CSS.escape(dynamic.dataset.filterPart)}"]`)
      replacement?.closest('details')?.setAttribute('open', ''); replacement?.focus()
      return
    }
    const search = event.target.closest('.screener-symbol-filter, .screener-volume-filter, .screener-volume-max, .screener-market-cap-min, .screener-market-cap-max, .screener-price-min, .screener-price-max, .screener-change-min, .screener-change-max, .screener-change-pct-min, .screener-change-pct-max, .screener-price-as-of')
    if (!search) return
    const current = screenerFilterState.get(search.dataset.sourceId) || { search: '', sector: '', minMarketCap: '', maxMarketCap: '', minVolume: '', maxVolume: '', minPrice: '', maxPrice: '', minChange: '', maxChange: '', minChangePct: '', maxChangePct: '', priceAsOf: '' }
    const fieldByClass = { 'screener-symbol-filter': 'search', 'screener-volume-filter': 'minVolume', 'screener-volume-max': 'maxVolume', 'screener-market-cap-min': 'minMarketCap', 'screener-market-cap-max': 'maxMarketCap', 'screener-price-min': 'minPrice', 'screener-price-max': 'maxPrice', 'screener-change-min': 'minChange', 'screener-change-max': 'maxChange', 'screener-change-pct-min': 'minChangePct', 'screener-change-pct-max': 'maxChangePct', 'screener-price-as-of': 'priceAsOf' }
    const field = Object.keys(fieldByClass).find(className => search.classList.contains(className))
    if (!field) return
    const stateField = fieldByClass[field]
    const update = { [stateField]: search.value }
    screenerFilterState.set(search.dataset.sourceId, { ...current, ...update })
    renderScreenerSources()
    const replacement = document.querySelector(`.${field}[data-source-id="${CSS.escape(search.dataset.sourceId)}"]`)
    replacement?.closest('details')?.setAttribute('open', '')
    replacement?.focus()
  })
  $('screener-sources').addEventListener('change', event => {
    const candidate = event.target.closest('.screener-candidate-select')
    if (candidate) {
      if (candidate.checked) screenerCandidateSelections.add(candidate.value); else screenerCandidateSelections.delete(candidate.value)
      syncScreenerCandidateSelectionUi()
      return
    }
    const dynamic = event.target.closest('.screener-dynamic-filter')
    if (dynamic) { dynamic.dispatchEvent(new Event('input', { bubbles: true })); return }
    const refreshInterval = event.target.closest('.screener-refresh-interval')
    if (refreshInterval) {
      const source = screenerSources.find(item => item.id === refreshInterval.dataset.sourceId)
      if (refreshInterval.value === 'custom') {
        if (source) { source.refresh_interval_custom = true; source.refresh_interval_explicit = true; saveScreenerSources(); renderScreenerSources() }
        return
      }
      const interval = Number(refreshInterval.value)
      if (source && screenerRefreshIntervals.includes(interval)) {
        source.refresh_interval_ms = interval
        source.refresh_interval_explicit = true
        source.refresh_interval_custom = false
        saveScreenerSources()
        renderScreenerSources()
      }
      return
    }
    const sector = event.target.closest('.screener-sector-filter')
    if (!sector) return
    const current = screenerFilterState.get(sector.dataset.sourceId) || { search: '', sector: '', minMarketCap: '', maxMarketCap: '', minVolume: '', maxVolume: '', minPrice: '', maxPrice: '', minChange: '', maxChange: '', minChangePct: '', maxChangePct: '', priceAsOf: '' }
    const update = { sector: sector.value }
    screenerFilterState.set(sector.dataset.sourceId, { ...current, ...update })
    renderScreenerSources()
    document.querySelector(`.screener-sector-filter[data-source-id="${CSS.escape(sector.dataset.sourceId)}"]`)?.closest('details')?.setAttribute('open', '')
  })
  $('preview-auto-policy').addEventListener('click', previewAutomationPolicy)
  $('save-auto-draft').addEventListener('click', saveAutomationDraft)
  $('auto-ack').addEventListener('input', event => { $('save-auto-policy').disabled = !automationPreview || event.target.value !== automationPreview.acknowledgement_phrase })
  $('save-auto-policy').addEventListener('click', saveAutomationPolicy)
  document.querySelectorAll('input[name="straddle-mode"]').forEach(input => input.addEventListener('change', () => { syncStraddleOptions(); if (straddleRunnerState.strategy) renderStraddle(straddleRunnerState) }))
  $('start-straddle').addEventListener('click', () => controlStraddle('start'))
  $('stop-straddle').addEventListener('click', () => controlStraddle('stop'))
  document.querySelectorAll('input[name="nifty-straddle-mode"]').forEach(input => input.addEventListener('change', () => { syncNiftyStraddleOptions(); if (niftyStraddleRunnerState.strategy) renderNiftyStraddle(niftyStraddleRunnerState) }))
  document.querySelectorAll('input[name="nifty-straddle-exit"]').forEach(input => input.addEventListener('change', syncNiftyStraddleOptions))
  $('start-nifty-straddle').addEventListener('click', () => controlNiftyStraddle('start'))
  $('stop-nifty-straddle').addEventListener('click', () => controlNiftyStraddle('stop'))
  $('squareoff-straddle').addEventListener('click', () => prepareStraddleSquareoff('sensex'))
  $('squareoff-nifty-straddle').addEventListener('click', () => prepareStraddleSquareoff('nifty'))
  $('straddle-squareoff-confirmation').addEventListener('input', event => { $('confirm-straddle-squareoff').disabled = event.target.value !== straddleSquareoffPreviews.sensex?.confirmation_phrase || !straddleSquareoffPreviews.sensex?.submission_eligible })
  $('nifty-straddle-squareoff-confirmation').addEventListener('input', event => { $('confirm-nifty-straddle-squareoff').disabled = event.target.value !== straddleSquareoffPreviews.nifty?.confirmation_phrase || !straddleSquareoffPreviews.nifty?.submission_eligible })
  $('confirm-straddle-squareoff').addEventListener('click', () => submitStraddleSquareoff('sensex'))
  $('confirm-nifty-straddle-squareoff').addEventListener('click', () => submitStraddleSquareoff('nifty'))
  ;['planning-capital', 'daily-loss-limit', 'idea-risk-limit', 'risk-reserve', 'max-positions', 'minimum-rr', 'enforce-risk-controls', 'stop-basis', 'order-type'].forEach(id => $(id).addEventListener('input', renderPolicyImpact))
  ;['planning-capital', 'daily-loss-limit', 'idea-risk-limit', 'risk-reserve', 'max-positions', 'minimum-rr', 'enforce-risk-controls', 'stop-basis', 'order-type'].forEach(id => $(id).addEventListener('change', () => { renderPolicyImpact(); if (analysisRun) collectCandidates() }))
  $('reauth').addEventListener('click', async () => {
    const button = $('reauth'); button.disabled = true; button.textContent = 'Checking FYERS session…'
    try {
      const status = await fetchJson('/api/auth/status')
      if (status.authenticated) { $('broker-state').textContent = status.message; return }
      if (!status.ready) throw new Error(status.message || 'FYERS OAuth configuration is not ready.')
      button.textContent = 'Opening FYERS login…'
      const data = await fetchJson('/api/auth/start'); window.location.assign(data.url)
    } catch (error) { $('broker-state').textContent = error.message; button.disabled = false; button.textContent = 'Refresh authentication' }
  })

  document.addEventListener('visibilitychange', () => {
    updateScreenerScheduleLabels()
    if (!document.hidden) runScreenerScheduler()
  })

  syncStraddleOptions(); syncNiftyStraddleOptions(); renderPolicyImpact(); loadAutomationPolicy(); refreshAnalysis(); refreshAccount(); refreshClosed(); refreshTicketCapabilities(); loadKamaRunner(); refreshStraddle(); refreshNiftyStraddle(); runScreenerScheduler()
  setInterval(refreshAccount, accountRefreshMs)
  setInterval(refreshStraddle, straddleRefreshMs)
  setInterval(refreshNiftyStraddle, straddleRefreshMs)
})()
