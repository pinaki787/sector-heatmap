/* Enable with ?feedTiming=1. Read-only diagnostics; no extra broker requests. */
(() => {
  if (new URLSearchParams(location.search).get('feedTiming') !== '1') return;
  const events = [], requests = [], backend = new Map();
  const record = (stage, detail = {}) => {
    events.push({stage, browser_ms: +performance.now().toFixed(3), ...detail});
    if (events.length > 1000) events.shift();
  };
  record('debug_script_loaded');
  const originalFetch = window.fetch;
  window.fetch = async function(input, options) {
    const url = new URL(input instanceof Request ? input.url : String(input), location.href);
    const tracked = url.origin === location.origin && /^\/api\/(heatmap|account|sector-analysis)(\/|$)/.test(url.pathname);
    if (!tracked) return originalFetch.apply(this, arguments);
    const request = {id: requests.length + 1, path: url.pathname, start_ms: performance.now()};
    requests.push(request);
    if (requests.length > 300) requests.shift();
    record('fetch_start', {id: request.id, path: request.path});
    try {
      const response = await originalFetch.apply(this, arguments);
      request.headers_ms = performance.now();
      record('response_headers', {id: request.id, status: response.status, duration_ms: +(request.headers_ms - request.start_ms).toFixed(3)});
      const originalJson = response.json.bind(response);
      response.json = async () => {
        const data = await originalJson();
        request.json_ms = performance.now();
        record('json_ready', {id: request.id, duration_ms: +(request.json_ms - request.headers_ms).toFixed(3)});
        if (data.feed_timing) backend.set(data.feed_timing.trace_id, data.feed_timing);
        // Record only booleans, never account payloads, errors, tokens, or positions.
        record('status_payload', {id: request.id, connected: data.connected === true});
        return data;
      };
      return response;
    } catch (error) { record('fetch_failed', {id: request.id}); throw error; }
  };
  const selectors = '#broker-state, #account-state, #analysis-status, #screener-status, .market-status';
  const last = new WeakMap();
  const observer = new MutationObserver(() => {
    document.querySelectorAll(selectors).forEach(element => {
      const text = element.textContent;
      if (last.get(element) === text) return;
      last.set(element, text);
      // Do not capture text: status errors may contain provider details.
      const detail = {element: element.id || element.className, live_label: /connected|live fyers feed/i.test(text) && !/disconnected|unavailable/i.test(text)};
      record('status_dom_updated', detail);
      requestAnimationFrame(() => requestAnimationFrame(() => record('status_paint_opportunity', detail)));
    });
  });
  observer.observe(document.documentElement, {subtree: true, childList: true, characterData: true});
  window.feedTimingDebug = {
    report() {
      console.table(events);
      for (const trace of backend.values()) {
        console.table(trace.events.map((event, i, all) => ({...event, step_ms: +(event.elapsed_ms - (all[i - 1]?.elapsed_ms || 0)).toFixed(3)})));
      }
      return {browser: events.slice(), requests: requests.map(r => ({...r})), backend: [...backend.values()]};
    },
    download() {
      const blob = new Blob([JSON.stringify(this.report(), null, 2)], {type: 'application/json'});
      const url = URL.createObjectURL(blob), anchor = document.createElement('a');
      anchor.href = url; anchor.download = 'fyers-feed-timing.json'; anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    stop() { observer.disconnect(); window.fetch = originalFetch; }
  };
  console.info('Feed timing enabled. Run feedTimingDebug.report() or feedTimingDebug.download().');
})();
