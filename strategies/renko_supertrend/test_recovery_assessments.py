"""Lifecycle regression coverage: revisions cannot consume fresh entry candles."""
from copy import deepcopy
from .test_runner import RenkoLifecycleTests,FakeBroker
from .test_signals import candle
from .runner import Runner,configuration,analysis
import unittest

class RecoveryAssessmentTests(unittest.TestCase):
    setUp=RenkoLifecycleTests.setUp
    start=RenkoLifecycleTests.start
    append=RenkoLifecycleTests.append

    def initialize(self):
        self.start();self.r.step()
        # Start these scenarios flat with an initialized, consumed baseline.
        if self.r.state['position']:
            self.append(80);self.r.step()
        self.assertIsNone(self.r.state['position'])
        return self.r.state['eligible_since']

    def test_repeated_old_corrections_cannot_move_boundary_or_consume_new_entry(self):
        boundary=self.initialize()
        for index,price in enumerate((60,40,20)):
            self.b.rows[0]['close']=100+(index%2)
            self.append(price)
            self.r.step()
            self.assertEqual(self.r.state['eligible_since'],boundary)
            if self.r.state['position']:break
        self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(self.r.state['position']['direction'],'BEARISH')
        self.assertEqual(self.r.state['latest_entry_assessment']['code'],'ELIGIBLE')
        count=len(self.r.state['order_history']);quota=self.r.state['trades_used']
        self.r.step();self.r.step()
        self.assertEqual(len(self.r.state['order_history']),count)
        self.assertEqual(self.r.state['trades_used'],quota);self.assertEqual(self.b.sent,[])

    def test_revised_consumed_bar_never_replays_order_or_rewrites_assessment(self):
        self.start();self.r.step();old=deepcopy(self.r.state['latest_entry_assessment'])
        self.r.state['position']=None
        count=len(self.r.state['order_history'])
        self.b.rows[0]['close']-=1;self.r.step()
        self.assertEqual(len(self.r.state['order_history']),count)
        self.assertEqual(self.r.state['latest_entry_assessment'],old)
        self.assertIsNone(self.r.state['position'])

    def test_real_reconnection_boundary_is_preserved_through_history_repair(self):
        self.initialize();self.b.stream_status=lambda:dict(connected=False,generation=1)
        self.r.step();self.assertEqual(self.r.state['status'],'WAITING_FOR_STREAM')
        self.b.now+=2;self.b.stream_status=lambda:dict(connected=True,generation=2)
        self.b.rows[0]['close']-=1;self.r.step()
        self.assertEqual(self.r.state['eligible_since'],self.b.now)
        self.assertIsNone(self.r.state['position'])
        boundary=self.b.now
        self.b.now+=2;self.b.rows[0]['close']+=1;self.r.step()
        self.assertEqual(self.r.state['eligible_since'],boundary)

    def test_no_entry_event_still_has_durable_assessment_with_gate_evidence(self):
        self.start();self.r.state['eligible_since']=self.b.now
        self.r.step()
        a=self.r.state['latest_entry_assessment']
        self.assertEqual(a['code'],'BEFORE_ELIGIBILITY');self.assertIn('ema10',a['signal'])
        self.assertEqual(a['run_id'],self.r.state.get('run_id'))
        self.append(121);self.r.step()
        a=self.r.state['latest_entry_assessment']
        self.assertFalse(a['eligible']);self.assertIn(a['code'],('WAITING_WIDENING','NO_ENTRY_EVENT'))
        self.assertEqual(len(self.r.state['entry_assessments']),2)
        self.r.step();self.assertEqual(len(self.r.state['entry_assessments']),2)

    def test_missing_forming_ohlc_does_not_block_completed_entry(self):
        self.b.forming=lambda *args: (_ for _ in ()).throw(ValueError('Broker forming OHLC unavailable'))
        self.c.update(intrabar_entries=False)
        self.start();self.r.step()
        self.assertIsNotNone(self.r.state['position']);self.assertEqual(self.b.sent,[])

    def test_invalid_history_blocks_without_advancing_consumed_candle(self):
        self.start();self.r.signal();prior=self.r.state.get('last_processed_bar')
        self.b.rows[0]['high']=1
        with self.assertRaisesRegex(ValueError,'Invalid'):self.r.step()
        self.assertEqual(self.r.state.get('last_processed_bar'),prior)
        self.assertIsNone(self.r.state['position']);self.assertEqual(self.b.sent,[])

    def test_seeded_rsi_remains_required_after_correction(self):
        self.c['rsi_slope_enabled']=True
        prices=[100+i for i in range(30)]+[130,140]
        self.b.rows=[{**candle(i,p),'timestamp':self.b.now-60*(len(prices)-i)-5} for i,p in enumerate(prices)]
        self.start();self.r.signal();self.r.state['eligible_since']=self.b.now-10
        self.append(90);self.b.rows[0]['close']-=1;self.r.step()
        a=self.r.state['latest_entry_assessment']
        self.assertTrue(a['signal']['rsi_slope_pass'])
        if a['eligible']:self.assertLess(a['signal']['rsi14_slope'],0)
        self.assertEqual(self.r.state['eligible_since'],self.b.now-70)

    def test_seeded_opposing_rsi_still_blocks_after_history_repair(self):
        self.c['rsi_slope_enabled']=True
        prices=[140-i for i in range(30)]+[110,100]
        self.b.rows=[{**candle(i,p),'timestamp':self.b.now-60*(len(prices)-i)-5} for i,p in enumerate(prices)]
        self.start();self.r.state['eligible_since']=self.b.now;self.r.step()
        self.append(101);self.b.rows[0]['close']-=.1;self.r.step()
        a=self.r.state['latest_entry_assessment']
        self.assertFalse(a['signal']['rsi_slope_pass'])
        self.assertGreater(a['signal']['rsi14_slope'],0)
        self.assertFalse(a['eligible']);self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.b.sent,[])

    def test_completed_ema_exit_survives_history_repair_and_entry_cutoff(self):
        self.start();self.r.step();self.assertIsNotNone(self.r.state['position'])
        self.r.state['eligible_since']=self.b.now+1000
        self.append(80);self.b.rows[0]['close']-=.1
        self.r.step()
        self.assertIsNone(self.r.state['position'])
        exit=self.r.state['order_history'][-1]
        self.assertEqual(exit['reason'],'EMA10_CONFIRMED_BREACH')
        snap=exit['indicator_snapshot']
        self.assertEqual(snap['indicators']['timestamp'],self.b.rows[-1]['timestamp'])
        self.assertEqual(snap['indicators']['ema_exit_length'],10)
        self.assertEqual(snap['indicators']['ema_exit'],snap['indicators']['ema10'])
        self.assertEqual(snap['captured_at'],self.b.now)
        self.r.step();self.assertEqual(len(self.r.state['order_history']),2)

    def test_revision_of_same_fresh_candle_reconsiders_protective_exit_without_old_order_replay(self):
        self.start();self.r.step();self.append(125);self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        row=self.b.rows[-1];row.update(open=80,high=81,low=79,close=80)
        self.r.step();self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['order_history'][-1]['reason'],'EMA10_CONFIRMED_BREACH')
        count=len(self.r.state['order_history']);self.r.step();self.assertEqual(len(self.r.state['order_history']),count)

