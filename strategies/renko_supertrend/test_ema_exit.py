import unittest
from .ema_exit import settings,confirmed_values,confirmed_cross,live_breach

class OptionalEmaTests(unittest.TestCase):
    def test_period_default_validation_and_host_closes(self):
        self.assertEqual(settings({})['ema_exit_length'],10)
        for raw in [True,0,1.5,1001,float('nan')]:
            with self.assertRaises(ValueError):settings(dict(ema_exit_length=raw))
        rows=[dict(timestamp=1,close=100),dict(timestamp=2,close=110),dict(timestamp=3,close=200,is_forming=True)]
        self.assertEqual(len(confirmed_values(rows,30)),2)
        self.assertAlmostEqual(confirmed_values(rows,10)[-1]['ema_exit'],100+20/11)
        self.assertAlmostEqual(confirmed_values(rows,30)[-1]['ema_exit'],100+20/31)
    def test_confirmation_both_directions_off_and_no_repeated_breach(self):
        above=dict(timestamp=1,close=101,ema_exit=100)
        below=dict(timestamp=2,close=99,ema_exit=100)
        self.assertTrue(confirmed_cross(above,below,'BULLISH'))
        self.assertFalse(confirmed_cross(above,{**below,'is_forming':True},'BULLISH'))
        self.assertFalse(confirmed_cross(above,below,'BULLISH',False))
        self.assertFalse(confirmed_cross(below,{**below,'timestamp':3},'BULLISH'))
        self.assertTrue(confirmed_cross({**below,'timestamp':1},{**above,'timestamp':2},'BEARISH'))
    def test_fresh_tick_both_directions_and_stale_rejection(self):
        self.assertTrue(live_breach(100,99,100,101,10,'BULLISH')[0])
        self.assertTrue(live_breach(100,101,100,101,30,'BEARISH')[0])
        self.assertEqual(live_breach(100,99,100,101,10,'BULLISH',False),(False,None))
        with self.assertRaises(ValueError):live_breach(100,99,100,116,10,'BULLISH')

class RunnerEmaControlsTests(unittest.TestCase):
    from .test_runner import RenkoLifecycleTests as _Fixtures
    setUp=_Fixtures.setUp
    start=_Fixtures.start
    def test_disabled_ema_preserves_opposite_supertrend_exit(self):
        self.c.update(ema_exit_enabled=False,ema_exit_length=30)
        self.start();self.r.step()
        p=self.r.state['position']
        self.assertIsNotNone(p)
        sig=self.r.signal()
        self.assertFalse(sig['ema_exit_enabled'])
        self.assertIn('ema_exit',sig)
        self.assertIsNone(self.r.exit_reason_for(dict(sig,close=1,supertrend_cross_direction=None),p))
        self.assertEqual(self.r.exit_reason_for(dict(sig,close=1,supertrend_cross_direction='BEARISH'),p),self.r.exit_reason)
    def test_custom_period_fresh_tick_exit_and_saved_evidence(self):
        self.c.update(ema_exit_enabled=True,ema_exit_length=30)
        self.start();self.r.step()
        self.r.state['config']['intrabar_entries']=True
        self.b.forming=lambda *args:None
        self.b.live_price=lambda *args:(80,self.b.now)
        self.r.step()
        t=self.r.snapshot()['trade_history'][0]
        self.assertEqual(t['exit_reasons'],['EMA30_INTRABAR_BREACH'])
        self.assertEqual(t['ema_exit_length'],30)
        self.assertIn('ema_exit',t['exit_indicator_snapshots'][0]['indicators'])
