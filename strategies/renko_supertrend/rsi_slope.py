"""Wilder RSI14 of host closes, identical seeding/flat convention to chart display."""
def observe(state,close,length=14):
 old=state.get('rsi_host',{})
 previous=old.get('value')
 next=dict(old,previous=close)
 if 'previous' in old:
  delta=close-old['previous'];gain=max(delta,0);loss=max(-delta,0)
  count=old.get('count',0)+1;next['count']=count
  if count<=length:
   next['gain']=old.get('gain',0)+gain/length;next['loss']=old.get('loss',0)+loss/length
  else:
   next['gain']=(old['gain']*(length-1)+gain)/length;next['loss']=(old['loss']*(length-1)+loss)/length
  next['value']=None if count<length else ((50 if next['gain']==0 else 100) if next['loss']==0 else 100-100/(1+next['gain']/next['loss']))
 state['rsi_host']=next
 current=next.get('value');slope=None if previous is None or current is None else current-previous
 return dict(rsi14=current,rsi14_previous=previous,rsi14_slope=slope)

def apply(entry,state,observation,direction,enabled):
 entry.update(observation,rsi_slope_enabled=enabled)
 slope=observation['rsi14_slope']
 passing=slope is not None and (slope>0 if direction=='BULLISH' else slope<0)
 reason='WAITING_RSI_WARMUP' if slope is None else 'WAITING_RSI_FLAT' if slope==0 else 'WAITING_RSI_DIRECTION'
 entry.update(rsi_slope_pass=passing if enabled else None,rsi_slope_diagnostic=('PASS' if passing else reason) if enabled else 'OFF')
 if enabled and not passing:
  # Re-arm widening after a blocked slope so a later eligible bar can qualify.
  state['ema_qualified']=None
  if entry.get('entry_qualified') or entry.get('retest_signal'):
   entry.update(entry_direction=None,entry_qualified=False,entry_buy_signal=False,entry_sell_signal=False,entry_diagnostic=reason)
   if entry.get('retest_signal'):entry.update(retest_signal=False,retest_rsi_blocked=True)
 return entry
