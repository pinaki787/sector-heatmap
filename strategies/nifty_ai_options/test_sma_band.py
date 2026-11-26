import unittest

from sma_band import SMA30Band


class SMA30BandCalculationTests(unittest.TestCase):
    def test_warmup_and_exact_high_low_means_use_wicks(self):
        band = SMA30Band()
        for i in range(29):
            self.assertIsNone(band.update(1000+i*60, 120, 80, 100))
        self.assertIsNone(band.snapshot())
        value = band.update(1000+29*60, 180, 50, 100)
        self.assertEqual(value["upper"], 122)
        self.assertEqual(value["lower"], 79)
        self.assertEqual(value["close"], 100)
        self.assertEqual(value["period"], 30)

    def test_thirty_first_candle_drops_only_the_oldest(self):
        band = SMA30Band()
        band.update(1000, 180, 50, 100)
        for i in range(1, 30):
            band.update(1000+i*60, 120, 80, 100)
        value = band.update(2800, 120, 80, 100)
        self.assertEqual((value["upper"], value["lower"]), (120, 80))
        self.assertEqual(len(band.rows), 30)

    def test_invalid_and_out_of_order_rows_cannot_mutate_state(self):
        band = SMA30Band()
        band.update(1000, 120, 80, 100)
        for row in [(1000,120,80,100),(999,120,80,100),
                    (1060,float("nan"),80,100),(1060,120,101,100),
                    (1060,99,80,100),(1060,True,80,100)]:
            with self.assertRaises(ValueError):
                band.update(*row)
            self.assertEqual(band.timestamp, 1000)
            self.assertEqual(len(band.rows), 1)

    def test_reused_snapshot_keeps_precision_and_cannot_mutate_cache(self):
        band = SMA30Band()
        for i in range(30):
            band.update(1000+i*60, 100.123456789, 90.987654321, 95.12345)
        value = band.snapshot()
        self.assertAlmostEqual(value["upper"], 100.123456789, places=12)
        self.assertAlmostEqual(value["lower"], 90.987654321, places=12)
        value["upper"] = 0
        self.assertGreater(band.snapshot()["upper"], 100)


class StrictFarEdgeExitTests(unittest.TestCase):
    def policy(self,basis='underlying',kind='sma',enabled=True):
        from sma_band import BandPolicy
        p=BandPolicy({'timeframe':1,'band_price_basis':basis,kind+'_band_period':2,kind+'_band_exit':enabled})
        if kind.upper() in p.states:p.states[kind.upper()].value=dict(upper=120,lower=100,close=110)
        return p

    def test_underlying_boundaries_for_long_call_short_put(self):
        for side in ('LONG','CE','SHORT','PE'):
            for close in (99.99,100,100.01,110,119.99,120,120.01):
                with self.subTest(side=side,close=close):
                    p=self.policy();p.states['SMA'].value['close']=close
                    expected=close<100 if side in ('LONG','CE') else close>120
                    self.assertEqual(bool(p.exit_reason({'side':side})),expected)

    def test_premium_source_keeps_long_semantics_for_bought_call_and_put(self):
        for side in ('CE','PE'):
            for close,expected in ((99.99,True),(100,False),(110,False),(120,False),(120.01,False)):
                p=self.policy('premium');p.states['SMA'].value['close']=close
                self.assertEqual(p.exit_reason({'side':side}),'OPTIONAL_PREMIUM_SMA_BAND' if expected else None)

    def test_disabled_exit_and_ema_far_edge_behavior_unchanged(self):
        self.assertIsNone(self.policy(enabled=False).exit_reason({'side':'LONG'}))
        for side in ('LONG','CE','SHORT','PE'):
            for close in (99.99,100,110,120,120.01):
                p=self.policy(kind='ema');p.states['EMA'].value['close']=close
                self.assertEqual(bool(p.exit_reason({'side':side})),close<100 if side in ('LONG','CE') else close>120)

    def test_completed_candle_and_selected_source_required(self):
        from sma_band import BandPolicy,observe_band
        from types import SimpleNamespace
        from unittest.mock import Mock
        for side,low,high,closes in [
            ('CE',80,120,[(89.99,True),(90,False),(90.01,False),(110,False),(120,False)]),
            ('PE',100,140,[(131,True),(130,False),(129.99,False),(110,False),(100,False)])]:
            for close,expected in closes:
                with self.subTest(side=side,close=close):
                    config=dict(timeframe=1,band_price_basis='underlying',sma_band_period=2,sma_band_exit=True)
                    band=BandPolicy(config)
                    band.observe(dict(kind='underlying',timestamp=1000,high=120,low=100,close=110,closed=True),config)
                    engine=SimpleNamespace(config=config,band=band,position=dict(side=side,entry_timestamp=1050),exit=Mock(return_value=['EXIT']))
                    for event in [
                        dict(kind='price',series='underlying',timestamp=1100,close=close),
                        dict(kind='premium',timestamp=1100,high=high,low=low,close=close,closed=True),
                        dict(kind='underlying',timestamp=1100,high=high,low=low,close=close,closed=False)]:
                        self.assertEqual(observe_band(engine,event),[])
                    engine.exit.assert_not_called()
                    result=observe_band(engine,dict(kind='underlying',timestamp=1100,high=high,low=low,close=close,closed=True,closed_at=1160,available_at=1161))
                    self.assertEqual(bool(result),expected)
                    self.assertEqual(engine.exit.call_count,int(expected))

if __name__ == "__main__":
    unittest.main()
