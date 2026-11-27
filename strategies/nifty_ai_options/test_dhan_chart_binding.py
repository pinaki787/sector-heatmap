import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from strategies.nifty_ai_options.dhan_chart_binding import identity,display_payload
class DhanChartBindingTests(unittest.TestCase):
 def test_exact_master_identity_no_hardcoded_id(self):
  native=SimpleNamespace(underlying=Mock(return_value=dict(SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='I',SEM_SMST_SECURITY_ID='321')))
  self.assertEqual(identity(native,'NSE:NIFTY'),'IDX_I:321');native.underlying.assert_called_once_with('NSE:NIFTY')
 def test_invalid_master_and_wrong_source_rejected(self):
  native=SimpleNamespace(underlying=lambda s:dict(SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='I',SEM_SMST_SECURITY_ID='unknown'))
  with self.assertRaises(ValueError):identity(native,'NSE:NIFTY')
  with self.assertRaises(ValueError):display_payload(dict(symbol='OTHER'),'NSE:NIFTY','IDX_I:13')
 def test_display_mapping_preserves_execution_evidence_and_values(self):
  p=dict(symbol='NSE:NIFTY',rows=[[1,2,3,1,2,0]],signal_points=[dict(symbol='NSE:NIFTY',st=10)],moving_bands=[dict(underlying='NSE:NIFTY')])
  result=display_payload(p,'NSE:NIFTY','IDX_I:13')
  self.assertEqual(result['execution_symbol'],'NSE:NIFTY');self.assertEqual(result['symbol'],'IDX_I:13');self.assertEqual(result['signal_points'][0]['symbol'],'IDX_I:13')
  self.assertEqual(result['rows'],p['rows']);self.assertEqual(p['symbol'],'NSE:NIFTY')
