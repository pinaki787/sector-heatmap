import unittest
from unittest.mock import patch
from sector_heatmap.delta_india import DeltaReadUnavailable
from tests import test_delta_atm_runner as fixture

class RecoveryTests(unittest.TestCase):
 setUp=fixture.AtmOptionRunner.setUp
 signal=fixture.AtmOptionRunner.signal
 config=fixture.AtmOptionRunner.config
 def enter(self):
  cfg=self.config();cfg['strategy_mode']='FUTURES';self.b.start_runner(cfg);self.req.now+=300;self.signal('BULLISH');self.b.runner_tick();return cfg
 def history(self,cfg):
  cursor=self.b.runner['last_candle'];self.req.now+=900
  rows=[dict(timestamp=cursor+300,rsi_ma=50,cross_direction='BEARISH'),dict(timestamp=cursor+600,rsi_ma=50,cross_direction='BULLISH'),dict(timestamp=cursor+900,rsi_ma=50,cross_direction=None)]
  self.b.chart=lambda *a,**k:dict(last_completed=rows[-1],candles=rows)
  return rows
 def test_missed_exit_before_later_recross_is_closed_without_historical_entry(self):
  cfg=self.enter();rows=self.history(cfg)
  with patch('sector_heatmap.delta_india.delta_rsi_series',return_value=rows):self.b.runner_tick()
  self.assertIsNone(self.b.paper['position']);self.assertEqual(len(self.b.paper['trades']),1)
  fill=self.b.paper['trades'][0]['exit_fills'][0];self.assertEqual(fill['reason'],'OPPOSITE_CROSSOVER');self.assertEqual(fill['signal_close'],rows[0]['timestamp']+300)
 def test_latched_exit_survives_read_failure_and_restart_then_retries_once(self):
  cfg=self.enter();self.req.now+=300;self.signal('BEARISH');original=self.b.close_runner
  with patch.object(self.b,'close_runner',side_effect=DeltaReadUnavailable('outage')):
   with self.assertRaises(DeltaReadUnavailable):self.b.runner_tick()
  position=self.b.paper['position'];self.assertIn('runner_exit_signal',position)
  import json
  self.assertIn('runner_exit_signal',json.loads(self.b.path.read_text())['position'])
  from sector_heatmap.delta_india import DeltaIndia
  restarted=DeltaIndia(self.b.path,requester=self.b.requester,clock=self.b.clock);self.assertFalse(restarted.runner['running']);self.assertEqual(restarted.paper['position']['runner_exit_signal'],position['runner_exit_signal'])
  with patch.object(self.b,'chart',side_effect=AssertionError('latched exit must not depend on history')),patch.object(self.b,'close_runner',wraps=original) as close:
   self.b.runner_tick();self.assertEqual(close.call_count,1)
  self.assertIsNone(self.b.paper['position']);self.assertEqual(len(self.b.paper['trades'][0]['exit_fills']),1)
 def test_missing_recovery_candle_blocks_exit_replay_and_entries(self):
  cfg=self.enter();rows=self.history(cfg);rows.pop(0)
  with patch('sector_heatmap.delta_india.delta_rsi_series',return_value=rows):
   with self.assertRaisesRegex(DeltaReadUnavailable,'gap'):self.b.runner_tick()
  self.assertEqual(self.b.paper['position']['contracts'],10);self.assertEqual(len(self.b.paper['trades']),1)
 def test_worker_retries_transient_reads_but_stops_on_ownership_failure(self):
  class Event:
   def __init__(self):self.calls=0;self.stopped=False;self.delays=[]
   def wait(self,n):self.delays.append(n);self.calls+=1;return self.stopped or self.calls>2
   def is_set(self):return self.stopped
   def set(self):self.stopped=True
  for error,expected in [(DeltaReadUnavailable('outage'),2),(ValueError('Broker position differs'),1)]:
   event=Event();self.b.stop_event=event;self.b.runner['running']=True
   with patch.object(self.b,'runner_tick',side_effect=[error,None]) as tick:self.b._run(event);self.assertEqual(tick.call_count,expected)
   self.assertEqual(self.b.runner['running'],expected==2)
   if expected==2:self.assertEqual(event.delays,[2,2,2]);self.assertIsNone(self.b.runner['recovery'])
