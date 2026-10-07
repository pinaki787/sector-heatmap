import unittest
from .risk import levels,hard_exit,validate_spot_levels

class HardBoundaryTests(unittest.TestCase):
    def test_call_and_put_touch_and_gap_boundaries(self):
        call=dict(spot_target=110,spot_stop=90)
        put=dict(spot_target=90,spot_stop=110)
        for direction,c in [('BULLISH',call),('BEARISH',put)]:
            validate_spot_levels(100,direction,c)
            self.assertIsNone(hard_exit(100,direction,c))
            self.assertEqual(hard_exit(c['spot_target'],direction,c),'SPOT_TARGET_EXIT')
            self.assertEqual(hard_exit(c['spot_stop'],direction,c),'SPOT_STOP_EXIT')
        self.assertEqual(hard_exit(85,'BULLISH',call),'SPOT_STOP_EXIT')
        self.assertEqual(hard_exit(115,'BEARISH',put),'SPOT_STOP_EXIT')
    def test_blanks_disable_and_wrong_direction_rejected(self):
        c=levels(dict(spot_target='',spot_stop=None))
        self.assertIsNone(hard_exit(100,'BULLISH',c))
        for raw in [True,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):levels(dict(spot_stop=raw))
        with self.assertRaises(ValueError):validate_spot_levels(100,'BEARISH',dict(spot_stop=90))

class HardBoundaryRunnerTests(unittest.TestCase):
    from .test_runner import RenkoLifecycleTests as _Fixtures
    setUp=_Fixtures.setUp
    start=_Fixtures.start
    def test_stop_exits_on_tick_without_new_completed_candle(self):
        self.c.update(spot_target=130,spot_stop=90)
        self.b.live_price=lambda *args:(120,self.b.now)
        self.start();self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        bar=self.r.state['last_signal']['timestamp']
        self.b.live_price=lambda *args:(90,self.b.now)
        self.r.step()
        t=self.r.snapshot()['trade_history'][0]
        self.assertEqual(t['exit_reasons'],['SPOT_STOP_EXIT'])
        self.assertEqual(self.r.state['last_signal']['timestamp'],bar)
        self.assertEqual(t['spot_stop'],90)
    def test_stale_boundary_tick_does_not_exit(self):
        self.c.update(spot_stop=90)
        self.b.live_price=lambda *args:(120,self.b.now)
        self.start();self.r.step()
        self.b.live_price=lambda *args:(80,self.b.now-16)
        self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(len(self.r.state['order_history']),1)
        self.assertIn('Fresh underlying',self.r.state['hard_boundary_error'])
