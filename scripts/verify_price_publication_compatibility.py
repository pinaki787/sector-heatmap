"""Offline publisher interface compatibility checks; no broker access."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock
p=Path('.private/chart-order-rollouts/fyers-sensex-execution-alignment-20261119/price_basis.candidate.py')
spec=importlib.util.spec_from_file_location('strategies.renko_supertrend.candidate_price_compatibility',p)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CompatibilityTests(unittest.TestCase):
    def test_cached_legacy_signature(self):
        calls=[]
        def legacy(runner,*,engine=None,config=None):calls.append((runner,engine,config));return 'published'
        self.assertEqual(module._publish_price_confirmed(legacy,'runner',engine={'rows':[]},config={'x':1}),'published')
        self.assertEqual(calls,[('runner',{'rows':[]},{'x':1})])
    def test_new_signature_uses_immutable(self):
        def current(runner,*,engine=None,config=None,immutable_rows=False):return immutable_rows
        self.assertTrue(module._publish_price_confirmed(current,None,engine={},config={}))
    def test_internal_type_error_not_replayed(self):
        calls=[]
        def broken(runner,*,engine=None,config=None,immutable_rows=False):
            calls.append(1);raise TypeError('inside publisher')
        with self.assertRaisesRegex(TypeError,'inside publisher'):
            module._publish_price_confirmed(broken,None,engine={},config={})
        self.assertEqual(calls,[1])
    def test_variadic_publisher(self):
        publisher=Mock(return_value='ok')
        self.assertEqual(module._publish_price_confirmed(publisher,None,engine={},config={}),'ok')
        publisher.assert_called_once_with(None,engine={},config={},immutable_rows=True)
if __name__=='__main__':unittest.main()
