/* Public investment research. Codex login only; no order actions. */
(() => {
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=v=>v==null||!Number.isFinite(Number(v))?'—':new Intl.NumberFormat('en-IN',{maximumFractionDigits:2}).format(Number(v));
const pct=v=>v==null?'—':fmt(v)+'%';
const title=v=>({QUALITY_REVIEW:'Quality review',MOMENTUM_REVIEW:'Momentum review',EXTENDED_WAIT:'Extended · wait',EXCLUDED:'Outside rules',UNAVAILABLE:'Data unavailable',RESEARCH_PRIORITY:'Research priority',WATCHLIST:'Watchlist',INSUFFICIENT_EVIDENCE:'Evidence incomplete'}[v]||v||'Not reviewed');
const periods={'6': 'Perf.6M','12': 'Perf.Y'};
const yearChoices=Array.from({length:10},(_,index)=>index+1);
const horizonLabel=period=>period.endsWith('y')?period.slice(0,-1)+'Y':period+'M';
const annualWindow=(row,period)=>row.annual_returns?.[period.slice(0,-1)];
const returnValue=(row,period)=>period.endsWith('y')?annualWindow(row,period)?.return_pct:row.metrics?.[periods[period]];
function growth(row,period){
 const value=returnValue(row,period);
 if(!Number.isFinite(value)||value < -100)return null;
 const years=period.endsWith('y')?Number(period.slice(0,-1)):Number(period)/12;
 return years===1?value:100*Math.expm1(Math.log1p(value/100)/years);
}
const pageSize=25;
let output=null,active=null,newest=0,page=0,jobId=null;
const selected=new Set();
const preferenceKey='sector-pulse:investment-sort';

function mount(){
 const work=document.querySelector('.work'),nav=document.querySelector('.nav'),context=window.SectorPulseWorkspace;
 if(!work||!nav||document.getElementById('investment'))return false;
 if(context&& !context.admin&&Array.isArray(context.allowed_features)&&!context.allowed_features.includes('investment'))return true;
 const navButton=document.createElement('button');navButton.type='button';navButton.dataset.view='investment';navButton.textContent='Investment';navButton.setAttribute('aria-pressed','false');
 // Investment belongs with the primary research views, before parser/asset groups.
 const researchAnchor=nav.querySelector('[data-view="screener"]')||nav.querySelector('[data-view="sectors"]');
 if(researchAnchor)researchAnchor.after(navButton);else nav.prepend(navButton);
 const section=document.createElement('section');section.id='investment';section.className='view';
 section.innerHTML=`<header class="head"><div><span class="label">EQUITY RESEARCH · 6–18 MONTH HORIZON</span><h1>Investment</h1><p class="muted">Discover strength across NSE equities. Review the business behind the breakout.</p></div><span class="status">Research only</span></header>
 <section class="panel investment-form"><label class="field" for="investment-default-broker">Delivery broker account<select id="investment-default-broker"></select></label><p class="muted">Default for equity entry reviews. Equity-specific account selections take precedence.</p></section>
 <section class="panel investment-intro"><div><span class="label">TWO VIEWS · ONE EVIDENCE SET</span><h2>Price strength meets company quality</h2><p>Rules surface the shortlist. Codex reviews its strengths, risks and missing evidence using your existing login.</p></div><div class="investment-stages"><span><b>01</b> Rule screening</span><span><b>02</b> Codex review</span><span><b>03</b> Your decision</span></div></section>
 <form class="panel investment-form" id="investment-form"><div class="investment-fields"><label class="field">Analysis<select id="investment-mode"><option value="RULES_ONLY">Rule-based screening</option><option value="CODEX_CHATGPT">Rules + AI · Codex login</option></select></label><label class="field">Maximum below ATH (%)<input id="investment-distance" type="number" value="5" min="0" max="30" step="0.5" required></label><label class="field">Minimum market cap (₹ crore)<input id="investment-cap" type="number" value="1000" min="0" max="100000" required></label><label class="field">Minimum daily turnover (₹ crore)<input id="investment-turnover" type="number" value="1" min="0" max="1000" step="0.1" required></label></div><label class="field investment-symbols">Check specific symbols too<input id="investment-symbols" placeholder="For example: PASHUPATI-EQ, TECHM" maxlength="600"><small>Optional · up to 20 symbols. Includes the reasons a stock falls outside the rules.</small></label><div class="investment-actions"><button class="button" id="investment-run" type="submit">Screen NSE equities</button><button class="button secondary" id="investment-stop" type="button" hidden>Stop screening</button><button class="button secondary" id="investment-export" type="button" disabled>Export evidence</button><button class="button secondary" id="investment-saved" type="button">Saved results</button></div><p class="muted">Universe: all NSE EQ shares in the public instrument master. AI reviews up to ten candidates, with your symbol checks first. No API-key fallback.</p><p id="investment-status" role="status" aria-live="polite">Ready to screen. No research job has been submitted.</p></form>
 <div class="investment-coverage" id="investment-coverage"></div>
 <section class="panel" id="investment-ai-summary" hidden></section>
 <section class="panel"><div class="investment-result-head"><div><span class="label">INVESTMENT SHORTLIST</span><h2>Rules and AI, side by side</h2><p id="investment-asof" class="muted">Results retain their captured rules and timestamps.</p></div><div class="investment-result-controls">
 <label class="field">Find a candidate<input id="investment-search" type="search" placeholder="Symbol or company"></label>
 <label class="field">Return period<select id="investment-period"><option value="12">12 months</option><option value="6">6 months</option><optgroup label="Annual price history">${yearChoices.map(year=>`<option value="${year}y">${year} ${year===1?'year':'years'}</option>`).join('')}</optgroup></select></label>
 <label class="field">Sort by<select id="investment-sort"><option value="">Screening rank</option><option value="return-desc">Return · highest first</option><option value="return-asc">Return · lowest first</option><option value="cagr-desc">CAGR · highest first</option><option value="cagr-asc">CAGR · lowest first</option></select></label>
 </div></div><div class="investment-results-actions"><button class="button secondary" type="button" id="investment-xlsx" disabled>Download Excel</button><button class="button secondary" type="button" id="investment-clear" disabled>Clear selection</button><span id="investment-selection" role="status">0 selected</span></div><div class="table-wrap"><table class="investment-table"><thead><tr><th>Equity</th><th>Sector &amp; RS strength</th><th>Price / reported ATH</th><th>Rule assessment</th><th>Business metrics</th><th>Daily technical entry</th><th>AI Assessment</th><th>Evidence</th></tr></thead><tbody id="investment-rows"><tr><td colspan="8" class="empty">Run a screen to discover candidates. A high price alone does not establish investment conviction.</td></tr></tbody></table></div><div class="investment-results-actions investment-pages" hidden><button class="button secondary" type="button" id="investment-prev">Previous</button><span id="investment-page" aria-live="polite"></span><button class="button secondary" type="button" id="investment-next">Next</button></div></section>
 <section class="panel" id="investment-audit" hidden><span class="label">YOUR SYMBOL CHECKS</span><h2>Why a stock qualifies—or does not</h2><div id="investment-audit-rows"></div></section>
 <details class="panel investment-method"><summary>Screening rules and evidence limits</summary><p>Discovery requires a price within your ATH threshold, a daily price bar no older than five calendar days, minimum market cap and 30-day average volume × latest price turnover, price above both 50-day and 200-day averages, and positive 6- and 12-month returns.</p><p>Quality review adds reported ROE ≥ 15%, revenue and diluted EPS growth ≥ 10%, and positive P/E ≤ 60. These are initial research thresholds; sector suitability and financial reporting periods need review. An eligible price more than 15% above its 50-day average is marked Extended · wait.</p><p>ATH is the provider-reported available-history high. Full corporate-action-adjusted history, average slopes, cash flows, debt and sector valuation require further verification. Missing values stay unknown. No candidate is automatically labelled high conviction. A conditional entry is one exchange tick above the greater of the reported ATH and reference price. The stop is two daily ATR14 below that entry, rounded down to tick; the target is twice that rounded risk above entry (2R). These are planning levels, not a structural-stop assessment or price forecast. Fresh quote, breakout, corporate-action and liquidity checks are required before a separate investment decision.</p><p>Daily Fib levels use a confirmed swing low within six months. When there is no valid confirmed swing high, the levels use the highest completed daily high after that low and show Developing high. A pivot requires five completed bars on either side. A break of the swing low requires a new confirmed low. The 50% and 56% buy levels are measured down from the swing high as a share of the high-to-low range.</p><p>Sector RS compares equal-weight peer-group returns with Nifty 500 over 6 and 12 months, in percentage points. Positive means outperformance. Leading requires positive RS in both windows; Lagging requires negative RS in both; otherwise Mixed. Each window requires at least five peers on the benchmark session. Unavailable or old saved results are never assigned a score. This is separate from the Sector rotation dashboard’s index-based RS score.</p><p>The month options use scanner performance. Year options use daily closes at the latest completed session and on or before the selected calendar anniversary. Annual history excludes dividends and requires a close within seven days of the anniversary.</p><p>Jobs remain on the server when you leave this page. Stop requests retain partial results. AI receives public company evidence only and cannot place orders.</p></details>
 <dialog id="investment-detail"><div class="investment-detail-head"><h2 id="investment-detail-title">Company evidence</h2><div class="investment-results-actions"><button class="button secondary" id="investment-report" type="button">Download report</button><button class="button secondary" id="investment-detail-close" type="button">Close</button></div></div><p id="investment-report-status" role="status"></p><div class="investment-form panel" id="investment-holding-account"><label class="field" for="investment-broker">Delivery broker account<select id="investment-broker" aria-describedby="investment-broker-status"></select></label><small id="investment-broker-status" role="status"></small><div class="investment-fields" id="investment-entry-fields" hidden><label class="field">Daily Fib level<select id="investment-entry-level"><option value="">Choose a level</option></select></label><label class="field">Target shares<input id="investment-entry-quantity" type="number" min="1" step="1" inputmode="numeric"></label></div><div class="investment-results-actions" id="investment-entry-actions" hidden><button class="button secondary" id="investment-entry-preview" type="button">Review entry monitor</button><button class="button secondary" id="investment-entry-stop" type="button" hidden>Stop monitoring</button></div><p id="investment-entry-status" role="status"></p><div id="investment-entry-confirmation" hidden><p id="investment-entry-terms"></p><label class="field">Confirmation<input id="investment-entry-phrase" type="text" autocomplete="off"></label><button class="button" id="investment-entry-enable" type="button">Enable live entry monitoring</button></div></div><div id="investment-detail-body"></div></dialog>`;
 work.append(section);
 const $=id=>document.getElementById(id);
 const sort=$('investment-sort'),period=$('investment-period');
 try{
  const saved=JSON.parse(localStorage.getItem(preferenceKey));
  for(const [control,value] of [[sort,saved?.sort],[period,saved?.period]]){
   if(Array.from(control.options).some(option=>option.value===value))control.value=value;
  }
 }catch{}
 function selectionStatus(){
  $('investment-selection').textContent=selected.size+' selected';
  $('investment-xlsx').disabled=$('investment-clear').disabled=!selected.size;
 }
 function returnsText(row){
  return [
   horizonLabel(period.value)+' return '+pct(returnValue(row,period.value)),
   horizonLabel(period.value)+' CAGR '+pct(growth(row,period.value)),
  ];
 }
 function activate(){
  if(window.SectorPulseWorkspace?.sidebar_visibility?.investment===false)return;
  document.querySelectorAll('.nav [data-view]').forEach(b=>{const yes=b===navButton;b.classList.toggle('active',yes);b.setAttribute('aria-pressed',String(yes));});
  document.querySelectorAll('.work > .view').forEach(v=>v.classList.toggle('active',v===section));
  try{localStorage.setItem('sector-pulse:selected-view','investment');}catch{}
 }
 navButton.addEventListener('click',activate);
 if(context?.sidebar_visibility?.investment===false){navButton.hidden=true;navButton.style.display='none';section.hidden=true;section.style.display='none';}
 else {
  const linkedView=new URLSearchParams(location.search).get('view');
  if(linkedView==='investment'||linkedView!=='chart-workspace'&&(window.SectorPulseInvestmentSelected||localStorage.getItem('sector-pulse:selected-view')==='investment'))activate();
 }
 const signed=v=>v==null?'—':(v>0?'+':'')+fmt(v);
 const rsTitle=s=>({LEADING:'Leading',LAGGING:'Lagging',MIXED:'Mixed',UNAVAILABLE:'Unavailable'}[s]||'Not captured');
 function sectorCell(row){
  const sector=row.sector_strength,stock=row.relative_strength,w=sector?.windows||{};
  return '<strong>'+esc(row.sector||'Sector unavailable')+'</strong><small class="investment-rs-state">'+esc(rsTitle(sector?.status))+' sector</small><small>Sector RS · 6M '+signed(w['6m']?.excess_pp)+' pp</small><small>Sector RS · 12M '+signed(w['12m']?.excess_pp)+' pp</small><small>Stock RS · 12M '+signed(stock?.windows?.['12m'])+' pp</small><small>vs Nifty 500 · peer group</small>';
 }
 function pullbackCell(row){
  const level=row.daily_pullback;
  if(level?.price_50==null||level?.price_56==null)return '<strong>Daily Fib level unavailable</strong><small>'+esc(level?.reason||'Daily swing analysis is pending or was not captured. Run a fresh screen for older results.')+'</small>';
  return '<strong>50% · ₹'+fmt(level.price_50)+'</strong><small>56% · ₹'+fmt(level.price_56)+'</small>'+(level.swing_high_status==='DEVELOPING'?'<small>Developing high</small>':'');
 }
 function planCell(row){
  const p=row.plan;
  if(!p||p.status==='UNAVAILABLE')return '<strong>Levels unavailable</strong><small>'+esc(p?.reason||'Not captured in this saved result. Run a new screen.')+'</small>';
  return '<strong>Breakout entry ₹'+fmt(p.entry)+'</strong><small>Stop-loss ₹'+fmt(p.stoploss)+'</small><small>Target ₹'+fmt(p.target)+'</small><small>Reward / risk '+fmt(p.reward_risk)+':1</small><small>'+(p.status==='CONDITIONAL'?'Conditional · needs confirmation':'Outside screening rules')+'</small>';
 }
 function card(row){
  const m=row.metrics||{};
  return `<tr><td><label class="investment-pick"><input type="checkbox" class="investment-select" value="${esc(row.symbol)}" ${selected.has(row.symbol)?'checked':''}><span class="investment-sr-only">Select ${esc(row.symbol)}</span></label><strong>${esc(row.symbol.replace('NSE:','').replace(/-EQ$/,''))}</strong><small>${esc(row.name)}</small></td><td>${sectorCell(row)}</td><td><strong>₹${fmt(row.price)}</strong><small>ATH ₹${fmt(row.reported_ath)}</small><small>${fmt(row.distance_pct)}% below · unverified</small>${returnsText(row).map(text=>'<small>'+text+'</small>').join('')}</td><td><span class="investment-tag ${row.rule_status==='EXTENDED_WAIT'?'wait':''}">${esc(title(row.rule_status))}</span><small>Turnover ₹${fmt(row.turnover_crore)} cr</small><small>Conviction needs verification</small></td><td><span>ROE ${pct(m.return_on_equity)} · P/E ${fmt(m.price_earnings_ttm)}</span><small>Revenue growth ${pct(m.total_revenue_yoy_growth_ttm)}</small><small>EPS growth ${pct(m.earnings_per_share_diluted_yoy_growth_ttm)}</small></td><td>${pullbackCell(row)}</td><td><strong>${esc(row.ai?title(row.ai.classification):'Not reviewed')}</strong><small>${esc(row.ai?.rationale||'Choose Rules + AI to request a Codex login review.')}</small></td><td><button type="button" class="button secondary investment-open" data-symbol="${esc(row.symbol)}">Review</button></td></tr>`;
 }
 function render(){
  if(!output)return;
  const q=$('investment-search').value.trim().toLowerCase(),rows=output.rows||[],c=output.coverage||{};
  const filtered=rows.filter(row=>(row.symbol+' '+row.name).toLowerCase().includes(q));
  if(sort.value){
   const [metric,direction]=sort.value.split('-');
   const value=metric==='cagr'?growth:returnValue;
   const sign=direction==='asc'?1:-1;
   filtered.sort((a,b)=>{
    const x=value(a,period.value),y=value(b,period.value);
    if(!Number.isFinite(x))return Number.isFinite(y)?1:0;
    if(!Number.isFinite(y))return -1;
    return sign*(x-y);
   });
  }
  const pages=Math.max(1,Math.ceil(filtered.length/pageSize));
  page=Math.min(page,pages-1);
  const start=page*pageSize;
  const visible=filtered.slice(start,start+pageSize);
  $('investment-rows').innerHTML=visible.map(card).join('')||(active?'<tr><td colspan="8" class="empty">Screening is running. Partial results will appear here.</td></tr>':'<tr><td colspan="8" class="empty">No candidates match these rules. Check a specific symbol or adjust the filters.</td></tr>');
  $('investment-prev').disabled=page===0;
  $('investment-next').disabled=page+1===pages;
  $('investment-prev').parentElement.hidden=pages===1;
  $('investment-page').textContent=(start+1)+'–'+(start+visible.length)+' of '+filtered.length;
  selectionStatus();
  $('investment-coverage').innerHTML=[['NSE EQ universe',c.eq_universe],['With market data',c.screened],['Passed discovery',c.eligible],['Missing market data',c.missing]].map(([label,value])=>`<div class="panel"><span class="label">${label}</span><strong>${fmt(value)}</strong></div>`).join('');
  const date=output.created_at?new Date(output.created_at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}):'—';
  $('investment-asof').textContent='Captured '+date+' IST · Showing '+(c.displayed||0)+' of '+(c.eligible||0)+' candidates · Maximum below ATH '+fmt(output.policy?.distance_pct)+'% · '+(output.policy?.mode==='CODEX_CHATGPT'?'Rules + Codex login':'Rules only');
  if(output.sector_context)$('investment-asof').textContent+=' · Sector RS vs Nifty 500 · '+(output.sector_context.benchmark_bar_at?new Date(output.sector_context.benchmark_bar_at).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata'}):'benchmark unavailable');
  const ai=$('investment-ai-summary');ai.hidden=output.ai_status==='NOT_REQUESTED';ai.innerHTML='<span class="label">CODEX LOGIN REVIEW · '+esc(output.ai_status)+'</span><h2>AI evidence assessment</h2><p>'+esc(output.ai_summary||output.ai_message||'Review is in progress; rule output is retained.')+'</p><small>'+esc((output.ai_scope||[]).join(', '))+'</small>';
  $('investment-audit').hidden=!(output.audit||[]).length;
  $('investment-audit-rows').innerHTML=(output.audit||[]).map(r=>`<article class="investment-audit-card"><div><strong>${esc(r.symbol)}</strong><span class="investment-tag">${esc(title(r.rule_status))}</span></div><p>${esc((r.reasons||[]).join(' · ')||'All discovery rules passed. Business and ATH verification remain required.')}</p><button class="button secondary investment-open" type="button" data-symbol="${esc(r.symbol)}">Review evidence</button></article>`).join('');
  if(period.value.endsWith('y')){
   const withHistory=filtered.filter(row=>Number.isFinite(returnValue(row,period.value))).length;
   $('investment-asof').textContent+=' · '+horizonLabel(period.value)+' history available for '+withHistory+' of '+filtered.length+' matching candidates';
   if(rows.length&&!rows.some(row=>row.annual_returns)&&!active)$('investment-asof').textContent+=' · Run a new screen to collect annual history.';
  }
  if(c.eligible>rows.length)$('investment-asof').textContent+=' · This result contains a limited shortlist. Run a new screen for current coverage.';
  window.SectorPulseSeasonality?.investment(section,{rows:visible,audit:output.audit});
  $('investment-export').disabled=false;
 }
 let reviewedSymbol=null,reviewedRow=null,entryPreview=null,entryJob=null;
 const entryStatus=$('investment-entry-status');
 const entryLevel=$('investment-entry-level');
 const entryQuantity=$('investment-entry-quantity');
 const entrySupport=()=> (window.BrokerForms?.accounts()||[]).find(row=>row.id===deliveryBroker.value)?.broker==='DHAN';
 const entryIdentity=()=>({symbol:reviewedSymbol,account_id:deliveryBroker.value});
 const sameEntry=selection=>reviewedSymbol===selection.symbol&&deliveryBroker.value===selection.account_id;
 async function entryRequest(action,selection,fields={}){
  const headers={'Content-Type':'application/json'};
  if(window.SectorPulseWorkspace?.csrf)headers['X-CSRF-Token']=window.SectorPulseWorkspace.csrf;
  const response=await fetch('/api/investment/entry-monitor/'+action,{
   method:'POST',headers,body:JSON.stringify({...selection,...fields})
  });
  const result=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(result.error||'Entry monitoring is unavailable in this workspace.');
  return result;
 }
 function clearEntryPreview(){
  entryPreview=null;$('investment-entry-confirmation').hidden=true;$('investment-entry-phrase').value='';
 }
 function renderEntryJob(job){
  entryJob=job;
  const activeJob=!!job&&!job.terminal;
  $('investment-entry-preview').hidden=activeJob;
  $('investment-entry-stop').hidden=!activeJob;
  $('investment-entry-stop').disabled=job?.status==='CANCELLING';
  if(!job){entryStatus.textContent=entryLevel.options.length>1?'Checks run at market open and after close.':'A fresh Investment result with daily Fib prices is required for a new monitor.';return;}
  const state=job.output;
  const stopping=job.status==='CANCELLED'||job.status==='CANCELLING';
  const filled=state?.plan?' · '+fmt(state.filled)+' / '+fmt(state.plan.quantity)+' shares filled':'';
  const details=stopping?'Existing broker orders and holdings stay in place.':state?.reason||job.error||job.message||'';
  entryStatus.textContent=title(job.status==='COMPLETED'?state?.status||job.status:job.terminal?job.status:state?.status||job.status)+filled+(details?' · '+details:'');
 }
 async function refreshEntry(){
  if(!entrySupport()||!reviewedSymbol)return;
  const selection=entryIdentity();
  try{
   const value=await entryRequest('status',selection);
   if(sameEntry(selection))renderEntryJob(value.job);
  }catch(error){if(sameEntry(selection))entryStatus.textContent=error.message;}
 }
 function refreshEntryControls(){
  clearEntryPreview();
  entryJob=null;
  const supported=entrySupport();
  $('investment-entry-fields').hidden=!supported;
  $('investment-entry-actions').hidden=!supported;
  $('investment-entry-stop').hidden=true;
  $('investment-entry-preview').hidden=false;
  const fib=reviewedRow?.daily_pullback;
  entryLevel.replaceChildren(new Option('Choose a level',''));
  for(const ratio of ['50','56']){
   if(fib?.['price_'+ratio]!=null)entryLevel.add(new Option(ratio+'% · ₹'+fmt(fib['price_'+ratio]),ratio));
  }
  const hasLevels=entryLevel.options.length>1;
  $('investment-entry-preview').disabled=!hasLevels;
  entryStatus.textContent=supported?'Checking monitor status…':deliveryBroker.value?
   'Automatic entry monitoring is currently available on Dhan accounts.':'';
  if(supported){
   void refreshEntry();
   if(!hasLevels)entryStatus.textContent='A fresh Investment result with daily Fib prices is required for a new monitor.';
  }
 }
 entryQuantity.oninput=entryLevel.onchange=clearEntryPreview;
 $('investment-entry-preview').onclick=async()=>{
  const selection=entryIdentity(),level=entryLevel.value,quantity=Number(entryQuantity.value);
  if(!level||!Number.isSafeInteger(quantity)||quantity<=0){entryStatus.textContent='Choose a Fib level and enter a whole number of shares.';return;}
  clearEntryPreview();
  try{
   const value=await entryRequest('preview',selection,{research_job_id:jobId,level,quantity});
   if(!sameEntry(selection)||entryLevel.value!==level||Number(entryQuantity.value)!==quantity)return;
   entryPreview=value;
   const plan=value.plan;
   $('investment-entry-terms').textContent=plan.account_label+' · '+plan.symbol+' · Buy up to '+fmt(plan.quantity)+
    ' delivery shares at ₹'+fmt(plan.limit_price)+' ('+plan.ratio+'% Fib), up to ₹'+fmt(plan.notional)+
    '. Checks at market open and after close can send DAY limit orders and AMOs for unfilled shares. Type '+value.confirmation+' to enable.'+
    (plan.swing_high_status==='DEVELOPING'?' The swing high is still developing. Enabling fixes this limit price for the monitor.':'')+
    (Number(plan.notional)>50000?' Order value exceeds ₹50,000.':'');
   $('investment-entry-confirmation').hidden=false;
  }catch(error){if(sameEntry(selection))entryStatus.textContent=error.message;}
 };
 $('investment-entry-enable').onclick=async()=>{
  if(!entryPreview)return;
  const selection=entryIdentity(),button=$('investment-entry-enable');
  button.disabled=true;
  try{
   const value=await entryRequest('enable',selection,{preview_id:entryPreview.preview_id,confirmation:$('investment-entry-phrase').value.trim()});
   if(sameEntry(selection)){clearEntryPreview();renderEntryJob(value.job);}
  }catch(error){if(sameEntry(selection))entryStatus.textContent=error.message;}
  finally{button.disabled=false;}
 };
 $('investment-entry-stop').onclick=async()=>{
  if(!entryJob)return;
  const selection=entryIdentity(),button=$('investment-entry-stop');
  button.disabled=true;
  try{
   const value=await entryRequest('stop',selection,{monitor_job_id:entryJob.job_id});
   if(sameEntry(selection))renderEntryJob(value.job);
  }catch(error){if(sameEntry(selection))entryStatus.textContent=error.message;button.disabled=false;}
 };
 setInterval(()=>{if($('investment-detail').open&&entrySupport())void refreshEntry();},15000);
 const deliveryBroker=$('investment-broker');
 const defaultBroker=$('investment-default-broker');
 const defaultBrokerKey='sector-pulse:investment-default-delivery:'+context?.username;
 let defaultBrokerId='';
 try{if(context?.username)defaultBrokerId=localStorage.getItem(defaultBrokerKey)||'';}catch{}
 function deliveryChoices(){
  return window.BrokerAccountOptions?.choices(window.BrokerForms?.accounts()||[],{kind:'sector'})||[];
 }
 function setBrokerOptions(select,rows,saved,placeholder){
  select.replaceChildren(new Option(placeholder,''));
  for(const row of rows){
   const option=new Option(row.label,row.id);
   option.disabled=row.disabled;
   select.add(option);
  }
  const available=rows.filter(row=>!row.disabled);
  select.value=available.some(row=>row.id===saved)?saved:'';
  select.disabled=!available.length;
  return available;
 }
 function fillDefaultBroker(){
  setBrokerOptions(defaultBroker,deliveryChoices(),defaultBrokerId,'Select a delivery account');
 }
 defaultBroker.onchange=()=>{
  defaultBrokerId=defaultBroker.value;
  try{if(context?.username)localStorage.setItem(defaultBrokerKey,defaultBrokerId);}catch{}
  fillDeliveryBrokers();
 };
 function fillDeliveryBrokers(){
  if(!reviewedSymbol)return;
  const key='sector-pulse:investment-delivery:'+JSON.stringify([context?.username,reviewedSymbol]);
  let saved=null;
  try{if(context?.username)saved=localStorage.getItem(key);}catch{}
  const available=setBrokerOptions(deliveryBroker,deliveryChoices(),saved||defaultBrokerId,
   defaultBrokerId?'Use Investment default':'Select a delivery account');
  deliveryBroker.disabled=!available.length;
  const status=$('investment-broker-status');
  status.textContent=saved&&!deliveryBroker.value?'Previously selected account is unavailable. Choose another account.':available.length?'Choose the account you intend to use for this equity.':'No eligible delivery accounts available. Configure FYERS, Dhan or Motilal Oswal under Brokers.';
  deliveryBroker.onchange=()=>{
   refreshEntryControls();
   if(!context?.username){status.textContent='Account selected for this review.';return;}
   try{
    if(deliveryBroker.value)localStorage.setItem(key,deliveryBroker.value);
    else{localStorage.removeItem(key);fillDeliveryBrokers();}
    status.textContent=deliveryBroker.value?'Delivery account preference saved for '+reviewedSymbol+'.':'Delivery account preference cleared.';
   }catch{status.textContent='Broker selected for this review. The browser could not save your preference.';}
  };
  refreshEntryControls();
 }
 window.addEventListener('broker-accounts-ready',()=>{fillDefaultBroker();fillDeliveryBrokers();});
 fillDefaultBroker();
 function detail(symbol){
  const r=[...(output?.rows||[]),...(output?.audit||[])].find(r=>r.symbol===symbol);if(!r)return;
  reviewedSymbol=r.symbol;
  reviewedRow=r;
  entryQuantity.value='';
  fillDeliveryBrokers();
  $('investment-detail-title').textContent=r.name||r.symbol;
  $('investment-detail-body').innerHTML=`<p><b>${esc(r.symbol)}</b> · ${esc(title(r.rule_status))}</p><p>Provider daily bar: ${esc((r.market_bar_at||r.price_as_of)?new Date(r.market_bar_at||r.price_as_of).toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata'}):'unavailable')}. This identifies the session, not live quote freshness. ATH verification remains incomplete.</p><h3>Sector and relative strength</h3>${sectorCell(r)}<p>RS is the return difference versus Nifty 500 in percentage points. Sector returns use an equal-weight group of current NSE EQ peers sharing the provider sector classification; this is not an official sector-index return or a 0–100 score.</p><p>Matched peers: 6M ${fmt(r.sector_strength?.windows?.['6m']?.members)} / 12M ${fmt(r.sector_strength?.windows?.['12m']?.members)} of ${fmt(r.sector_strength?.total_members)}. At least five peers and the same benchmark session are required. Stock RS 6M: ${signed(r.relative_strength?.windows?.['6m'])} pp.</p><h3>Daily Fib pullback entry</h3>${pullbackCell(r)}${r.daily_pullback?.price_50!=null?`<p>Daily swing low ₹${fmt(r.daily_pullback.swing_low)} on ${esc(r.daily_pullback.swing_low_date)} to high ₹${fmt(r.daily_pullback.swing_high)} on ${esc(r.daily_pullback.swing_high_date)}. Completed daily data through ${esc(r.daily_pullback.as_of)}.</p>`:''}<h3>ATH breakout, stop-loss and target</h3>${planCell(r)}<p>${esc(r.plan?.method||'No plan evidence captured.')}</p><p>${esc(r.plan?.trigger||'')}</p><p>${esc(r.plan?.invalidation||'')}</p><ul>${(r.plan?.limitations||[]).map(v=>'<li>'+esc(v)+'</li>').join('')}</ul><h3>Rule evidence</h3><ul>${(r.checks||[]).map(c=>'<li>'+esc(c.name)+': <b>'+(c.passed?'Pass':'Failed or unavailable')+'</b></li>').join('')}</ul><h3>Missing verification</h3><ul>${(r.missing||[]).map(s=>'<li>'+esc(s)+'</li>').join('')}</ul><h3>AI Assessment</h3><p>${esc(r.ai?.rationale||'No AI review saved for this candidate.')}</p><ul>${(r.ai?.risks||[]).map(s=>'<li>'+esc(s)+'</li>').join('')}</ul><h3>Evidence needed</h3><ul>${(r.ai?.evidence_needed||[]).map(s=>'<li>'+esc(s)+'</li>').join('')}</ul><h3>Public financial filing</h3><p>${esc(r.filing?.reason||'No dated filing captured in this rule-only result.')}</p><p>${esc(r.filing?.period_end?'Reporting period: '+r.filing.period_end:'')}</p><dl class="investment-filing-metrics">${Object.entries(r.filing?.metrics||{}).map(([k,v])=>'<div><dt>'+esc(k.replaceAll('_',' '))+'</dt><dd>'+fmt(v)+'</dd></div>').join('')}</dl><h3>Sources</h3><ul>${[...(output.sources||[]),...(r.filing?.sources||[])].filter(s=>/^https:\/\//.test(s.url)).map(s=>'<li><a href="'+esc(s.url)+'" target="_blank" rel="noopener noreferrer">'+esc(s.title)+'</a></li>').join('')}</ul>`;
  const selectedPeriod=period.value;
  const annual=selectedPeriod.endsWith('y')?annualWindow(r,selectedPeriod):null;
  const returns=document.createElement('p');
  returns.textContent=returnsText(r).join(' · ')+(annual?' · '+annual.from_date+' to '+annual.to_date:'');
  $('investment-detail-body').prepend(returns);
  const source=output;
  $('investment-report-status').textContent='';
  const button=$('investment-report');
  button.onclick=async()=>{
   button.disabled=true;
   const status=$('investment-report-status');
   status.textContent='Preparing report and chart evidence…';
   try{
    const evidence=$('investment-detail-body').cloneNode(true);
    const paragraphs=[...evidence.querySelectorAll('p, h3, li, dt, dd')].map(node=>node.textContent);
    paragraphs.push(...Array.from(evidence.querySelectorAll('a'),link=>link.href));
    await window.SectorPulseInvestmentExports.report(r,source,paragraphs,selectedPeriod,growth,returnValue);
    status.textContent='Report downloaded.';
   }catch(error){status.textContent='Report unavailable. '+error.message;}
   finally{button.disabled=false;}
  };
  $('investment-detail').showModal();
 }
 section.addEventListener('click',e=>{const b=e.target.closest('.investment-open');if(b)detail(b.dataset.symbol);});
 $('investment-detail-close').onclick=()=>$('investment-detail').close();
 $('investment-search').oninput=()=>{page=0;render();};
 for(const control of [sort,period])control.onchange=()=>{
  try{localStorage.setItem(preferenceKey,JSON.stringify({sort:sort.value,period:period.value}));}catch{}
  page=0;
  render();
 };
 $('investment-prev').onclick=()=>{page--;render();};
 $('investment-next').onclick=()=>{page++;render();};
 $('investment-rows').onchange=event=>{
  const box=event.target.closest('.investment-select');
  if(!box)return;
  if(box.checked)selected.add(box.value);else selected.delete(box.value);
  selectionStatus();
 };
 $('investment-clear').onclick=()=>{selected.clear();render();};
 $('investment-xlsx').onclick=()=>{
  const rows=(output?.rows||[]).filter(row=>selected.has(row.symbol));
  window.SectorPulseInvestmentExports.workbook(rows,growth,returnValue);
 };
 $('investment-saved').onclick=()=>window.SectorPulseJobs?.open('ANALYSIS');
 $('investment-export').onclick=()=>{
  const blob=new Blob([JSON.stringify(output,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='investment-evidence.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 };
 function jobEvent(event){
  const job=event.detail?.job;if(job?.request?.path?.includes('/entry-monitor/'))return;
  if(job?.request?.path?.includes('/seasonality/')||job?.feature!=='investment'||job.created<newest)return;
  if(jobId!==job.job_id){jobId=job.job_id;selected.clear();page=0;}
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
   if(value.schema==='investment/v1'){selected.clear();page=0;output=value;render();$('investment-run').disabled=false;}
  }catch(error){$('investment-status').textContent=error.message;$('investment-run').disabled=false;}
 };
 return true;
}
function start(){if(mount())return;const observer=new MutationObserver(()=>{if(mount())observer.disconnect();});observer.observe(document.body,{childList:true,subtree:true});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
