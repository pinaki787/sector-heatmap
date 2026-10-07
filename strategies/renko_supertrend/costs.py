"""Explicit Sensex-options cost estimates from owned cumulative fills, never broker bills."""
from decimal import Decimal,ROUND_HALF_UP
from datetime import datetime
from zoneinfo import ZoneInfo
import math,re

D=lambda v:Decimal(str(v))
SOURCE={
 'exchange':'https://fyers.in/charges-list',
 'stt':'https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf',
 'sebi_stamp_gst':'https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies',
 'gst_basis':'https://fyers.in/charges-list',
 'stt_rounding':'https://nsearchives.nseindia.com/content/circulars/cmtr5588.htm',
}
RATES=dict(exchange=0.000325,sebi=0.000001,stt_sell=0.0015,stamp_buy=0.00003,gst=0.18)
MODEL=dict(id='SENSEX_OPTIONS_2026_04_V1',verified_on='2026-10-06',effective_stt='2026-04-01',effective_exchange='2024-10-01',rates=RATES,sources=SOURCE,brokerage_per_executed_order=15,rounding='STT and stamp: half-up whole rupee on cumulative runner-only client/day amounts, allocated by order. Exchange/SEBI/GST: half-up paise. Broker account aggregation and invoices may differ.',basis='Paper fee estimates; Live fill-based fee estimates, NOT broker-confirmed costs. Regular option premium BUY/SELL only; no expiry/exercise/DP costs. Actual slippage is embedded in fills; optional additional premium points are a separate sensitivity deduction.')


def rounded(x,unit='0.01'):return D(x).quantize(D(unit),rounding=ROUND_HALF_UP)
def valid(x):return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)

def settings(payload):
    raw=payload.get('additional_slippage_points',0)
    raw=0 if raw in (None,'') else raw
    try:v=float(raw)
    except (ValueError,TypeError):raise ValueError('Additional slippage must be nonnegative option premium points.')
    if isinstance(raw,bool) or not math.isfinite(v) or v<0:raise ValueError('Additional slippage must be nonnegative option premium points.')
    return dict(additional_slippage_points=v)


def applicable(row):
    stamp=row.get('first_fill_confirmed_at',row.get('filled_at'))
    return bool(re.fullmatch(r'BSE:SENSEX\d.*(?:CE|PE)',row.get('symbol',''))) and valid(stamp) and datetime.fromtimestamp(stamp,ZoneInfo('Asia/Kolkata')).date().isoformat()>='2026-04-01'


def fee(turnover,side,brokerage=15,stt=None,stamp=None):
    t=D(turnover);exchange=rounded(t*D(RATES['exchange']));sebi=rounded(t*D(RATES['sebi']))
    stt=rounded(t*D(RATES['stt_sell']),'1') if stt is None and side=='SELL' else D(stt or 0)
    stamp=rounded(t*D(RATES['stamp_buy']),'1') if stamp is None and side=='BUY' else D(stamp or 0)
    gst=rounded((D(brokerage)+exchange+sebi)*D(RATES['gst']))
    parts=dict(brokerage=D(brokerage),exchange=exchange,sebi=sebi,stt=stt,stamp=stamp,gst=gst)
    return {**{k:float(v) for k,v in parts.items()},'total':float(sum(parts.values())),'premium_turnover':float(t)}


def ledger_costs(orders):
    result={};days={}
    for row in sorted(orders,key=lambda r:r.get('first_fill_confirmed_at',r.get('filled_at',r.get('submitted_at',0))) or 0):
        key=row.get('tag') or row.get('order_id')
        if not row.get('filled') or key in result:continue
        if row.get('broker')=='DELTA_INDIA':
            from .delta_costs import order_cost
            result[key]=order_cost(row);continue
        if not applicable(row) or not valid(row.get('average_price')) or not valid(row.get('quantity_multiplier')):
            result[key]=None;continue
        day=datetime.fromtimestamp(row.get('first_fill_confirmed_at',row.get('filled_at')),ZoneInfo('Asia/Kolkata')).date().isoformat()
        totals=days.setdefault(day,dict(stt=D(0),stamp=D(0)))
        t=D(row['filled'])*D(row['average_price'])*D(row['quantity_multiplier'])
        allocated={}
        for name,rate,side in [('stt','stt_sell','SELL'),('stamp','stamp_buy','BUY')]:
            old=totals[name];new=old+t*D(RATES[rate]) if row['side']==side else old
            allocated[name]=rounded(new,'1')-rounded(old,'1');totals[name]=new
        result[key]=fee(t,row['side'],stt=allocated['stt'],stamp=allocated['stamp'])
    return result


def trade_costs(trade,ledger):
    rows=[r for r in trade['orders'] if r.get('filled')]
    if rows and all(r.get('broker')=='DELTA_INDIA' for r in rows):
        from .delta_costs import trade_costs as native_costs
        return native_costs(trade,ledger)
    keys=[r.get('tag') or r.get('order_id') for r in rows]
    if not rows or any(ledger.get(k) is None for k in keys):
        return dict(available=False,reason='Verified Sensex option rates or complete fill evidence unavailable.',model=MODEL,realized_net=None,unrealized_net=None)
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
    projected=fee(D(bid)*D(remaining)*mult,'SELL') if remaining and valid(bid) else None
    open_slip=slip*D(remaining*2)*mult
    unrealized=trade.get('unrealized_pnl')
    open_net=float(rounded(D(unrealized)-open_buy-D(projected['total'])-open_slip)) if remaining and projected and valid(unrealized) else 0.0 if not remaining else None
    parts={k:float(sum(D(ledger[key][k]) for key in keys)) for k in ['brokerage','exchange','sebi','stt','stamp','gst','total']}
    return dict(available=True,model=MODEL,kind='PAPER_ESTIMATE' if trade['mode']=='PAPER' else 'LIVE_FILL_BASED_ESTIMATE_UNRECONCILED',incurred=parts,entry_costs_incurred=float(buy),exit_costs_incurred=float(sell),entry_costs_allocated_realized=float(rounded(buy_alloc)),entry_costs_remaining=float(rounded(open_buy)),estimated_exit_costs=projected,realized_net=realized_net,unrealized_net=open_net,additional_slippage_points=float(slip),realized_additional_slippage=float(realized_slip),open_liquidation_additional_slippage=float(open_slip),actual_slippage='Embedded in execution fill prices; separately measured amount unavailable, no double deduction.',orders=[dict(order_key=k,**ledger[k]) for k in keys])
