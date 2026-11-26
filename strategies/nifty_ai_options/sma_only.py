"""Completed-candle SMA-band decisions, with no Supertrend dependency."""
import math
def enabled(config):return config.get('supertrend_enabled',True) is False
def validate(config):
 if not isinstance(config.get('supertrend_enabled',True),bool):raise ValueError('Supertrend switch must be boolean')
 if enabled(config):
  if not config.get('sma_band_entry') or not config.get('sma_band_exit'):raise ValueError('SMA-only requires SMA band entry and exit')
  if config.get('ema_band_entry') or config.get('ema_band_exit') or config.get('sma_exit_enabled'):raise ValueError('SMA-only cannot include other indicator rules')
def side(engine):
 if not enabled(engine.config):
  result=engine.under_result
  return ('CE' if result['direction']<0 else 'PE') if result else None
 value=engine.band.states.get('SMA')
 value=value.value if value else None
 if not value:return None
 if engine.config.get('band_price_basis','underlying')=='premium':
  return (getattr(engine,'contract',{}) or {}).get('option_type') if value['close']>value['upper'] else None
 return 'CE' if value['close']>value['upper'] else 'PE' if value['close']<value['lower'] else None
def entry(engine,options):
 pending=getattr(engine,'sma_only_pending',None)
 if engine.position or not pending or not getattr(engine,'entry_quotes_ready',True):return None
 direction,at=pending
 if at<=getattr(engine,'entry_reset_at',0):engine.sma_only_pending=None;return None
 contract=getattr(engine,'contract',None)
 if not contract or options and contract.get('option_type')!=direction:return None
 if not engine.band.entry_ready(direction,engine.config,getattr(engine,'entry_observation_at',at)):engine.sma_only_pending=None;return None
 if not options and direction=='SHORT' and not engine.allow_short:return None
 engine.sma_only_pending=None
 engine.band.consume_entry()
 engine.position=dict(contract,side=direction,entry_timestamp=at,signal_timestamp=at,entry_gate='SMA_BAND_ONLY')
 return dict(action='BUY' if options else 'OPEN_'+direction,timestamp=at,position=dict(engine.position),confirmation=dict(confirmation_basis='SMA_RETEST_FOLLOWUP_CANDLE' if engine.config.get('sma_retest_required',True) else 'SMA_BAND_COMPLETED_CANDLE'))
def hybrid_price(engine,event,options):
 if event.get('series','underlying')!=engine.config.get('band_price_basis','underlying'):return []
 if options and event.get('series')=='premium' and event.get('symbol')!=(getattr(engine,'contract',{}) or {}).get('symbol'):raise ValueError('Exact selected premium required')
 kind=event.get('series','underlying')
 stamp=event.get('timestamp');available=event.get('available_at')
 if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in (stamp,available,event.get('close'))) or stamp>available:raise ValueError('Valid broker price availability required')
 state=getattr(engine,'sma_hybrid_order',{})
 prior=state.get(kind)
 seq=event.get('sequence')
 if seq is not None and (isinstance(seq,bool) or not isinstance(seq,int) or seq<1):raise ValueError('Ordered SMA hybrid price sequence required')
 if prior and (stamp<prior[0] or available<prior[1] or seq is not None and seq<=prior[2]):raise ValueError('Duplicate/out-of-order SMA hybrid price')
 engine.sma_hybrid_order=dict(state,**{kind:(stamp,available,seq or 0)})
 try:from .hybrid_basis import price,brick_event
 except ImportError:from hybrid_basis import price,brick_event
 bars,_=price(engine,event,kind,indicator=False)
 engine.band.observe(event,engine.config)
 if not bars:return []
 unit=dict(bars[-1],kind='brick',closed=True,closed_at=stamp,available_at=available)
 if engine.position:
  entered=engine.position.get('entry_confirmed_at',engine.position.get('entry_timestamp',0))
  reason=engine.band.exit_reason(engine.position,unit['close'])
  if reason and stamp>entered:
   actions=engine.exit(available,reason)
   actions[0]['confirmation']=dict(confirmation_basis='COMPLETED_RENKO_BRICK',closed_at=stamp,available_at=available)
   return actions
  return []
 if engine.config.get('sma_retest_required',True):return []
 value=engine.band.states.get('SMA');value=value.value if value else None
 direction='LONG' if value and unit['close']>value['upper'] else 'SHORT' if value and unit['close']<value['lower'] else None
 if not direction or engine.config.get('band_price_basis')=='premium' and direction!='LONG':return []
 if options:direction=(getattr(engine,'contract',{}) or {}).get('option_type') if kind=='premium' else 'CE' if direction=='LONG' else 'PE'
 engine.sma_only_pending=(direction,available)
 if options and (getattr(engine,'contract',{}) or {}).get('option_type')!=direction:return [dict(action='SELECT',side=direction,timestamp=available)]
 action=entry(engine,options)
 if action:action['confirmation']=dict(confirmation_basis='COMPLETED_RENKO_BRICK',closed_at=stamp,available_at=available)
 return [action] if action else []

