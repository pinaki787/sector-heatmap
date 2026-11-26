import unittest
from unittest.mock import patch
from test_sma_only import config,candle,warm,retest,follow
from direct import DirectStrategy
from core import Strategy
from test_ui_bridge import PAYLOAD
import ui_bridge
class OptionalRetestTests(unittest.TestCase):
 def test_new_configuration_defaults_off_and_rejects_non_boolean(self):
  with patch.object(ui_bridge,'owner_broker',return_value='FYERS'),patch('native_reference.resolve_reference',return_value=None):
   self.assertFalse(ui_bridge.configuration(PAYLOAD,'owner')['sma_retest_required'])
   self.assertTrue(ui_bridge.configuration(dict(PAYLOAD,ai_sma_retest_required=True),'owner')['sma_retest_required'])
   with self.assertRaises(ValueError):ui_bridge.configuration(dict(PAYLOAD,ai_sma_retest_required='false'),'owner')
 def test_off_allows_completed_band_side_entry_without_supertrend_or_retest(self):
  e=DirectStrategy(config(sma_retest_required=False))
  with patch.object(e.under_ai,'update',side_effect=AssertionError('Supertrend called')):
   warm(e)
   a=e.update_hybrid(candle(220,30))
   self.assertEqual(a[0]['action'],'OPEN_LONG')
   self.assertEqual(a[0]['confirmation']['confirmation_basis'],'SMA_BAND_COMPLETED_CANDLE')
   self.assertEqual(e.update_hybrid(candle(280,2))[0]['action'],'CLOSE_LONG')
 def test_on_keeps_retest_and_immediate_followup_mandatory(self):
  e=DirectStrategy(config(sma_retest_required=True));warm(e)
  self.assertEqual(e.update_hybrid(candle(220,30)),[])
  e=DirectStrategy(config(sma_retest_required=True));warm(e);retest(e)
  self.assertEqual(follow(e)[0]['action'],'OPEN_LONG')
 def test_forming_candle_cannot_enter_even_with_retest_off(self):
  e=DirectStrategy(config(sma_retest_required=False));warm(e)
  x=candle(220,30);x['closed']=False
  self.assertEqual(e.update_hybrid(x),[])
 def test_option_signal_selection_without_retest_off(self):
  e=Strategy(config(sma_retest_required=False));e.reset_contract(dict(symbol='PUT',option_type='PE'),.2)
  warm(e);self.assertEqual(e.update_hybrid(candle(220,30))[0]['side'],'CE')
  e.reset_contract(dict(symbol='CALL',option_type='CE'),.2)
  self.assertEqual(e.selected_gate_entry()['action'],'BUY')
 def test_legacy_captured_config_without_flag_retains_mandatory_retest(self):
  e=DirectStrategy(config());warm(e)
  self.assertEqual(e.update_hybrid(candle(220,30)),[])
