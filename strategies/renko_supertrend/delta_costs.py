"""Delta native-currency regular option fee estimates; never broker invoices.

Current product taker rate is saved with each order. Official India fee page:
https://www.delta.exchange/fees (verified 2026-10-07): 3.5% premium cap,
18% GST on trading fees. Expiry/settlement/liquidation costs are excluded.
"""
from decimal import Decimal
import math

MODEL=dict(id='DELTA_INDIA_OPTION_NATIVE_ESTIMATE_2026_10_07',source='https://www.delta.exchange/fees',
           premium_cap=.035,gst=.18,basis='Recorded native commission when available, otherwise product taker rate × observed index notional, capped at 3.5% premium; GST estimated at 18%. No discounts assumed. Not broker-invoiced costs; regular filled option BUY/SELL only, excludes expiry/exercise/liquidation.')


def number(value):
    if isinstance(value,bool):raise ValueError('Invalid native cost evidence.')
    n=Decimal(str(value))
    if not n.is_finite() or n<0:raise ValueError('Invalid native cost evidence.')
    return n


def order_cost(row):
    try:
        qty=number(row['filled']); price=number(row['average_price']); units=number(row['quantity_multiplier'])
        if min(qty,price,units)<=0:return None
        if row.get('execution_route')=='DELTA_PERPETUAL':
            commission=row.get('native_commission')
            fee=number(commission) if commission is not None else qty*units*price*number(row['taker_commission_rate'])
            return dict(commission=float(fee),gst=float(fee*number(MODEL['gst'])),total=float(fee*(1+number(MODEL['gst']))),
                        kind='PERPETUAL_TRADING_FEE_ESTIMATE',currency=row['quote_currency'],
                        model=dict(id='DELTA_PERPETUAL_TRADING_FEES_ONLY',basis='Recorded commission or product taker rate on fill notional; estimated GST. Funding/liquidation excluded.'))
        commission=row.get('native_commission')
        if commission is not None:
            fee=number(commission);kind='BROKER_COMMISSION_PLUS_ESTIMATED_GST'
        else:
            policy=row['native_fee_policy']; rate=number(policy['taker_rate']); index=number(policy['index_price'])
            if not 0<rate<1 or index<=0:return None
            fee=min(qty*units*index*rate,qty*units*price*number(MODEL['premium_cap']))
            kind='NATIVE_TAKER_ESTIMATE'
        gst=fee*number(MODEL['gst'])
        return dict(commission=float(fee),gst=float(gst),total=float(fee+gst),kind=kind,
                    currency=row['quote_currency'],model=MODEL)
    except (KeyError,ValueError,TypeError,ArithmeticError):return None


def trade_costs(trade,ledger):
    rows=[r for r in trade['orders'] if r.get('filled')]
    get=lambda r:ledger.get(r.get('tag') or r.get('order_id'))
    unavailable=dict(available=False,model=MODEL,reason='Native fee or index observation unavailable; costs remain unknown.',realized_net=None,unrealized_net=None)
    if not rows or any(get(r) is None for r in rows):return unavailable
    if len({get(r)['currency'] for r in rows})!=1:return unavailable
    bought=trade['entry_filled'];sold=trade['exit_filled'];remaining=trade['remaining_quantity']
    if not bought or remaining is None or sold>bought:return unavailable
    buy=sum(get(r)['total'] for r in rows if r.get('is_entry',r['side']=='BUY'));sell=sum(get(r)['total'] for r in rows if not r.get('is_entry',r['side']=='BUY'))
    allocated=buy*sold/bought
    cfg=(trade.get('entry_indicator_snapshot') or {}).get('settings') or {}
    slip=float(cfg.get('additional_slippage_points') or 0)*sold*2*trade['quantity_multiplier']
    gross=trade.get('realized_pnl')
    net=gross-allocated-sell-slip if isinstance(gross,(float,int)) and math.isfinite(gross) else 0 if not sold else None
    if trade.get('execution_route')=='DELTA_PERPETUAL':
        return dict(available=False,realized_net=None,unrealized_net=None,trading_fees=sum(get(r)['total'] for r in rows),
                    model=get(rows[0])['model'],reason='Funding/liquidation evidence unavailable; all-in net and after-cost loss filtering remain unknown.')
    incurred={key:sum(get(r)[key] for r in rows) for key in ('commission','gst','total')}
    return dict(available=True,model=MODEL,kind='NATIVE_COST_ESTIMATE',currency=get(rows[0])['currency'],incurred=incurred,
                entry_costs_incurred=buy,exit_costs_incurred=sell,entry_costs_allocated_realized=allocated,
                entry_costs_remaining=buy-allocated,realized_net=net,unrealized_net=0 if remaining==0 else None,
                estimated_exit_costs=None,orders=[dict(order_key=r.get('tag'),**get(r)) for r in rows],
                reason='Open liquidation fee requires a fresh index observation; unavailable until that evidence exists.')
