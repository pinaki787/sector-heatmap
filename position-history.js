/* Read-only ledger projection. Legacy links require retained ownership events. */
(function(root){
 function project(state){
  const rows=(state.order_history || []).map(r=>({...r,...(root.PositionHistoryMetadata?.[r.symbol] || {})})),events=state.events || [];
  for(const r of rows)if(!r.strategy)r.strategy=r.reason==='EMA_CLOSE_ENTRY'?'EMA Cloud (historical)':r.reason==='RSI_CLOSE_ENTRY'?'RSI (historical MA unavailable)':'Unavailable (legacy ledger)';
  for(const link of root.PositionHistoryLinks || []){
   const entry=rows.filter(r=>r.order_id===link.entry_order_id&&r.symbol===link.symbol&&r.mode===link.mode&&r.filled===link.quantity&&r.average_price===link.entry_price);
   const exits=rows.filter(r=>link.exit_order_ids.includes(r.order_id)&&r.symbol===link.symbol&&r.mode===link.mode&&r.filled===link.quantity&&r.average_price===link.exit_price);
   if(entry.length===1&&exits.length===link.exit_order_ids.length)for(const r of [...entry,...exits]){r.lifecycle_id=entry[0].tag;r.strategy=link.strategy;r.linkage_source=link.source;}
  }
  let owner=null;
  const ordered=[...rows].sort((a,b)=>a.submitted_at-b.submitted_at);
  const confirmed=(r,status)=>events.some(e=>{const match=e.message?.match(/^([^:]+): confirmed ([0-9]+) filled at ([0-9.]+);/);return e.status===status&&Math.abs(e.at-r.updated_at)<.1&&match?.[1]===r.reason&&Number(match[2])===r.filled&&Number(match[3])===r.average_price;});
  for(const r of ordered){
   if(r.lifecycle_id)continue;
   if(r.side==='BUY'){
    if(owner){owner=null;continue;}
    if(r.filled>0&&confirmed(r,'POSITION_OPEN')){r.lifecycle_id=r.tag;r.linkage_source='Retained POSITION_OPEN ownership event';owner=r;}
   }else if(owner&&r.symbol===owner.symbol&&r.mode===owner.mode&&r.product===owner.product&&r.filled>0&&r.filled<=owner.filled&&confirmed(r,r.filled===owner.filled?'FLAT':'POSITION_OPEN')){
    r.lifecycle_id=owner.lifecycle_id;r.strategy=owner.strategy;r.linkage_source='Retained confirmed owned-exit event';if(r.filled===owner.filled)owner=null;else owner={...owner,filled:owner.filled-r.filled};
   }else if(r.filled)owner=null;
  }
  const p=state.position;
  if(p){const matches=rows.filter(r=>r.side==='BUY'&&r.symbol===p.symbol&&r.mode===state.config?.mode&&r.filled===p.quantity&&r.average_price===p.entry_price&&Math.abs(r.updated_at-p.opened_at)<.1&&(p.entry_order_id?r.order_id===p.entry_order_id:true));if(matches.length===1){const r=matches[0];r.lifecycle_id=r.lifecycle_id || r.tag;r.lot_size=p.lot_size;r.quantity_multiplier=p.quantity_multiplier;r.linkage_source='Exact current owned-position fill and timestamp';if(r.reason==='RSI_CLOSE_ENTRY')r.strategy=state.config?.label || r.strategy;}}
  const groups=new Map();for(const r of rows){const key=[r.mode,r.lifecycle_id || 'unpaired:'+r.tag].join(':');if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}
  return [...groups.values()].reverse().map(rs=>{
   const b=rs.filter(r=>r.side==='BUY'),s=rs.filter(r=>r.side==='SELL'),qty=a=>a.reduce((n,r)=>n+(r.filled || 0),0),avg=a=>qty(a)&&a.every(r=>!r.filled||Number.isFinite(r.average_price))?a.reduce((n,r)=>n+(r.filled || 0)*(r.average_price || 0),0)/qty(a):null;
   const bought=qty(b),sold=qty(s),buy=avg(b),sell=avg(s),linked=!!rs[0].lifecycle_id,matched=linked&&sold<=bought?sold:null;
   const meta=rs.find(r=>r.quantity_multiplier>0),mult=meta?.quantity_multiplier,lot=rs.find(r=>r.lot_size>0)?.lot_size;
   const pnl=matched>0&&buy!=null&&sell!=null&&mult>0?matched*(sell-buy)*mult:null;
   return {contract:rs[0].symbol,status:!linked?'PAIRING UNAVAILABLE':!bought?'UNFILLED':sold===bought?'CLOSED':sold?'PARTIAL EXIT':'OPEN',strategy:b[0]?.strategy || rs[0].strategy,mode:rs[0].mode,entry_order_ids:b.map(r=>r.order_id || 'Paper tag '+r.tag),exit_order_ids:s.map(r=>r.order_id || 'Paper tag '+r.tag),entry_price:buy,exit_price:sell,invested_amount:bought&&buy!=null&&mult>0?bought*buy*mult:null,realized_pnl:pnl,pnl_percent:pnl==null?null:100*(sell-buy)/buy,entry_requested:b.reduce((n,r)=>n+r.requested,0),exit_requested:s.reduce((n,r)=>n+r.requested,0),entry_filled:bought,exit_filled:sold,matched_quantity:matched,lots:lot&&bought?bought/lot:null,entry_time:b.find(r=>r.filled)?.updated_at,exit_time:s.filter(r=>r.filled).at(-1)?.reason==='EXTERNAL_MANUAL_EXIT_RECONCILIATION'?null:s.filter(r=>r.filled).at(-1)?.updated_at,exit_time_detail:s.some(r=>r.reason==='EXTERNAL_MANUAL_EXIT_RECONCILIATION')?'External fill time unavailable':null,entry_types:b.map(r=>r.requested_type),exit_types:s.map(r=>r.requested_type),products:[...new Set(rs.map(r=>r.product))],entry_reasons:b.map(r=>r.reason),exit_reasons:s.map(r=>r.reason)};
  });
 }
 root.PositionHistory={project};if(typeof module!=='undefined')module.exports={project};
})(typeof window!=='undefined'?window:globalThis);
