import unittest
from types import SimpleNamespace
from .swing_targets import SwingBook,capture,target_exit,admission
from .test_current_trend_midline import CurrentTrendTests
class SwingTargetTests(unittest.TestCase):
 def book(self):
  b=SwingBook()
  for i,v in enumerate([100,102,105,103,101,99,97,99,101]):b.observe(dict(close=v),i+1)
  return b
 def engine(self):
  e=CurrentTrendTests().engine(enabled=False);e.config.update(swing_targets_enabled=True,display_mode='RENKO');e.swing_book=self.book();return e
 def test_two_right_bricks_required_and_forming_is_ignored(self):
  b=SwingBook()
  for i,v in enumerate([100,102,105,103]):b.observe(dict(close=v),i)
  self.assertIsNone(b.high);b.observe(dict(close=101,provisional=True),4);self.assertIsNone(b.high)
  b.observe(dict(close=101),4);self.assertEqual(b.high,dict(price=105,origin_at=2,confirmed_at=4))
 def test_target_frozen_per_entry_and_only_favorable_level(self):
  e=self.engine();e.under_result=dict(bar_close=100)
  p=capture(e,dict(side='LONG',entry_timestamp=10));self.assertEqual(p['swing_target']['price'],105)
  e.swing_book.high=dict(price=110);self.assertEqual(p['swing_target']['price'],105)
  e.under_result=dict(bar_close=111);self.assertNotIn('swing_target',capture(e,dict(side='LONG')))
 def test_long_target_then_wait_for_strict_later_breakout(self):
  e=self.engine();e.under_result=dict(bar_close=100);e.position=capture(e,dict(side='LONG',entry_timestamp=10))
  unit=dict(kind='brick',closed=True,open=104,close=105,closed_at=11,available_at=11)
  actions=target_exit(e,[unit],11);self.assertEqual(actions[0]['action'],'CLOSE_LONG')
  e.swing_observed_at=12
  self.assertFalse(admission(e,'LONG',dict(bar_close=105)));self.assertTrue(admission(e,'LONG',dict(bar_close=106)))
  self.assertTrue(admission(e,'SHORT',dict(bar_close=104)))
 def test_short_support_and_put_share_underlying_target(self):
  for side in ('SHORT','PE'):
   e=self.engine();e.under_result=dict(bar_close=100);e.position=capture(e,dict(side=side,entry_timestamp=10))
   self.assertEqual(e.position['swing_target']['price'],97)
   if side=='PE':e.exit=lambda at,reason:[dict(action='SELL',reason=reason)]
   self.assertIsNotNone(target_exit(e,[dict(kind='brick',closed=True,close=97,closed_at=11,available_at=11)],11))
 def test_old_or_forming_units_do_not_exit(self):
  for changes in [dict(provisional=True),dict(closed=False),dict(kind='candle'),dict(available_at=9,closed_at=9)]:
   e=self.engine();e.under_result=dict(bar_close=100);e.position=capture(e,dict(side='LONG',entry_timestamp=10))
   unit=dict(kind='brick',closed=True,close=106,closed_at=11,available_at=11);unit.update(changes)
   self.assertIsNone(target_exit(e,[unit],11))
 def test_existing_position_without_captured_target_is_preserved(self):
  e=self.engine();e.position=dict(side='LONG',entry_timestamp=10)
  self.assertIsNone(target_exit(e,[dict(kind='brick',closed=True,close=110,closed_at=11,available_at=11)],11))
 def test_real_direct_strategy_exits_at_target_and_reenters_on_breakout(self):
  e=self.engine();e.under_result=dict(bar_close=100,direction=-1,st=98)
  e.position=capture(e,dict(e.contract,side='LONG',entry_timestamp=10))
  helper=CurrentTrendTests()
  actions=helper.tick(e,-1,105,99,at=11,opening=104)
  self.assertEqual(actions[0]['reason'],'CONFIRMED_RENKO_SWING_TARGET');self.assertIsNone(e.position)
  e.swing_observed_at=12
  self.assertEqual(helper.tick(e,-1,105,99,at=12,opening=104),[])
  e.swing_observed_at=13
  self.assertEqual(helper.tick(e,-1,106,99,at=13,opening=105)[0]['action'],'OPEN_LONG')
 def test_option_strategy_uses_underlying_support_and_resistance_for_exits(self):
  helper=CurrentTrendTests()
  for side,direction,close,opening in [('CE',-1,105,104),('PE',1,97,98)]:
   e=helper.engine(option=True,enabled=False);e.config.update(swing_targets_enabled=True,display_mode='RENKO')
   e.reset_contract(dict(symbol=side,option_type=side),.2);e.swing_book=self.book()
   e.under_result=dict(direction=direction,bar_close=100,st=98)
   e.position=capture(e,dict(e.contract,side=side,entry_timestamp=10))
   actions=helper.tick(e,direction,close,100,at=11,opening=opening)
   self.assertEqual(actions[0]['action'],'SELL');self.assertEqual(actions[0]['reason'],'CONFIRMED_RENKO_SWING_TARGET')
 def test_disabled_and_candles_preserve_rules(self):
  for update in [dict(swing_targets_enabled=False),dict(display_mode='CANDLES')]:
   e=self.engine();e.config.update(update);e.under_result=dict(bar_close=100)
   self.assertNotIn('swing_target',capture(e,dict(side='LONG')))
if __name__=='__main__':unittest.main()
