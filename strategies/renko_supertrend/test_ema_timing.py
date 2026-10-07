import unittest
from unittest.mock import patch
from .test_runner import RenkoLifecycleTests
from .test_signals import candle
class EmaTimingTests(unittest.TestCase):
 setUp=RenkoLifecycleTests.setUp
 start=RenkoLifecycleTests.start
 def test_timing_matrix_for_owned_and_pending_positions(self):
  self.start();self.r.step();original=dict(self.r.state['position'])
  self.b.forming=lambda *a:None
  for length in (10,30,50):
   for direction,price in [('BULLISH',80),('BEARISH',140)]:
    for enabled in (False,True):
     for pending in (False,True):
      with self.subTest(length=length,direction=direction,intrabar=enabled,pending=pending):
       c=self.r.state['config'];c.update(ema_exit_length=length,ema_exit_enabled=True,intrabar_entries=enabled)
       p=dict(original,direction=direction);self.r.state['position']=None if pending else p
       self.r.state['pending']=dict(order=dict(side=1),position=p) if pending else None
       self.r.state.pop('pending_entry_exit_reason',None);self.r.state['accepting_entries']=True
       self.b.live_price=lambda *a:(price,self.b.now)
       with patch('strategies.renko_supertrend.runner.BaseRunner.step',return_value=None):self.r.step()
       reason=self.r.state.get('pending_entry_exit_reason') if pending else p.get('exit_reason')
       self.assertEqual(reason,'EMA'+str(length)+'_INTRABAR_BREACH' if enabled else None)
 def test_off_wick_ignored_then_completed_close_exits(self):
  self.start();self.r.step();original=dict(self.r.state['position'])
  self.b.forming=lambda *a:None
  for length in (10,30,50):
   for direction,adverse in [('BULLISH',80),('BEARISH',140)]:
    with self.subTest(length=length,direction=direction):
     c=self.r.state['config'];c.update(intrabar_entries=False,ema_exit_length=length)
     self.r.state['position']=dict(original,direction=direction);self.r.state['pending']=None
     self.b.live_price=lambda *a:(adverse,self.b.now)
     with patch('strategies.renko_supertrend.runner.BaseRunner.step',return_value=None):self.r.step()
     self.assertFalse(self.r.state['position'].get('exit_requested',False))
     sig=self.r.signal();sig.update(close=adverse,ema_exit=100,ema_exit_enabled=True,supertrend_cross_direction=None,timestamp=sig['timestamp']+60)
     with patch.object(self.r,'signal',return_value=sig),patch.object(self.r,'fresh_cross',return_value=True):self.r.step()
     self.assertIsNone(self.r.state['position'])
     self.assertEqual(self.r.state['order_history'][-1]['reason'],'EMA'+str(length)+'_CONFIRMED_BREACH')
