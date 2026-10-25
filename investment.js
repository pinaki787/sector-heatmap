/* Public investment research. Codex login only; no order actions. */
(() => {
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>v==null||!Number.isFinite(Number(v))?'—':new Intl.NumberFormat('en-IN',{maximumFractionDigits:2}).format(Number(v));
const pct=v=>v==null?'—':fmt(v)+'%';
const title=v=>({QUALITY_REVIEW:'Quality review',MOMENTUM_REVIEW:'Momentum review',EXTENDED_WAIT:'Extended · wait',EXCLUDED:'Outside rules',UNAVAILABLE:'Data unavailable',RESEARCH_PRIORITY:'Research priority',WATCHLIST:'Watchlist',INSUFFICIENT_EVIDENCE:'Evidence incomplete'}[v]||v||'Not reviewed');
let output=null,active=null,newest=0;
function mount(){
 const work=document.querySelector('.work'),nav=document.querySelector('.nav'),context=window.SectorPulseWorkspace;
 if(!work||!nav||document.getElementById('investment'))return false;
 if(context&& !context.admin&&Array.isArray(context.allowed_features)&&!context.allowed_features.includes('investment'))return true;
 const navButton=document.createElement('button');navButton.type='button';navButton.dataset.view='investment';navButton.textContent='Investment';navButton.setAttribute('aria-pressed','false');nav.append(navButton);
 const section=document.createElement('section');section.id='investment';section.className='view';
 section.innerHTML=`<header class="head"><div><span class="label">EQUITY RESEARCH · 6–18 MONTH HORIZON</span><h1>Investment</h1><p class="muted">Discover strength across NSE equities. Review the business behind the breakout.</p></div><span class="status">Research only</span></header>
 <section class="panel investment-intro"><div><span class="label">TWO VIEWS · ONE EVIDENCE SET</span><h2>Price strength meets company quality</h2><p>Rules surface the shortlist. Codex reviews its strengths, risks and missing evidence using your existing login.</p></div><div class="investment-stages"><span><b>01</b> Rule screening</span><span><b>02</b> Codex review</span><span><b>03</b> Your decision</span></div></section>
 <form class="panel investment-form" id="investment-form"><div class="investment-fields"><label class="field">Analysis<select id="investment-mode"><option value="RULES_ONLY">Rule-based screening</option><option value="CODEX_CHATGPT">Rules + AI · Codex login</option></select></label><label class="field">Maximum below ATH (%)<input id="investment-distance" type="number" value="5" min="0" max="30" step="0.5" required></label><label class="field">Minimum market cap (₹ crore)<input id="investment-cap" type="number" value="1000" min="0" max="100000" required></label><label class="field">Minimum daily turnover (₹ crore)<input id="investment-turnover" type="number" value="1" min="0" max="1000" step="0.1" required></label></div><label class="field investment-symbols">Check specific symbols too<input id="investment-symbols" placeholder="For example: PASHUPATI-EQ, TECHM" maxlength="600"><small>Optional · up to 20 symbols. Includes the reasons a stock falls outside the rules.</small></label><div class="investment-actions"><button class="button" id="investment-run" type="submit">Screen NSE equities</button><button class="button secondary" id="investment-stop" type="button" hidden>Stop screening</button><button class="button secondary" id="investment-export" type="button" disabled>Export evidence</button><button class="button secondary" id="investment-saved" type="button">Saved results</button></div><p class="muted">Universe: all NSE EQ shares in the public instrument master. AI reviews up to ten candidates, with your symbol checks first. No API-key fallback.</p><p id="investment-status" role="status" aria-live="polite">Ready to screen. No research job has been submitted.</p></form>
 <div class="investment-coverage" id="investment-coverage"></div>
 <section class="panel" id="investment-ai-summary" hidden></section>
 <section class="panel"><div class="investment-result-head"><div><span class="label">INVESTMENT SHORTLIST</span><h2>Rules and AI, side by side</h2><p id="investment-asof" class="muted">Results retain their captured rules and timestamps.</p></div><label class="field">Find a candidate<input id="investment-search" type="search" placeholder="Symbol or company"></label></div><div class="table-wrap"><table class="investment-table"><thead><tr><th>Equity</th><th>Sector &amp; RS strength</th><th>Price / reported ATH</th><th>Rule assessment</th><th>Business metrics</th><th>Conditional entry plan</th><th>AI Assessment</th><th>Evidence</th></tr></thead><tbody id="investment-rows"><tr><td colspan="8" class="empty">Run a screen to discover candidates. A high price alone does not establish investment conviction.</td></tr></tbody></table></div></section>
 <section class="panel" id="investment-audit" hidden><span class="label">YOUR SYMBOL CHECKS</span><h2>Why a stock qualifies—or does not</h2><div id="investment-audit-rows"></div></section>
 <details class="panel investment-method"><summary>Screening rules and evidence limits</summary><p>Discovery requires a price within your ATH threshold, a daily price bar no older than five calendar days, minimum market cap and 30-day average volume × latest price turnover, price above both 50-day and 200-day averages, and positive 6- and 12-month returns.</p><p>Quality review adds reported ROE ≥ 15%, revenue and diluted EPS growth ≥ 10%, and positive P/E ≤ 60. These are initial research thresholds; sector suitability and financial reporting periods need review. An eligible price more than 15% above its 50-day average is marked Extended · wait.</p><p>ATH is the provider-reported available-history high. Full corporate-action-adjusted history, average slopes, cash flows, debt and sector valuation require further verification. Missing values stay unknown. No candidate is automatically labelled high conviction. A conditional entry is one exchange tick above the greater of the reported ATH and reference price. The stop is two daily ATR14 below that entry, rounded down to tick; the target is twice that rounded risk above entry (2R). These are planning levels, not a structural-stop assessment or price forecast. Fresh quote, breakout, corporate-action and liquidity checks are required before a separate investment decision.</p><p>Sector RS compares equal-weight peer-group returns with Nifty 500 over 6 and 12 months, in percentage points. Positive means outperformance. Leading requires positive RS in both windows; Lagging requires negative RS in both; otherwise Mixed. Each window requires at least five peers on the benchmark session. Unavailable or old saved results are never assigned a score. This is separate from the Sector rotation dashboard’s index-based RS score.</p><p>Jobs remain on the server when you leave this page. Stop requests retain partial results. AI receives public company evidence only and cannot place orders.</p></details>
 <dialog id="investment-detail"><div class="investment-detail-head"><h2 id="investment-detail-title">Company evidence</h2><button class="button secondary" id="investment-detail-close" type="button">Close</button></div><div id="investment-detail-body"></div></dialog>`;
 work.append(section);
 const $=id=>document.getElementById(id);
 function activate(){
  if(window.SectorPulseWorkspace?.sidebar_visibility?.investment===false)return;
  document.querySelectorAll('.nav [data-view]').forEach(b=>{const yes=b===navButton;b.classList.toggle('active',yes);b.setAttribute('aria-pressed',String(yes));});
  document.querySelectorAll('.work > .view').forEach(v=>v.classList.toggle('active',v===section));
  try{localStorage.setItem('sector-pulse:selected-view','investment');}catch{}
 }
 navButton.addEventListener('click',activate);
 if(context?.sidebar_visibility?.investment===false){navButton.hidden=true;navButton.style.display='none';section.hidden=true;section.style.display='none';}
 else if(window.SectorPulseInvestmentSelected||new URLSearchParams(location.search).get('view')==='investment'||localStorage.getItem('sector-pulse:selected-view')==='investment')activate();
 const signed=v=>v==null?'—':(v>0?'+':'')+fmt(v);
 const rsTitle=s=>({LEADING:'Leading',LAGGING:'Lagging',MIXED:'Mixed',UNAVAILABLE:'Unavailable'}[s]||'Not captured');
 function sectorCell(row){
  const sector=row.sector_strength,stock=row.relative_strength,w=sector?.windows||{};
  return '<strong>'+esc(row.sector||'Sector unavailable')+'</strong><small class="investment-rs-state">'+esc(rsTitle(sector?.status))+' sector</small><small>Sector RS · 6M '+signed(w['6m']?.excess_pp)+' pp</small><small>Sector RS · 12M '+signed(w['12m']?.excess_pp)+' pp</small><small>Stock RS · 12M '+signed(stock?.windows?.['12m'])+' pp</small><small>vs Nifty 500 · peer group</small>';
 }
 function planCell(row){
  const p=row.plan;
  if(!p||p.status==='UNAVAILABLE')return '<strong>Levels unavailable</strong><small>'+esc(p?.reason||'Not captured in this saved result. Run a new screen.')+'</small>';
  return '<strong>Entry ₹'+fmt(p.entry)+'</strong><small>Stop-loss ₹'+fmt(p.stoploss)+'</small><small>Target ₹'+fmt(p.target)+'</small><small>Reward / risk '+fmt(p.reward_risk)+':1</small><small>'+(p.status==='CONDITIONAL'?'Conditional · needs confirmation':'Outside screening rules')+'</small>';
 }
 function card(row){
  const m=row.metrics||{};
  return `<tr><td><strong>${esc(row.symbol.replace('NSE:','').replace(/-EQ$/,''))}</strong><small>${esc(row.name)}</small></td><td>${sectorCell(row)}</td><td><strong>₹${fmt(row.price)}</strong><small>ATH ₹${fmt(row.reported_ath)}</small><small>${fmt(row.distance_pct)}% below · unverified</small></td><td><span class="investment-tag ${row.rule_status==='EXTENDED_WAIT'?'wait':''}">${esc(title(row.rule_status))}</span><small>Turnover ₹${fmt(row.turnover_crore)} cr</small><small>Conviction needs verification</small></td><td><span>ROE ${pct(m.return_on_equity)} · P/E ${fmt(m.price_earnings_ttm)}</span><small>Revenue growth ${pct(m.total_revenue_yoy_growth_ttm)}</small><small>EPS growth ${pct(m.earnings_per_share_diluted_yoy_growth_ttm)}</small></td><td>${planCell(row)}</td><td><strong>${esc(row.ai?title(row.ai.classification):'Not reviewed')}</strong><small>${esc(row.ai?.rationale||'Choose Rules + AI to request a Codex login review.')}</small></td><td><button type="button" class="button secondary investment-open" data-symbol="${esc(row.symbol)}">Review</button></td></tr>`;
 }
 function render(){
  if(!output)return;
  const q=$('investment-search').value.toLowerCase(),rows=output.rows||[],c=output.coverage||{};
  $('investment-rows').innerHTML=rows.filter(r=>(r.symbol+' '+r.name).toLowerCase().includes(q)).map(card).join('')||(active?'<tr><td colspan="8" class="empty">Screening is running. Partial results will appear here.</td></tr>':'<tr><td colspan="8" class="empty">No candidates match these rules. Check a specific symbol or adjust the filters.</td></tr>');
  $('investment-coverage').innerHTML=[['NSE EQ universe',c.eq_universe],['With market data',c.screened],['Passed discovery',c.eligible],['Missing market data',c.missing]].map(([label,value])=>`<div class="panel"><span class="label">${label}</span><strong>${fmt(value)}</strong></div>`).join('');
  const date=output.created_at?new Date(output.created_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}):'—';
  $('investment-asof').textContent='Captured '+date+' IST · Showing '+(c.displayed||0)+' of '+(c.eligible||0)+' candidates · Maximum below ATH '+fmt(output.policy?.distance_pct)+'% · '+(output.policy?.mode==='CODEX_CHATGPT'?'Rules + Codex login':'Rules only');
  if(output.sector_context)$('investment-asof').textContent+=' · Sector RS vs Nifty 500 · '+(output.sector_context.benchmark_bar_at?new Date(output.sector_context.benchmark_bar_at).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata'}):'benchmark unavailable');
  const ai=$('investment-ai-summary');ai.hidden=output.ai_status==='NOT_REQUESTED';ai.innerHTML='<span class="label">CODEX LOGIN REVIEW · '+esc(output.ai_status)+'</span><h2>AI evidence assessment</h2><p>'+esc(output.ai_summary||output.ai_message||'Review is in progress; rule output is retained.')+'</p><small>'+esc((output.ai_scope||[]).join(', '))+'</small>';
  $('investment-audit').hidden=!(output.audit||[]).length;
  $('investment-audit-rows').innerHTML=(output.audit||[]).map(r=>`<article class="investment-audit-card"><div><strong>${esc(r.symbol)}</strong><span class="investment-tag">${esc(title(r.rule_status))}</span></div><p>${esc((r.reasons||[]).join(' · ')||'All discovery rules passed. Business and ATH verification remain required.')}</p><button class="button secondary investment-open" type="button" data-symbol="${esc(r.symbol)}">Review evidence</button></article>`).join('');
  $('investment-export').disabled=false;
 }
 function detail(symbol){
  const r=[...(output?.audit||[]),...(output?.rows||[])].find(r=>r.symbol===symbol);if(!r)return;
  $('investment-detail-title').textContent=r.name||r.symbol;
  $('investment-detail-body').innerHTML=`<p><b>${esc(r.symbol)}</b> · ${esc(title(r.rule_status))}</p><p>Provider daily bar: ${esc((r.market_bar_at||r.price_as_of)?new Date(r.market_bar_at||r.price_as_of).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata'}):'unavailable')}. This identifies the session, not live quote freshness. ATH verification remains incomplete.</p><h3>Sector and relative strength</h3>${sectorCell(r)}<p>RS is the return difference versus Nifty 500 in percentage points. Sector returns use an equal-weight group of current NSE EQ peers sharing the provider sector classification; this is not an official sector-index return or a 0–100 score.</p><p>Matched peers: 6M ${fmt(r.sector_strength?.windows?.['6m']?.members)} / 12M ${fmt(r.sector_strength?.windows?.['12m']?.members)} of ${fmt(r.sector_strength?.total_members)}. At least five peers and the same benchmark session are required. Stock RS 6M: ${signed(r.relative_strength?.windows?.['6m'])} pp.</p><h3>Conditional entry, stop-loss and target</h3>${planCell(r)}<p>${esc(r.plan?.method||'No plan evidence captured.')}</p><p>${esc(r.plan?.trigger||'')}</p><p>${esc(r.plan?.invalidation||'')}</p><ul>${(r.plan?.limitations||[]).map(v=>'<li>'+esc(v)+'</li>').join('')}</ul><h3>Rule evidence</h3><ul>${(r.checks||[]).map(c=>'<li>'+esc(c.name)+': <b>'+(c.passed?'Pass':'Failed or unavailable')+'</b></li>').join('')}</ul><h3>Missing verification</h3><ul>${(r.missing||[]).map(s=>'<li>'+esc(s)+'</li>').join('')}</ul><h3>AI Assessment</h3><p>${esc(r.ai?.rationale||'No AI review saved for this candidate.')}</p><ul>${(r.ai?.risks||[]).map(s=>'<li>'+esc(s)+'</li>').join('')}</ul><h3>Evidence needed</h3><ul>${(r.ai?.evidence_needed||[]).map(s=>'<li>'+esc(s)+'</li>').join('')}</ul><h3>Public financial filing</h3><p>${esc(r.filing?.reason||'No dated filing captured in this rule-only result.')}</p><p>${esc(r.filing?.period_end?'Reporting period: '+r.filing.period_end:'')}</p><dl class="investment-filing-metrics">${Object.entries(r.filing?.metrics||{}).map(([k,v])=>'<div><dt>'+esc(k.replaceAll('_',' '))+'</dt><dd>'+fmt(v)+'</dd></div>').join('')}</dl><h3>Sources</h3><ul>${[...(output.sources||[]),...(r.filing?.sources||[])].filter(s=>/^https:\/\//.test(s.url)).map(s=>'<li><a href="'+esc(s.url)+'" target="_blank" rel="noopener noreferrer">'+esc(s.title)+'</a></li>').join('')}</ul>`;
  $('investment-detail').showModal();
 }
 section.addEventListener('click',e=>{const b=e.target.closest('.investment-open');if(b)detail(b.dataset.symbol);});
 $('investment-detail-close').onclick=()=>$('investment-detail').close();
 $('investment-search').oninput=render;
 $('investment-saved').onclick=()=>window.SectorPulseJobs?.open('ANALYSIS');
 $('investment-export').onclick=()=>{
  const blob=new Blob([JSON.stringify(output,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='investment-evidence.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
 function jobEvent(event){
  const job=event.detail?.job;if(job?.feature!=='investment'||job.created<newest)return;
  newest=job.created;active=job.terminal?null:{id:job.job_id,base:event.detail.base};
  $('investment-run').disabled=!job.terminal;$('investment-stop').hidden=!!job.terminal;
  $('investment-status').textContent='Job '+job.job_id.slice(0,8)+' · '+job.status+' · '+(job.error||job.message||'');
  if(job.output?.schema==='investment/v1'){output=job.output;render();}
 }
 ['sector-pulse-job-submitted','sector-pulse-job-update','sector-pulse-job-output'].forEach(name=>window.addEventListener(name,jobEvent));
 window.addEventListener('sector-pulse-jobs-refreshed',()=>{for(const record of window.SectorPulseJobs?.records.values()||[])jobEvent({detail:{job:record.job,base:record.base}});});
 for(const record of window.SectorPulseJobs?.records.values()||[])jobEvent({detail:{job:record.job,base:record.base}});
 $('investment-stop').onclick=async()=>{
  if(!active)return;
  try{await window.SectorPulseJobs.client.cancel(active.base,active.id);}catch(e){$('investment-status').textContent=e.message;}
 };
 $('investment-form').onsubmit=async e=>{
  e.preventDefault();$('investment-run').disabled=true;
  const payload={mode:$('investment-mode').value,distance_pct:Number($('investment-distance').value),min_market_cap_crore:Number($('investment-cap').value),min_turnover_crore:Number($('investment-turnover').value),symbols:$('investment-symbols').value};
  try{
   const response=await fetch('/api/investment/analyze',{method:'POST',headers:{'Content-Type':'application/json','X-Job-Return-Accepted':'1'},body:JSON.stringify(payload)}),value=await response.json();
   if(!response.ok)throw Error(value.error||'Screening could not start.');
   if(value.schema==='investment/v1'){output=value;render();$('investment-run').disabled=false;}
  }catch(error){$('investment-status').textContent=error.message;$('investment-run').disabled=false;}
 };
 return true;
}
function start(){if(mount())return;const observer=new MutationObserver(()=>{if(mount())observer.disconnect();});observer.observe(document.body,{childList:true,subtree:true});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
