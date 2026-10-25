from copy import deepcopy
from . import test_runner as fixtures
from .runner import analysis, configuration, HistoryRevision
import unittest


class HistoryRecoveryTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    start=fixtures.RenkoLifecycleTests.start
    append=fixtures.RenkoLifecycleTests.append

    def initialized(self):
        self.r.state['config']=configuration(self.c)
        self.r.signal()

    def test_one_point_revisions_replay_same_anchor_without_old_entry(self):
        self.start();self.r.state['eligible_since']=self.b.now;self.r.signal()
        anchor=self.r.state['renko_engine']['anchor']
        self.b.rows[0]['close']-=1
        self.b.rows[1]['close']+=1
        self.r.step()
        rebuilt=analysis(self.b.rows,self.r.state['config'],.05)
        self.assertEqual(self.r.state['renko_engine'],rebuilt)
        self.assertEqual(self.r.state['renko_engine']['anchor'],anchor)
        self.assertEqual(self.r.state['eligible_since'],self.b.now)
        self.assertIsNone(self.r.state['position']);self.assertIsNone(self.r.state['pending'])
        self.assertEqual(self.r.state['trades_used'],0)
        self.assertFalse(self.r.state.get('order_history'))
        self.assertEqual(len(self.r.state['history_recoveries'][0]['changes']),2)
        self.assertEqual(self.b.sent,[])

    def test_same_revised_history_does_not_recover_repeatedly(self):
        self.initialized();self.b.rows[0]['close']-=1
        self.r.signal();gate=self.r.state.get('eligible_since')
        self.b.now+=1;self.r.signal()
        self.assertEqual(len(self.r.state['history_recoveries']),1)
        self.assertEqual(self.r.state.get('eligible_since'),gate)

    def test_partial_anchor_or_missing_interior_stays_blocked_and_unchanged(self):
        self.initialized();original=deepcopy(self.r.state)
        self.b.rows[-1]['high']+=1
        for rows in [self.b.rows[1:],[self.b.rows[0],self.b.rows[-1]]]:
            with self.assertRaisesRegex(ValueError,'original'):
                self.r.current_analysis(rows,self.r.state['config'],.05)
            self.assertEqual(self.r.state,original)

    def test_invalid_ohlc_is_not_treated_as_recoverable_revision(self):
        self.initialized();original=deepcopy(self.r.state)
        self.b.rows[0]['high']=1
        with self.assertRaisesRegex(ValueError,'Invalid'):
            self.r.signal()
        self.assertEqual(self.r.state,original)

    def test_execution_ownership_quota_and_locks_survive_indicator_rebuild(self):
        self.initialized()
        values=dict(position={'direction':'BULLISH','symbol':'TEST','quantity':20},
                    pending={'id':'UNCERTAIN'},run_id='SAME',trades_used=4,
                    realized_pnl=-123,seen=['CONSUMED'],order_history=[{'tag':'OWNED'}],
                    sideways_lock={'active':True,'high':130,'low':90})
        self.r.state.update(deepcopy(values));self.b.rows[0]['close']-=1
        self.r.current_analysis(self.b.rows,self.r.state['config'],.05)
        for key,value in values.items():self.assertEqual(self.r.state[key],value)

    def test_new_completed_signal_after_recovery_remains_eligible(self):
        self.start();self.r.state['eligible_since']=self.b.now;self.r.signal();self.b.rows[0]['close']-=1
        self.r.step()
        # Allow the unchanged EMA alignment/widening conditions to qualify;
        # a single downward candle is not automatically a bearish entry.
        for price in (80,60,40):
            self.append(price);self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(self.r.state['trades_used'],1)
        self.assertEqual(self.b.sent,[])

    def test_intrabar_old_tick_blocked_but_later_fresh_tick_can_enter(self):
        from .test_intrabar import TickBroker
        self.b=TickBroker();self.r.adapter=self.b;self.c['intrabar_entries']=True
        self.start();self.r.state['eligible_since']=self.b.now;self.r.signal();self.b.rows[0]['close']-=1
        self.r.step();self.assertIsNone(self.r.state['position'])
        self.b.now+=1;self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(self.r.state['trades_used'],1)
        self.assertEqual(self.b.sent,[])

    def test_analysis_still_raises_typed_revision_for_direct_consumers(self):
        self.initialized();self.b.rows[0]['close']-=1
        with self.assertRaises(HistoryRevision):analysis(self.b.rows,self.r.state['config'],.05,self.r.state['renko_engine'])

    def test_backfilled_completed_candle_rebuilds_without_old_order_or_gate_change(self):
        # The source was incomplete when first processed, then fills its gap.
        omitted=self.b.rows.pop(1)
        self.initialized()
        self.r.state.update(eligible_since=self.b.now,seen=['CONSUMED'],trades_used=2,run_id='UNCHANGED')
        original=deepcopy(self.r.state)
        self.b.rows.insert(1,omitted)
        rebuilt=self.r.current_analysis(self.b.rows,self.r.state['config'],.05)
        expected=analysis(self.b.rows,self.r.state['config'],.05)
        self.assertEqual(rebuilt,expected)
        for key in ('eligible_since','seen','trades_used','run_id','position','pending','order_history'):
            self.assertEqual(self.r.state.get(key),original.get(key))
        self.assertEqual(self.r.state['history_recoveries'][-1]['backfilled_bars'],1)
        self.assertEqual(self.b.sent,[])

    def test_backfill_older_than_retained_hashes_rebuilds_without_execution_changes(self):
        from .test_signals import candle
        rows=[candle(i,100+(i%17)) for i in range(1205)]
        omitted=rows.pop(30)
        self.b.rows=rows
        self.initialized()
        saved=deepcopy(self.r.state['renko_engine'])
        self.assertLess(omitted['timestamp'],min(map(float,saved['price_fingerprints'])))
        self.r.state.update(eligible_since=self.b.now,seen=['CONSUMED'],trades_used=2,run_id='UNCHANGED')
        original=deepcopy(self.r.state)
        self.b.rows.insert(30,omitted)
        with self.assertRaises(HistoryRevision):
            analysis(self.b.rows,self.r.state['config'],.05,saved)
        rebuilt=self.r.current_analysis(self.b.rows,self.r.state['config'],.05)
        self.assertEqual(rebuilt,analysis(self.b.rows,self.r.state['config'],.05))
        self.assertEqual(rebuilt['state']['count'],1205)
        for key in ('eligible_since','seen','trades_used','run_id','position','pending','order_history'):
            self.assertEqual(self.r.state.get(key),original.get(key))
        self.assertEqual(self.b.sent,[])

    def test_price_revision_before_retained_hashes_rebuilds_at_same_anchor(self):
        from .test_signals import candle
        self.b.rows=[candle(i,100+(i%17)) for i in range(1205)]
        self.initialized()
        before=deepcopy(self.r.state)
        self.b.rows[30]['close']-=.5
        with self.assertRaises(HistoryRevision):
            analysis(self.b.rows,self.r.state['config'],.05,self.r.state['renko_engine'])
        rebuilt=self.r.current_analysis(self.b.rows,self.r.state['config'],.05)
        self.assertEqual(rebuilt,analysis(self.b.rows,self.r.state['config'],.05))
        self.assertEqual(before.get('order_history'),self.r.state.get('order_history'))
        self.assertEqual(self.b.sent,[])

    def test_missing_old_candle_stays_blocked_without_reseeding(self):
        from .test_signals import candle
        self.b.rows=[candle(i,100+(i%17)) for i in range(1205)]
        self.initialized()
        original=deepcopy(self.r.state)
        self.b.rows.pop(30)
        with self.assertRaisesRegex(ValueError,'original'):
            self.r.current_analysis(self.b.rows,self.r.state['config'],.05)
        self.assertEqual(self.r.state,original)

    def other_instrument_lock(self):
        self.initialized();self.r.state['config']['sideways_enabled']=True
        self.r.state['run_id']='NEW'
        self.r.state['sideways_lock']=dict(active=True,underlying='BSE:SENSEX-INDEX',
            trade_id='PAPER-TRADE-OLD',high=73000,low=72900)
        self.r.state['order_history']=[dict(side='BUY',underlying_symbol='BSE:SENSEX-INDEX',
            run_id='PREVIOUS',mode='PAPER',lifecycle_id='OLD')]

    def test_proven_prior_instrument_lock_archived_with_new_freshness_gate(self):
        self.other_instrument_lock();history=deepcopy(self.r.state['order_history'])
        self.assertTrue(self.r.sideways_entry_gate())
        self.assertIsNone(self.r.state['sideways_lock'])
        self.assertEqual(self.r.state['order_history'],history)
        self.assertEqual(self.r.state['eligible_since'],self.b.now)
        self.assertEqual(self.r.state['sideways_archived'][0]['archive_reason'],'NEW_RUN_DIFFERENT_UNDERLYING')
        self.assertEqual(self.r.state['sideways_archived'][0]['high'],73000)

    def test_unknown_or_current_run_range_not_silently_cleared(self):
        for current_owner in (False,True):
            self.other_instrument_lock()
            if current_owner:self.r.state['order_history'][0]['run_id']='NEW'
            else:self.r.state['order_history']=[]
            self.assertFalse(self.r.sideways_entry_gate())
            self.assertTrue(self.r.state['sideways_lock']['active'])

    def test_same_underlying_loss_range_remains_active(self):
        self.other_instrument_lock()
        self.r.state['sideways_lock']['underlying']=self.r.state['config']['underlying']
        self.r.state['sideways_lock']['triggered_at']=self.b.now-1
        self.b.live_price=lambda c,now:(72910,now)
        self.assertFalse(self.r.sideways_entry_gate())
        self.assertTrue(self.r.state['sideways_lock']['active'])


if __name__=='__main__':unittest.main()
