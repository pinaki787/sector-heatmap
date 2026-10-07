import unittest
from . import ema_proximity as ema, trailing_stop as trail
from .test_runner import RenkoLifecycleTests

class OptionalGuardTests(unittest.TestCase):
    def test_defaults_do_not_filter(self):
        self.assertFalse(ema.settings({})['ema_proximity_enabled'])
        self.assertFalse(trail.settings({})['trailing_enabled'])
        self.assertIsNone(ema.check({},None,None,None))
    def test_atr_distance_boundary_both_sides(self):
        c={**ema.settings({}),'ema_proximity_enabled':True}
        for price in (90,110):self.assertEqual(ema.check(c,price,100,20)['max_points'],10)
        for price in (89.99,110.01):
            with self.assertRaisesRegex(ValueError,'too far'):ema.check(c,price,100,20)
        with self.assertRaises(ValueError):ema.check(c,100,100,None)
    def test_points_do_not_require_atr(self):
        c=ema.settings(dict(ema_proximity_enabled=True,ema_proximity_mode='POINTS',ema_proximity_distance=2))
        self.assertEqual(ema.check(c,102,100,None)['distance_points'],2)
    def test_premium_ratchets_for_calls_and_puts(self):
        c=trail.settings(dict(trailing_enabled=True))
        for direction in ('BULLISH','BEARISH'):
            s,hit=trail.advance(None,c,direction,100,101,101,101,100);self.assertFalse(hit)
            s,hit=trail.advance(s,c,direction,120,102,102,102,100);self.assertEqual(s['stop'],108)
            s,hit=trail.advance(s,c,direction,108,103,103,103,100);self.assertTrue(hit);self.assertEqual(s['best'],120)
    def test_underlying_put_ratchets_down_and_exits_at_touch(self):
        c=trail.settings(dict(trailing_enabled=True,trailing_basis='UNDERLYING_POINTS',trailing_distance=5))
        s,_=trail.advance(None,c,'BEARISH',100,101,101,101,100)
        s,_=trail.advance(s,c,'BEARISH',90,102,102,102,100)
        s,hit=trail.advance(s,c,'BEARISH',95,103,103,103,100)
        self.assertTrue(hit);self.assertEqual(s['stop'],95)
    def test_stale_future_pre_fill_and_duplicate_prices(self):
        c=trail.settings(dict(trailing_enabled=True));s,_=trail.advance(None,c,'BULLISH',100,101,101,101,100)
        for exchange,received,now in ((99,101,101),(101,101,117),(102,102,101)):
            with self.assertRaises(ValueError):trail.advance(s,c,'BULLISH',1,exchange,received,now,100)
            self.assertEqual(s['stop'],90)
        other,hit=trail.advance(s,c,'BULLISH',1,101,101,101,100)
        self.assertIs(other,s);self.assertFalse(hit)

class TrailingLifecycleTests(RenkoLifecycleTests):
    def test_trailing_closes_full_paper_position_without_broker_order(self):
        self.c.update(trailing_enabled=True,ema_exit_enabled=False)
        premium=[10]
        self.b.quote=lambda symbol:dict(bid=premium[0],ask=premium[0],exchange_at=self.b.now,received_at=self.b.now)
        self.start();self.r.step();self.assertIsNotNone(self.r.state['position'])
        for value in (10,12):
            self.b.now+=1;premium[0]=value;self.r.step()
        self.assertAlmostEqual(self.r.state['position']['renko_trailing']['stop'],10.8)
        self.b.now+=1;premium[0]=10.7;self.r.step()
        self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['order_history'][-1]['reason'],'RENKO_TRAILING_STOP')
        self.assertEqual(self.b.sent,[])
        self.r.step();self.assertEqual(len(self.r.state['order_history']),2)

class ProximityLifecycleTests(unittest.TestCase):
    setUp=RenkoLifecycleTests.setUp
    start=RenkoLifecycleTests.start
    def prepare(self,distance):
        from .test_intrabar import TickBroker
        self.b=TickBroker();self.r.adapter=self.b
        self.c.update(intrabar_entries=True,ema_proximity_enabled=True,ema_proximity_mode='POINTS',ema_proximity_distance=distance)
        self.start()
    def test_far_entry_blocked_before_intent(self):
        self.prepare(.01)
        with self.assertRaisesRegex(ValueError,'too far'):self.r.step()
        self.assertIsNone(self.r.state['position']);self.assertIsNone(self.r.state['pending'])
        self.assertEqual(self.r.state.get('order_history',[]),[]);self.assertEqual(self.b.sent,[])
    def test_near_entry_records_price_evidence(self):
        self.prepare(100);self.r.step()
        evidence=self.r.state['position']['entry_indicator_snapshot']['ema_proximity_observation']
        self.assertEqual(evidence['price'],130);self.assertEqual(evidence['max_points'],100)
        self.assertEqual(evidence['exchange_at'],self.b.now)
