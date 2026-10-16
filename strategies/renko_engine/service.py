"""Account-bound Renko Engine service. Reads never activate trading."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from .rules import replay,settings,STRATEGY
from .runner import REVISION
from strategies.ema_crossover.runner import TIMEFRAMES

class Service:
 def __init__(self,runner,chart_broker,account_id,broker):
  self.runner=runner;self.chart_broker=chart_broker;self.account_id=account_id;self.broker=broker
  self.runner.valuation_adapter=chart_broker
 def identity(self,p):
  if p.get('account_id')!=self.account_id or p.get('broker')!=self.broker:raise PermissionError('Renko Engine account or broker mismatch.')
 def candles(self,p):
  self.identity(p)
  symbol=p.get('underlying');timeframe=p.get('timeframe')
  if not symbol or timeframe not in TIMEFRAMES:raise ValueError('Select an exact instrument and timeframe.')
  days=int(p.get('history_days',45))
  if days not in (7,45,90):raise ValueError('Unsupported history range.')
  independent=settings(p.get('engine_settings',{}))
  from .rules import epoch
  history_start=min(self.runner.clock()-days*86400,epoch(independent['anchorTime'])-86400)
  if self.runner.clock()-history_start>180*86400:raise ValueError('Anchor requires over 180 days of broker history. Choose a covered deterministic anchor.')
  c=dict(underlying=symbol,timeframe=timeframe,history_start=history_start,broker=self.broker,execution_route=p.get('execution_route','OPTIONS'),carry_policy='CONTINUOUS',session_deadline=None)
  rows=self.chart_broker.candles(c);tick=self.chart_broker.host_tick_size(symbol)
  return rows,tick
 def snapshot(self):
  return dict(self.runner.snapshot(),broker=self.broker,account_id=self.account_id,strategy=STRATEGY,runtime_revision=REVISION)
 def read(self,action):
  if action=='runner':return self.snapshot()
  if action=='capabilities':return dict(broker=self.broker,account_id=self.account_id,modes=['PAPER','LIVE','BACKTEST'],live_enabled=bool(self.runner.adapter.live_enabled()),runtime_revision=REVISION,strategy=STRATEGY)
  raise ValueError('Unknown Renko Engine read action.')
 def write(self,action,p):
  self.identity(p)
  if action in ('chart','backtest'):
   rows,tick=self.candles(p)
   seconds=TIMEFRAMES[p['timeframe']]
   rows=[r for r in rows if not r.get('is_forming') and r['timestamp']+seconds<=self.runner.clock()]
   costs=p.get('backtest_costs') or {}
   if set(costs)-{'commission','slippage_ticks','capital'}:raise ValueError('Unknown backtest cost setting.')
   result=replay(rows,p.get('engine_settings',{}),tick,seconds,**costs)
   if not result['rows']:raise ValueError('No completed broker candles.')
   from .rules import epoch
   covered=rows[0]['timestamp']<=epoch(settings(p.get('engine_settings',{}))['anchorTime'])
   currency=(self.chart_broker.delta.product(p['underlying']).get('quoting_currency') or 'native quote units') if self.broker=='DELTA_INDIA' else 'INR'
   return dict(result,quote_currency=currency,broker=self.broker,account_id=self.account_id,tick_size=tick,timeframe=p['timeframe'],anchor_covered=covered,mode='BACKTEST',basis='Chart-instrument one-unit simulation; not option returns. Explicit modeled friction; no broker orders.',runtime_revision=REVISION)
  if action=='start':
   return self.runner.start(p)
  if action=='stop':return self.runner.stop()
  raise ValueError('Unknown Renko Engine action.')
