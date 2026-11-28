import unittest
from unittest.mock import patch
from .direct import DirectStrategy
from .core import Strategy
from .trend_filter import current_trend_confirmation
class CurrentTrendTests(unittest.TestCase):
 def engine(self,option=False,enabled=True):
  c=dict(underlying='NSE:TEST-EQ',market='NSE',timeframe=5,reference_value=12,product='MARGIN',midline_filter_enabled=enabled,midline_period=123,calculation_mode='HYBRID',supertrend_basis='COMPLETED_RENKO',entry_gate='underlying_flip',exit_supertrend='underlying',signal_source='UNDERLYING')
  e=Strategy(c) if option else DirectStrategy(c)
  if option:e.reset_contract(dict(symbol='PUT',option_type='PE'),.2)
  return e
 def result(self,direction,close,line):return dict(direction=direction,flip=False,bar_close=close,midline=line,midline_period=123,st=102 if direction==1 else 98)
 def tick(self,e,direction,close,line,at=100,opening=None):
  opening=close+1 if opening is None else opening
  result=self.result(direction,close,line)
  bar=dict(open=opening,high=max(opening,close),low=min(opening,close),close=close,_signal_result=result)
  with patch('strategies.nifty_ai_options.hybrid_basis.price',return_value=([bar],result)):
   return e.update_hybrid(dict(kind='price',series='underlying',symbol='NSE:TEST-EQ',timestamp=at,available_at=at,close=close))
 def test_sell_above_midline_waits_then_later_close_below_enters_without_new_flip(self):
  e=self.engine();e.under_result=self.result(1,101,100)
  self.assertEqual(self.tick(e,1,101,100),[])
  actions=self.tick(e,1,99,100,101)
  self.assertEqual(actions[0]['action'],'OPEN_SHORT')
  self.assertEqual(actions[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_CURRENT_TREND_MIDLINE')
  self.assertEqual(self.tick(e,1,98,100,102),[])
 def test_buy_below_midline_then_later_above_enters_without_new_flip(self):
  e=self.engine();e.under_result=self.result(-1,99,100)
  self.assertEqual(self.tick(e,-1,99,100,opening=98),[])
  actions=self.tick(e,-1,101,100,101,opening=100)
  self.assertEqual(actions[0]['action'],'OPEN_LONG')
 def test_current_direction_governs_even_when_confirming_brick_color_is_opposite(self):
  e=self.engine();e.under_result=self.result(1,98,100)
  self.assertEqual(self.tick(e,1,99,100,opening=98)[0]['action'],'OPEN_SHORT')
 def test_equal_missing_disabled_partial_and_paused_do_not_enter(self):
  for variant in ['equal','missing','disabled','partial','paused']:
   e=self.engine(enabled=variant!='disabled');e.under_result=self.result(1,101,100)
   if variant=='paused':e.entry_paused=True
   line=None if variant=='missing' else 100
   close=100 if variant=='equal' else 99
   self.assertEqual(self.tick(e,1,close,line,opening=close+.5 if variant=='partial' else close+1),[],variant)
 def test_options_put_and_call_use_same_underlying_current_trend_rule(self):
  for side,direction,close,opening in [('PE',1,99,100),('CE',-1,101,100)]:
   e=self.engine(option=True);e.reset_contract(dict(symbol=side,option_type=side),.2);e.under_result=self.result(direction,101 if side=='PE' else 99,100)
   actions=self.tick(e,direction,close,100,opening=opening)
   self.assertEqual(actions[0]['action'],'BUY');self.assertEqual(actions[0]['position']['side'],side)
 def test_existing_position_exits_are_still_independent_of_midline(self):
  e=self.engine();e.under_result=self.result(-1,101,100);e.position=dict(e.contract,side='LONG',entry_timestamp=1)
  actions=self.tick(e,1,99,98)
  self.assertEqual(actions[0]['action'],'CLOSE_LONG');self.assertNotIn('OPEN_SHORT',[a['action'] for a in actions])
 def test_stale_or_open_units_never_qualify(self):
  e=self.engine();r=self.result(1,99,100)
  unit=dict(kind='brick',closed=True,open=100,close=99,available_at=100,closed_at=100)
  for changes in [dict(closed=False),dict(provisional=True),dict(historyOnly=True),dict(closed_at=101),dict(kind='candle')]:
   self.assertIsNone(current_trend_confirmation(e,dict(unit,**changes),r))
  e.entry_reset_at=100;self.assertIsNone(current_trend_confirmation(e,unit,r))
