"""Read-only final signal checks shared by entry authorization and chart replay.
Broker ownership, freshness, quota and locks remain live execution checks, never
invented from historical candles. Missing selected-rule evidence fails closed.
"""
import math
from .indicator_families import apply
REVISION='strategy-qualified-replay-v1'

def check(config,signal,direction,*,external=True):
 c=apply(config);s=signal
 def fail(reason):return {'allowed':False,'reason':reason,'revision':REVISION}
 def number(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
 if direction not in ('BULLISH','BEARISH') or not s.get('entry_qualified'):return fail('WAITING_SELECTED_STRATEGY')
 if s.get('provisional') or s.get('is_forming'):return fail('WAITING_COMPLETED_OBSERVATION')
 bullish=direction=='BULLISH';close=s.get('close')
 def beyond(a,b):return number(a) and number(b) and (a>b if bullish else a<b)
 if not number(close):return fail('MISSING_CLOSE')
 if c.get('strategy_basis')=='RENKO':
  if not s.get('has_completed_brick') or not beyond(close,s.get('open')) or s.get('brick_direction')!=direction:return fail('WAITING_MATCHING_RENKO_BRICK')
  from .swing_breakout import enabled as swing_enabled
  if swing_enabled(c):
   gate=(s.get('swing_breakout') or {}).get('sides',{}).get(direction) or {}
   if not gate.get('allowed') or gate.get('required')!=c['swing_breakout_bricks'] or gate.get('count',0)<c['swing_breakout_bricks'] or not beyond(close,(gate.get('reference') or {}).get('price')):return fail('WAITING_SWING_BREAKOUT_CLOSES')
 if c.get('sma_entry_enabled') and (s.get('sma_length') != c.get('sma_length', 5) or not beyond(close, s.get('sma'))):
  return fail('WAITING_SMA')
 if c.get('supertrend_enabled') and (s.get('pine_direction')!=(-1 if bullish else 1)):return fail('WAITING_SUPERTREND_DIRECTION')
 if c.get('supertrend_slope_enabled'):
  g=s.get('supertrend_slope_filter') or {}
  if not g.get('allowed') or g.get('lookback')!=c.get('supertrend_slope_bars',1) or not beyond(g.get('slope_atr'),c.get('supertrend_slope_min_atr',0) if bullish else -c.get('supertrend_slope_min_atr',0)):return fail('WAITING_SUPERTREND_SLOPE')
 for flag,key in (('ema_fast_enabled','ema10'),('ema_slow_enabled','ema30'),('ema_third_enabled','ema100')):
  if c.get(flag) and not beyond(close,s.get(key)):return fail('WAITING_'+key.upper())
 if c.get('ema_fast_enabled') and c.get('ema_slow_enabled') and not beyond(s.get('ema10'),s.get('ema30')):return fail('WAITING_EMA_ORDER')
 prior=s.get('ema30') if c.get('ema_slow_enabled') else s.get('ema10') if c.get('ema_fast_enabled') else None
 if c.get('ema_third_enabled') and (c.get('ema_fast_enabled') or c.get('ema_slow_enabled')) and not beyond(prior,s.get('ema100')):return fail('WAITING_EMA_THIRD_ORDER')
 if c.get('ema_widening_enabled') and s.get('ema_widening') is not True:return fail('WAITING_EMA_WIDENING')
 if c.get('use_adx') and (not number(s.get('adx')) or s['adx']<c.get('adx_threshold',20)):return fail('WAITING_ADX')
 if c.get('rsi_slope_enabled') and s.get('rsi_slope_pass') is not True:return fail('WAITING_RSI_SLOPE')
 if c.get('rsi_level_enabled'):
  from .rsi_level import matches
  if not matches(s.get('rsi14'),direction,c):return fail('WAITING_RSI_LEVEL')
 if not external:return {'allowed':True,'reason':'ALL_SELECTED_STRATEGY_RULES_PASS','revision':REVISION}
 for flag,key in (('anti_chop_enabled','anti_chop'),('manual_trend_enabled','manual_trend'),('calibrated_enabled','calibrated_filter'),('zone_entry_enabled','zone_entry_filter'),('market_structure_enabled','market_structure'),('higher_timeframe_enabled','mtf_supertrend'),('ema_proximity_enabled','ema_proximity'),('ema_momentum_enabled','ema_momentum'),('line_entry_enabled','line_entry_filter')):
  if c.get(flag) and not (s.get(key) or {}).get('allowed'):return fail('WAITING_'+key.upper())
 if any(c.get(f'rsi_htf_{slot}_enabled') for slot in (1,2,3)) and not (s.get('mtf_rsi') or {}).get('allowed'):return fail('WAITING_MTF_RSI')
 return {'allowed':True,'reason':'ALL_SELECTED_STRATEGY_RULES_PASS','revision':REVISION}

def events(rows,config):
 """Accept only qualified entries and their paired original simulated exits."""
 output=[];held=None
 for row in rows:
  if row.get('provisional') or row.get('is_forming'):continue
  bricks=row.get('brick_events',[]) if row.get('strategy_basis')=='RENKO' else [row]
  for brick in bricks:
   event=brick.get('lifecycle_event')
   if not event:continue
   sig=dict(brick)
   if row.get('strategy_basis')=='RENKO':sig['has_completed_brick']=True
   direction='BULLISH' if event.startswith('BUY') else 'BEARISH'
   if event in ('BUY','SELL'):
    decision=({'allowed':False,'reason':'WAITING_STRATEGY_ENTRY_EVENT','revision':REVISION} if config.get('trend_reentry_enabled',True) is False and sig.get('entry_direction')!=direction and sig.get('cross_direction')!=direction else check(config,sig,direction))
    if held is not None or not decision['allowed']:continue
    held=direction
   else:
    if held!=direction:continue
    held=None;decision={'allowed':True,'reason':'PAIRED_ELIGIBLE_SIMULATED_TRADE','revision':REVISION}
   output.append({**sig,'strategy_entry_check':decision,'event_scope':'SIMULATION','source_timestamp':row['timestamp']})
 return output
