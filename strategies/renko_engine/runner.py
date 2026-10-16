"""Independent Renko Engine signals on the existing broker execution lifecycle."""
from copy import deepcopy
import hashlib,json,secrets
from .rules import STRATEGY,settings,replay,epoch
from strategies.renko_supertrend.runner import Runner,configuration as fyers_configuration
from strategies.renko_supertrend.delta_runner import DeltaRunner
from strategies.renko_supertrend.delta_contracts import configuration as delta_configuration
from strategies.ema_crossover.runner import TIMEFRAMES

REVISION='renko-engine-direct-start-v2'
def configuration(payload,broker='FYERS'):
 if payload.get('strategy')!=STRATEGY:raise ValueError('Explicit independent Renko Engine strategy required.')
 if payload.get('broker')!=broker:raise ValueError('Broker differs from the selected account.')
 independent=settings(payload.get('engine_settings',{}))
 # Execution settings stay separate from independent Renko signal settings.
 p=dict(payload,strategy='RENKO_SUPERTREND_V1',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',supertrend_enabled=True,ema_fast_enabled=False,ema_slow_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,rsi_level_enabled=False,use_adx=False,retest_enabled=False,sideways_enabled=False,zone_target_enabled=False,market_structure_enabled=False,higher_timeframe_enabled=False,ema_proximity_enabled=False,ema_exit_enabled=False,supertrend_exit_enabled=False,intrabar_entries=False,spot_target=None,spot_stop=None,trailing_enabled=False)
 if broker=='DELTA_INDIA':
  p.update(price_source='PERPETUAL_LAST_TRADE',order_terms='MARKETABLE_LIMIT_IOC',carry_policy='DAILY_SQUARE_OFF' if independent['sessionOnly'] else 'CONTINUOUS',session_deadline=f"{independent['flatHour']:02}:{independent['flatMinute']:02}" if independent['sessionOnly'] else None)
  c=delta_configuration(p)
 else:
  if broker=='DHAN' and payload.get('execution_route','OPTIONS')!='OPTIONS':raise ValueError('Dhan currently supports bought options only.')
  c=fyers_configuration(p);c['broker']=broker
 return dict(c,strategy=STRATEGY,label='Renko Engine',engine_settings=independent,history_start=epoch(independent['anchorTime'])-86400)

def cutoff(now,config):
 # Compatibility with shared lifecycle releases that delegate Engine cutoffs.
 from datetime import datetime
 from zoneinfo import ZoneInfo
 c=settings(config.get('engine_settings',{}));day=datetime.fromtimestamp(now,ZoneInfo('Asia/Kolkata'))
 return now>epoch(c['endTime']) or bool(c['sessionOnly'] and day.hour*60+day.minute>=c['flatHour']*60+c['flatMinute'])

class IndependentSignals:
 strategy_id=STRATEGY
 runtime_revision=REVISION
 signal_policy='INDEPENDENT_RENKO_COMPLETED_CANDLE'
 activation_name='RENKO ENGINE'
 entry_reason='RENKO_ENGINE_ENTRY'
 exit_reason='RENKO_ENGINE_OPPOSITE_SIGNAL'
 def entry_preflight(self,order,contract,quote):
  if hasattr(self,'engine_execution_allowed') and not self.engine_execution_allowed():raise ValueError('Global execution policy blocks new entries.')
  return super().entry_preflight(order,contract,quote)
 def signal_key(self,sig):
  c=self.state['config'];digest=hashlib.sha256(json.dumps(c['engine_settings'],sort_keys=True).encode()).hexdigest()[:16]
  return f"RENKO_ENGINE:{c['underlying']}:{c['timeframe']}:{digest}:{sig['timestamp']}"
 def signal(self):
  c=self.state['config'];seconds=TIMEFRAMES[c['timeframe']]
  rows=[r for r in self.adapter.candles(c) if not r.get('is_forming') and r['timestamp']+seconds<=self.clock()]
  if not rows:raise ValueError('Completed broker candles unavailable.')
  # The deterministic recurrence must start at the saved strategy anchor.
  anchor=epoch(c['engine_settings']['anchorTime'])
  if rows[0]['timestamp']>anchor:raise ValueError('Full history from the independent Renko anchor is required; execution withheld.')
  result=replay(rows,c['engine_settings'],self.adapter.host_tick_size(c['underlying']),seconds)
  sig=dict(result['rows'][-1])
  sig.update(raw_engine_direction=sig['cross_direction'],cross_direction=sig['entry_direction'],supertrend_cross_direction=None,ema10=sig['fast'],ema30=sig['slow'],ema_exit_enabled=False,ema_widening=True,adx=None,box=sig['brick'],supertrend=sig['level'],pine_direction=-sig['trend'],entry_diagnostic='INDEPENDENT_RENKO_SIGNAL' if sig['entry_direction'] else 'NO_ENTRY_EVENT')
  self.state['last_signal']=sig;self.save();return sig
 def fresh_cross(self,sig):
  position=self.state.get('position')
  if not position:return super().fresh_cross(sig)
  seconds=TIMEFRAMES[self.state['config']['timeframe']]
  closed_at=sig['timestamp']+seconds
  token=hashlib.sha256(json.dumps([position.get('lifecycle_id'),sig['timestamp'],sig.get('raw_engine_direction'),sig.get('squareoff'),sig['close']]).encode()).hexdigest()
  if token==(self.state.get('latest_exit_assessment') or {}).get('token'):return False
  eligible=0<=self.clock()-closed_at<=seconds
  self.state['latest_exit_assessment']=dict(token=token,timestamp=sig['timestamp'],event_at=closed_at,eligible=eligible,observed_at=self.clock())
  self.save()
  return eligible and bool(self.exit_reason_for(sig,position))
 def exit_reason_for(self,sig,position):
  if sig.get('squareoff'):return 'RENKO_ENGINE_SESSION_END'
  direction=sig.get('raw_engine_direction')
  if direction and direction!=position['direction']:return self.exit_reason
  return None
 def exit_signal(self,sig,direction):
  return bool(self.exit_reason_for(sig,dict(direction=direction)))
 def activate(self,payload,background=True):
  return self.start(payload,background)
 def start(self,payload,background=True):
  # Start is one atomic action with the complete visible configuration. Shared
  # preparation remains internal so broker/risk validation and ownership locks
  # are identical to the existing execution lifecycle.
  from strategies.ema_crossover.runner import Runner as BaseRunner
  with self.lock:
   if self.state['running'] or (self.thread and self.thread.is_alive()):raise ValueError('Renko Engine runner is already active or finishing shutdown.')
   if self.state.get('position') or self.state.get('pending'):raise ValueError('Existing exposure must finish stopping/reconciliation before a new start.')
   p=super().preview(payload)
   c=p['config'];rows=self.adapter.candles(c)
   completed=[r for r in rows if not r.get('is_forming') and r['timestamp']+TIMEFRAMES[c['timeframe']]<=self.clock()]
   if not completed or completed[0]['timestamp']>epoch(c['engine_settings']['anchorTime']):raise ValueError('Broker history does not cover the independent anchor; start withheld.')
   replay(completed,c['engine_settings'],self.adapter.host_tick_size(c['underlying']),TIMEFRAMES[c['timeframe']])
   previous_run_id=self.state.get('run_id')
   self.state['run_id']='RENKO-ENGINE-'+secrets.token_hex(10)
   try:return BaseRunner.start(self,dict(preview_id=p['id'],confirmation=p['confirmation']),background)
   except Exception:
    self.state['run_id']=previous_run_id
    raise
 def override_entry(self,payload):
  raise ValueError('Manual override is not part of the independent Renko Engine strategy.')

class FyersRunner(IndependentSignals,Runner):
 configure=staticmethod(lambda p:configuration(p,'FYERS'))
class DhanRunner(IndependentSignals,Runner):
 configure=staticmethod(lambda p:configuration(p,'DHAN'))
class DeltaEngineRunner(IndependentSignals,DeltaRunner):
 configure=staticmethod(lambda p:configuration(p,'DELTA_INDIA'))
