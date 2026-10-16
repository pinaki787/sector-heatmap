/* Read-only job reporting. Every view binds to one account and one runner identity. */
(function(root){
'use strict';
const finite=n=>typeof n==='number'&&Number.isFinite(n);
function epoch(value){if(finite(value))return value;if(typeof value==='string'){const n=Date.parse(value);if(Number.isFinite(n))return n/1000;}return null;}
function identity(state){return state.run_id||state.run_started_at||state.started_at||null;}
function rows(state,audit){
 if(audit&&audit.run_id===identity(state))return audit.trades||[];
 const start=epoch(state.run_started_at||state.started_at),run=identity(state);
 return (state.trade_history||state.position_history||[]).filter(row=>{
  const owners=new Set([row.run_id,...(row.orders||[]).map(o=>o.run_id)].filter(Boolean));
  if(owners.size)return !!run&&owners.size===1&&owners.has(run);
  const entry=epoch(row.entry_time||row.opened_at);return start!==null&&entry!==null&&entry>=start;
 });
}
function lifecycle(state){
 if(state.status==='STALLED'||state.heartbeat?.stalled===true)return {label:'Stalled',detail:state.heartbeat?.reason||state.message||'Runner reported a stalled heartbeat.',tone:'warning'};
 if(state.pending)return {label:'Reconciling order',detail:'Broker order reconciliation remains active.',tone:'warning'};
 if(state.shutdown_pending)return {label:'Stopping',detail:'Waiting for the runner’s existing stop behavior to finish.',tone:'warning'};
 if(state.running)return {label:'Running',detail:state.position?'Managing an owned position.':'Watching for eligible entry criteria.',tone:'live'};
 if(state.position)return {label:'Monitoring paused',detail:'The owned position remains recorded; check its protection.',tone:'warning'};
 return {label:identity(state)?'Stopped':'Saved',detail:'Opening this view does not start the runner.',tone:'quiet'};
}
function tradePnl(row){
 const cost=row.costs||{};
 const realized=finite(cost.realized_net)?cost.realized_net:null,unrealized=finite(cost.unrealized_net)?cost.unrealized_net:null;
 if(realized!==null&&(!row.remaining_quantity||unrealized!==null))return {value:realized+(row.remaining_quantity?unrealized:0),basis:'After estimated costs'};
 const gross=finite(row.realized_pnl)?row.realized_pnl:null;
 return {value:gross,basis:gross!==null?'Realized · before fees':'Unavailable; confirmed fill/valuation evidence missing'};
}
function render(container,model){
 const doc=container.ownerDocument,state=model.state||{},audit=model.audit||state.job_audit,trades=rows(state,audit),life=model.lifecycleStatus&&['COMPLETED','FAILED','CANCELLED','INTERRUPTED'].includes(model.lifecycleStatus)?{label:model.lifecycleStatus.charAt(0)+model.lifecycleStatus.slice(1).toLowerCase(),detail:'Saved job output; current runner activity is available from the runner list.',tone:'quiet'}:lifecycle(state),currency=state.pnl_currency||(model.account?.broker==='DELTA_INDIA'?null:'INR');
 const el=(tag,text,cls)=>{const node=doc.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
 const date=v=>epoch(v)!==null?new Date(epoch(v)*1000).toLocaleString('en-IN'):'Not recorded';
 const price=v=>finite(v)?v.toLocaleString('en-IN',{maximumFractionDigits:4}):'Unavailable';
 const money=v=>finite(v)&&currency?currency+' '+v.toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2}):'Unavailable';
 const expanded=new Set([...container.querySelectorAll('details[open]')].map(n=>n.dataset.auditKey));
 container.replaceChildren();container.classList.add('runner-detail');
 const header=el('header',undefined,'runner-detail-heading'),titles=el('div');titles.append(el('p',(model.account?.label||'Selected account')+' · '+(model.strategy||state.strategy||'Runner'),'runner-detail-eyebrow'),el('h3',model.title||state.config?.underlying||state.config?.symbol||'Runner details'));header.append(titles,el('span',life.label,'runner-status runner-status-'+life.tone));container.append(header);
 container.append(el('p',model.connectionError?'Status connection delayed. Last saved evidence is shown; the runner has not been declared stalled.':life.detail,'runner-detail-note'));
 const metrics=el('div',undefined,'runner-detail-metrics');
 const gross=trades.length&&trades.every(t=>finite(t.realized_pnl))?trades.reduce((sum,t)=>sum+t.realized_pnl,0):null;
 for(const [label,value] of [['Net profit / loss',money(state.cost_pnl?.total_net)],['Realized · before fees',money(gross)],['Trades recorded',String(trades.filter(t=>t.status!=='UNFILLED').length)],['Mode',state.config?.mode||state.mode||'Unknown'],['Started',date(state.run_started_at||state.started_at)]]){const tile=el('div');tile.append(el('span',label),el('strong',value));metrics.append(tile);}container.append(metrics);
 container.append(el('p',state.cost_pnl?.basis||'After-cost job P&L is unavailable from this runner. Trade rows show their recorded P&L basis.','runner-detail-note'));
 const actions=el('div',undefined,'runner-detail-actions');
 if(model.chartUrl){const a=el('a','Open candle chart');a.href=model.chartUrl;actions.append(a);}
 if(model.onRefresh){const b=el('button','Refresh job');b.type='button';b.onclick=model.onRefresh;actions.append(b);}
 if(model.onStop){const b=el('button','Stop this job');b.type='button';b.onclick=model.onStop;actions.append(b);}
 const download=el('button','Download trade journal');download.type='button';download.onclick=()=>{const value={run_id:identity(state),account_id:model.account?.id,broker:model.account?.broker,trades,events:audit?.events||state.events||[],observed_at:model.observedAt};const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download='runner-trade-journal.json';a.click();URL.revokeObjectURL(url);};actions.append(download);container.append(actions);
 const reference=el('details'),referenceTitle=el('summary','Job identity and update time');reference.dataset.auditKey='identity';reference.append(referenceTitle,el('p',String(model.jobId||identity(state)||'Not recorded')),el('p','Status received: '+date(model.observedAt||audit?.observed_at)));container.append(reference);
 container.append(el('h4','Trade journal'));
 if(!trades.length)container.append(el('p','No trades with verified ownership for this run. Older or unassigned records remain in the strategy journal.','runner-detail-empty'));
 else{
  const scroll=el('div',undefined,'runner-journal-scroll'),table=el('table'),thead=el('thead'),head=el('tr');
  for(const label of ['Contract / status','Entry time','Entry price','Exit time','Exit price','Quantity','Profit / loss','Entry criteria & audit'])head.append(el('th',label));thead.append(head);table.append(thead);const body=el('tbody');
  for(const row of trades){const tr=el('tr'),pnl=tradePnl(row),add=text=>{const cell=el('td',text);tr.append(cell);return cell;};add((row.contract||row.symbol||row.underlying_symbol||'Unknown contract')+' · '+(row.status||'Recorded'));add(date(row.entry_time));add(price(row.entry_price));add(date(row.end_time||row.exit_time));add(price(row.exit_price));add(String(row.entry_filled??row.quantity??'Unavailable'));const cell=add(money(pnl.value));cell.append(el('small',pnl.basis));const details=el('details'),summary=el('summary','View trade audit');details.append(summary);
   details.dataset.auditKey='trade:'+String(row.audit_id||row.trade_id||row.lifecycle_id||row.entry_time);
   const criteria=(row.entry_reasons||[]).filter(Boolean).join(' · ')||row.entry_reason||'Entry reason was not recorded.';
   details.append(el('p','Entry: '+criteria),el('p','Exit: '+((row.exit_reasons||[]).filter(Boolean).join(' · ')||row.exit_reason||'Not recorded')));
   for(const [label,value] of [['Entry indicator evidence',row.entry_indicator_snapshot],['Exit indicator evidence',row.exit_indicator_snapshots],['Order and fill events',row.orders],['Reconciliation events',row.reconciliation_events]])if(value&&(Array.isArray(value)?value.length:true)){details.append(el('h5',label));const pre=el('pre',JSON.stringify(value,null,2));details.append(pre);}
   add('').append(details);body.append(tr);
  }table.append(body);scroll.append(table);container.append(scroll);
 }
 if(audit?.unassigned_rows)container.append(el('p',audit.unassigned_rows+' journal rows could not be assigned to this run and are excluded.','runner-detail-note'));
 const events=audit?.events||[];if(events.length){const section=el('details'),summary=el('summary','Runner activity ('+events.length+')');section.dataset.auditKey='activity';section.append(summary);for(const event of events)section.append(el('p',date(event.at||event.timestamp)+' · '+(event.status||event.kind||'Event')+' · '+(event.message||'')));container.append(section);}
 for(const node of container.querySelectorAll('details'))if(expanded.has(node.dataset.auditKey))node.open=true;
 return {trades:trades.length,run:identity(state)};
}
function installStyle(doc){if(doc.getElementById('runner-detail-styles'))return;const style=doc.createElement('style');style.id='runner-detail-styles';style.textContent=`.runner-detail{border-top:2px solid #83b7e5;margin-top:22px;padding-top:20px;color:#e4ecf7;font-family:inherit}.runner-detail-heading{display:flex;justify-content:space-between;align-items:center;gap:16px}.runner-detail h3{font-size:22px;margin:4px 0 12px}.runner-detail-eyebrow,.runner-detail-note{color:#acbbcf;font-size:13px;line-height:1.6}.runner-status{border:1px solid #52647e;border-radius:5px;padding:6px 10px;font-size:12px;white-space:nowrap}.runner-status-live{color:#a8e4ce;border-color:#408b78}.runner-status-warning{color:#f2cf89;border-color:#957b43}.runner-detail-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1px;background:#34445c;border:1px solid #34445c;border-radius:8px;overflow:hidden}.runner-detail-metrics>div{padding:16px;background:#18273b;min-width:0}.runner-detail-metrics span{display:block;color:#acbbcf;font-size:12px}.runner-detail-metrics strong{display:block;margin-top:8px;font-variant-numeric:tabular-nums;font-size:17px;overflow-wrap:anywhere}.runner-detail-actions{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}.runner-detail button,.runner-detail-actions a{font:inherit;font-size:13px;border:1px solid #52647e;background:#263953;color:#dbeaf7;border-radius:5px;padding:9px 12px;text-decoration:none;cursor:pointer}.runner-detail :is(button,a,summary):focus-visible{outline:2px solid #91c4ff;outline-offset:3px}.runner-detail details{margin:10px 0}.runner-detail summary{cursor:pointer;color:#b4d6f5}.runner-detail pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:280px;overflow:auto;font-size:12px;background:#101b2b;padding:12px}.runner-journal-scroll{overflow:auto}.runner-detail table{width:100%;min-width:980px;border-collapse:collapse;table-layout:fixed}.runner-detail :is(th,td){position:static;white-space:normal;overflow-wrap:anywhere}.runner-detail th:first-child{width:150px}.runner-detail th:last-child{width:210px}.runner-detail :is(th,td){text-align:left;padding:12px 10px;border-bottom:1px solid #34445c;vertical-align:top;font-size:12px}.runner-detail th{color:#acbbcf;white-space:nowrap}.runner-detail td{font-variant-numeric:tabular-nums}.runner-detail td small{display:block;color:#acbbcf;margin-top:5px}.runner-detail-empty{padding:22px;border:1px dashed #52647e;border-radius:6px;color:#acbbcf}@media(max-width:700px){.runner-detail-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.runner-detail-heading{align-items:flex-start}.runner-detail h3{font-size:18px}}`;doc.head.append(style);}
if(typeof module!=='undefined'&&module.exports){module.exports={identity,rows,lifecycle,tradePnl,render,installStyle};return;}
root.RunnerJobDetails={identity,rows,lifecycle,tradePnl,render,installStyle};installStyle(document);
})(typeof window==='undefined'?globalThis:window);
