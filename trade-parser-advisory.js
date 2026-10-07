/* Advisory feedback has no reference to order buttons, broker status, or order routes. */
;(function (root) {
  const labels = {
    price_action: 'Price action and structure', support_resistance: 'Support / resistance',
    supply_demand: 'Supply / demand', breakout_volume: 'Breakout and volume', entry: 'Entry',
    targets_partial_profits: 'Targets and partial profits', initial_stop: 'Initial stop',
    trailing_stop: 'Trailing stop', reward_risk: 'Reward / risk',
    volume_vwap_momentum: 'Volume, VWAP and momentum', relative_strength_sector: 'Relative strength and sector'
  }
  function render(output, data) {
    output.replaceChildren()
    output.hidden = false
    output.style.cssText = 'margin-top:12px;white-space:normal;border:1px solid #64748b;background:#14202d;color:#e2e8f0;padding:16px;border-radius:12px'
    const add = (parent, tag, text) => {
      const el = output.ownerDocument.createElement(tag)
      el.textContent = text
      parent.appendChild(el)
      return el
    }
    add(output, 'h3', 'OpenAI feedback · advisory only')
    add(output, 'p', data.message || 'Analysis runs independently of order submission.')
    if (data.contract) add(output, 'p', `${data.contract} · Evidence captured ${data.captured_at} · ${data.model}`)
    for (const [key, title] of [['intraday', 'Intraday'], ['swing', 'Swing · 1–5 trading days']]) {
      const report = data[key]
      if (!report) continue
      const verdict = ['PASS', 'FAIL'].includes(report.verdict) ? report.verdict : 'UNAVAILABLE'
      const card = add(output, 'section', '')
      const colors = verdict === 'PASS' ? ['#35b878', '#b9f4d2', '#102d24'] : verdict === 'FAIL' ? ['#df5b67', '#ffc2c8', '#351920'] : ['#64748b', '#e2e8f0', '#14202d']
      card.style.cssText = `margin-top:12px;padding:14px;border:1px solid ${colors[0]};color:${colors[1]};background:${colors[2]};border-radius:8px`
      add(card, 'h3', `${title}: ${verdict}`)
      const reasons = add(card, 'ul', '')
      for (const reason of report.reasons || []) add(reasons, 'li', reason)
      const details = add(card, 'details', '')
      add(details, 'summary', 'Analysis and conditional trade plan')
      for (const [field, label] of Object.entries(labels)) {
        const p = add(details, 'p', '')
        add(p, 'strong', label + ': ')
        add(p, 'span', report[field] || 'Unavailable')
      }
      if (report.missing_evidence?.length) add(card, 'p', 'Missing evidence: ' + report.missing_evidence.join('; '))
    }
    if (data.missing_evidence?.length) add(output, 'p', 'Data limitations: ' + data.missing_evidence.join('; '))
  }
  function create(output, fetcher = root.fetch.bind(root), timeoutMs = 60000) {
    let generation = 0
    let controller
    const clear = () => {
      generation++
      controller?.abort()
      output.replaceChildren()
      output.hidden = true
    }
    const start = async payload => {
      const current = ++generation
      controller?.abort()
      const active = new AbortController()
      controller = active
      const timer = setTimeout(() => active.abort(), timeoutMs)
      try {
        render(output, {message: 'Checking AI connection and evidence in the background. Order submission proceeds independently.'})
        const response = await fetcher('/api/trade-recommendation/ai-analysis', {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload), signal: active.signal
        })
        if (!response.ok) throw new Error('unavailable')
        const data = await response.json()
        if (data.advisory_only !== true) throw new Error('server update required')
        if (generation === current) render(output, data)
      } catch (error) {
        if (generation === current) render(output, {message: error.name === 'AbortError'
          ? 'AI feedback unavailable: analysis timed out.' : 'AI feedback unavailable: connection or analysis failed.'})
      } finally { clearTimeout(timer) }
    }
    // Schedule after the broker request has already been dispatched. No returned promise to await.
    const schedule = payload => {
      const expected = generation
      setTimeout(() => {
        if (generation === expected) void start(payload).catch(() => {})
      }, 0)
    }
    return {schedule, clear, start}
  }
  root.SectorPulseTradeAdvisory = {create, render}
  if (typeof module !== 'undefined') module.exports = {create, render}
})(typeof window === 'undefined' ? globalThis : window)
