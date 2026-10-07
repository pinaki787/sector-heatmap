;(function () {
  const host = document.getElementById('trade-parser')
  if (!host) return
  const panel = document.createElement('section')
  panel.className = 'panel'
  panel.style.marginTop = '16px'
  panel.innerHTML = `<h2>WhatsApp polling</h2><p class="muted">Only the latest verified unread message is eligible. WhatsApp read state and this app’s processed IDs are checked separately; already processed messages are not retried.</p><p class="muted">Read-only recommendations → review → your fresh go-ahead. Existing FYERS parser route; no automatic orders.</p><div class="field-grid"><label class="field">Exact group name<input id="wa-group" value="Trading With Mo 2.O"></label><label class="field">Interval (seconds)<input id="wa-interval" type="number" min="30" max="3600" value="60"></label></div><div class="packet-actions" style="margin-top:12px"><button class="button secondary" id="wa-save">Save configuration</button><button class="button" id="wa-start" disabled>Start polling</button><button class="button secondary" id="wa-stop" disabled>Stop polling</button><button class="button secondary" id="wa-refresh">Refresh status</button></div><p id="wa-status" role="status">Checking polling service…</p><p id="wa-source" class="ticket-warning"></p><details><summary>Source setup and screenshot fallback</summary><p>A signed-in native WhatsApp window is not a server API connection. An installed local adapter must verify the selected group, message ID, full date/time, message body and reply/forward metadata. Screenshots showing only clock times or image-only calls are blocked until these can be verified. The native reader uses Accessibility. Unattended polling does not capture screenshots. Image-only or undated calls remain blocked; OCR alone does not certify source, time or reply context. Build the helper with scripts/whatsapp/build.sh and grant permissions to your dashboard launcher in macOS Privacy & Security. Keep using manually verified messages in the parser meanwhile.</p><p>Messages expire after five minutes. Polling always starts stopped after a restart. No WhatsApp message is sent.</p></details><h3>Recommendation review queue</h3><div id="wa-queue"></div>`
  host.appendChild(panel)
  const el = id => document.getElementById(id)
  async function api(action, body) {
    const response = await fetch('/api/whatsapp/' + action, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    if (!response.ok) {
      let error
      try { error = (await response.json()).error } catch (_) {}
      throw new Error(error || (response.status === 404 ? 'Polling backend update pending. Restart the dashboard when safe.' : 'Polling request failed.'))
    }
    return response.json()
  }
  function render(data, setConfig = false) {
    if (setConfig) { el('wa-group').value = data.config.group; el('wa-interval').value = data.config.interval }
    el('wa-status').textContent = `${data.running ? (data.error ? 'POLLING ERROR' : 'RUNNING') : 'STOPPED'} · ${data.last_poll ? 'Last poll: '+data.last_poll : 'No poll performed'}${data.error ? ' · '+data.error : ''}`
    el('wa-source').textContent = data.blocker || (data.error ? 'Reader installed; source verification failed. No recommendations ingested from this failed read.' : 'Reader installed. Source verification is checked on each poll.')
    el('wa-start').disabled = data.running || !data.source_ready
    el('wa-stop').disabled = !data.running
    el('wa-save').disabled = data.running
    el('wa-queue').replaceChildren()
    if (!data.queue.length) el('wa-queue').textContent = 'No recommendations received.'
    for (const item of data.queue) {
      const card = document.createElement('article'); card.className = 'ticket-warning'; card.style.marginTop = '10px'
      const text = document.createElement('p'); text.style.whiteSpace = 'pre-wrap'
      text.textContent = `${item.state} · ${item.group} · ${item.timestamp || 'Time unverified'}\n${item.text}\n${item.reason}`
      card.appendChild(text)
      if (item.state === 'REVIEW') {
        const review = document.createElement('button'); review.className = 'button secondary'; review.textContent = 'Recheck and load into parser'
        review.onclick = () => act(async () => {
          const result = await api('review', {id:item.id})
          const input = el('trade-parser-input'); input.value = result.text; input.dispatchEvent(new Event('input',{bubbles:true}))
          el('trade-parser-run').click() // Parsing only. Never prepare or submit.
          input.scrollIntoView({behavior:'smooth',block:'center'})
          el('wa-status').textContent = 'Loaded for review. Check exact contract and order details; fresh confirmation is still required.'
        })
        const dismiss = document.createElement('button'); dismiss.className='button secondary'; dismiss.textContent='Dismiss'
        dismiss.onclick=()=>act(async()=>render(await api('dismiss',{id:item.id})))
        card.append(review,dismiss)
      }
      el('wa-queue').appendChild(card)
    }
  }
  async function act(fn) { try { await fn() } catch (error) { el('wa-status').textContent=error.message } }
  el('wa-save').onclick=()=>act(async()=>render(await api('config',{group:el('wa-group').value,interval:Number(el('wa-interval').value)}),true))
  el('wa-start').onclick=()=>act(async()=>render(await api('start',{})))
  el('wa-stop').onclick=()=>act(async()=>render(await api('stop',{})))
  el('wa-refresh').onclick=()=>act(async()=>render(await api('status')))
  let refreshing = false
  async function refreshStatus(initial = false) {
    if (refreshing || document.hidden) return
    refreshing = true
    try { await act(async()=>render(await api('status'),initial)) } finally { refreshing = false }
  }
  void refreshStatus(true)
  window.setInterval(()=>void refreshStatus(),5000)
  document.addEventListener('visibilitychange',()=>{ if (!document.hidden) void refreshStatus() })
})()
