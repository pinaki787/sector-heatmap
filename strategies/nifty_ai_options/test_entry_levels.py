import unittest
from .test_current_trend_midline import CurrentTrendTests
from .trend_filter import entry_allowed
from .indicator import AIRenko
class EntryLevelsTests(unittest.TestCase):
 def engine(self,**config):
  e=CurrentTrendTests().engine(enabled=False);e.config.update(config);return e
 def test_blank_keeps_original_policy(self):
  e=self.engine();self.assertTrue(entry_allowed(e,'LONG',{}))
 def test_strict_long_call_and_short_put(self):
  e=self.engine(bull_entry_level=100,bear_entry_level=90)
  for side in ('LONG','CE'):
   self.assertFalse(entry_allowed(e,side,dict(bar_close=100)))
   self.assertTrue(entry_allowed(e,side,dict(bar_close=100.00000001)))
  for side in ('SHORT','PE'):
   self.assertFalse(entry_allowed(e,side,dict(bar_close=90)))
   self.assertTrue(entry_allowed(e,side,dict(bar_close=89.99999999)))
 def test_midline_and_price_must_both_qualify(self):
  e=self.engine(bull_entry_level=100,midline_filter_enabled=True)
  self.assertFalse(entry_allowed(e,'LONG',dict(bar_close=101,midline=102,midline_period=123)))
  self.assertTrue(entry_allowed(e,'LONG',dict(bar_close=103,midline=102,midline_period=123)))
 def test_latest_trend_waits_for_later_completed_brick(self):
  helper=CurrentTrendTests();e=self.engine(bear_entry_level=100);e.under_result=helper.result(1,101,102)
  self.assertEqual(helper.tick(e,1,101,102),[])
  self.assertEqual(helper.tick(e,1,99,102,101)[0]['action'],'OPEN_SHORT')
 def test_other_side_level_does_not_enable_continuation(self):
  helper=CurrentTrendTests();e=self.engine(bull_entry_level=100);e.under_result=helper.result(1,99,102)
  self.assertEqual(helper.tick(e,1,99,102),[])
 def test_close_tracking_with_and_without_midline(self):
  for period in (None,123):
   r=AIRenko(track_close=True,midline_period=period).update(dict(open=100,high=101,low=99,close=100))
   self.assertEqual(r['bar_close'],100)
 def test_missing_close_blocks_configured_filter(self):
  self.assertFalse(entry_allowed(self.engine(bull_entry_level=100),'LONG',{}))
if __name__=='__main__':unittest.main()
