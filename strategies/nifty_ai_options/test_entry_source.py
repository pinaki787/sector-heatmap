import unittest
import test_option_hybrid
from unittest.mock import patch
from ui_bridge import configuration

class EntrySourceTests(unittest.TestCase):
 def engine(self,mode):
  e=test_option_hybrid.OptionHybridTests().engine();e.config['entry_gate']=mode;return e
 def test_underlying_entry_does_not_wait_for_bullish_premium(self):
  e=self.engine('underlying_flip');e.premium_result=dict(direction=1)
  actions=[]
  for i,p in enumerate(range(94,115,2)):
   actions=e.update_hybrid(dict(kind='price',series='underlying',timestamp=2000+i,close=p))
   if any(a['action']=='BUY' for a in actions):break
  self.assertEqual(actions[0]['action'],'BUY')
  self.assertEqual(e.position['entry_gate'],'underlying_flip')
 def test_premium_entry_waits_for_its_own_fresh_flip(self):
  e=self.engine('underlying_trend_premium_flip');e.under_result=dict(direction=-1,st=90)
  # Already bullish premium with no new flip cannot enter.
  self.assertEqual(e.update_hybrid(dict(kind='price',series='premium',symbol='CALL',timestamp=2000,close=46)),[])
  for i,p in enumerate([43,40,37,34,31,28]):
   self.assertFalse(any(a['action']=='BUY' for a in e.update_hybrid(dict(kind='price',series='premium',symbol='CALL',timestamp=2100+i,close=p))))
  actions=[]
  for i,p in enumerate(range(30,80,2)):
   actions=e.update_hybrid(dict(kind='price',series='premium',symbol='CALL',timestamp=2200+i,close=p))
   if actions:break
  self.assertEqual(actions[0]['action'],'BUY')
 def test_underlying_mode_still_needs_enabled_band_and_correct_contract(self):
  e=self.engine('underlying_flip');e.hybrid_active=True;e.under_result=dict(direction=-1,st=90);e.pending_underlying_flip=2000
  e.band.allows=lambda *_:False
  self.assertIsNone(e.selected_gate_entry())
  e.band.allows=lambda *_:True;e.pending_underlying_flip=2001;e.contract['option_type']='PE'
  self.assertIsNone(e.selected_gate_entry())
 def test_underlying_mode_does_not_change_premium_exit(self):
  e=self.engine('underlying_flip');e.manual_entry('CE',2000)
  self.assertEqual(e.update_hybrid(dict(kind='price',series='underlying',timestamp=2001,close=88)),[])
  for i,p in enumerate([44,43,42,41,40,39,38]):
   actions=e.update_hybrid(dict(kind='price',series='premium',symbol='CALL',timestamp=2100+i,close=p))
   if actions:break
  self.assertEqual(actions[0]['action'],'SELL')
  self.assertEqual(actions[0]['reason'],'AI_RENKO_SUPERTREND_PREMIUM')
 def test_bridge_validates_and_captures_selection(self):
  base=dict(account_id='a'*32,broker='FYERS',underlying='NSE:NIFTY50-INDEX',timeframe='1 minute')
  with patch('ui_bridge.owner_broker',return_value='FYERS'),patch('native_reference.resolve_reference',return_value=None):
   for source,gate in [('UNDERLYING','underlying_flip'),('PREMIUM','underlying_trend_premium_flip')]:
    self.assertEqual(configuration(dict(base,ai_entry_source=source),'a'*32)['entry_gate'],gate)
   with self.assertRaises(ValueError):configuration(dict(base,ai_entry_source='invalid'),'a'*32)

if __name__=='__main__':unittest.main()
