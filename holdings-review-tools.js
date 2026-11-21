/* Portfolio evidence charts and explicitly confirmed Dhan holding actions. */
(() => {
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>v==null?'—':new Intl.NumberFormat('en-IN',{maximumFractionDigits:2}).format(v);
const emaPeriods=[10,20,30,50,100,200];
function holdingEmaSeries(candles,period){
 if(candles.length<period)return [];
 const closes=candles.map(c=>c.close);let value=closes.slice(0,period).reduce((sum,v)=>sum+v,0)/period;
 const points=[{time:candles[period-1].time,value}];
 for(let i=period;i<candles.length;i++){value+=(closes[i]-value)*2/(period+1);points.push({time:candles[i].time,value});}
 return points;
}
let scope=null,chartDialog=null,actionDialog=null,charts=[],observer=null,selectedPreview=null,actionScope=null,researchLoad=0;
const style=document.createElement('style');
style.textContent=`
#holdings .holding-pnl{min-width:170px;vertical-align:top;font-variant-numeric:tabular-nums}
#holdings .holding-pnl-label{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;margin-bottom:9px}
#holdings .holding-pnl strong{display:block;font-size:18px;font-weight:700;line-height:1.35;white-space:nowrap}
#holdings .holding-pnl[data-pnl=profit] .holding-pnl-label,#holdings .holding-pnl[data-pnl=profit] strong,#holdings .holding-pnl[data-pnl=profit]>small:not(.holding-pnl-basis){color:#83d8b0}
#holdings .holding-pnl[data-pnl=loss] .holding-pnl-label,#holdings .holding-pnl[data-pnl=loss] strong,#holdings .holding-pnl[data-pnl=loss]>small:not(.holding-pnl-basis){color:#ff9a99}
#holdings .holding-pnl[data-pnl=flat],#holdings .holding-pnl[data-pnl=unavailable]{color:#b1c2d3}
#holdings .holding-pnl .holding-pnl-basis{max-width:170px;color:#9eafc3;font-size:11px;line-height:1.5}
.holding-tools{display:grid;gap:9px;min-width:152px;margin:0}
.holding-tools .button{width:100%;min-height:40px;margin:0;padding:10px 14px;border-radius:7px;font-size:12px;font-weight:650;line-height:1.3;text-align:center;white-space:nowrap}
.holding-tools .holding-chart-button{background:transparent;color:#b7cde0;border:1px solid #3c526a;box-shadow:none}
.holding-tools .holding-action-button{background:#386da0;color:#f3f7fb;border:1px solid #5882a9;box-shadow:none}
.holding-tools .holding-action-button:disabled{background:#182b3f;color:#849bb0;border-color:#30465b;white-space:normal}
#holdings .holding-actions-cell{width:180px;min-width:180px;vertical-align:middle;border-left:1px solid #294058;padding:20px 18px;background:#102235}
#holdings .holding-actions-heading{width:180px;min-width:180px;border-left:1px solid #294058}
#holdings .holdings-controls .holdings-toolbar{justify-content:flex-start;gap:12px}
#holdings .holdings-controls .holdings-toolbar>.field{margin-right:auto;min-width:240px}
#holdings .holdings-controls .holdings-toolbar .button{min-height:40px;padding:10px 16px;white-space:nowrap}
#holdings .holdings-secondary,#holdings #holdings-export{background:transparent;border:1px solid #3c526a;color:#b7cde0;box-shadow:none}
@media(max-width:1000px){#holdings .holdings-controls .holdings-toolbar{display:grid;grid-template-columns:1fr 1fr;align-items:stretch}#holdings .holdings-controls .holdings-toolbar>.field{grid-column:1/-1;min-width:0;margin:0}#holdings .holdings-controls .holdings-toolbar>div{grid-column:1/-1}#holdings .holdings-controls .holdings-toolbar>div .button{flex:1}.holding-dialog{padding:16px}.holding-chart-toolbar{gap:12px}}

.holding-dialog{width:min(1150px,94vw);max-height:92vh;overflow:auto;background:#0e1d30;color:#d9e7f3;border:1px solid #49627f;border-radius:12px;padding:22px}
.holding-dialog::backdrop{background:#030b16cc}.holding-dialog header{display:flex;justify-content:space-between;align-items:start;gap:20px}
.holding-dialog h2{font-size:22px;margin:4px 0 12px}.holding-dialog p{line-height:1.6}.holding-dialog .chart-price{height:420px}
.holding-dialog .chart-study{height:135px}.holding-chart-toolbar{display:flex;gap:18px;flex-wrap:wrap;margin:16px 0}
.holding-dialog .legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;margin:14px 0}.holding-dialog .field{display:inline-flex;flex-direction:column;gap:7px;margin:12px 20px 12px 0}
.holding-dialog input,.holding-dialog select{padding:10px;background:#152b44;color:inherit;border:1px solid #54708c;border-radius:5px}
.holding-dialog pre{white-space:pre-wrap;background:#081525;padding:16px;border-radius:7px}
.holding-dialog .live-consent{display:flex;gap:10px;align-items:start;margin:18px 0}.holding-dialog [role=status]{white-space:pre-wrap}
.holding-dialog button:focus-visible,.holding-dialog input:focus-visible,.holding-dialog select:focus-visible{outline:3px solid #8fd4ff;outline-offset:3px}
`;
style.textContent+='\n#holding-evidence-chart{padding:0;width:min(1220px,96vw);max-height:94vh;border-color:#36516b}\n#holding-evidence-chart>header{padding:20px 24px;border-bottom:1px solid #294058;gap:20px;background:#102238;position:sticky;top:0;z-index:3}\n#holding-evidence-chart h2{font-size:20px;margin:5px 0 0;letter-spacing:.01em}\n#holding-evidence-chart>p,#holding-evidence-chart>.holding-chart-toolbar,#holding-evidence-chart>.legend{margin:16px 24px}\n#holding-evidence-chart>p{font-size:12px;color:#a9bed3;line-height:1.65}\n#holding-evidence-chart .holding-chart-toolbar{align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid #294058}\n#holding-evidence-chart .holding-chart-toolbar>.field{min-width:220px;display:grid;gap:6px}\n#holding-evidence-chart select{background:#152b43;border:1px solid #45627e;color:#e3edf7;border-radius:7px;padding:9px 12px;min-height:40px}\n#holding-evidence-chart .holding-overlays{border:1px solid #36516b;border-radius:7px;padding:10px 14px;min-width:185px;max-width:540px}\n#holding-evidence-chart .holding-overlays summary{cursor:pointer;font-weight:650;color:#c8d9e9}\n#holding-evidence-chart .holding-overlay-options{display:flex;gap:12px 20px;flex-wrap:wrap;padding-top:14px;font-size:12px}\n#holding-evidence-chart .holding-overlay-options label{display:flex;gap:6px;align-items:center;white-space:nowrap}\n#holding-evidence-chart .legend{display:flex;gap:8px;flex-wrap:wrap}\n#holding-evidence-chart .legend span{border:1px solid #294058;background:#102238;border-radius:5px;padding:7px 10px;font-size:11px;font-variant-numeric:tabular-nums}\n#holding-evidence-chart .holding-chart-panel{margin:14px 24px;border:1px solid #294058;border-radius:8px;overflow:hidden}\n#holding-evidence-chart .holding-chart-title{padding:10px 14px;color:#9eb7cf;background:#102238;font-size:11px;font-weight:650;letter-spacing:.04em}\n#holding-evidence-chart .chart-price{height:350px}\n#holding-evidence-chart .chart-study{height:110px}\n@media(max-width:700px){#holding-evidence-chart>header{padding:16px}#holding-evidence-chart h2{font-size:16px}#holding-evidence-chart>p,#holding-evidence-chart>.holding-chart-toolbar,#holding-evidence-chart>.legend,#holding-evidence-chart .holding-chart-panel{margin:12px}#holding-evidence-chart .holding-chart-toolbar{align-items:stretch;gap:12px}#holding-evidence-chart .holding-overlays{width:100%;max-width:none}#holding-evidence-chart .chart-price{height:300px}}\n';
style.textContent+="\n/* Keep research controls beside the instrument, within the initial viewport. */\n#holdings .holdings-table td:nth-child(2),#holdings .holdings-table th:nth-child(2){position:sticky;left:0;z-index:2;background:#102238;min-width:190px;max-width:230px;border-right:1px solid #36516b}\n#holdings .holding-research-tools{display:grid;gap:7px;margin-top:12px;width:100%;max-width:190px}\n#holdings .holding-research-tools .button{display:block;width:100%;min-height:36px;margin:0!important;padding:8px 10px;border:1px solid #496a86;border-radius:7px;background:#163149;color:#d9e7f3;font-size:12px;font-weight:650;line-height:1.35;white-space:normal;text-align:center;box-shadow:none}\n#holdings .holding-research-tools .seasonality-action{border-color:#4e817d;background:#153a3b;color:#c6eee4}\n";
style.textContent+="\n#holding-evidence-chart .legend{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;align-items:stretch}\n#holding-evidence-chart .legend .holding-study-key{display:grid;grid-template-columns:8px 1fr;gap:5px 8px;padding:9px 11px;font-size:11px;min-width:0}\n#holding-evidence-chart .holding-study-key i{width:7px;height:7px;border-radius:50%;align-self:center}\n#holding-evidence-chart .holding-study-key span{border:0;background:none;padding:0;font-size:11px}\n#holding-evidence-chart .holding-study-key b{grid-column:2;font-size:13px;color:#edf4fa;font-variant-numeric:tabular-nums}\n#holding-evidence-chart .holding-candle-readout{padding:9px 14px;background:#102238;border-bottom:1px solid #294058;color:#c7d9e8;font-size:12px;line-height:1.65;min-height:36px;font-variant-numeric:tabular-nums}\n#holding-evidence-chart .chart-price{height:410px}\n#holding-evidence-chart>header{position:sticky;top:0;z-index:5}\n@media(max-width:900px){#holding-evidence-chart .legend{grid-template-columns:repeat(3,minmax(0,1fr))}}\n@media(max-width:700px){#holding-evidence-chart .legend{grid-template-columns:repeat(2,minmax(0,1fr))}#holding-evidence-chart .chart-price{height:320px}#holding-evidence-chart .holding-chart-toolbar{display:grid;grid-template-columns:1fr 1fr}#holding-evidence-chart .holding-chart-toolbar>.field{min-width:0}#holding-evidence-chart .holding-overlays{grid-column:1/-1}#holding-evidence-chart .holding-candle-readout{font-size:11px}}\n";
style.textContent+="\n#holding-evidence-chart>header{padding:16px 20px}#holding-evidence-chart h2{font-size:18px}\n#holding-evidence-chart>.holding-chart-asof{margin:10px 20px;font-size:11px}\n#holding-evidence-chart>.holding-chart-toolbar{margin:10px 20px;padding:8px 0;justify-content:flex-start;gap:12px}\n#holding-evidence-chart .holding-chart-toolbar>.field{margin:0;min-width:170px}\n#holding-evidence-chart .holding-overlays{min-width:185px}\n#holding-evidence-chart [data-settings-status]{margin:6px 20px;font-size:11px}\n#holding-evidence-chart [data-ema-availability]:empty{display:none}\n#holding-evidence-chart>.legend{margin:10px 20px}\n#holding-evidence-chart .holding-chart-panel{margin:12px 20px}\n#holding-evidence-chart .chart-price{height:clamp(280px,44vh,420px)}\n#holding-evidence-chart .holding-chart-context{margin:14px 20px;padding:12px;border:1px solid #294058;border-radius:7px;font-size:12px;color:#a9bed3}\n#holding-evidence-chart .holding-chart-context summary{cursor:pointer;font-weight:650}\n@media(max-width:700px){#holding-evidence-chart .holding-chart-toolbar>.field{min-width:0}#holding-evidence-chart>header{padding:14px}#holding-evidence-chart .chart-price{height:300px}#holding-evidence-chart .holding-chart-panel{margin:10px 12px}}\n";
document.head.append(style);
function dispose(){observer?.disconnect();observer=null;for(const chart of charts)chart.remove();charts=[];}
function closeAll(){researchLoad++;chartDialog?.close();actionDialog?.close();selectedPreview=null;actionScope=null;dispose();}
function dialog(id){
 let d=document.getElementById(id);if(d)return d;
 d=document.createElement('dialog');d.id=id;d.className='holding-dialog';document.body.append(d);
 d.addEventListener('close',()=>{if(d===chartDialog)dispose();if(d===actionDialog){selectedPreview=null;actionScope=null;}});
 return d;
}
function priceChart(container){
 const chart=LightweightCharts.createChart(container,{autoSize:true,height:container.classList.contains('chart-price')?(window.innerWidth<700?300:350):110,
 layout:{background:{color:'#0e1d30'},textColor:'#b8cce0'},grid:{vertLines:{color:'#1c3248'},horzLines:{color:'#1c3248'}},
 rightPriceScale:{borderColor:'#38516b',minimumWidth:78,alignLabels:true,scaleMargins:{top:0.12,bottom:0.12}},timeScale:{borderColor:'#38516b',timeVisible:false,rightOffset:8,barSpacing:8,minBarSpacing:4}});
 charts.push(chart);return chart;
}
function line(chart,data,title,color,width=2){
 const s=chart.addLineSeries({title:'',color,lineWidth:width,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,priceFormat:{type:'price',precision:2,minMove:0.01}});s.setData(data||[]);return s;
}
function draw(row,weekly=false,enabled={},range="recent"){
 dispose();const d=row.chart;const root=chartDialog;
 root.querySelectorAll('.chart-price,.chart-study').forEach(c=>c.replaceChildren());
 root.querySelector('.daily-studies').hidden=weekly;
 const chart=priceChart(root.querySelector('.chart-price')),candles=chart.addCandlestickSeries({upColor:'#68d7b2',downColor:'#ff8f82',wickUpColor:'#68d7b2',wickDownColor:'#ff8f82',borderVisible:false,priceLineVisible:false,lastValueVisible:true,priceFormat:{type:'price',precision:2,minMove:0.01}});
 candles.setData(weekly?d.weekly_candles:d.candles);
 const bars=weekly?d.weekly_candles:d.candles,emaSeries=new Map();
 const colors=['#72dcca','#ffd477','#8ebaff','#e2a8d5','#c4b5fd','#f59f69'];
 for(const [index,period] of emaPeriods.entries()){
  const points=holdingEmaSeries(bars,period),key='ema'+period;
  if(enabled[key]!==false&&points.length)emaSeries.set(period,{series:line(chart,points,'EMA '+period,colors[index],1),color:colors[index],value:points.at(-1).value});
 }
 for(const [key,title,color] of [['weekly_ema20','Prior weekly EMA20','#c8a7ff'],['support20','Prior 20-session low','#70b8a2'],['resistance20','Prior 20-session high','#e49eab'],['low5','Five-session low','#79c7ae']]){
  if(enabled[key]===true)line(chart,weekly?(key==='weekly_ema20'?d.weekly_ema20:[]):d.series[key],title,color,1);
 }
 root.querySelector('.legend').innerHTML=[...emaSeries].map(([p,v])=>`<span class="holding-study-key"><i style="background:${v.color}"></i><span>EMA ${p}</span><b data-ema-value="${p}">${num(v.value)}</b></span>`).join('');
 const readout=root.querySelector('[data-candle-readout]');
 const showReadout=(c,day)=>{if(readout)readout.textContent=c?(typeof day==='object'&&day?.year?String(day.year)+'-'+String(day.month).padStart(2,'0')+'-'+String(day.day).padStart(2,'0'):String(day||'Latest completed session'))+' · Open '+num(c.open)+' · High '+num(c.high)+' · Low '+num(c.low)+' · Close '+num(c.close):'Move across the chart to inspect a completed candle.';};
 showReadout(bars.at(-1),bars.at(-1)?.time);
 chart.subscribeCrosshairMove(param=>{const c=param.seriesData?.get(candles);showReadout(c||bars.at(-1),c?param.time:bars.at(-1)?.time);for(const [p,v] of emaSeries){const label=root.querySelector('[data-ema-value="'+p+'"]');if(label)label.textContent=num(param.time?param.seriesData?.get(v.series)?.value:v.value);}});
 const unavailable=emaPeriods.filter(p=>enabled['ema'+p]!==false&&bars.length<p);
 root.querySelector('[data-ema-availability]').textContent=unavailable.length?'EMA '+unavailable.join(', ')+' unavailable: '+bars.length+' completed '+(weekly?'weekly':'daily')+' candles; each EMA needs its full period.':'';
 for(const [value,title,color] of [[row.candidate_stop,'Candidate stop','#ffb168'],[row.average_price,'Average cost','#97adbf']]){
  if(value>0&&enabled[title==='Candidate stop'?'candidate_stop':'average_cost']===true){candles.createPriceLine({price:value,title:'',color,lineStyle:2,lineWidth:1,axisLabelVisible:false});root.querySelector('.legend').insertAdjacentHTML('beforeend',`<span class="holding-study-key"><i style="background:${color}"></i><span>${esc(title)}</span><b>${num(value)}</b></span>`);}
 }
 chart.timeScale().fitContent();
 if(range!=="all"&&bars.length){const count=weekly?52:(window.innerWidth<700?60:120);chart.timeScale().setVisibleLogicalRange({from:Math.max(0,bars.length-count),to:bars.length+8});}
 if(!weekly){
  const rsi=priceChart(root.querySelector('.chart-rsi')),atr=priceChart(root.querySelector('.chart-atr'));
  const rs=line(rsi,d.series.rsi14,'RSI14','#c8a7ff');line(atr,d.series.atr14,'ATR14','#ffd477');
  for(const level of [30,70])rs.createPriceLine({price:level,title:String(level),color:'#657c94',lineStyle:2,lineWidth:1,axisLabelVisible:true});
  const visible=chart.timeScale().getVisibleRange();if(visible)for(const c of [rsi,atr])c.timeScale().setVisibleRange(visible);
  let syncing=false;
  chart.timeScale().subscribeVisibleTimeRangeChange(range=>{
   if(!range||syncing)return;syncing=true;try{for(const target of charts)if(target!==chart)target.timeScale().setVisibleRange(range);}finally{syncing=false;}
  });
 }
 observer=new ResizeObserver(()=>{for(const c of charts)c.applyOptions({width:root.querySelector('.chart-price').clientWidth});});observer.observe(root.querySelector('.chart-price'));
}
async function showChart(row,source,loaded=false){
 researchLoad++;
 if(!row.chart?.candles?.length&&!loaded){
  chartDialog=dialog('holding-evidence-chart');chartDialog.setAttribute('aria-label','Analysis chart for '+row.symbol);
  chartDialog.innerHTML=`<header><h2>${esc(row.symbol)}</h2><button class="button" data-close>Close chart</button></header><p role="status">Loading completed daily candles from the selected broker account…</p>`;
  chartDialog.querySelector('[data-close]').onclick=()=>chartDialog.close();chartDialog.showModal();
  const captured=scope;
  try{
   if(!source?.job?.job_id)throw Error('No saved holding job is available for this chart.');
   const data=await request(source,'/api/holdings-analysis/chart',{job_id:source.job.job_id,row_id:row.id});
   if(scope!==captured||!chartDialog.open)return;
   return showChart({...row,chart:data.chart},source,true);
  }catch(error){
   if(scope===captured&&chartDialog.open)chartDialog.querySelector('[role="status"]').textContent='Chart unavailable: '+error.message;
   return;
  }
 }
 if(!row.chart?.candles?.length){
  chartDialog=dialog('holding-evidence-chart');chartDialog.setAttribute('aria-label','Analysis chart for '+row.symbol);
  dispose();
  chartDialog.innerHTML=`<header><div><span class="label">SAVED CHART EVIDENCE</span><h2>${esc(row.symbol)}</h2></div><button class="button" data-close>Close chart</button></header><p role="status">Chart unavailable for this saved review: no completed candle data was captured.</p><p>${(row.reasons||[]).map(esc).join(' ')}</p><p>The portfolio snapshot is retained. A chart cannot be reconstructed from a holding price alone. This view does not rerun analysis or change your account.</p>`;
  chartDialog.querySelector('[data-close]').onclick=()=>chartDialog.close();chartDialog.showModal();return;
 }
 if(!window.LightweightCharts){alert('The chart library is unavailable. Refresh the dashboard.');return;}
 chartDialog=dialog('holding-evidence-chart');chartDialog.setAttribute('aria-label','Analysis chart for '+row.symbol);
 const preferenceKey='sector-pulse:holdings-chart-overlays:v1:'+String(window.SectorPulseWorkspace?.username||'user')+':'+String(source?.accountId||'dashboard');
 let savedSettings={};try{savedSettings=JSON.parse(localStorage.getItem(preferenceKey)||'{}')||{};}catch{}
 const savedOverlays=savedSettings.overlays||savedSettings;
 const overlayChoices=[...emaPeriods.map(p=>['ema'+p,'EMA '+p]),['weekly_ema20','Prior weekly EMA20'],['support20','20-session low'],['resistance20','20-session high'],['low5','Five-session low'],...(row.candidate_stop>0?[['candidate_stop','Candidate stop']]:[]),...(row.average_price>0?[['average_cost','Average cost']]:[])];
 const overlayOn=key=>typeof savedOverlays[key]==='boolean'?savedOverlays[key]:emaPeriods.some(p=>key==='ema'+p);
 const e=loaded?Object.fromEntries(Object.entries(row.chart.series||{}).map(([key,points])=>[key,points.at(-1)?.value])):row.evidence||{};
 if(loaded)e.close=row.chart.candles.at(-1)?.close;
 chartDialog.innerHTML=`<header><div><span class="label">${row.research_only?"PUBLIC PRICE HISTORY":"HOLDING PRICE HISTORY"}</span><h2>${esc(row.symbol.replace(/-EQ$/,""))} · Candlestick chart</h2></div><button class="button" data-close>Close chart</button></header>
 <p class="holding-chart-asof">Completed session ${esc(row.chart.last_session)}${row.chart.stale?' · Latest expected session '+esc(row.chart.expected_session)+' unavailable from broker':''} · Read-only price history</p>
 <div class="holding-chart-toolbar"><label class="field">Candles<select data-timeframe><option value="daily">Daily · review timeframe</option><option value="weekly">Prior completed weeks</option></select></label><label class="field">Visible history<select data-chart-range><option value="recent">Recent sessions</option><option value="all">All available history</option></select></label>
 <details class="holding-overlays"><summary>Chart overlays</summary><div class="holding-overlay-options">${overlayChoices.map(([key,label])=>`<label><input type="checkbox" data-overlay="${key}" ${overlayOn(key)?'checked':''}> ${label}</label>`).join('')}</div></details><button class="button" data-save-chart>Save settings</button></div><p data-settings-status role="status">Changes apply to this chart. Save to use them next time.</p>
 <div class="legend">${emaPeriods.map(p=>{const points=holdingEmaSeries(row.chart.candles,p);return `<span>EMA ${p} ${num(points.at(-1)?.value)}</span>`;}).join('')}<span>RSI14 ${num(e.rsi14)}</span><span>ATR14 ${num(e.atr14)}</span></div><p data-ema-availability role="status"></p>
 <section class="holding-chart-panel"><div class="holding-chart-title">PRICE · COMPLETED CANDLES</div><div class="holding-candle-readout" data-candle-readout></div><div class="chart-price" aria-label="Candlestick chart with EMA and protective levels"></div></section>
 <div class="daily-studies"><section class="holding-chart-panel"><div class="holding-chart-title">MOMENTUM · RSI 14</div><div class="chart-study chart-rsi" aria-label="Daily RSI14 chart"></div></section><section class="holding-chart-panel"><div class="holding-chart-title">VOLATILITY · ATR 14</div><div class="chart-study chart-atr" aria-label="Daily ATR14 chart"></div></section></div>
 <details class="holding-chart-context"><summary>Source and review notes</summary><p>${esc(row.chart.basis)}</p><p>${(row.reasons||[]).map(esc).join(' ')} ${row.research_only?'Historical price evidence; separate from portfolio returns and conditional investment targets.':'Candidate stop is a planning level, not an existing broker order.'}</p></details>`;
 chartDialog.querySelector('[data-close]').onclick=()=>chartDialog.close();
 const update=()=>draw(row,chartDialog.querySelector('[data-timeframe]').value==='weekly',Object.fromEntries([...chartDialog.querySelectorAll('[data-overlay]')].map(n=>[n.dataset.overlay,n.checked])),chartDialog.querySelector('[data-chart-range]').value);
 chartDialog.querySelector('[data-timeframe]').value=savedSettings.timeframe==='weekly'?'weekly':'daily';
 chartDialog.querySelector('[data-chart-range]').value=savedSettings.range==='all'?'all':'recent';
 chartDialog.querySelectorAll('select,input').forEach(n=>n.onchange=()=>{chartDialog.querySelector('[data-settings-status]').textContent='Unsaved chart settings';update();});
 chartDialog.querySelector('[data-save-chart]').onclick=()=>{
  const settings={timeframe:chartDialog.querySelector('[data-timeframe]').value,range:chartDialog.querySelector('[data-chart-range]').value,overlays:Object.fromEntries([...chartDialog.querySelectorAll('[data-overlay]')].map(c=>[c.dataset.overlay,c.checked]))};
  try{localStorage.setItem(preferenceKey,JSON.stringify(settings));chartDialog.querySelector('[data-settings-status]').textContent='Chart settings saved for your user and this broker account.';}
  catch{chartDialog.querySelector('[data-settings-status]').textContent='Chart settings could not be saved in this browser.';}
 };if(!chartDialog.open)chartDialog.showModal();update();
}
async function request(scope,path,payload){
 const context=window.SectorPulseWorkspace;
 const headers={'Content-Type':'application/json'};if(context?.csrf)headers['X-CSRF-Token']=context.csrf;
 const options={method:'POST',headers,body:JSON.stringify({...payload,broker:scope.broker,account_id:scope.accountId})};
 const response=await (window.BrokerForms?window.BrokerForms.fetch('holdings',path,options):fetch(path,options));
 const value=await response.json();if(!response.ok)throw Error(value.error||'Holding action failed.');
 return value;
}
function openAction(row,source,manualAction=null){
 if(manualAction)row={...row,advisory_action:row.action,action:manualAction};
 actionDialog=dialog('holding-action-ticket');actionDialog.setAttribute('aria-label','Review recommended action for '+row.symbol);
 selectedPreview=null;actionScope={...source,row};
 const trail=row.action==='TRAIL';
 actionDialog.innerHTML=`<header><div><span class="label">BROKER ACTION · REVIEW FIRST</span><h2>${trail?'Set recommended protective stop':row.action==='EXIT'?'Exit holding':'Book profit'} · ${esc(row.symbol)}</h2></div><button class="button" data-close>Close</button></header>
 <p>${trail?'Create one fixed Dhan Forever protective SELL stop at the recommended level. It will not trail automatically. Existing orders are checked to prevent duplicate protection.':'Prepare a LIMIT SELL for the quantity below. Review the final quantity and price before submitting.'}</p>
 <p>Broker: ${esc(source.broker)} · Product: ${esc(row.holding_type)} · ${manualAction?'Your decision':'Recommendation'}: ${esc(row.action)} · Candidate stop: ${num(row.candidate_stop)} INR</p>
 <label class="field">Shares<input data-quantity type="number" min="1" step="1" max="${row.quantity}" value="${row.action==='BOOK_PROFIT'?'':row.quantity}" ${trail||manualAction==='EXIT'?'readonly':''}></label>
 <label class="field">${trail?'Sell limit below trigger (optional)':'Sell limit (optional)'}<input data-limit type="number" min="0.01" step="0.01" placeholder="Use broker-validated default"></label>
 <div><button class="button" data-preview>Preview recommended action</button></div>
 <div data-plan hidden></div><p role="status" data-status>Preview is read-only. No broker order has been sent.</p>`;
 actionDialog.querySelector('[data-close]').onclick=()=>actionDialog.close();
 const status=actionDialog.querySelector('[data-status]'),plan=actionDialog.querySelector('[data-plan]');
 const invalidate=()=>{selectedPreview=null;plan.hidden=true;status.textContent='Inputs changed. Prepare a new preview.';};
 actionDialog.querySelectorAll('[data-quantity],[data-limit]').forEach(n=>n.oninput=invalidate);
 actionDialog.querySelector('[data-preview]').onclick=async()=>{
  const button=actionDialog.querySelector('[data-preview]');button.disabled=true;plan.hidden=true;selectedPreview=null;
  try{
   if(!actionScope?.job?.job_id)throw Error('Run a fresh completed review before preparing an action.');
   const quantity=Number(actionDialog.querySelector('[data-quantity]').value);
   if(!Number.isInteger(quantity)||quantity<=0)throw Error('Enter the number of shares to sell/protect.');
   const limit=actionDialog.querySelector('[data-limit]').value;
   status.textContent='Checking current holding, native instrument, orders and existing protection…';
   const captured=actionScope;
   const preview=await request(captured,'/api/holdings-analysis/action-preview',{job_id:captured.job.job_id,row_id:row.id,quantity,...(manualAction?{manual_action:manualAction}:{}),...(limit?{limit_price:Number(limit)}:{})});
   if(actionScope!==captured||!actionDialog.open)return;
   selectedPreview=preview;const t=preview.ticket;
   plan.innerHTML=`<h3>Exact broker ticket</h3><pre>${esc(preview.description)}\n${esc(preview.symbol)} · ${esc(t.transactionType)} ${num(t.quantity)} shares · ${esc(t.productType)}\nLimit ₹${num(t.price)}${t.triggerPrice?' · Trigger ₹'+num(t.triggerPrice):''}\n${esc(preview.endpoint==='/forever/orders'?'Dhan Forever SINGLE · fixed stop':'Regular LIMIT exit')}\nReference quote ₹${num(preview.reference_price)}\nPreview expires in two minutes.</pre>
    <p>${preview.warnings.map(esc).join(' ')}${t.quantity*t.price>50000?' Order value exceeds ₹50,000; review the full notional before confirming.':''}</p>
    <label class="live-consent"><input type="checkbox" data-consent> I authorize this exact live broker order. I understand that acknowledgement does not guarantee a fill.</label>
    <label class="field">Type ${esc(preview.confirmation_phrase)}<input data-phrase autocomplete="off"></label>
    <button class="button" data-submit disabled>Confirm live action</button>`;
   plan.hidden=false;status.textContent=preview.live_submission_enabled?'Preview ready. Review every detail before confirming. No order has been sent.':'Live execution is disabled for this account. Preview only.';
   const submit=plan.querySelector('[data-submit]');
   const enable=()=>{submit.disabled=!preview.live_submission_enabled||!plan.querySelector('[data-consent]').checked||plan.querySelector('[data-phrase]').value!==preview.confirmation_phrase;};
   plan.querySelector('[data-consent]').onchange=enable;plan.querySelector('[data-phrase]').oninput=enable;
   submit.onclick=async()=>{
    if(selectedPreview!==preview||actionScope!==captured)return;
    submit.disabled=true;button.disabled=true;status.textContent='Submitting the exact reviewed action once…';
    // Consume the browser preview before sending; an uncertain request is never retried.
    selectedPreview=null;
    try{
     const result=await request(captured,'/api/holdings-analysis/action-submit',{preview_id:preview.preview_id,confirmation:plan.querySelector('[data-phrase]').value,live_confirmation:true});
     status.textContent=`${result.status}${result.order_id?' · Broker order '+result.order_id:''} · ${result.message}`;
    }catch(error){status.textContent=error.message+' Check the Dhan order book before another action. No automatic retry.';}
    plan.querySelectorAll('input').forEach(n=>n.disabled=true);
   };
  }catch(error){status.textContent=error.message+' No order was submitted by this preview.';}
  finally{if(selectedPreview===null&&!plan.hidden)button.disabled=true;else button.disabled=false;}
 };
 actionDialog.showModal();
}
async function showInvestmentChart(symbol){
 const token=++researchLoad;
 chartDialog=dialog('holding-evidence-chart');chartDialog.setAttribute('aria-label','Investment chart for '+symbol);
 chartDialog.innerHTML=`<header><div><span class="label">PUBLIC PRICE HISTORY</span><h2>${esc(symbol.replace(/-EQ$/,''))} · Candlestick chart</h2></div><button class="button secondary" data-close>Close chart</button></header><p role="status">Loading completed daily candles. The analysis remains tracked in Saved jobs if you close this chart.</p>`;
 chartDialog.querySelector('[data-close]').onclick=()=>chartDialog.close();chartDialog.showModal();
 try{
  const headers={'Content-Type':'application/json'};if(window.SectorPulseWorkspace?.csrf)headers['X-CSRF-Token']=window.SectorPulseWorkspace.csrf;
  const response=await fetch('/api/investment/seasonality/analyze',{method:'POST',headers,body:JSON.stringify({symbol})});const data=await response.json();
  if(!response.ok)throw Error(data.error||'Public chart history is unavailable.');
  if(token!==researchLoad||!chartDialog.open)return;
  if(!data.chart?.candles?.length)throw Error(data.chart_unavailable_reason||'No completed candlestick history was returned for this symbol.');
  return showChart({symbol,chart:data.chart,research_only:true,reasons:[]},{accountId:'investment',broker:'PUBLIC'},true);
 }catch(error){if(token===researchLoad&&chartDialog.open)chartDialog.querySelector('[role="status"]').textContent='Chart unavailable: '+error.message;}
}
window.HoldingsReviewTools={
 openInvestmentChart:showInvestmentChart,
 render(section,value){
  if(scope&&scope.accountId!==value.accountId)closeAll();scope=value;
  const tableRows=[...section.querySelectorAll('#holdings-rows tr')];
  value.rows.forEach((row,index)=>{
   const tr=tableRows[index];if(!tr)return;tr.querySelector('.holding-actions-cell')?.remove();const cell=document.createElement('td');cell.className='holding-actions-cell';tr.append(cell);
   const tools=document.createElement('div');tools.className='holding-tools';
   const chart=document.createElement('button');chart.className='button holding-chart-button';chart.type='button';chart.textContent='View chart';chart.onclick=()=>showChart(row,value);
   const action=document.createElement('button');action.className='button holding-action-button';action.type='button';
   const eligible=['TRAIL','EXIT','BOOK_PROFIT'].includes(row.action);
   action.textContent=row.action==='TRAIL'?'Review stop':row.action==='EXIT'?'Review exit':row.action==='BOOK_PROFIT'?'Review profit booking':row.action==='HOLD'?'Hold · no order needed':'Review needed · no action';
   action.disabled=!eligible||value.broker!=='DHAN'||row.kind!=='DELIVERY_EQUITY';
   action.title=value.broker!=='DHAN'?'Reviewed holding execution is currently supported for Dhan only.':eligible?'Open a broker-validated preview. Nothing is submitted until you explicitly confirm.':'This recommendation does not define an executable order.';
   action.onclick=()=>openAction(row,value);if(value.broker==='DHAN')tools.append(action);if(['DHAN','FYERS','MOTILAL_OSWAL','DELTA_INDIA'].includes(value.broker)&&['DELIVERY_EQUITY','LINEAR_FUTURE'].includes(row.kind)){const trailing=document.createElement('button');trailing.className='button holding-chart-button';trailing.type='button';trailing.textContent='Automatic trailing';window.HoldingsTrailing?.decorate(trailing,row,value);tools.append(trailing);}if(value.broker==='DHAN'&&row.kind==='DELIVERY_EQUITY'){
    for(const [decision,label] of [['EXIT','Exit'],['BOOK_PROFIT','Book profit']]){
     const manual=document.createElement('button');manual.type='button';manual.className='button holding-action-button';manual.textContent=label;
     manual.title='Your decision: prepare a fresh broker-validated LIMIT SELL preview. No order until exact confirmation.';
     manual.onclick=()=>openAction(row,value,decision);tools.append(manual);
    }
   }
   tr.querySelector('.holding-research-tools')?.remove();
   const research=document.createElement('div');research.className='holding-research-tools';research.setAttribute('aria-label','Research for '+row.symbol);research.append(chart);tr.children[1].append(research);cell.append(tools);
  });
 }
};
window.addEventListener('broker-account-change',event=>{if(event.detail?.kind==='holdings')closeAll();});
})();
