"""Position-specific exit monitoring evidence and health; chart preferences are irrelevant."""
from copy import deepcopy

def saved_paper_config(position):
 existing=(position.get('monitoring') or {}).get('config')
 if existing:return deepcopy(existing)
 context=position.get('entry_context') or {};settings=context.get('settings') or {}
 required=('resolution','rsi_length','ma_length','ma_type')
 if any(settings.get(k) is None for k in required) or not context.get('symbol'):raise ValueError('Exact entry monitoring settings were not recorded; cannot infer them from the selected chart.')
 cfg=deepcopy(settings);cfg.update(symbol=context['symbol'],mode='PAPER',contracts=position['contracts'],direction='BOTH')
 if position.get('strategy')=='DELTA_ATM_OPTIONS' or position.get('signal_symbol'):
  if position.get('signal_symbol')!=context['symbol'] or position.get('signal_direction') not in ('BULLISH','BEARISH'):raise ValueError('Held option underlying/direction evidence is inconsistent.')
  cfg['strategy_mode']='ATM_OPTIONS'
 elif context['symbol']==position.get('symbol'):cfg['strategy_mode']='FUTURES'
 else:raise ValueError('Held contract and recorded signal source differ without verified option routing.')
 trailing=context.get('trailing_settings')
 if position.get('trailing'):
  if not trailing or any(k not in trailing for k in ('trailing_enabled','trailing_mode','trailing_step')):raise ValueError('Exact held-position trailing settings are missing.')
  cfg.update({k:v for k,v in trailing.items() if not k.startswith('_')})
 else:cfg['trailing_enabled']=False
 if position.get('submit_managed'):cfg['one_shot']=True;cfg['execution_symbol']=position['symbol']
 return cfg

def health(position,runner,now):
 if not position:return dict(state='FLAT',alert=False,message='No owned position requires monitoring.')
 monitor=position.get('monitoring') or {};cfg=monitor.get('config') or {}
 detail=dict(symbol=position.get('symbol'),signal_symbol=cfg.get('symbol') or position.get('signal_symbol'),resolution=cfg.get('resolution') or position.get('entry_timeframe'),exit_only=bool(runner.get('exit_only')),desired=bool(monitor.get('enabled')),last_checked=monitor.get('last_checked'))
 same=(runner.get('config') or {}).get('mode')==position.get('mode')
 if not runner.get('running') or not same:
  reason='Intentional stop' if monitor.get('reason')=='INTENTIONAL_STOP' else 'Monitoring inactive'
  return dict(detail,state='INACTIVE',alert=True,message=reason+' · held position has no active exit/trailing checks.')
 if runner.get('recovery'):return dict(detail,state='RETRYING',alert=True,message='Public data interrupted; retrying exit monitoring. '+runner['recovery'].get('error',''))
 checked=monitor.get('last_checked')
 if checked is not None and now-checked>15:return dict(detail,state='STALE',alert=True,message='Monitoring heartbeat overdue; check the running worker.')
 return dict(detail,state='ACTIVE',alert=False,message='EXIT-ONLY monitoring active; no new entries or reentry.' if runner.get('exit_only') else 'Held-position exit/trailing monitoring active.')
