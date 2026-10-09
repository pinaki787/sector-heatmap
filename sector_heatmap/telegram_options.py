"""Telegram underlying recommendations → long ATM-option plans, never orders.

The execution coordinator must consume a genuinely new post, verify sizing and
Renko ownership, then recheck the trigger and resolve again at submission time.
Underlying recommendation prices must never become option limit/stop prices.
"""
import math
from strategies.renko_supertrend.delta_contracts import option_contract

EXPIRY_POLICY='NEAREST_UNEXPIRED_ATM'

def recommendation_plan(parsed,underlying):
 if parsed.get('action') not in ('BUY','SELL','SHORT'):raise ValueError('Explicit bullish BUY or bearish SELL/SHORT recommendation required.')
 if not underlying or not isinstance(underlying,str):raise ValueError('Exact supported underlying required.')
 direction='BULLISH' if parsed['action']=='BUY' else 'BEARISH'
 instruction=parsed.get('entry_instruction')
 if instruction not in ('LIMIT','STOP_LIMIT'):raise ValueError('Explicit underlying entry instruction required.')
 entry=parsed.get('entry')
 if isinstance(entry,bool) or not isinstance(entry,(float,int)) or not math.isfinite(entry) or entry<=0:raise ValueError('Positive underlying entry/trigger required.')
 return dict(underlying=underlying,direction=direction,option_type='CE' if direction=='BULLISH' else 'PE',side='BUY',execution_route='OPTIONS',expiry_policy=EXPIRY_POLICY,underlying_entry=entry,underlying_instruction=instruction,recommendation_stop=parsed.get('stop_loss'),recommendation_targets=list(parsed.get('targets') or []),exit_owner='RENKO_SUPERTREND',status='REQUIRES_SIZING_AND_MANAGEMENT_AUTHORIZATION')

def trigger_satisfied(plan,price,exchange_at,now):
 if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (price,exchange_at,now)) or price<=0 or not 0<=now-exchange_at<=15:raise ValueError('Fresh underlying traded-price observation required.')
 bullish=plan['direction']=='BULLISH';entry=plan['underlying_entry']
 if plan['underlying_instruction']=='STOP_LIMIT':return price>entry if bullish else price<entry
 return price<=entry if bullish else price>=entry

def resolve_at_trigger(delta,plan,price,exchange_at,now):
 if not trigger_satisfied(plan,price,exchange_at,now):return dict(plan,status='WAITING_UNDERLYING_TRIGGER',contract=None)
 route=delta.chart_option(plan['underlying'],'BUY' if plan['direction']=='BULLISH' else 'SELL')
 meta=option_contract(route['product'],now)
 if route['signal_symbol']!=plan['underlying'] or meta['option_type']!=plan['option_type'] or route.get('side')!='buy':raise ValueError('Exact underlying/long-option route mismatch.')
 if meta['expiry_epoch']-now<=60:raise ValueError('Nearest expiry is inside protection window; no later-expiry fallback.')
 q=route['quote']
 if q.get('symbol')!=meta['symbol'] or not 0<=now-q['exchange_at']<=15 or not 0<q['bid']<=q['ask']:raise ValueError('Fresh executable exact-option quote required.')
 return dict(plan,status='TRIGGERED_PREVIEW_ONLY',contract=meta,option_quote=q,option_entry_price_basis='FRESH_OPTION_ASK_MARKETABLE_IOC',underlying_observation=dict(price=price,exchange_at=exchange_at),quantity=None,submission_enabled=False)
