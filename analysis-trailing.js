/* Shared protection review in Screener and Analysis Handoff. Never enables on load. */
(function(root){
'use strict';
function supported(account){return !!account?.configured&&['DHAN','FYERS','MOTILAL_OSWAL','DELTA_INDIA'].includes(account.broker);}
function protectable(row){return !!row?.native_identity?.securityId&&((row.kind==='DELIVERY_EQUITY'&&row.quantity>0&&['NSE_EQ','BSE_EQ'].includes(row.native_identity.exchangeSegment))||(row.kind==='LINEAR_FUTURE'&&row.quantity!==0&&row.native_identity.exchangeSegment==='DELTA_24X7'));}
function eligible(row){return protectable(row)&&row.action==='TRAIL'&&row.candidate_stop>0;}
function owns(job,accountId,origin){return job?.kind==='ANALYSIS'&&job.feature==='holdings'&&job.request?.account_id===accountId&&job.request?.payload?.trailing_origin===origin&&job.output?.account_id===accountId;}
function endpoint(account,url,payload={}){
 if(!supported(account))throw Error('Select a configured supported protection account.');
 if(payload.account_id&&payload.account_id!==account.id||payload.broker&&payload.broker!==account.broker)throw Error('Protection account changed. Review again.');
 if(!/^\/api\/holdings-analysis\/(analyze|trail-status|trail-preview|trail-enable|trail-stop|trail-interval)$/.test(url))throw Error('Unsupported protection action.');
 const base=account.broker==='DHAN'?'/api/dhan/':account.broker==='MOTILAL_OSWAL'?'/api/motilal/':'/broker-workspace/'+encodeURIComponent(account.id)+'/api/'+(account.broker==='DELTA_INDIA'?'delta-india/':'');
 return base+url.slice(5)+'?account_id='+encodeURIComponent(account.id);
}
if(typeof module!=='undefined'&&module.exports){module.exports={supported,protectable,eligible,owns,endpoint};return;}
const money=(v,c='INR')=>typeof v==='number'&&Number.isFinite(v)?(c==='INR'?'₹':c+' ')+v.toLocaleString('en-IN',{maximumFractionDigits:2}):'—';
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const panels=[];
function mount(origin){
 const section=document.getElementById(origin);if(!section||section.querySelector('.analysis-trailing'))return;
 const panel=el('section',undefined,'panel analysis-trailing');panel.setAttribute('aria-label',(origin==='handoff'?'Analysis Handoff':'Screener')+' automatic trailing');
 panel.innerHTML='<div class="analysis-trail-head"><div><span class="label">EXISTING POSITIONS · PROTECTION</span><h2>Automatic trailing</h2><p>Review an existing holding or supported futures position, then explicitly enable trailing.</p></div><span class="analysis-trail-default">60 min default · editable</span></div><div class="analysis-trail-toolbar"><label class="field">Protection account<select aria-label="Protection account"><option value="">Choose an account</option></select></label><button class="button" data-review>Review held positions</button><button class="button secondary" data-monitor-status>Monitor status</button><button class="button secondary" data-stop-analysis hidden>Stop review</button></div><p class="analysis-trail-scope">Dhan, FYERS and Motilal delivery equities: 9:15 a.m.–3:30 p.m. IST on trading days. Delta verified linear futures: 24/7. Uses completed-daily evidence; unfilled recommendations and options are excluded. Existing strategy protection is never replaced.</p><p role="status" data-status>Select the exact account to read its positions. Monitoring is off until explicitly enabled.</p><div data-monitors></div><div data-rows></div>';
 // A separate protection panel keeps advisory/entry actions distinct from owned-position controls.
 const anchor=origin==='handoff'?section.querySelector('.handoff-exit-monitor'):section.querySelector('#screener-analysis');
 if(anchor)anchor.insertAdjacentElement(origin==='screener'?'beforebegin':'afterend',panel);else section.append(panel);
 const select=panel.querySelector('select'),review=panel.querySelector('[data-review]'),stop=panel.querySelector('[data-stop-analysis]'),note=panel.querySelector('[data-status]'),rows=panel.querySelector('[data-rows]');
 let revision=0,activeJob=null,busy=false,reportJob=null;
 const key='sector-pulse:'+origin+':protection-account';
 function account(){return root.BrokerForms.accounts().find(a=>a.id===select.value)||null;}
 function refreshAccounts(){
  const saved=select.value||localStorage.getItem(key)||'',context=root.BrokerForms.account(origin);
  select.replaceChildren(new Option('Choose an account',''));
  for(const a of root.BrokerForms.accounts()){
   const option=new Option(({DHAN:'Dhan',FYERS:'FYERS',MOTILAL_OSWAL:'Motilal Oswal',DELTA_INDIA:'Delta India'}[a.broker]||a.broker)+' · '+a.label+(supported(a)?'':' — trailing unavailable'),a.id);
   option.disabled=!supported(a);select.add(option);
  }
  select.value=[...select.options].some(o=>o.value===saved&&!o.disabled)?saved:supported(context)?context.id:'';
  review.disabled=!supported(account())||busy;
 }
 function source(a,job){
  const captured=revision;
  return {broker:a.broker,accountId:a.id,job,origin,fetch:async(url,options)=>{
   if(captured!==revision||select.value!==a.id)throw Error('Protection account changed. Reopen the review.');
   const payload=JSON.parse(options.body||'{}'),path=endpoint(a,url,payload);
   const response=await root.fetch(path,options);
   if(captured!==revision||select.value!==a.id)throw Error('Protection account changed during the request. Check the original account before another action.');
   return response;
  }};
 }
 function render(job){
  if(!owns(job,select.value,origin))return;
  reportJob=job;rows.replaceChildren();
  const report=job.output,list=report.rows||[],fresh=report.as_of&&Date.now()-Date.parse(report.as_of)<=600000;
  note.textContent=(fresh?'':'Saved review is stale; review positions again before enablement. ')+list.length+' position(s) reviewed · '+new Date(report.as_of).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+'. No new monitor or order started.';
  if(!list.length){rows.append(el('p',['FYERS','MOTILAL_OSWAL'].includes(job.request.payload.broker)?'No delivery holdings were returned. Intraday positions and options are outside this trailing route.':'No holdings or open positions were returned for this account.'));return;}
  const wrap=el('div',undefined,'analysis-trail-table-wrap'),table=el('table'),head=el('thead'),hr=el('tr');
  for(const label of ['Holding / position','Quantity','Profit / loss','Suggested stop','Protection'])hr.append(el('th',label));
  head.append(hr);table.append(head);const body=el('tbody'),a=account();
  for(const row of list){
   const tr=el('tr'),identity=el('td');identity.append(el('strong',row.symbol),el('small',row.holding_type||row.kind));tr.append(identity,el('td',String(row.quantity??'—')));
   const pnl=typeof row.gross_pnl==='number'?row.gross_pnl:row.broker_unrealized_pnl,p=el('td',money(pnl,row.currency));p.dataset.pnl=pnl>0?'profit':pnl<0?'loss':'flat';p.append(el('small','Gross unrealized · before costs'));tr.append(p,el('td',money(row.candidate_stop,row.currency)));
   const action=el('td'),button=el('button','Automatic trailing','button secondary');button.type='button';button.disabled=!protectable(row);
   action.append(button);
   if(protectable(row))root.HoldingsTrailing.decorate(button,row,source(a,job));
   else action.append(el('small',!fresh?'Run a fresh review':row.rationale||'No eligible delivery-equity trailing recommendation.'));
   tr.append(action);[...tr.children].forEach((cell,i)=>cell.dataset.label=['Holding / position','Quantity','Profit / loss','Suggested stop','Protection'][i]);body.append(tr);
  }
  table.append(body);wrap.append(table);rows.append(wrap);
 }
 function restore(){
  const saved=[...(root.SectorPulseJobs?.records?.values()||[])].map(r=>r.job).filter(j=>owns(j,select.value,origin)&&j.status==='COMPLETED').sort((a,b)=>b.created-a.created)[0];
  if(saved)render(saved);
 }
 select.onchange=()=>{
  revision++;reportJob=null;rows.replaceChildren();panel.querySelector('[data-monitors]').replaceChildren();localStorage.setItem(key,select.value);
  root.dispatchEvent(new CustomEvent('protection-account-change',{detail:{origin}}));
  review.disabled=!supported(account())||busy;note.textContent='Protection account changed. Review its current positions before enabling trailing.';restore();
 };
 const monitorStatus=panel.querySelector('[data-monitor-status]');
 monitorStatus.onclick=async()=>{
  const a=account();if(!supported(a)){note.textContent='Select the exact protection account first.';return;}
  monitorStatus.disabled=true;const captured=revision,target=panel.querySelector('[data-monitors]');
  try{
   const response=await source(a).fetch('/api/holdings-analysis/trail-status',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':root.BrokerForms.context()?.csrf||root.SectorPulseWorkspace?.csrf||''},body:JSON.stringify({broker:a.broker,account_id:a.id})});
   const data=await response.json();if(!response.ok)throw Error(data.error||'Monitor status unavailable.');
   if(captured!==revision)return;target.replaceChildren();
   if(!data.monitors.length){target.append(el('p','No saved trailing monitors for this account.'));return;}
   for(const state of data.monitors){
    const item=el('article',undefined,'analysis-trail-saved-monitor'),button=el('button','Open monitor controls','button secondary');
    item.append(el('strong',state.symbol+' · '+state.status.replaceAll('_',' ')),el('p','Every '+state.interval_minutes+' minutes · '+(state.message||'')));
    button.type='button';button.onclick=()=>root.HoldingsTrailing.open({symbol:state.symbol,quantity:state.quantity,average_price:state.average_price,holding_type:state.holding_type,currency:state.currency,candidate_stop:state.managed_stop?.ticket?.triggerPrice,action:'REVIEW_NEEDED',native_identity:{securityId:state.security_id,exchangeSegment:state.exchange_segment}},source(a));
    item.append(button);target.append(item);
   }
  }catch(error){if(captured===revision)note.textContent=error.message;}
  finally{monitorStatus.disabled=false;}
 };
 review.onclick=async()=>{
  const a=account();if(busy||!supported(a))return;
  busy=true;review.disabled=true;select.disabled=true;stop.hidden=false;const captured=revision;
  try{
   const headers={'Content-Type':'application/json','X-Job-Return-Accepted':'1','X-CSRF-Token':root.BrokerForms.context()?.csrf||root.SectorPulseWorkspace?.csrf||''};
   const response=await source(a).fetch('/api/holdings-analysis/analyze',{method:'POST',headers,body:JSON.stringify({broker:a.broker,account_id:a.id,offset:0,limit:1,inventory_only:true,trailing_origin:origin})});
   const accepted=await response.json();if(!response.ok)throw Error(accepted.error||'Portfolio review failed.');
   if(!accepted.job_id)throw Error('The server did not return a saved review job. Open Saved jobs before retrying.');
   const base=new URL(['FYERS','DELTA_INDIA'].includes(a.broker)?'/broker-workspace/'+encodeURIComponent(a.id)+'/api/jobs':'/api/jobs',location.origin);base.searchParams.set('account_id',a.id);
   activeJob={base:base.href,id:accepted.job_id};note.textContent='Review is running on the server. You can leave this section; output remains in Saved jobs.';
   const job=accepted.job?.terminal?accepted.job:await root.SectorPulseJobs.client.watch(base,accepted.job_id);
   if(captured!==revision)return;
   if(job.status!=='COMPLETED')throw Error(a.broker==='MOTILAL_OSWAL'&&String(job.error||job.message).includes('MotilalError')?'Motilal portfolio is unavailable. Check or reconnect that broker account, then review again. Saved monitor status and Stop remain available.':job.error||job.message||'Review did not complete.');
   render(job);
  }catch(error){if(captured===revision)note.textContent=error.message+' No trailing enablement was requested.';}
  finally{busy=false;activeJob=null;select.disabled=false;review.disabled=!supported(account());stop.hidden=true;}
 };
 stop.onclick=async()=>{if(!activeJob)return;stop.disabled=true;try{await root.SectorPulseJobs.client.cancel(activeJob.base,activeJob.id);}catch(error){note.textContent=error.message;}finally{stop.disabled=false;}};
 root.addEventListener('sector-pulse-jobs-refreshed',()=>{if(!busy&&!reportJob)restore();});
 root.addEventListener('sector-pulse-job-output',event=>{if(!busy&&owns(event.detail.job,select.value,origin))render(event.detail.job);});
 refreshAccounts();restore();panels.push({refreshAccounts});
}
async function start(){
 await root.BrokerForms.ready;
 const style=el('style');style.textContent='.analysis-trailing{margin-top:24px;border-top:3px solid #5882a9}.analysis-trail-head{display:flex;align-items:start;justify-content:space-between;gap:24px}.analysis-trail-head h2{margin:7px 0 10px}.analysis-trail-head p,.analysis-trail-scope{color:#adc0d3;line-height:1.65}.analysis-trail-default{border:1px solid #405a73;border-radius:6px;padding:9px 12px;color:#b8d3e8;white-space:nowrap;font-size:12px}.analysis-trail-toolbar{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin:20px 0}.analysis-trail-toolbar .field{min-width:260px;flex:1;max-width:440px;margin:0}.analysis-trail-toolbar .button{min-height:40px;margin:0!important;box-sizing:border-box}.analysis-trailing [role=status]{padding:12px 0;color:#bdd0e2}.analysis-trail-saved-monitor{border:1px solid #354e67;border-radius:8px;padding:16px;margin:14px 0}.analysis-trail-saved-monitor p{line-height:1.6;color:#adc0d3}.analysis-trail-table-wrap{overflow:auto}#screener .analysis-trailing table,#handoff .analysis-trailing table{width:100%;min-width:0;table-layout:auto;border-collapse:collapse}.analysis-trailing th{text-align:left;font-size:11px;letter-spacing:.05em;color:#a9bfd4;padding:14px 12px;border-bottom:1px solid #456079}.analysis-trailing td{padding:18px 12px;border-bottom:1px solid #2e445b;vertical-align:middle;font-variant-numeric:tabular-nums}.analysis-trailing td small{display:block;font-size:11px;color:#9db4c9;margin-top:8px;max-width:270px;line-height:1.5}.analysis-trailing td[data-pnl=profit]{color:#83d8b0}.analysis-trailing td[data-pnl=loss]{color:#ff9a99}.analysis-trailing td:last-child{border-left:1px solid #2e445b;min-width:170px}.analysis-trailing button:focus-visible,.analysis-trailing select:focus-visible{outline:3px solid #8fd4ff;outline-offset:3px}.analysis-trailing [hidden]{display:none!important}@media(max-width:1000px){.analysis-trailing table,.analysis-trailing tbody{display:block}.analysis-trailing thead{display:none}.analysis-trailing tbody{display:grid;gap:14px}.analysis-trailing tr{display:grid;grid-template-columns:1fr 1fr;border:1px solid #354e67;border-radius:8px;overflow:hidden}.analysis-trailing td{display:block;min-width:0;padding:14px 16px}.analysis-trailing td:before{content:attr(data-label);display:block;color:#a9bfd4;font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:9px}.analysis-trailing td:first-child,.analysis-trailing td:last-child{grid-column:1/-1}.analysis-trailing td:last-child{border-left:0;border-bottom:0;min-width:0}.analysis-trailing td:last-child .button{width:100%;min-height:40px}}@media(max-width:720px){.analysis-trail-head{flex-direction:column;gap:10px}.analysis-trail-toolbar{display:grid;grid-template-columns:1fr}.analysis-trail-toolbar .field{min-width:0;max-width:none}.analysis-trail-toolbar .button{width:100%}}';document.head.append(style);
 mount('screener');mount('handoff');
 root.addEventListener('broker-accounts-ready',()=>panels.forEach(p=>p.refreshAccounts()));
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})(typeof window==='undefined'?globalThis:window);
