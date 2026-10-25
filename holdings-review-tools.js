/* Portfolio evidence charts and explicitly confirmed Dhan holding actions. */
(() => {
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>v==null?'—':new Intl.NumberFormat('en-IN',{maximumFractionDigits:2}).format(v);
let scope=null,chartDialog=null,actionDialog=null,charts=[],observer=null,selectedPreview=null,actionScope=null;
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
document.head.append(style);
function dispose(){observer?.disconnect();observer=null;for(const chart of charts)chart.remove();charts=[];}
function closeAll(){chartDialog?.close();actionDialog?.close();selectedPreview=null;actionScope=null;dispose();}
function dialog(id){
 let d=document.getElementById(id);if(d)return d;
 d=document.createElement('dialog');d.id=id;d.className='holding-dialog';document.body.append(d);
 d.addEventListener('close',()=>{if(d===chartDialog)dispose();if(d===actionDialog){selectedPreview=null;actionScope=null;}});
 return d;
}
function priceChart(container){
 const chart=LightweightCharts.createChart(container,{autoSize:true,height:container.classList.contains('chart-price')?420:135,
 layout:{background:{color:'#0e1d30'},textColor:'#b8cce0'},grid:{vertLines:{color:'#1c3248'},horzLines:{color:'#1c3248'}},
 rightPriceScale:{borderColor:'#38516b'},timeScale:{borderColor:'#38516b',timeVisible:false}});
 charts.push(chart);return chart;
}
function line(chart,data,title,color,width=2){
 const s=chart.addLineSeries({title,color,lineWidth:width,priceLineVisible:false,lastValueVisible:true,priceFormat:{type:'price',precision:2,minMove:0.01}});s.setData(data||[]);return s;
}
function draw(row,weekly=false,enabled={}){
 dispose();const d=row.chart;const root=chartDialog;
 root.querySelectorAll('.chart-price,.chart-study').forEach(c=>c.replaceChildren());
 root.querySelector('.daily-studies').hidden=weekly;
 const chart=priceChart(root.querySelector('.chart-price')),candles=chart.addCandlestickSeries({upColor:'#68d7b2',downColor:'#ff8f82',wickUpColor:'#68d7b2',wickDownColor:'#ff8f82',borderVisible:false,priceFormat:{type:'price',precision:2,minMove:0.01}});
 candles.setData(weekly?d.weekly_candles:d.candles);
 if(weekly)line(chart,d.weekly_ema20,'Weekly EMA20','#c8a7ff');
 else for(const [key,title,color] of [['ema20','EMA20','#ffd477'],['ema50','EMA50','#7ac5ff'],['weekly_ema20','Prior weekly EMA20','#c8a7ff'],['support20','Prior 20-session low','#70b8a2'],['resistance20','Prior 20-session high','#e49eab'],['low5','Five-session low','#79c7ae']]){
  if(enabled[key]!==false)line(chart,d.series[key],title,color,key.includes('20')&&key.includes('session')?1:2);
 }
 for(const [value,title,color] of [[row.candidate_stop,'Candidate stop','#ffb168'],[row.average_price,'Average cost','#97adbf']]){
  if(value>0)candles.createPriceLine({price:value,title,color,lineStyle:2,lineWidth:1,axisLabelVisible:true});
 }
 chart.timeScale().fitContent();
 if(!weekly){
  const rsi=priceChart(root.querySelector('.chart-rsi')),atr=priceChart(root.querySelector('.chart-atr'));
  const rs=line(rsi,d.series.rsi14,'RSI14','#c8a7ff');line(atr,d.series.atr14,'ATR14','#ffd477');
  for(const level of [30,70])rs.createPriceLine({price:level,title:String(level),color:'#657c94',lineStyle:2,lineWidth:1,axisLabelVisible:true});
  for(const c of [rsi,atr])c.timeScale().setVisibleLogicalRange(chart.timeScale().getVisibleLogicalRange());
  let syncing=false;
  for(const source of charts)source.timeScale().subscribeVisibleTimeRangeChange(range=>{
   if(!range||syncing)return;syncing=true;try{for(const target of charts)if(target!==source)target.timeScale().setVisibleRange(range);}finally{syncing=false;}
  });
 }
 observer=new ResizeObserver(()=>{for(const c of charts)c.applyOptions({width:root.querySelector('.chart-price').clientWidth});});observer.observe(root.querySelector('.chart-price'));
}
function showChart(row){
 if(!row.chart?.candles?.length){alert('Run a fresh analysis to save the exact candles and indicators for this holding.');return;}
 if(!window.LightweightCharts){alert('The chart library is unavailable. Refresh the dashboard.');return;}
 chartDialog=dialog('holding-evidence-chart');chartDialog.setAttribute('aria-label','Analysis chart for '+row.symbol);
 const e=row.evidence||{};
 chartDialog.innerHTML=`<header><div><span class="label">RECOMMENDATION EVIDENCE</span><h2>${esc(row.symbol)} · ${esc(row.action.replaceAll('_',' '))}</h2></div><button class="button" data-close>Close chart</button></header>
 <p>Completed session ${esc(row.chart.last_session)} · ${esc(row.chart.basis)} Pan and zoom to inspect the review history.</p>
 <div class="holding-chart-toolbar"><label class="field">Candles<select data-timeframe><option value="daily">Daily · review timeframe</option><option value="weekly">Prior completed weeks</option></select></label>
 ${[['ema20','EMA20'],['ema50','EMA50'],['weekly_ema20','Prior weekly EMA20'],['support20','20-session low'],['resistance20','20-session high'],['low5','Five-session low']].map(([key,label])=>`<label><input type="checkbox" data-overlay="${key}" checked> ${label}</label>`).join('')}</div>
 <div class="legend"><span>EMA20 ${num(e.ema20)}</span><span>EMA50 ${num(e.ema50)}</span><span>Prior weekly EMA20 ${num(e.weekly_ema20)}</span><span>Candidate stop ${num(row.candidate_stop)}</span><span>Five-session low ${num(e.low5)}</span><span>Close − 2 ATR ${num(e.close-2*e.atr14)}</span><span>RSI14 ${num(e.rsi14)}</span><span>ATR14 ${num(e.atr14)}</span></div>
 <div class="chart-price" aria-label="Candlestick chart with EMA and protective levels"></div>
 <div class="daily-studies"><div class="chart-study chart-rsi" aria-label="Daily RSI14 chart"></div><div class="chart-study chart-atr" aria-label="Daily ATR14 chart"></div></div>
 <p>${(row.reasons||[]).map(esc).join(' ')} Candidate stop is a planning level, not an existing broker order.</p>`;
 chartDialog.querySelector('[data-close]').onclick=()=>chartDialog.close();
 const update=()=>draw(row,chartDialog.querySelector('[data-timeframe]').value==='weekly',Object.fromEntries([...chartDialog.querySelectorAll('[data-overlay]')].map(n=>[n.dataset.overlay,n.checked])));
 chartDialog.querySelectorAll('select,input').forEach(n=>n.onchange=update);chartDialog.showModal();update();
}
async function request(scope,path,payload){
 const context=window.SectorPulseWorkspace;
 const headers={'Content-Type':'application/json'};if(context?.csrf)headers['X-CSRF-Token']=context.csrf;
 const options={method:'POST',headers,body:JSON.stringify({...payload,broker:scope.broker,account_id:scope.accountId})};
 const response=await (window.BrokerForms?window.BrokerForms.fetch('holdings',path,options):fetch(path,options));
 const value=await response.json();if(!response.ok)throw Error(value.error||'Holding action failed.');
 return value;
}
function openAction(row,source){
 actionDialog=dialog('holding-action-ticket');actionDialog.setAttribute('aria-label','Review recommended action for '+row.symbol);
 selectedPreview=null;actionScope={...source,row};
 const trail=row.action==='TRAIL';
 actionDialog.innerHTML=`<header><div><span class="label">BROKER ACTION · REVIEW FIRST</span><h2>${trail?'Set recommended protective stop':row.action==='EXIT'?'Exit holding':'Book profit'} · ${esc(row.symbol)}</h2></div><button class="button" data-close>Close</button></header>
 <p>${trail?'Create one fixed Dhan Forever protective SELL stop at the recommended level. It will not trail automatically. Existing orders are checked to prevent duplicate protection.':'Prepare a LIMIT SELL for the quantity below. Review the final quantity and price before submitting.'}</p>
 <p>Broker: ${esc(source.broker)} · Product: ${esc(row.holding_type)} · Recommendation: ${esc(row.action)} · Candidate stop: ${num(row.candidate_stop)} INR</p>
 <label class="field">Shares<input data-quantity type="number" min="1" step="1" max="${row.quantity}" value="${row.action==='BOOK_PROFIT'?'':row.quantity}" ${trail?'readonly':''}></label>
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
   const preview=await request(captured,'/api/holdings-analysis/action-preview',{job_id:captured.job.job_id,row_id:row.id,quantity,...(limit?{limit_price:Number(limit)}:{})});
   if(actionScope!==captured||!actionDialog.open)return;
   selectedPreview=preview;const t=preview.ticket;
   plan.innerHTML=`<h3>Exact broker ticket</h3><pre>${esc(preview.description)}\n${esc(preview.symbol)} · ${esc(t.transactionType)} ${num(t.quantity)} shares · ${esc(t.productType)}\nLimit ₹${num(t.price)}${t.triggerPrice?' · Trigger ₹'+num(t.triggerPrice):''}\n${esc(preview.endpoint==='/forever/orders'?'Dhan Forever SINGLE · fixed stop':'Regular LIMIT exit')}\nReference quote ₹${num(preview.reference_price)}\nPreview expires in two minutes.</pre>
    <p>${preview.warnings.map(esc).join(' ')}</p>
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
window.HoldingsReviewTools={
 render(section,value){
  if(scope&&scope.accountId!==value.accountId)closeAll();scope=value;
  const tableRows=[...section.querySelectorAll('#holdings-rows tr')];
  value.rows.forEach((row,index)=>{
   const tr=tableRows[index];if(!tr)return;tr.querySelector('.holding-actions-cell')?.remove();const cell=document.createElement('td');cell.className='holding-actions-cell';tr.append(cell);
   const tools=document.createElement('div');tools.className='holding-tools';
   const chart=document.createElement('button');chart.className='button holding-chart-button';chart.type='button';chart.textContent='View chart';chart.onclick=()=>showChart(row);
   const action=document.createElement('button');action.className='button holding-action-button';action.type='button';
   const eligible=['TRAIL','EXIT','BOOK_PROFIT'].includes(row.action);
   action.textContent=row.action==='TRAIL'?'Review stop':row.action==='EXIT'?'Review exit':row.action==='BOOK_PROFIT'?'Review profit booking':row.action==='HOLD'?'Hold · no order needed':'Review needed · no action';
   action.disabled=!eligible||value.broker!=='DHAN'||row.kind!=='DELIVERY_EQUITY';
   action.title=value.broker!=='DHAN'?'Reviewed holding execution is currently supported for Dhan only.':eligible?'Open a broker-validated preview. Nothing is submitted until you explicitly confirm.':'This recommendation does not define an executable order.';
   action.onclick=()=>openAction(row,value);if(value.broker==='DHAN')tools.append(action);if(['DHAN','FYERS','MOTILAL_OSWAL','DELTA_INDIA'].includes(value.broker)&&['DELIVERY_EQUITY','LINEAR_FUTURE'].includes(row.kind)){const trailing=document.createElement('button');trailing.className='button holding-chart-button';trailing.type='button';trailing.textContent='Automatic trailing';window.HoldingsTrailing?.decorate(trailing,row,value);tools.append(trailing);}tools.append(chart);cell.append(tools);
  });
 }
};
window.addEventListener('broker-account-change',event=>{if(event.detail?.kind==='holdings')closeAll();});
})();
