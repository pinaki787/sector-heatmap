import unittest
from unittest.mock import patch
from . import mtf_supertrend as mtf


def candles(seconds, count=100):
    return [dict(timestamp=i*seconds,open=100+i,high=102+i,low=99+i,close=101+i) for i in range(count)]


class AgreementTests(unittest.TestCase):
    def test_direction_truth_table(self):
        for one in ('BULLISH','BEARISH'):
            for five in ('BULLISH','BEARISH'):
                for side in ('BULLISH','BEARISH'):
                    self.assertEqual(mtf.agreement(dict(direction=one),dict(direction=five),side),one==five==side)

    def test_no_future_five_minute_close_or_forming_value(self):
        base=candles(300)
        confirmed=mtf.latest(base,{},.05,300,30000)
        future=dict(timestamp=30000,open=1,high=10000,low=1,close=1)
        self.assertEqual(mtf.latest(base+[future],{},.05,300,30299),confirmed)
        future['is_forming']=True
        self.assertEqual(mtf.latest(base+[future],{},.05,300,30000),confirmed)

    def test_unavailable_stale_invalid_and_warmup_fail_closed(self):
        one=candles(60,500);five=candles(300)
        for bad,at in [([],30000),(five,30300),(five[:-1],30000)]:
            self.assertFalse(mtf.check(one,bad,{},.05,'BULLISH',at)['allowed'])
        bad=[dict(c) for c in five];bad[-1]['high']=0
        self.assertFalse(mtf.check(one,bad,{},.05,'BULLISH',30000)['allowed'])
        self.assertFalse(mtf.check(candles(60,2),candles(300,2),{},.05,'BULLISH',600)['allowed'])

    def test_success_requires_both_completed_sources(self):
        one=candles(60,500);five=candles(300)
        result=mtf.check(one,five,{},.05,'BULLISH',30000)
        self.assertTrue(result['allowed'])
        self.assertEqual(result['one_minute']['timestamp'],29940)
        self.assertEqual(result['five_minute']['timestamp'],29700)
        self.assertFalse(mtf.check(one,five,{},.05,'BEARISH',30000)['allowed'])


from .runner import Runner
REAL_AGREEMENT = Runner.supertrend_agreement
from .test_runner import RenkoLifecycleTests
from .test_signals import candle


class RunnerAgreementTests(unittest.TestCase):
    setUp = RenkoLifecycleTests.setUp
    start = RenkoLifecycleTests.start
    append = RenkoLifecycleTests.append

    def source(self, prices):
        end=int(self.b.now)//300*300
        five=[{**candle(i,price),'timestamp':end-900+i*300} for i,price in enumerate(prices)]
        original=self.b.candles
        self.b.candles=lambda c: five if c['timeframe']=='5 minutes' else original(c)
        return patch.object(self.r,'supertrend_agreement',side_effect=lambda *a,**k:REAL_AGREEMENT(self.r,*a,**k))

    def test_matching_timeframes_enter_call_and_preserve_exit_when_five_unavailable(self):
        with self.source([100,110,120]):
            self.start();self.r.step()
            self.assertEqual(self.r.state['position']['symbol'],'NSE:TESTCE')
            self.assertTrue(self.r.state['position']['entry_indicator_snapshot']['indicators']['mtf_supertrend']['allowed'])
            original=self.b.candles
            def source(c):
                if c['timeframe']=='5 minutes':raise ValueError('Five-minute feed missing')
                return original(c)
            self.b.candles=source
            self.append(80);self.r.step()
            self.assertIsNone(self.r.state['position'])
            self.assertEqual(self.r.state['order_history'][-1]['reason'],'EMA10_CONFIRMED_BREACH')
            self.assertEqual(self.b.sent,[])

    def test_opposing_five_minute_blocks_normal_and_manual_entry(self):
        with self.source([120,110,80]):
            self.start();self.r.step()
            self.assertIsNone(self.r.state['position'])
            self.assertEqual(self.r.state['latest_entry_assessment']['code'],'SUPERTREND_TIMEFRAME_AGREEMENT')
            with self.assertRaisesRegex(ValueError,'do not agree'):
                self.r.submit(dict(symbol='NSE:TESTCE',side=1,qty=20),dict(symbol='NSE:TESTCE',direction='BULLISH',entry_mode='MANUAL_OVERRIDE'),'MANUAL_OVERRIDE_ENTRY')
            self.assertEqual(self.r.state.get('order_history',[]),[])
            self.assertEqual(self.b.sent,[])

    def test_direction_changes_during_preflight_block_before_order_intent(self):
        with self.source([100,110,120]):
            self.start();sig=self.r.signal()
            self.assertTrue(sig['mtf_supertrend']['allowed'])
            with patch.object(self.r,'supertrend_agreement',return_value=dict(allowed=False,reason='Directions changed')):
                with self.assertRaisesRegex(ValueError,'Directions changed'):
                    self.r.submit(dict(symbol='NSE:TESTCE',side=1,qty=20),dict(symbol='NSE:TESTCE',direction='BULLISH'),'RENKO_EMA_ENTRY')
            self.assertEqual(self.r.state.get('order_history',[]),[])
            self.assertEqual(self.b.sent,[])
