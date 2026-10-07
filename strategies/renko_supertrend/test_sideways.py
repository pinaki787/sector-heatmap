import json,unittest
from pathlib import Path
from . import sideways,test_runner as fixtures
from .runner import Runner

class RangeRulesTests(unittest.TestCase):
    def exposure(self):
        e=None
        for p,t in [(999,99),(100,100),(105,110),(95,120),(101,130),(800,301)]:
            e=sideways.observe(e,100,p,t,t,exit_at=300)
        return e
    def test_only_exposure_ticks_not_prior_swing_or_after_exit(self):
        e=self.exposure();self.assertEqual((e['high'],e['low']),(105,95))
        self.assertEqual(e['first_tick_at'],100)
    def test_negative_loss_and_host_candle_bucket_window(self):
        e=self.exposure();c=dict(sideways_enabled=True,sideways_max_candles=3)
        for t,count in [(130,2),(179,2),(180,3)]:
            lock=sideways.freeze(e,t,-1,60,c,'T','BSE:SENSEX-INDEX')
            self.assertEqual(lock['host_candles'],count)
        for pnl in [0,1,None]:self.assertIsNone(sideways.freeze(e,180,pnl,60,c,'T','S'))
        self.assertIsNone(sideways.freeze(e,240,-1,60,c,'T','S'))
        self.assertIsNone(sideways.freeze(e,180,-1,60,dict(c,sideways_enabled=False),'T','S'))
        self.assertIsNone(sideways.freeze(e,180,-1,60,dict(c,sideways_max_candles=2),'T','S'))
    def test_frozen_range_strict_breakout_freshness_and_restoration(self):
        lock=sideways.freeze(self.exposure(),180,-10,60,dict(sideways_enabled=True),'T','S')
        restored=json.loads(json.dumps(lock))
        for price in [95,100,105]:self.assertIsNone(sideways.breakout(restored,price,181,181))
        self.assertEqual(sideways.breakout(restored,105.01,181,181),'BREAK_ABOVE_POSITION_HIGH')
        self.assertEqual(sideways.breakout(restored,94.99,181,181),'BREAK_BELOW_POSITION_LOW')
        self.assertIsNone(sideways.breakout(restored,110,181,197))
        self.assertIsNone(sideways.breakout(restored,110,180,181))
        self.assertEqual(restored['high'],105)

class RangeRunnerTests(unittest.TestCase):
    def setUp(self):
        fixtures.RenkoLifecycleTests.setUp(self)
        self.c['underlying']='BSE:SENSEX-INDEX'
        self.b.resolve=lambda c,d:dict(symbol='BSE:SENSEX26O0872700CE' if d=='BULLISH' else 'BSE:SENSEX26O0872700PE',lot_size=20,tick_size=.05,quantity_multiplier=1)

    start=fixtures.RenkoLifecycleTests.start
    def test_losing_call_freezes_ticks_and_restore_retains_lock(self):
        self.c['sideways_enabled']=True;self.start();self.r.step()
        p=self.r.state['position'];entry=p['opened_at']
        for price,stamp in [(999,entry-1),(130,entry+1),(115,entry+2)]:
            self.b.now=stamp
            self.r.adapter.on_tick(dict(symbol=self.c['underlying'],ltp=price,exch_feed_time=stamp))
        self.b.quote=lambda symbol:dict(bid=8,ask=10)
        self.b.now=entry+65
        self.r.submit(self.b.order(p['symbol'],p['quantity'],-1,{}),p,'TEST_EXIT')
        lock=self.r.state['sideways_lock']
        self.assertEqual((lock['high'],lock['low']),(130,115))
        self.assertTrue(lock['active']);self.assertEqual(lock['host_candles'],2)
        other=Runner(self.b,self.path,lambda:self.b.now);self.addCleanup(other.release)
        self.assertEqual(other.state['sideways_lock'],lock)
        self.b.live_price=lambda *args:(130,self.b.now)
        self.assertFalse(other.sideways_entry_gate())
        self.b.now+=1;self.b.live_price=lambda *args:(130.01,self.b.now)
        self.assertTrue(other.sideways_entry_gate())
        self.assertFalse(other.state['sideways_lock']['active'])
        self.assertEqual(other.state['eligible_since'],self.b.now)
        self.assertFalse(other.fresh_cross(dict(timestamp=int(self.b.now//60)*60-60,cross_direction='BULLISH')))
        self.assertEqual(self.b.sent,[])
    def test_put_range_uses_underlying_extrema_and_off_never_blocks(self):
        self.start();self.r.step()
        self.r.state['position']['direction']='BEARISH'
        entry=self.r.state['position']['opened_at'];self.b.now=entry+1
        self.r.adapter.on_tick(dict(symbol=self.c['underlying'],ltp=80,exch_feed_time=self.b.now))
        self.r.drain_position_ticks()
        self.r.state['sideways_lock']=dict(active=True,high=120,low=80,triggered_at=entry)
        self.assertTrue(self.r.sideways_entry_gate())
        self.assertEqual(self.r.state['position']['exposure_range']['low'],80)

    def test_losing_put_freezes_position_only_range_and_preserves_exit(self):
        self.c['sideways_enabled']=True;self.start();self.r.step()
        p=self.r.state['position'];p['direction']='BEARISH'
        p['symbol']='BSE:SENSEX26O0872700PE'
        self.r.state['order_history'][0]['symbol']=p['symbol']
        entry=p['opened_at']
        for price,stamp in [(1000,entry-1),(80,entry+1),(90,entry+2)]:
            self.b.now=stamp
            self.r.adapter.on_tick(dict(symbol=self.c['underlying'],ltp=price,exch_feed_time=stamp))
        self.b.quote=lambda symbol:dict(bid=8,ask=10)
        self.b.now=entry+65
        self.r.submit(self.b.order(p['symbol'],p['quantity'],-1,{}),p,'TEST_EXIT')
        self.assertIsNone(self.r.state['position'])
        lock=self.r.state['sideways_lock']
        self.assertTrue(lock['active'])
        self.assertEqual((lock['high'],lock['low']),(90,80))
        self.assertEqual(lock['host_candles'],2)
        self.assertLess(self.r.snapshot()['cost_pnl']['realized_net'],0)
        self.assertEqual(self.b.sent,[])
