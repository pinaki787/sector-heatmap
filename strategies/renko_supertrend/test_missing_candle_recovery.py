import threading
import unittest
from unittest.mock import Mock, patch

from .stream import recover_chart_candles, browser_frame
from .test_runner import RenkoLifecycleTests


class ChartRecoveryTests(unittest.TestCase):
    def test_backfill_is_nonblocking_single_flight_and_retries_after_failure(self):
        broker=Mock();entered=threading.Event();release=threading.Event()
        def history(c):
            entered.set();release.wait(2)
            raise ValueError('history gap')
        broker.candles.side_effect=history
        config=dict(underlying='NSE:TEST',timeframe='1 minute')
        recover_chart_candles(broker,config,100)
        self.assertTrue(entered.wait(.5))
        recover_chart_candles(broker,config,120)
        self.assertEqual(broker.candles.call_count,1)
        release.set();broker._browser_candle_recovery['worker'].join(1)
        broker.observe.assert_not_called()
        broker.candles.side_effect=None;broker.candles.return_value=[dict(timestamp=120)]
        recover_chart_candles(broker,config,105)
        self.assertEqual(broker.candles.call_count,1)
        recover_chart_candles(broker,config,110)
        broker._browser_candle_recovery['worker'].join(1)
        broker.observe.assert_called_once_with(config,broker.candles.return_value)
        broker.place.assert_not_called()

    def test_no_recovery_from_stale_ticks_and_completed_mode_warning_scope(self):
        broker=Mock(connected=True,frame_seconds={})
        broker.forming.side_effect=ValueError('intrabar entry blocked')
        broker.live_price.side_effect=ValueError('stale tick')
        config=dict(underlying='NSE:TEST',timeframe='1 minute',intrabar_entries=False)
        with patch('strategies.renko_supertrend.stream.recover_chart_candles') as recover:
            frame=browser_frame(Mock(),broker,config,Mock(),130)
            recover.assert_not_called()
            broker.live_price.side_effect=None;broker.live_price.return_value=(10,130)
            frame=browser_frame(Mock(),broker,config,Mock(),130)
            recover.assert_called_once_with(broker,config,130)
            self.assertIn('separate confirmed history',frame['market']['error'])
            self.assertNotIn('intrabar entry blocked',frame['market']['error'])


class CompletedFallbackTests(unittest.TestCase):
    setUp=RenkoLifecycleTests.setUp
    start=RenkoLifecycleTests.start

    def missing(self):
        self.c['intrabar_entries']=True
        self.b.forming=lambda *a: (_ for _ in ()).throw(ValueError('OHLC unavailable'))

    def test_missing_forming_uses_fresh_confirmed_evidence_once(self):
        self.missing();self.start();self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(self.r.state['latest_entry_assessment']['signal']['entry_data_mode'],'COMPLETED_CANDLE_FALLBACK')
        self.r.step();self.assertEqual(len(self.r.state['order_history']),1)
        self.assertEqual(self.b.sent,[])

    def test_completed_mode_auto_qualification_submission_and_reconciliation_with_fake_broker(self):
        # LIVE exercises the actual order lifecycle against FakeBroker only.
        self.c.update(mode='LIVE',intrabar_entries=False)
        self.b.forming=lambda *a: (_ for _ in ()).throw(ValueError('OHLC unavailable'))
        self.start();self.r.step()
        self.assertEqual(self.r.state['latest_entry_assessment']['code'],'ELIGIBLE')
        self.assertEqual(len(self.b.sent),1)
        pending=self.r.state['pending']
        self.b.book=[dict(pending['order'],id=pending['id'],status=2,filledQty=20,tradedPrice=10)]
        self.b.qty=20;self.r.step()
        self.assertEqual(self.r.state['position']['quantity'],20)
        self.assertEqual(self.r.state['order_history'][-1]['reason'],'RENKO_EMA_ENTRY')
        self.r.step();self.assertEqual(len(self.b.sent),1)

    def test_stale_completed_evidence_never_replayed_on_recovery(self):
        self.missing();self.start();self.b.now+=120;self.r.step()
        self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['latest_entry_assessment']['code'],'STALE_EVENT')
        self.r.step();self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.b.sent,[])

    def test_invalid_completed_history_is_not_replaced_with_ticks(self):
        self.missing();self.start();self.b.rows[-1]['high']=1
        with self.assertRaisesRegex(ValueError,'Invalid'):self.r.step()
        self.assertIsNone(self.r.state.get('last_processed_bar'))
        self.assertIsNone(self.r.state['position'])
