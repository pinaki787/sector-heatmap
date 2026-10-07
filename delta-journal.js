/* Journal projection only: never reconstruct missing historical indicators. */
(function(root){
 const number=v=>v!=null&&Number.isFinite(Number(v))?Number(v):null;
 root.DeltaJournalRows=({state={},account=null,conversion=null,now=Date.now()/1000})=>{
  const rows=[];
  const add=(base,context)=>{
   const c=context||{},bar=c.candle||{},cfg=c.settings||{},bb=c.bollinger||{},policy=c.inr_conversion||conversion;
   const native=base.fill_price!=null&&base.quantity!=null&&base.contract_value!=null?base.fill_price*base.quantity*base.contract_value:null;
   const valid=policy?.rate>0&&Number.isFinite(policy.verified_at)&&(c.inr_conversion?c.observed_at:now)-policy.verified_at>=-2&&(c.inr_conversion?c.observed_at:now)-policy.verified_at<=86400;
   rows.push({...base,strike:root.DeltaOptionStrike?root.DeltaOptionStrike({symbol:base.symbol}):(/^[CP]-[^-]+-([^-]+)-/.exec(base.symbol||'')?.[1]||null),
    underlying:c.symbol||base.signal_symbol||null,timeframe:c.timeframe||null,candle_time:bar.timestamp??null,candle_completed:bar.completed??null,
    open:bar.open??null,high:bar.high??null,low:bar.low??null,close:bar.close??null,rsi:c.rsi??null,rsi_length:cfg.rsi_length??null,ma_type:cfg.ma_type??null,ma_length:cfg.ma_length??null,rsi_ma:c.rsi_ma??null,
    bb_upper:bb.upper??null,bb_middle:bb.middle??null,bb_lower:bb.lower??null,bb_length:bb.length??null,bb_deviation:bb.deviation??null,bb_basis:bb.basis||c.bollinger_unavailable||'Not recorded',
    transition:c.transition||null,signal_price:c.signal_price??null,reversal_price:c.reversal_price??null,reason:c.reason||base.reason||'Not recorded',
    observed_at:c.observed_at??null,evidence:c.capture_kind||'NOT_RECORDED_LEGACY',unavailable:c.unavailable||null,price_basis:c.price_basis||'Not recorded',
    native_value:native,value_basis:/^[CP]-/.test(base.symbol||'')?'Option premium before fees':'Futures notional; not margin or cash invested',
    inr_equivalent:valid&&base.currency==='USD'&&native!=null?native*policy.rate:base.currency==='INR'?native:null,
    inr_rate:valid&&base.currency==='USD'?policy.rate:null,inr_source:valid?policy.source:null,inr_verified_at:valid?policy.verified_at:null,
    inr_basis:c.inr_conversion?'Policy recorded with event':'Export/display-time policy; historical INR cash not recorded',context_json:context?JSON.stringify(context):'Not recorded',context:context||null});
  };
  for(const t of state.paper?.trades||[]){const base={workflow:'PAPER',id:t.lifecycle_id||t.id,symbol:t.symbol,side:t.side,currency:t.quote_currency,contract_value:number(t.contract_value),signal_symbol:t.signal_symbol};
   add({...base,event:'ENTRY',time:t.entry_time,quantity:number(t.contracts),fill_price:number(t.entry_price),status:t.status,reason:t.entry_reason},t.entry_context);
   for(const [i,f] of (t.exit_fills||[]).entries())add({...base,event:'EXIT',id:base.id+':exit:'+i,time:f.time,quantity:number(f.contracts),fill_price:number(f.price),status:'FILLED',reason:f.reason,realized_pnl:number(f.pnl)},f.event_context);
   if(!(t.exit_fills||[]).length&&t.status==='CLOSED')add({...base,event:'LEGACY EXIT AVERAGE',time:t.exit_time,quantity:number(t.contracts),fill_price:number(t.exit_price),status:'CLOSED',realized_pnl:number(t.realized_pnl)},null);
  }
  for(const o of state.orders||[]){const base={workflow:'LIVE',id:o.request_id,symbol:o.symbol,side:o.request?.side,currency:o.product?.quoting_currency,contract_value:o.product?.notional_type==='vanilla'&&o.product?.is_quanto===false&&o.product?.contract_unit_currency===o.product?.underlying&&o.product?.quoting_currency===o.product?.settlement_currency?number(o.product.contract_value):null,signal_symbol:o.signal_symbol};
   const merged=new Map((o.journal_fills||[]).map(f=>[String(f.id),f]));for(const f of account?.fills||[])if(f.id!=null&&o.order_id!=null&&String(f.order_id)===String(o.order_id)&&String(f.product_id)===String(o.request?.product_id)&&f.symbol===o.symbol&&f.side===o.request?.side)merged.set(String(f.id),f);
   if(!merged.size)add({...base,event:'ORDER SNAPSHOT',time:o.updated_at||o.created_at,quantity:number(o.filled_contracts),fill_price:number(o.average_fill_price),status:o.status,reason:o.execution_reason},o.event_context);
   for(const f of merged.values())add({...base,event:o.request?.reduce_only?'EXIT':'ENTRY',id:base.id+':fill:'+f.id,time:typeof f.created_at==='number'?f.created_at:Date.parse(f.created_at)/1000,quantity:number(f.size),fill_price:number(f.price),status:'BROKER FILL',reason:o.execution_reason},o.event_context);
  }
  return rows.sort((a,b)=>(a.time||0)-(b.time||0));
 };
})(typeof window==='undefined'?globalThis:window);
