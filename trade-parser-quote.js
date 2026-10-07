;(function (root) {
  const formatTime = stamp => {
    if (!stamp || !Number.isFinite(new Date(stamp).getTime())) return 'unavailable'
    return new Date(stamp).toLocaleString('en-GB', {timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}) + ' IST'
  }
  function render(output, data) {
    const valid = data.status === 'READY' && Number.isFinite(data.ltp) && data.ltp > 0
    const age = data.provider_timestamp ? (Date.now() - new Date(data.provider_timestamp).getTime()) / 1000 : NaN
    const fresh = valid && data.freshness === 'FRESH' && age >= -5 && age <= 30
    output.textContent = valid
      ? `FYERS LTP: ₹${data.ltp.toFixed(2)} · ${data.symbol}\n${fresh ? 'FRESH — provider timestamp within 30 seconds' : 'FRESHNESS UNCONFIRMED — do not treat as a verified live price'}\nFYERS timestamp: ${formatTime(data.provider_timestamp)} · Fetched: ${formatTime(data.fetched_at)}`
      : `${data.message || 'FYERS LTP unavailable.'}${data.symbol ? '\n' + data.symbol : ''}`
    output.style.whiteSpace = 'pre-line'
    output.style.color = fresh ? '#b9f4d2' : valid ? '#f1d598' : '#b8c7da'
  }
  function create(output, button, fetcher = root.fetch.bind(root)) {
    let version = 0, ticket = null, controller = null, agingTimer = null, retryTimer = null, retryUntil = 0
    function clear() {
      version++
      ticket = null
      controller?.abort()
      clearTimeout(agingTimer)
      clearTimeout(retryTimer)
      button.disabled = true
      render(output, {message:'FYERS LTP unavailable — parse an exact contract first.'})
    }
    async function refresh() {
      if (!ticket || Date.now() < retryUntil) return
      const target = ticket, current = ++version
      controller?.abort()
      clearTimeout(agingTimer)
      const active = new AbortController()
      controller = active
      button.disabled = true
      render(output, {symbol:target.symbol,message:'Fetching FYERS LTP…'})
      const timer = setTimeout(() => active.abort(), 10000)
      try {
        const response = await fetcher('/api/trade-recommendation/quote', {method:'POST',
          headers:{'Content-Type':'application/json'},body:JSON.stringify(target),signal:active.signal})
        if (!response.ok) throw new Error(response.status === 404 ? 'SERVER_UPDATE' : 'UNAVAILABLE')
        const data = await response.json()
        if (data.symbol !== target.symbol) throw new Error('CONTRACT_MISMATCH')
        if (version !== current) return
        render(output, data)
        if (data.reason === 'RATE_LIMITED') {
          retryUntil = Date.now() + Math.max(1, Number(data.retry_after_seconds) || 60) * 1000
          clearTimeout(retryTimer)
          retryTimer = setTimeout(() => { if (ticket) button.disabled = false }, retryUntil - Date.now())
        }
        if (data.freshness === 'FRESH') agingTimer = setTimeout(() => {
          if (version === current) render(output, {...data,freshness:'UNCONFIRMED'})
        }, Math.max(0, 31000 - Math.max(0, Date.now() - new Date(data.provider_timestamp).getTime())))
      } catch (error) {
        if (version === current) render(output, {symbol:target.symbol,message:error.message === 'SERVER_UPDATE'
          ? 'FYERS LTP unavailable: dashboard backend update is pending.' : 'FYERS LTP unavailable: quote request failed or timed out.'})
      } finally {
        clearTimeout(timer)
        if (version === current) button.disabled = Date.now() < retryUntil
      }
    }
    function select(text, symbol) {
      clear()
      if (!symbol) return
      ticket = {text, symbol}
      if (Date.now() < retryUntil) {
        render(output, {symbol, message:'FYERS LTP rate-limited. Wait for the refresh cooldown to finish.'})
        retryTimer = setTimeout(() => { if (ticket) button.disabled = false }, retryUntil - Date.now())
      } else void refresh()
    }
    button.addEventListener('click', () => { void refresh() })
    clear()
    return {select, clear}
  }
  root.SectorPulseParserQuote = {create,render}
  if (typeof module !== 'undefined') module.exports = {create,render}
})(typeof window === 'undefined' ? globalThis : window)
