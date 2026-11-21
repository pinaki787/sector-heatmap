"""Regression checks for staged incremental immutable price-row publication."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from strategies.renko_supertrend.confirmed_feed import (
    bind_confirmed, confirmed_export, publish_confirmed)

CASE = Path('.private/chart-order-rollouts/fyers-sensex-execution-alignment-20261119')


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.state = json.loads((CASE/'state-snapshot.json').read_text())
        self.runner = SimpleNamespace(state=self.state)

    def publish(self, engine=None):
        engine = engine or self.state['renko_engine']
        publish_confirmed(self.runner, engine=engine,
                          config=self.state['config'], immutable_rows=True)
        return self.runner._confirmed_publication

    def test_exact_legacy_publication_values(self):
        actual = self.publish()
        expected = confirmed_export(self.state, include_rows=True)
        self.assertEqual({k:v for k,v in actual.items() if not k.startswith('_')}, expected)

    def test_reuses_only_unchanged_row_objects(self):
        engine = self.state['renko_engine']
        first = self.publish(engine)
        replacement = deepcopy(engine['rows'][-1])
        replacement['close'] += .25
        next_engine = {**engine, 'rows': engine['rows'][1:]+[replacement]}
        second = self.publish(next_engine)
        self.assertIs(second['rows'][0], first['rows'][1])
        self.assertIsNot(second['rows'][-1], first['rows'][-1])
        self.assertEqual(second['rows'], next_engine['rows'])
        self.assertEqual(len(self.runner._confirmed_row_cache[1]), 500)

    def test_reader_mutation_is_isolated(self):
        original = deepcopy(self.publish())
        c = self.state['config']
        reader = bind_confirmed(self.runner, self.state['run_id'], c['underlying'], c['timeframe'])
        reader['rows'][0]['close'] = -999
        reader['_engine']['state'].clear()
        self.assertEqual(self.runner._confirmed_publication, original)

    def test_run_change_discards_row_cache(self):
        first = self.publish()
        self.state['run_id'] = 'new-isolated-test-run'
        second = self.publish()
        self.assertIsNot(first['rows'][0], second['rows'][0])
        self.assertEqual(first['rows'], second['rows'])

    def test_mutable_default_does_not_use_row_cache(self):
        self.publish()
        engine = {**self.state['renko_engine']}
        publish_confirmed(self.runner, engine=engine)
        self.assertIsNone(self.runner._confirmed_row_cache)
        frozen = deepcopy(self.runner._confirmed_publication)
        engine['rows'][0]['close'] = -999
        self.assertEqual(self.runner._confirmed_publication, frozen)

    def test_offline_continuation_keeps_exact_durable_history(self):
        baseline = json.loads((CASE/'producer-profile/price-confirmed-history.json').read_text())
        candidate = json.loads((CASE/'producer-profile-candidate/price-confirmed-history.json').read_text())
        self.assertEqual(baseline, candidate)


if __name__ == '__main__':
    unittest.main()
