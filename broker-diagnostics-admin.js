/* Administrator-only per-broker controls. Server independently enforces authorization. */
(() => {
  document.addEventListener('DOMContentLoaded', () => {
    if (!window.SectorPulseWorkspace?.admin) return;
    const context = window.SectorPulseWorkspace;
    const panel = document.createElement('details');
    panel.style.cssText = 'margin:12px;padding:12px;border:1px solid #49617a;color:inherit;background:#122030';
    const summary = document.createElement('summary'); summary.textContent = 'Admin · broker delay diagnostics';
    const broker = document.createElement('select');
    for (const value of ['FYERS', 'DELTA_INDIA']) {
      if (context.workspace?.broker && context.workspace.broker !== value) continue;
      broker.add(new Option(value === 'FYERS' ? 'FYERS' : 'Delta India', value));
    }
    const duration = document.createElement('select');
    for (const value of [5, 15, 30, 60]) duration.add(new Option(`${value} minutes`, value));
    duration.value = '15';
    const label = document.createElement('p');
    label.textContent = 'Capture existing calls only. No restart or new broker request. Enable before reproducing the delay.';
    const output = document.createElement('pre'); output.style.cssText = 'overflow:auto;max-height:400px;white-space:pre-wrap';
    const events = [], payloadRequests = new WeakMap(); let active = false, selected = broker.value, expires = 0, last = performance.now(), originalFetch = window.fetch;
    const record = (operation, start, detail = {}) => {
      if (!active || Date.now() >= expires) return;
      const end = performance.now();
      const stack = new Error().stack?.split('\n').find(line => /https?:/.test(line) && !line.includes('broker-diagnostics-admin.js')) || '';
      const match = stack.match(/(https?:\/\/.*?):(\d+):(\d+)/);
      events.push({broker: selected, operation, start_utc: new Date(performance.timeOrigin + start).toISOString(),
        end_utc: new Date(performance.timeOrigin + end).toISOString(), elapsed_ms: +(end - start).toFixed(3),
        gap_from_preceding_step_ms: +(start - last).toFixed(3), script_url: match?.[1] || document.currentScript?.src || `${location.origin}/broker-diagnostics-admin.js`,
        line: match ? Number(match[2]) : null, ...detail});
      last = end; if (events.length > 1000) events.shift();
    };
    window.fetch = async function(input, options) {
      const url = new URL(input instanceof Request ? input.url : String(input), location.href);
      const delta = /^\/api\/(delta-india|renko-delta)\//.test(url.pathname);
      const observed = active && url.origin === location.origin && url.pathname.startsWith('/api/') &&
        !url.pathname.startsWith('/api/admin/') && ((selected === 'DELTA_INDIA') === delta);
      if (!observed) return originalFetch.apply(this, arguments);
      const start = performance.now(), captureBroker = selected;
      const caller = new Error().stack?.split('\n').find(line => /https?:/.test(line) && !line.includes('broker-diagnostics-admin.js'))?.match(/(https?:\/\/.*?):(\d+):(\d+)/);
      const source = {script_url: caller?.[1] || null, line: caller ? Number(caller[2]) : null};
      try {
        const response = await originalFetch.apply(this, arguments);
        const request_id = response.headers.get('X-Broker-Diagnostic-Request');
        record('fetch → headers ' + url.pathname, start, {request_id, broker: captureBroker, status: response.status, ...source});
        const originalJson = response.json.bind(response);
        response.json = async () => {
          const jsonStart = performance.now(), data = await originalJson();
          record('body read + JSON ' + url.pathname, jsonStart, {request_id, broker: captureBroker, ...source});
          if (data && typeof data === 'object') payloadRequests.set(data, request_id);
          return data;
        };
        return response;
      } catch (error) { record('fetch failed ' + url.pathname, start, {broker: captureBroker}); throw error; }
    };
    window.brokerDelayStatusCommitted = (brokerName, element, payload) => {
      if (brokerName !== selected) return;
      record('status writer committed ' + element, performance.now(), {request_id: payloadRequests.get(payload) || null});
    };
    // Observation only: DOM updates can have several contributing requests.
    const previous = new WeakMap();
    new MutationObserver(() => {
      if (!active) return;
      for (const element of document.querySelectorAll('#broker-state,#account-state,#analysis-status,#screener-status,#delta-status,.market-status')) {
        if (previous.get(element) === element.textContent) continue;
        previous.set(element, element.textContent);
        const start = performance.now(), name = element.id || element.className;
        record('status DOM observed ' + name, start, {line: null, source_note: 'MutationObserver; exact writer is not inferred'});
        requestAnimationFrame(() => requestAnimationFrame(() => record('next paint opportunity ' + name, start)));
      }
    }).observe(document.documentElement, {subtree: true, childList: true, characterData: true});
    async function api(payload) {
      const response = await originalFetch('/api/admin/broker-diagnostics' + (payload ? '' : '?broker=' + broker.value), payload ? {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
      } : {cache: 'no-store'});
      const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Diagnostic request failed');
      return data;
    }
    let latest;
    function show(data) {
      latest = data;
      output.textContent = `${data.broker}: ${data.enabled ? 'ENABLED' : 'OFF'} · ${data.remaining_seconds}s remaining · ${data.events.length} backend steps\n` +
        data.slowest_spans.map(e => `${e.elapsed_ms.toFixed(2)} ms | ${e.operation}\n${e.script_path}:${e.line}\n${e.start_utc} → ${e.end_utc} | preceding gap ${e.gap_from_preceding_step_ms ?? '—'} ms`).join('\n\n') +
        '\n\n' + data.findings.map(item => `[${item.evidence}] ${item.summary}`).join('\n') + '\n\n' + data.interpretation +
        '\n\nCHRONOLOGICAL TIMELINE (last 100 steps; export contains all retained steps)\n' +
        data.events.slice(-100).map(e => `${e.elapsed_since_capture_ms.toFixed(2)} ms from enable | ${e.operation} | ${e.outcome}\n${e.script_path}:${e.line} (${e.function})\n${e.start_utc} → ${e.end_utc || 'running'} | duration ${e.elapsed_ms ?? '—'} ms | from previous start ${e.time_from_preceding_step_start_ms ?? '—'} ms | completion gap ${e.gap_from_preceding_step_ms ?? '—'} ms | request ${e.request_id || 'see parent span'} | span ${e.span_id} / parent ${e.parent_span_id || '—'}`).join('\n\n');
    }
    function button(text, action) {
      const element = document.createElement('button'); element.type = 'button'; element.textContent = text;
      element.onclick = async () => {element.disabled = true; try {await action();} catch (e) {output.textContent = e.message;} finally {element.disabled = false;}};
      panel.append(element);
    }
    panel.append(summary, label, broker, duration);
    button('Enable capture', async () => {
      const data = await api({broker: broker.value, enabled: true, minutes: Number(duration.value)});
      events.length = 0; last = performance.now(); selected = broker.value; expires = Date.now() + data.remaining_seconds * 1000; active = true;
      broker.disabled = true; show(data);
    });
    button('Disable capture', async () => {show(await api({broker: broker.value, enabled: false})); active = false; broker.disabled = false;});
    button('Refresh report', async () => show(await api()));
    button('Export JSON', async () => {
      show(await api());
      const data = {...latest, browser_events: events.map(event => {
        let script_path = null;
        try {
          const source = new URL(event.script_url);
          if (source.origin === location.origin) script_path = latest.source_root + source.pathname;
        } catch {}
        return {...event, script_path, command_invocation: event.operation};
      }), browser_clock: 'performance.timeOrigin + performance.now; do not subtract server clock',
        screen_note: 'DOM observations are not guaranteed to belong to a single request. Paint events are opportunities, not physical screen paint.'};
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'}));
      const a = document.createElement('a'); a.href = url; a.download = `broker-delay-${broker.value}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    panel.append(output); document.body.append(panel);
    broker.onchange = () => {events.length = 0; api().then(show).catch(e => {output.textContent = e.message;});};
    api().then(show).catch(e => {output.textContent = e.message;});
  });
})();