def update(engine,event,options):
 kind=event.get('kind')
 engine.entry_observation_at=event.get('available_at',event.get('closed_at',event.get('timestamp')))
 if kind=='price':return hybrid_price(engine,event,options) if engine.config.get('calculation_mode')=='HYBRID' else []
 if kind=='sma':return []
 if kind not in ('underlying','premium'):raise ValueError('Exact SMA source required')
 if options and kind=='premium' and event.get('symbol')!=getattr(engine,'contract',{}).get('symbol'):raise ValueError('Exact selected premium required')
 if kind!=engine.config.get('band_price_basis','underlying'):return []
 if event.get('closed') is False:return []
 if event.get('source_basis') not in (None,'PROVIDER_CONFIRMED_CLOSE'):return []
 values=[event.get(k) for k in ('timestamp','open','high','low','close')]
 if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values):return []
 stamp,opening,high,low,close=values
 if not low<=min(opening,close)<=max(opening,close)<=high:return []
 closed=event.get('closed_at',stamp+engine.config['timeframe']*60);available=event.get('available_at',closed)
 if not stamp<closed<=available:return []
 key='sma_only_'+kind
 if stamp<=engine.last_time.get(key,0):raise ValueError('Duplicate/out-of-order SMA-only candle')
 engine.last_time[key]=stamp
 if engine.config.get('calculation_mode')=='HYBRID':
  try:from .hybrid_basis import seed,store
  except ImportError:from hybrid_basis import seed,store
  if event.get('source_basis') is None:
   formed=seed(engine,event,kind)
   try:from .hybrid_basis import record_signal
   except ImportError:from hybrid_basis import record_signal
   for brick in formed:record_signal(engine,event,kind,brick,{})
  else:store(engine).setdefault(kind,dict(forming=None)).update(frame=engine.config['timeframe'],confirmed_at=stamp,waiting=False)
 formed=[]
 if engine.config.get('supertrend_basis')=='COMPLETED_RENKO' and event.get('source_basis')=='PROVIDER_CONFIRMED_CLOSE':
  renko=engine.under_renko if kind=='underlying' else engine.option_renko
  formed=renko.update(close)
  try:from .hybrid_basis import record_signal
  except ImportError:from hybrid_basis import record_signal
  for brick in formed:record_signal(engine,event,kind,brick,{})
 engine.band.observe(event,engine.config)
 if engine.position:
  engine.sma_only_pending=None
  entered=engine.position.get('entry_confirmed_at',engine.position.get('entry_timestamp',0))
  if engine.config.get('exit_confirmation_mode')=='RENKO_BRICKS_ONLY':
   renko=engine.under_renko if kind=='underlying' else engine.option_renko
   bricks=formed if engine.config.get('supertrend_basis')=='COMPLETED_RENKO' else renko.update(close)
   if not bricks:return []
   reason=engine.band.exit_reason(engine.position,bricks[-1]['close'])
   if reason and closed>entered:
    actions=engine.exit(available,reason)
    actions[0]['confirmation']=dict(confirmation_basis='COMPLETED_RENKO_BRICK',closed_at=closed,available_at=available)
    return actions
   return []
  reason=engine.band.exit_reason(engine.position)
  small=engine.config.get('calculation_mode')!='HYBRID' or abs(close-opening)<(engine.spot_size if kind=='underlying' else engine.contract['option_brick'])
  if reason and closed>entered and small:return engine.exit(available,reason)
  return []
 brick_only=engine.config.get('exit_confirmation_mode')=='RENKO_BRICKS_ONLY'
 if brick_only:
  if not formed:return []
  close=formed[-1]['close']
 elif engine.config.get('calculation_mode')=='HYBRID':
  size=engine.spot_size if kind=='underlying' else engine.contract['option_brick']
  if abs(close-opening)>=size:return []
 if closed<=getattr(engine,'entry_reset_at',0):return []
 if engine.config.get('sma_retest_required',True):
  confirmation=engine.band.reentry(event,engine.config,None,flat=True,not_before=getattr(engine,'entry_reset_at',0))
 else:
  value=engine.band.states.get('SMA')
  value=value.value if value else None
  direction='LONG' if value and close>value['upper'] else 'SHORT' if value and close<value['lower'] else None
  if engine.config.get('band_price_basis')=='premium' and direction!='LONG':direction=None
  confirmation=dict(direction=direction,closed_at=closed,available_at=available) if direction else None
 if not confirmation:engine.sma_only_pending=None;return []
 if options:
  direction=(getattr(engine,'contract',{}) or {}).get('option_type') if engine.config.get('band_price_basis')=='premium' else 'CE' if confirmation['direction']=='LONG' else 'PE'
 else:direction=confirmation['direction']
 engine.sma_only_pending=(direction,available)
 if options and (getattr(engine,'contract',{}) or {}).get('option_type')!=direction:
  return [dict(action='SELECT',side=direction,timestamp=available)]
 action=entry(engine,options)
 if action and brick_only:action['confirmation']=dict(confirmation_basis='COMPLETED_RENKO_BRICK',closed_at=closed,available_at=available)
 return [action] if action else []
