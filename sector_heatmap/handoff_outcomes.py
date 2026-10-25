"""Report-only INR scenarios from bought-option premiums, not underlying moves."""
import math
from decimal import Decimal,ROUND_HALF_UP
from datetime import datetime,date
from zoneinfo import ZoneInfo
def number(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def whole(x):return number(x) and x>0 and int(x)==x
def money(x):return float(Decimal(str(x)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
def sizing(contract,lots,source):
    if contract.get('validated') is not True or not contract.get('symbol') or contract.get('option_type') not in ('CE','PE'):return dict(status='UNAVAILABLE',reason='Exact selected option contract is not validated.',lots=None,lot_size=None,quantity=None)
    try:date.fromisoformat(contract.get('expiry',''))
    except (ValueError,TypeError):return dict(status='UNAVAILABLE',reason='Exact contract expiry evidence is missing.',lots=None,lot_size=None,quantity=None)
    unit=contract.get('lot_size')
    if not whole(unit):return dict(status='UNAVAILABLE',reason='Exact validated contract master must supply a positive whole lot size; no default lot is used.',lots=None,lot_size=unit,quantity=None)
    if not whole(lots):return dict(status='UNAVAILABLE',reason='Selected report lots must be a positive whole number.',lots=None,lot_size=int(unit),quantity=None)
    if int(lots)*int(unit)>9007199254740991:return dict(status='UNAVAILABLE',reason='Report quantity exceeds the exact supported integer range.',lots=None,lot_size=int(unit),quantity=None)
    return dict(status='AVAILABLE',lots=int(lots),lot_size=int(unit),quantity=int(lots)*int(unit),lots_source=source,lot_source='Selected broker validated exact-contract master',lot_evidence={k:contract.get(k) for k in ('symbol','strike','option_type','expiry','lot_size','security_token','fy_token')})
def scenario_costs(entry,exit_price,quantity,broker,symbol,clock):
    if broker!='FYERS':return dict(status='UNAVAILABLE',total=None,reason='No verified scenario fee schedule is selected for '+str(broker or 'this broker')+'; another broker fee model is not substituted.')
    try:from strategies.renko_supertrend.costs import fee,exchange_rate,MODEL
    except ImportError:return dict(status='UNAVAILABLE',total=None,reason='Verified option fee model is unavailable; net is withheld.')
    rate=exchange_rate({'symbol':symbol})
    if rate is None or clock.astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()<'2026-04-01':return dict(status='UNAVAILABLE',total=None,reason='The exact segment or valuation date is outside the verified FYERS option fee schedule.')
    buy=fee(Decimal(str(entry))*quantity,'BUY',exchange_rate=rate);sell=fee(Decimal(str(exit_price))*quantity,'SELL',exchange_rate=rate)
    total=money(Decimal(str(buy['total']))+Decimal(str(sell['total'])))
    return dict(status='ESTIMATED',total=total,entry=buy,exit=sell,model=MODEL['id'],broker='FYERS',brokerage_plan='Published FYERS Standard: INR20 per executed order; account discounts/Prime tier not verified',executed_orders_assumed=2,exchange_rate=rate,sources=MODEL['sources'],verified_on='2026-10-25',basis='One BUY entry and one SELL exit for the whole report quantity. Standard brokerage, exchange/clearing/IPFT/SEBI, sell-side STT, buy-side stamp and GST. Standalone scenario rounding; account/day invoice aggregation can differ.',excluded_unknown_costs='Slippage, extra split/partial-fill orders, account-specific charges/discounts, exercise and physical delivery are not estimated. Net is after listed fees only; excluded costs are not assumed to be zero.')
def outcomes(horizon,contract,selected_lots,broker,clock,lots_source='Captured report-lots input'):
    size=sizing(contract,selected_lots,lots_source);result=dict(status='UNAVAILABLE',currency='INR',position_side='BUY_OPTION',sizing=size,target=None,stop=None,basis='Long Call and long Put both use (exit premium - entry premium) x quantity; underlying point changes are not option P&L.')
    if not str(contract.get('symbol','')).startswith(('NSE:','BSE:')):result.update(currency=None,reason='INR option outcome sizing is not verified for this contract market.');return result
    if size['status']!='AVAILABLE':result['reason']=size['reason'];return result
    quality=(horizon.get('source') or {}).get('data_quality')
    if quality in ('STALE','UNAVAILABLE','INSUFFICIENT DATA') or horizon.get('status')=='UNAVAILABLE':result['reason']=horizon.get('reason') or 'Premium/horizon evidence is stale or unavailable.';return result
    prices=horizon.get('premium') or {};entry=prices.get('entry')
    if not number(entry) or entry<=0:result['reason']='Validated positive option premium entry is unavailable.';return result
    reasons=[];quantity=size['quantity']
    for key,level in [('target',prices.get('target')),('stop',prices.get('stop_loss'))]:
        if not number(level) or level<=0 or (level<=entry if key=='target' else level>=entry):reasons.append(key.title()+' scenario premium is missing or invalid.');continue
        try:
            gross=money((Decimal(str(level))-Decimal(str(entry)))*quantity);cost=scenario_costs(entry,level,quantity,broker,contract.get('symbol',''),clock);net=money(Decimal(str(gross))-Decimal(str(cost['total']))) if cost['status']=='ESTIMATED' else None
        except (ArithmeticError,OverflowError,ValueError):reasons.append(key.title()+' scenario exceeds the supported numerical range.');continue
        result[key]=dict(status='ESTIMATED' if net is not None else 'GROSS_ONLY',entry_premium=entry,exit_premium=level,quantity=quantity,gross_pnl=gross,estimated_costs=cost,net_pnl=net,estimated_profit=net if key=='target' else None,estimated_loss=-net if key=='stop' and net is not None else None,gross_loss=-gross if key=='stop' else None)
    result['status']='ESTIMATED' if all(result[k] and result[k]['status']=='ESTIMATED' for k in ('target','stop')) else 'PARTIAL' if result['target'] or result['stop'] else 'UNAVAILABLE'
    result['reason']='; '.join(reasons) or None;result['snapshot_quality']=quality;result['execution_note']='Model-estimated report outcomes for the captured quote snapshot; not executable P&L or guaranteed exits.'
    return result
