"""Dhan retail option fee estimates, not contract-note charges."""
from .costs import D,rounded,valid,settings
MODEL=dict(id='DHAN_OPTIONS_2026_10_V1',verified_on='2026-10-11',
 sources=['https://options-trader.co/pricing/','https://dhan.co/pricing/','https://www.mcxccl.com/clearing-settlement/commodities-transaction-tax','https://www.mcxccl.com/clearing-settlement/faq'],
 brokerage_per_executed_order=20,
 basis='Retail regular option premium trades only; estimated charges, excludes exercise and delivery.')
def fee(turnover,side,exchange_rate=None):
    if exchange_rate==0.000418:return mcx_fee(turnover,side)
    if exchange_rate not in (0.000355299,0.000325,0.00005):raise ValueError('Verified Dhan exchange rate unavailable.')
    t=D(turnover)
    parts=dict(brokerage=D(20),exchange=rounded(t*D(exchange_rate)),sebi=rounded(t*D('0.000001')),
       ipft=rounded(t*D('0.000000001')),stt=rounded(t*D('0.0015'),'1') if side=='SELL' else D(0),
       stamp=rounded(t*D('0.00003'),'1') if side=='BUY' else D(0))
    parts['gst']=rounded(sum(parts[k] for k in ('brokerage','exchange','sebi','ipft'))*D('.18'))
    return {**{k:float(v) for k,v in parts.items()},'total':float(sum(parts.values())),'premium_turnover':float(t)}
def order_cost(row):
    if not row.get('filled') or not valid(row.get('average_price')) or not valid(row.get('quantity_multiplier')):return None
    try:return fee(D(row['filled'])*D(row['average_price'])*D(row['quantity_multiplier']),row['side'],row.get('dhan_exchange_rate'))
    except ValueError:return None
def trade_costs(trade,ledger):
    rows=[r for r in trade['orders'] if r.get('filled')]
    keys=[r.get('tag') or r.get('order_id') for r in rows]
    if not rows or any(ledger.get(k) is None for k in keys):
        return dict(available=False,reason='Verified Dhan option contract rates or complete fill evidence unavailable.',model=MODEL,realized_net=None,unrealized_net=None)
    entries=[r for r in rows if r['side']=='BUY'];exits=[r for r in rows if r['side']=='SELL']
    sumcost=lambda rs:sum(D(ledger[r.get('tag') or r.get('order_id')]['total']) for r in rs)
    buy=sumcost(entries);sell=sumcost(exits)
    bought=trade['entry_filled'];sold=trade['exit_filled'];remaining=trade['remaining_quantity']
    if not bought or remaining is None or sold>bought:return dict(available=False,reason='Owned quantity pairing unavailable.',model=MODEL,realized_net=None,unrealized_net=None)
    cfg=(trade.get('entry_indicator_snapshot') or {}).get('settings') or {}
    slip=D(settings(cfg)['additional_slippage_points']);mult=D(trade.get('quantity_multiplier') or 1)
    realized_slip=slip*D(sold*2)*mult
    buy_alloc=rounded(buy*D(sold)/D(bought));open_buy=buy-buy_alloc
    gross=trade.get('realized_pnl')
    realized_net=float(rounded(D(gross)-buy_alloc-sell-realized_slip)) if sold and valid(gross) else 0.0 if not sold else None
    quote=trade.get('valuation') or {};bid=quote.get('bid')
    projected=fee(D(bid)*D(remaining)*mult,'SELL',exchange_rate=rows[0].get('dhan_exchange_rate')) if remaining and valid(bid) else None
    open_slip=slip*D(remaining*2)*mult
    unrealized=trade.get('unrealized_pnl')
    open_net=float(rounded(D(unrealized)-open_buy-D(projected['total'])-open_slip)) if remaining and projected and valid(unrealized) else 0.0 if not remaining else None
    parts={k:float(sum(D(ledger[key].get(k,0)) for key in keys)) for k in ['brokerage','exchange','sebi','ipft','stt','ctt','stamp','gst','total']}
    return dict(available=True,model=MODEL,kind='PAPER_ESTIMATE' if trade['mode']=='PAPER' else 'LIVE_FILL_BASED_ESTIMATE_UNRECONCILED',incurred=parts,entry_costs_incurred=float(buy),exit_costs_incurred=float(sell),entry_costs_allocated_realized=float(rounded(buy_alloc)),entry_costs_remaining=float(rounded(open_buy)),estimated_exit_costs=projected,realized_net=realized_net,unrealized_net=open_net,additional_slippage_points=float(slip),realized_additional_slippage=float(realized_slip),open_liquidation_additional_slippage=float(open_slip),actual_slippage='Embedded in execution fill prices; separately measured amount unavailable, no double deduction.',orders=[dict(order_key=k,**ledger[k]) for k in keys])


def mcx_fee(turnover,side):
    """Regular non-agricultural option premium trades; excludes exercise/delivery."""
    if side not in ('BUY','SELL'):raise ValueError('Explicit fee side required.')
    t=D(turnover)
    if t<0:raise ValueError('Premium turnover cannot be negative.')
    parts=dict(brokerage=D(20),exchange=rounded(t*D('.000418')),
               sebi=rounded(t*D('.000001')),ipft=D(0),stt=D(0),
               ctt=rounded(t*D('.0005'),'1') if side=='SELL' else D(0),
               stamp=rounded(t*D('.00003'),'1') if side=='BUY' else D(0))
    parts['gst']=rounded(sum(parts[k] for k in ('brokerage','exchange','sebi','ipft'))*D('.18'))
    return {**{k:float(v) for k,v in parts.items()},'total':float(sum(parts.values())),
            'premium_turnover':float(t),'segment':'MCX_COMM'}