class RetestRevisionTests(unittest.TestCase):
    setUp=RenkoLifecycleTests.setUp
    def test_confirmed_retest_after_replay_survives_and_is_consumed_once(self):
        from .test_retest import CFG,rows
        self.c.update(CFG,intrabar_entries=False)
        self.b.rows=[{**bar,'timestamp':self.b.now-365+i*60} for i,bar in enumerate(rows()[:-1])]
        p=self.r.preview(self.c);self.r.start(dict(preview_id=p['id'],confirmation=p['confirmation']),background=False)
        self.r.step();boundary=self.r.state['eligible_since']
        self.b.now+=60;self.b.rows.append({**rows()[-1],'timestamp':self.b.now-65})
        self.b.rows[0]['close']-=.1
        self.r.step()
        self.assertEqual(self.r.state['eligible_since'],boundary)
        self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(self.r.state['order_history'][-1]['reason'],'EMA10_RETEST_BOUNCE')
        self.assertTrue(self.r.state['latest_entry_assessment']['signal']['retest_signal'])
        self.assertTrue(self.r.state['latest_entry_assessment']['signal']['retest_touch_evidence'])
        self.r.step();self.assertEqual(len(self.r.state['order_history']),1)
        self.assertEqual(self.b.sent,[])

    def test_confirmed_retest_needs_no_forming_ohlc_even_when_intrabar_is_enabled(self):
        from .test_retest import CFG,rows
        self.c.update(CFG,intrabar_entries=True)
        self.b.forming=lambda *args: (_ for _ in ()).throw(ValueError('Broker forming OHLC unavailable'))
        self.b.rows=[{**bar,'timestamp':self.b.now-365+i*60} for i,bar in enumerate(rows()[:-1])]
        p=self.r.preview(self.c);self.r.start(dict(preview_id=p['id'],confirmation=p['confirmation']),background=False)
        with self.assertRaisesRegex(ValueError,'forming OHLC'):self.r.step()
        self.b.now+=60;self.b.rows.append({**rows()[-1],'timestamp':self.b.now-65})
        self.b.rows[0]['close']-=.1;self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(self.r.state['order_history'][-1]['reason'],'EMA10_RETEST_BOUNCE')
        self.assertEqual(self.r.state['position']['entry_mode'],'CONFIRMED')
        self.r.step();self.assertEqual(len(self.r.state['order_history']),1)
