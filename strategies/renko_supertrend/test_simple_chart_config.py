import unittest
from types import SimpleNamespace
from .delta_service import Service
class SimpleChartConfig(unittest.TestCase):
 def test_simple_chart_merges_overlapping_exit_fields_and_masks_indicator_gates(self):
  owner=SimpleNamespace(instrument='BTCUSD',chart_broker=SimpleNamespace(session_policy=lambda c:None))
  q={k:[v] for k,v in dict(symbol='BTCUSD',timeframe='1 minute',strategy_basis='RENKO',strategy_mode='SIMPLE_BRICK',brick_mode='Manual',manual_brick='51.19',ema_exit_enabled='true',supertrend_enabled='true',supertrend_exit_enabled='true',swing_breakout_enabled='false').items()}
  c=Service.chart_config(owner,q)
  self.assertEqual(c['strategy_mode'],'SIMPLE_BRICK')
  for key in ('ema_exit_enabled','supertrend_enabled','supertrend_exit_enabled','supertrend_slope_enabled','swing_breakout_enabled'):self.assertFalse(c[key],key)
  self.assertTrue(c['renko_brick_exit_enabled'])
 def test_optional_supertrend_chart_retains_selected_exit(self):
  owner=SimpleNamespace(instrument='BTCUSD',chart_broker=SimpleNamespace(session_policy=lambda c:None))
  c=Service.chart_config(owner,{'symbol':['BTCUSD'],'strategy_mode':['SUPERTREND'],'strategy_basis':['RENKO'],'ema_exit_enabled':['true']})
  self.assertTrue(c['ema_exit_enabled'])
  self.assertTrue(c['supertrend_enabled'])
if __name__=='__main__':unittest.main()
