import unittest
from copy import deepcopy
from types import SimpleNamespace
from .live_chart import LiveChart
from .price_basis import observe
from .runner import analysis
from .test_brick_basis import BASE,candles

class LiveChartTests(unittest.TestCase):
    def setUp(self):
        self.config={**BASE,"manual_brick":10,"underlying":"TEST","timeframe":"5 minutes"}
        self.engine=analysis(candles([100,135,165,195,225,255,285,315]),self.config,.05)
        self.broker=SimpleNamespace(on_tick=None,tick=lambda symbol:None)
        self.chart=LiveChart(self.broker)
        self.chart.seed("a",self.engine,self.config,.05)
        self.stamp=self.engine["last"]["timestamp"]+1
        self.start=self.chart.entries["a"]["engine"]["state"]["price_renko"]["level"]*10
        self.response=dict(rows=deepcopy(self.engine["rows"]),history={},settings=self.config)
        self.chart.apply("a",self.response)
    def price(self,value,delta=1):
        self.stamp+=delta
        self.chart.accept(dict(symbol="TEST",ltp=value,exch_feed_time=self.stamp),self.stamp+.01)
    def test_stopped_chart_jump_exact_threshold_remainder_and_reversal(self):
        self.price(self.start+35)
        rows=self.chart.entries["a"]["rows"][-3:]
        self.assertEqual([r["close"] for r in rows],[self.start+10,self.start+20,self.start+30])
        self.assertTrue(all(r["supertrend"] is not None for r in rows))
        self.price(self.start+39)
        self.assertEqual(self.chart.entries["a"]["version"],3)
        self.price(self.start+40)
        self.assertEqual(self.chart.entries["a"]["version"],4)
        self.price(self.start+21)
        self.assertEqual(self.chart.entries["a"]["version"],4)
        self.price(self.start+20)
        self.assertEqual(self.chart.entries["a"]["rows"][-1]["close"],self.start+20)
        self.assertEqual(self.chart.entries["a"]["rows"][-1]["open"],self.start+30)
    def test_history_refresh_retains_live_confirmations(self):
        self.price(self.start+35)
        before=self.chart.apply("a")
        self.chart.seed("a",self.engine,self.config,.05)
        after=self.chart.apply("a",self.response)
        self.assertEqual(before["rows"],after["rows"])
        self.assertFalse(after["incremental"])
        self.assertTrue(after["live_price_confirmed"])
    def test_ordering_and_other_instrument_are_inert(self):
        self.price(self.start+35)
        before=self.chart.apply("a")
        for raw in [dict(symbol="OTHER",ltp=900,exch_feed_time=self.stamp+1),
                    dict(symbol="TEST",ltp=900,exch_feed_time=self.stamp-1),
                    dict(symbol="TEST",ltp=900,exch_feed_time=self.stamp)]:
            self.chart.accept(raw,self.stamp+.01)
        self.assertEqual(before,self.chart.apply("a"))
    def test_separate_brokers_and_settings_never_share_state(self):
        other=LiveChart(SimpleNamespace(on_tick=None))
        other.seed("a",self.engine,self.config,.05)
        self.chart.seed("b",self.engine,{**self.config,"underlying":"OTHER"},.05)
        self.price(self.start+35)
        self.assertEqual(other.entries["a"]["version"],0)
        self.assertEqual(self.chart.entries["b"]["version"],0)
    def test_same_accepted_observations_match_runner_engine(self):
        runner=deepcopy(self.chart.entries["a"]["engine"])
        config=self.chart.entries["a"]["config"]
        for value in [self.start+35,self.start+40,self.start+10,self.start+50]:
            self.price(value)
            expected=observe(runner,config,.05,dict(symbol="TEST",ltp=value,exch_feed_time=self.stamp),self.stamp+.01,0)
            if expected:self.assertEqual(expected[-1],self.chart.apply("a")["latest"])
    def test_callback_preserves_same_timestamp_arrival_sequence(self):
        import time
        stamp=time.time()
        self.broker.on_tick(dict(symbol="TEST",ltp=self.start+10,exch_feed_time=stamp,received_at=stamp))
        self.broker.on_tick(dict(symbol="TEST",ltp=self.start+30,exch_feed_time=stamp,received_at=stamp))
        self.assertEqual(self.chart.entries["a"]["version"],3)

    def test_large_valid_jump_completes_every_crossed_brick(self):
        self.price(self.start+10010)
        self.assertEqual(self.chart.entries["a"]["version"],1001)
        self.assertEqual(self.chart.apply("a")["latest"]["close"],self.start+10010)

    def test_seed_bounds_engine_copy_without_dropping_display_history(self):
        engine=deepcopy(self.engine)
        engine['rows']=deepcopy(engine['rows'])*100
        total=len(engine['rows'])
        self.chart.seed('large',engine,self.config,.05)
        item=self.chart.entries['large']
        self.assertEqual(len(item['rows']),total)
        self.assertLessEqual(len(item['engine']['rows']),500)
        self.assertEqual(len(engine['rows']),total)
        item['rows'][0]['close']=-1
        self.assertNotEqual(engine['rows'][0]['close'],-1)

    def test_unused_chart_contexts_are_bounded(self):
        for i in range(8):self.chart.seed(str(i),self.engine,self.config,.05)
        self.assertEqual(len(self.chart.entries),4)
        self.assertIn('7',self.chart.entries)

    def test_live_stream_sends_only_new_bricks_after_known_revision(self):
        before=self.chart.apply('a')
        self.price(self.start+30)
        delta=self.chart.apply('a',revision=before['live_chart_revision'])
        self.assertTrue(delta['incremental'])
        self.assertEqual(len(delta['rows']),3)
        self.assertTrue(all(r['confirmation_basis']=='ORDERED_LIVE_PRICE' for r in delta['rows']))
        merged=before['rows']+delta['rows']
        full=self.chart.apply('a')
        self.assertEqual(merged,full['rows'])
        self.assertEqual(delta['history']['display_count'],len(full['rows']))
        self.assertIsNone(self.chart.apply('a',revision=delta['live_chart_revision']))

    def test_reseed_never_merges_delta_into_previous_generation(self):
        before=self.chart.apply('a')
        self.chart.seed('a',self.engine,self.config,.05,replace=True)
        self.chart.apply('a',self.response)
        self.price(self.start+30)
        recovery=self.chart.apply('a',revision=before['live_chart_revision'])
        self.assertFalse(recovery['incremental'])
        self.assertEqual(recovery['rows'],self.chart.apply('a')['rows'])

    def test_stream_initial_identity_does_not_require_full_history_copy(self):
        revision=self.chart.revision('a')
        self.assertEqual(revision,self.chart.apply('a')['live_chart_revision'])
        self.assertIsNone(self.chart.apply('a',revision=revision))
        self.price(self.start+10)
        delta=self.chart.apply('a',revision=revision)
        self.assertTrue(delta['incremental'])
        self.assertEqual(len(delta['rows']),1)
        self.assertIsNone(self.chart.revision('missing'))
