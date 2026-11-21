"""Check bounded timing diagnostics without brokers or execution mutations."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from strategies.renko_supertrend.price_basis import _remember_price_publication, _record_price_execution_timing


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.runner=SimpleNamespace(state={'run_id':'OFFLINE'},clock=lambda:120)
        self.row={'market_event_at':100,'source_observed_at':101,
                  'source_generation':1,'source_sequence':9,
                  'source_event_index':0,'timestamp':100}

    def test_queue_measurement_uses_monotonic_publication_and_preserves_event(self):
        original=deepcopy(self.row)
        _remember_price_publication(self.runner,[self.row],
            {'queued_monotonic':10,'observe_seconds':.1,'durable_history_seconds':.2})
        record=_record_price_execution_timing(self.runner,self.row,15,.4,'BLOCKED')
        self.assertEqual(record['queue_wait_seconds'],5)
        self.assertEqual(record['receive_to_record_seconds'],19)
        self.assertEqual(record['execution_step_seconds'],.4)
        self.assertNotIn('queued_monotonic',record['publication'])
        self.assertEqual(original,self.row)
        self.assertEqual(self.runner.state['price_execution_timings'],[record])

    def test_identity_distinguishes_same_timestamp_bricks_and_generation(self):
        other={**self.row,'source_event_index':1}
        _remember_price_publication(self.runner,[self.row],{'queued_monotonic':10})
        record=_record_price_execution_timing(self.runner,other,15,.4,'BLOCKED')
        self.assertNotIn('queue_wait_seconds',record)
        other={**self.row,'source_generation':2}
        record=_record_price_execution_timing(self.runner,other,15,.4,'BLOCKED')
        self.assertNotIn('queue_wait_seconds',record)

    def test_cache_and_durable_timings_are_bounded(self):
        for i in range(2100):
            row={**self.row,'source_sequence':i}
            _remember_price_publication(self.runner,[row],{'queued_monotonic':10})
            _record_price_execution_timing(self.runner,row,15,.4,'EXPIRED_ENTRY_EVENT')
        self.assertEqual(len(self.runner._price_event_timings),2000)
        self.assertEqual(len(self.runner.state['price_execution_timings']),120)
        self.assertEqual(self.runner.state['price_execution_timings'][0]['source_sequence'],1980)

    def test_a_new_run_cannot_inherit_prior_queue_timing(self):
        _remember_price_publication(self.runner,[self.row],{'queued_monotonic':10})
        self.runner.state['run_id']='SECOND-RUN'
        record=_record_price_execution_timing(self.runner,self.row,15,0,'BLOCKED')
        self.assertNotIn('queue_wait_seconds',record)
        _remember_price_publication(self.runner,[self.row],{'queued_monotonic':14})
        self.assertEqual(len(self.runner._price_event_timings),1)
        record=_record_price_execution_timing(self.runner,self.row,15,0,'BLOCKED')
        self.assertEqual(record['queue_wait_seconds'],1)

    def test_missing_or_future_receipt_does_not_report_false_positive_age(self):
        for value in (None,True,130):
            row={**self.row,'source_observed_at':value}
            self.assertIsNone(_record_price_execution_timing(self.runner,row,15,0,'EXPIRED_ENTRY_EVENT')['receive_to_record_seconds'])


if __name__=='__main__':
    unittest.main()
