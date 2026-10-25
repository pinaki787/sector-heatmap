"""Split-distance policy: isolated fake-broker lifecycle, no account/broker access."""
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import ema_proximity as ema, preferences
from .test_runner import RenkoLifecycleTests
from .test_intrabar import TickBroker

C=dict(ema_proximity_enabled=True,ema_proximity_mode='ATR',ema_proximity_distance=.5,ema_momentum_enabled=True)
def signal(bull=True):
    return dict(timestamp=100,open=101 if bull else 99,high=114 if bull else 100,low=100 if bull else 86,
        close=113 if bull else 87,ema10=100,ema30=90 if bull else 110,rsi14_slope=2 if bull else -2,
        direction='BULLISH' if bull else 'BEARISH',entry_direction='BULLISH' if bull else 'BEARISH',
        entry_qualified=True,ema_widening=True,signal_allowed=True,retest_signal=False)

class MomentumPolicyTests(unittest.TestCase):
    def test_legacy_default_and_validation(self):
        self.assertFalse(ema.settings({})['ema_momentum_enabled'])
        for extra in ({'ema_proximity_enabled':False},{'ema_proximity_mode':'POINTS'}, {'ema_proximity_distance':1}, {'intrabar_entries':True}, {'ema_momentum_enabled':'yes'}):
            with self.assertRaises(ValueError):ema.settings({**C,**extra})
        with self.assertRaisesRegex(ValueError,'too far'):ema.check({**C,'ema_momentum_enabled':False},113,100,10)
    def test_symmetric_momentum_limits_and_evidence(self):
        for bull in (True,False):
            sig=signal(bull);direction=sig['direction'];price=115 if bull else 85
            e=ema.check(C,price,100,10,sig,direction)
            self.assertEqual(e['entry_path'],'MOMENTUM_FIRST_QUALIFICATION');self.assertEqual(e['configured_limit'],1.5)
            with self.assertRaisesRegex(ValueError,'too far'):ema.check(C,price+(.01 if bull else -.01),100,10,sig,direction)
    def test_chase_boundary_both_sides(self):
        for bull in (True,False):
            sig=signal(bull);sig['close']=112 if bull else 88
            price=sig['close']+(2.5 if bull else -2.5)
            ema.check(C,price,100,10,sig,sig['direction'])
            with self.assertRaisesRegex(ValueError,'chased'):ema.check(C,price+(.01 if bull else -.01),100,10,sig,sig['direction'])
    def test_retest_keeps_baseline_no_momentum_exception(self):
        sig={**signal(),'retest_signal':True}
        self.assertEqual(ema.check(C,105,100,10,sig,'BULLISH')['entry_path'],'RETEST')
        with self.assertRaisesRegex(ValueError,'too far'):ema.check(C,105.01,100,10,sig,'BULLISH')
    def test_no_continuation_provisional_wrong_trend_or_bad_shape(self):
        for extra in ({'entry_direction':None},{'provisional':True},{'direction':'BEARISH'}, {'ema_widening':False},{'rsi14_slope':-1},{'open':114},{'low':90,'high':130},{'rsi14_slope':math.nan}):
            with self.assertRaises(ValueError):ema.check(C,113,100,10,{**signal(),**extra},'BULLISH')
        with self.assertRaises(ValueError):ema.check(C,99,100,10,signal(),'BULLISH')
    def test_preferences_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'settings.json'
            value={'ema-momentum-enabled':True,'ema-proximity-enabled':True,'ema-proximity-mode':'ATR','ema-proximity-distance':'0.5'}
            preferences.write(path,{'settings':value},100)
            self.assertEqual(preferences.read(path)['settings'],value)

