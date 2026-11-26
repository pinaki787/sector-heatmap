import unittest,tempfile,time,copy
from pathlib import Path
from unittest.mock import patch,Mock
import native_sizing as n
import automatic_sizing as a
import ui_bridge as ui
from test_ui_bridge import PAYLOAD
class ManualParentTests(unittest.TestCase):
 def config(self,**kw):
  payload=dict(PAYLOAD,ai_sizing_mode='MANUAL_PARENT',ai_manual_parent_value=400);payload.update(kw)
  with patch.object(ui,'owner_broker',return_value='FYERS'),patch('native_reference.resolve_reference',side_effect=AssertionError('automatic cache forbidden')):
   return ui.configuration(payload,'owner')
 def test_parent_conversion_otm_atm_and_explicit_unverified_provenance(self):
  from core import Strategy
  for m,f in [('OTM',.25),('ATM',.5)]:
   c=self.config(ai_option_moneyness=m)
   self.assertEqual(Strategy(c).spot_size,400/12)
   self.assertEqual(c['reference_value'],400);self.assertEqual(c['reference_native_provider'],'USER')
   self.assertFalse(c['reference_context']['verified_native_size'])
   from sizing_policy import scale_reference
   self.assertEqual(scale_reference(400,'NSE',is_option=True,option_moneyness=m)['premium_brick'],400/12*f)
 def test_preview_and_paper_live_launch_never_use_provider(self):
  for mode in ('PAPER','LIVE'):
   c=self.config(mode=mode)
   with tempfile.TemporaryDirectory() as folder,patch.object(n,'authorize',side_effect=AssertionError('TV access forbidden')),patch.object(n,'acquire',side_effect=AssertionError('provider forbidden')):
    result=a.runtime_configuration(c,folder)
    self.assertEqual(result['reference_source'],'manual_parent_override')
    self.assertTrue((Path(folder)/'config.json').exists())
 def test_invalid_values_rejected(self):
  for v in (None,True,0,-1,float('nan'),float('inf'),'400'):
   with self.assertRaises(ValueError):self.config(ai_manual_parent_value=v)
 def test_symbol_account_category_or_session_cannot_reuse_manual_value(self):
  c=self.config()
  for field,value in [('underlying','BSE:SENSEX-INDEX'),('account','other'),('broker','DELTA_INDIA'),('market','MCX'),('asset','GOLD')]:
   with self.assertRaisesRegex(ValueError,'another account or instrument'):n.ensure(dict(c,**{field:value}))
  with self.assertRaisesRegex(ValueError,'expired'):n.ensure(dict(c,manual_parent_valid_until=time.time()-1))
 def test_manual_strategy_refresh_never_relabels_user_value_as_tradingview(self):
  c=self.config()
  engine=Mock();engine.config=c;engine.position=None
  engine.spot_size=400/12
  with patch.object(a.ReferenceMonitor,'_run'),patch.object(n,'authorize',side_effect=AssertionError('TV access forbidden')):
   wrapped=a.automatic_strategy(engine,c,exposure=lambda:False,chart_source=None,config_path=None)
   try:
    self.assertTrue(wrapped._refresh())
    self.assertEqual(engine.config['reference_native_provider'],'USER')
    self.assertEqual(engine.config['reference_state'],'MANUAL')
   finally:wrapped.close_native_sizing()

 def test_prepare_does_not_enqueue_automatic_acquisition(self):
  payload=dict(PAYLOAD,ai_sizing_mode='MANUAL_PARENT',ai_manual_parent_value=400)
  service=ui.Service.__new__(ui.Service);service.owner='owner'
  with patch.object(ui,'owner_broker',return_value='FYERS'),patch.object(n,'request',side_effect=AssertionError('provider request forbidden')):
   prepared=service.prepare(payload)
   self.assertEqual(prepared['config']['reference_state'],'MANUAL')
   self.assertIsNone(prepared['native_job'])
 def test_disabled_override_preserves_automatic_path(self):
  with patch.object(ui,'owner_broker',return_value='FYERS'),patch('native_reference.resolve_reference',return_value=None):
   c=ui.configuration(dict(PAYLOAD,ai_sizing_mode='AUTO',ai_manual_parent_value=400),'owner')
   self.assertEqual(c['reference_state'],'UNAVAILABLE')
   self.assertIsNone(c['reference_value'])

class RestoredManualSessionTests(unittest.TestCase):
 def test_restored_manual_value_keeps_original_session_and_never_renews_on_preview(self):
  payload=dict(PAYLOAD,ai_sizing_mode='MANUAL_PARENT',ai_manual_parent_value=300,ai_manual_parent_entered_at=time.time()-86400*5)
  with patch.object(ui,'owner_broker',return_value='FYERS'):
   with self.assertRaisesRegex(ValueError,'earlier session'):ui.configuration(payload,'owner')
 def test_same_session_restored_manual_value_preserves_entry_time(self):
  entered=time.time()-10
  with patch.object(ui,'owner_broker',return_value='FYERS'):
   c=ui.configuration(dict(PAYLOAD,ai_sizing_mode='MANUAL_PARENT',ai_manual_parent_value=300,ai_manual_parent_entered_at=entered),'owner')
   self.assertEqual(c['manual_parent_entered_at'],entered)
