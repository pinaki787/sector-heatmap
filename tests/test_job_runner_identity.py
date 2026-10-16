"""A saved job cannot stop a replacement trading run; fixtures send no orders."""
import unittest
from unittest.mock import patch
from tests import test_delta_atm_runner as fixture


class RunnerIdentityTests(unittest.TestCase):
    setUp=fixture.AtmOptionRunner.setUp
    signal=fixture.AtmOptionRunner.signal
    config=fixture.AtmOptionRunner.config

    def test_stop_for_old_run_preserves_replacement(self):
        with patch('sector_heatmap.delta_india.threading.Thread'):
            first=self.b.start_runner(self.config())['runner']['run_id']
            self.b.stop_runner({'run_id':first})
            second=self.b.start_runner(self.config())['runner']['run_id']
        self.assertNotEqual(first,second)
        with self.assertRaisesRegex(ValueError,'replacement run was preserved'):
            self.b.stop_runner({'run_id':first})
        self.assertTrue(self.b.runner['running'])
        self.assertEqual(self.b.runner['run_id'],second)
        self.b.stop_runner({'run_id':second})
        self.assertFalse(self.b.runner['running'])