class MomentumLifecycleTests(unittest.TestCase):
    setUp=RenkoLifecycleTests.setUp
    start=RenkoLifecycleTests.start
    def prepare(self,price=113):
        self.b=TickBroker();self.b.price=price;self.r.adapter=self.b
        self.c.update(C);self.c.update(ema_exit_enabled=False,sideways_enabled=False)
        self.start();self.r.signal()
        sig=signal();sig.update(timestamp=int(self.b.now//60)*60-60,cross_direction='BULLISH',entry_diagnostic='QUALIFIED',host_atr=10)
        self.r.state['renko_engine']['state'].update(ema10=100,ema30=90,ema100=80)
        self.r.state['renko_engine']['last'].update(timestamp=sig['timestamp'],host_atr=10)
        def observed():
            self.r.state['last_signal']=dict(sig)
            return dict(sig)
        self.r.signal=observed
        return sig
    def test_first_qualification_paper_fill_and_duplicate_protection(self):
        sig=self.prepare();self.r.step()
        p=self.r.state['position'];self.assertIsNotNone(p)
        self.assertEqual(p['entry_indicator_snapshot']['ema_proximity_observation']['entry_path'],'MOMENTUM_FIRST_QUALIFICATION')
        self.assertEqual(self.r.state['trades_used'],1);self.assertEqual(self.b.sent,[])
        self.r.step();self.assertEqual(len(self.r.state['order_history']),1)
    def test_chase_blocks_before_intent_then_continuation_cannot_retry(self):
        sig=self.prepare(116)
        with self.assertRaisesRegex(ValueError,'chased'):self.r.step()
        self.assertIsNone(self.r.state['pending']);self.assertIsNone(self.r.state['position']);self.assertEqual(self.b.sent,[])
        self.assertEqual(self.r.state['trades_used'],0)
        self.b.now+=60;sig.update(timestamp=sig['timestamp']+60,entry_direction=None)
        self.r.state['renko_engine']['last']['timestamp']=sig['timestamp']
        self.b.price=104
        self.r.step()
        self.assertEqual(self.r.state['latest_entry_assessment']['code'],'WAITING_NEW_QUALIFICATION')
        self.assertEqual(self.r.state.get('order_history',[]),[])
    def test_prearming_event_never_replayed(self):
        self.prepare();self.r.state['eligible_since']=self.b.now
        self.r.step();self.assertEqual(self.r.state['latest_entry_assessment']['code'],'BEFORE_ELIGIBILITY')
        self.assertIsNone(self.r.state['position']);self.assertEqual(self.b.sent,[])
    def test_existing_position_exit_does_not_use_entry_allowance(self):
        self.prepare();self.r.step();self.assertIsNotNone(self.r.state['position'])
        # An explicit owned-position exit uses the same submit path but must not
        # run any entry distance checks, even when the price is far away.
        p=self.r.state['position'];self.b.price=80
        order=self.b.order(p['symbol'],p['quantity'],-1,self.b.quote(p['symbol']))
        with patch('strategies.renko_supertrend.runner.ema_proximity.check',side_effect=AssertionError('entry filter on exit')):
            self.r.submit(order,p,'TEST_OWNED_EXIT')
        self.assertIsNone(self.r.state['position']);self.assertEqual(self.b.sent,[])

    def test_price_moves_during_broker_preflight_still_no_intent(self):
        self.c['mode']='LIVE'  # FakeBroker only; exercises broker preflight.
        self.prepare()
        def delayed_preflight(order,config):self.b.price=116
        self.b.preflight=delayed_preflight
        with self.assertRaisesRegex(ValueError,'chased'):self.r.step()
        self.assertIsNone(self.r.state['pending']);self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['trades_used'],0);self.assertEqual(self.b.sent,[])
    def test_new_qualification_after_block_can_enter(self):
        sig=self.prepare(116)
        with self.assertRaises(ValueError):self.r.step()
        self.b.now+=60;sig['timestamp']+=60
        self.r.state['renko_engine']['last']['timestamp']=sig['timestamp'];self.b.price=113
        self.r.step();self.assertIsNotNone(self.r.state['position']);self.assertEqual(self.b.sent,[])
    def test_retest_after_block_uses_baseline_and_can_enter(self):
        sig=self.prepare(116)
        with self.assertRaises(ValueError):self.r.step()
        self.b.now+=60;sig.update(timestamp=sig['timestamp']+60,retest_signal=True)
        self.r.state['renko_engine']['last']['timestamp']=sig['timestamp'];self.b.price=104
        self.r.step();self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(self.r.state['position']['entry_indicator_snapshot']['ema_proximity_observation']['entry_path'],'RETEST')
