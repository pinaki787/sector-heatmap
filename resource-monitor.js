/* Server resource telemetry: read-only, permission gated, visible-section polling only. */
(() => {
  'use strict';
  function mount() {
    const context = window.SectorPulseWorkspace, work = document.querySelector('.work'), nav = document.querySelector('.nav');
    if (!work || !nav || !context || (!context.admin && !context.allowed_features?.includes('resources'))) return;
    const visible = context.sidebar_visibility?.resources !== false;
    const button = document.createElement('button'); button.type = 'button'; button.dataset.view = 'resources'; button.textContent = 'Server resources'; button.hidden = !visible;
    nav.append(button);
    const section = document.createElement('section'); section.id = 'resources'; section.className = 'view'; section.hidden = !visible;
    section.innerHTML = `<header class="head"><div><span class="label">SERVER CAPACITY \u00b7 READ ONLY</span><h1>Server resources</h1><p class="muted">See what the server is using, what is available, and where delays may come from.</p></div><button type="button" class="button" id="resource-refresh">Refresh</button></header>
      <p id="resource-status" role="status" aria-live="polite">Open this view to read server telemetry.</p><div id="resource-alerts"></div><div class="resource-cards" id="resource-cards"></div>
      <section class="panel"><div class="head"><div><h2>Recorded utilisation</h2><p class="muted" id="resource-coverage"></p></div><label>History <select id="resource-range"><option value="24">Last 24 hours</option><option value="0">All retained records</option></select></label></div><div id="resource-charts"></div><p class="muted" id="resource-method"></p></section>
      <section class="panel resource-explain"><h2>How to read this server</h2><div class="resource-guide"><article><h3>CPU: work versus waiting</h3><p>CPU work is processing time across all cores. 100% means all cores are busy. I/O wait means waiting for storage. Steal means the virtual host has not given this server the CPU time it requested. Non-idle combines these; it can overstate actual work.</p><p>Look for sustained CPU work above 80%, or repeated wait/steal above 5%. These are investigation guides, not proof of a bottleneck.</p></article><article><h3>Memory: available matters</h3><p>Linux uses spare RAM to cache files and can reclaim much of it. The live card uses total minus available memory. Historical sysstat memory uses its own used-memory definition, so the percentages can differ slightly.</p><p>Less than 15% available deserves attention. No swap means there is no swap fallback if RAM runs out.</p></article><article><h3>Load and disk</h3><p>Load counts tasks running or waiting, including storage waits. Compare load with the number of cores; sustained load above that count can indicate queued work.</p><p>Disk percentage measures space, not speed. Above 85% warrants a storage review. A free disk can still have slow I/O.</p></article></div></section>
      <section class="panel resource-explain"><h2>Largest memory consumers now</h2><p class="muted">Resident memory per process; shared pages can be counted more than once. CPU here is a lifetime average per process (100% = one core), not the live server sample.</p><div class="table-wrap"><table class="resource-table"><thead><tr><th>Process</th><th>Resident memory</th><th>Lifetime CPU</th></tr></thead><tbody id="resource-processes"></tbody></table></div></section>`;
    work.append(section);
    const css = document.createElement('style'); css.textContent = `#resources{--resource-blue:#84c8f5;--resource-gold:#e8bd70;--resource-lilac:#b9a6e8}#resources p{line-height:1.65}#resources .resource-cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:20px 0}#resources .resource-card{padding:20px;background:var(--surface);border:1px solid var(--border);border-top:3px solid var(--resource-blue);border-radius:12px}#resources .resource-card strong{display:block;font:600 32px ui-monospace,monospace;margin:12px 0}#resources .resource-card p{font-size:12px;color:var(--muted)}#resources meter{width:100%;height:12px}#resources .resource-guide{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}#resources .resource-explain{margin-top:18px}#resources .resource-table{min-width:500px}#resources .resource-chart{margin-top:24px;position:relative}#resources .resource-tooltip{position:absolute;z-index:2;top:42px;max-width:300px;padding:10px 13px;background:#071321;color:#edf4ff;border:1px solid #84c8f5;border-radius:8px;box-shadow:0 4px 18px #0006;pointer-events:none;font:13px/1.6 ui-monospace,monospace;white-space:pre-line}#resources svg:focus-visible{outline:2px solid #84c8f5;outline-offset:3px}#resources svg{width:100%;height:150px;display:block}#resources .resource-chart-head{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}#resources .resource-notice{border-left:3px solid var(--resource-gold);padding:10px 15px;background:var(--surface)}#resources select{background:var(--surface);color:inherit;padding:8px;border:1px solid var(--border);border-radius:6px}#resources button:focus-visible,#resources select:focus-visible{outline:3px solid var(--resource-blue);outline-offset:3px}@media(max-width:1000px){#resources .resource-cards{grid-template-columns:repeat(2,minmax(0,1fr))}#resources .resource-guide{grid-template-columns:1fr}}@media(max-width:500px){#resources .resource-cards{grid-template-columns:1fr}}`;
    document.head.append(css);
    const $ = id => document.getElementById('resource-'+id);
    const esc = v => String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const size = v => (v/1024**3).toFixed(2)+' GiB';
    const time = v => new Date(v).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})+' IST';
    let data, busy = false;
    function charts() {
      if (!data) return;
      const hours = Number($('range').value), all = data.history.rows;
      const end = all.length ? Date.parse(all.at(-1).time) : Date.now();
      const rows = all.filter(r => !hours || Date.parse(r.time)>=end-hours*3600000);
      $('coverage').textContent = rows.length ? `${rows.length} records \u00b7 ${time(rows[0].time)} \u2192 ${time(rows.at(-1).time)} \u00b7 timestamps in IST` : 'No retained historical records.';
      $('method').textContent = data.history.interval_note + ' History is reread every 5 minutes. Disk card is current only.';
      $('charts').innerHTML = [['cpu','CPU work','#84c8f5'],['memory','Memory used (sysstat)','#b9a6e8'],['steal','Hypervisor steal','#e8bd70'],['iowait','Storage wait','#91d7c1']].map(([key,label,color])=>{
        const series=rows.filter(r=>Number.isFinite(r[key]));
        if(!series.length)return `<div class="resource-chart"><b>${label}</b><p>History unavailable.</p></div>`;
        const peak=series.reduce((a,b)=>a[key]>b[key]?a:b), first=Date.parse(rows[0].time), span=Math.max(1,end-first);
        const points=series.map(r=>`${30+(Date.parse(r.time)-first)/span*950},${125-r[key]*1.1}`).join(' ');
        return `<div class="resource-chart"><div class="resource-chart-head"><b>${label}</b><span>Peak in range ${peak[key].toFixed(2)}% \u00b7 ${esc(time(peak.time))}</span></div><svg data-resource-key="${key}" tabindex="0" viewBox="0 0 1000 145" preserveAspectRatio="none" role="img" aria-label="${label} from ${esc(time(series[0].time))} to ${esc(time(series.at(-1).time))}; peak ${peak[key]} percent. Hover or use left and right arrow keys to inspect recorded samples."><text x="0" y="18" fill="#aabdd0" font-size="12">100%</text><text x="0" y="138" fill="#aabdd0" font-size="12">0%</text><path d="M30 15H980 M30 70H980 M30 125H980" stroke="#36516f" fill="none"/><polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/><g class="resource-cursor" visibility="hidden"><line y1="15" y2="125" stroke="#edf4ff" stroke-dasharray="3 3"/><circle r="4" fill="${color}" stroke="#edf4ff" vector-effect="non-scaling-stroke"/></g></svg><div class="resource-tooltip" role="tooltip" hidden></div></div>`;
      }).join('');
      for (const svg of $('charts').querySelectorAll('svg[data-resource-key]')) {
        const key = svg.dataset.resourceKey, series = rows.filter(r => Number.isFinite(r[key]));
        const chart = svg.closest('.resource-chart'), tooltip = chart.querySelector('.resource-tooltip');
        const cursor = svg.querySelector('.resource-cursor'), line = cursor.querySelector('line'), dot = cursor.querySelector('circle');
        let selected = series.length - 1;
        function show(index) {
          selected = Math.max(0, Math.min(series.length - 1, index));
          const row = series[selected], first = Date.parse(rows[0].time), span = Math.max(1, end - first);
          const x = 30 + (Date.parse(row.time) - first) / span * 950;
          line.setAttribute('x1', x); line.setAttribute('x2', x);
          dot.setAttribute('cx', x); dot.setAttribute('cy', 125 - row[key] * 1.1);
          cursor.setAttribute('visibility', 'visible');
          const stamp = new Date(row.time).toLocaleString('en-IN', {timeZone:'Asia/Kolkata',year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
          const label = chart.querySelector('.resource-chart-head b').textContent;
          tooltip.textContent = `${stamp} IST\n${label}: ${row[key].toFixed(2)}%\nRecorded sample (nearest point)`;
          tooltip.hidden = false;
          const chartWidth = chart.clientWidth, pixelX = x / 1000 * svg.clientWidth;
          tooltip.style.left = Math.max(0, Math.min(pixelX + 12, chartWidth - tooltip.offsetWidth)) + 'px';
        }
        function hide() {tooltip.hidden = true; cursor.setAttribute('visibility', 'hidden');}
        svg.addEventListener('pointermove', event => {
          const bounds = svg.getBoundingClientRect();
          const fraction = Math.max(0, Math.min(1, ((event.clientX - bounds.left) / bounds.width * 1000 - 30) / 950));
          const target = Date.parse(rows[0].time) + fraction * Math.max(1, end - Date.parse(rows[0].time));
          let nearest = 0;
          for (let i = 1; i < series.length; i++) if (Math.abs(Date.parse(series[i].time) - target) < Math.abs(Date.parse(series[nearest].time) - target)) nearest = i;
          show(nearest);
        });
        svg.addEventListener('pointerleave', hide);
        svg.addEventListener('focus', () => show(selected));
        svg.addEventListener('blur', hide);
        svg.addEventListener('keydown', event => {
          if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {event.preventDefault(); show(selected + (event.key === 'ArrowLeft' ? -1 : 1));}
          if (event.key === 'Escape') hide();
        });
      }
    }
    function render() {
      const d=data, m=d.memory, c=d.cpu;
      $('cards').innerHTML = [
        ['CPU work',c.cpu+'%',c.cpu,`${d.cores} cores \u00b7 idle ${c.idle}%`,`Steal ${c.steal}% \u00b7 storage wait ${c.iowait}% \u00b7 non-idle ${c.non_idle}%`],
        ['Memory',m.used_pct+'%',m.used_pct,`${size(m.used)} of ${size(m.total)}`,`${size(m.available)} available \u00b7 ${size(m.cache)} file cache \u00b7 swap ${size(m.swap_used)} / ${size(m.swap_total)}`],
        ['Root disk',d.disk.used_pct+'%',d.disk.used_pct,`${size(d.disk.used)} of ${size(d.disk.total)}`,`${size(d.disk.free)} free \u00b7 current capacity, not disk speed`],
        ['Load / cores',d.load[0].toFixed(2)+' / '+d.cores,Math.min(100,d.load[0]/d.cores*100),'1-minute load versus CPU count',`5-minute ${d.load[1].toFixed(2)} \u00b7 15-minute ${d.load[2].toFixed(2)} \u00b7 uptime ${(d.uptime_seconds/86400).toFixed(1)} days`]
      ].map(([label,value,pct,detail,note])=>`<article class="resource-card"><span>${label}</span><strong>${value}</strong><meter min="0" max="100" value="${pct}" aria-label="${label}"></meter><p>${detail}</p><p>${note}</p></article>`).join('');
      $('alerts').innerHTML = [...d.warnings,...d.history.errors].map(v=>`<p class="resource-notice">${esc(v)}</p>`).join('') || '<p class="muted">This sample is below the investigation thresholds. Check trends before drawing a capacity conclusion.</p>';
      $('processes').innerHTML=d.processes.map(p=>`<tr><td>${esc(p.name)}</td><td>${size(p.rss_bytes)}</td><td>${p.cpu_lifetime_pct.toFixed(1)}%</td></tr>`).join('');
      $('status').textContent=`${d.hostname} \u00b7 sampled ${time(d.as_of)} \u00b7 short CPU sample \u00b7 refresh every 30 seconds while visible \u00b7 server cache 15 seconds`;
      charts();
    }
    async function refresh() {
      if (busy || section.hidden || !section.classList.contains('active') || document.hidden) return;
      busy=true; $('refresh').disabled=true;
      try {
        const response=await fetch('/api/resources',{cache:'no-store',signal:AbortSignal.timeout(20000)}), result=await response.json();
        if(!response.ok)throw Error(result.error||'Resource telemetry unavailable');
        data=result;render();
      } catch(e) {$('status').textContent=`Refresh failed: ${e.message}. ${data?'Displayed values are stale; last sample '+time(data.as_of)+'.':'No sample available.'}`;}
      finally {busy=false;$('refresh').disabled=false;}
    }
    button.onclick=()=>{
      if(section.hidden)return;
      document.querySelectorAll('.nav [data-view]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});
      document.querySelectorAll('.work > .view').forEach(v=>v.classList.toggle('active',v===section));
      try{localStorage.setItem('sector-pulse:selected-view','resources');}catch{}
      refresh();
    };
    $('refresh').onclick=refresh;$('range').onchange=charts;
    setInterval(refresh,30000); document.addEventListener('visibilitychange',refresh);
    try{if(visible&&localStorage.getItem('sector-pulse:selected-view')==='resources')button.click();}catch{}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
