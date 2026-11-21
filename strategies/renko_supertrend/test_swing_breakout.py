import unittest
from .swing_breakout import observe,check,settings
from .signals import Engine

class SwingBreakoutTests(unittest.TestCase):
 def feed(self,prices,n=2):
  state={};out=[]
  for i,p in enumerate(prices):out.append(observe(state,dict(close=p,timestamp=i),{'swing_breakout_bricks':n}))
  return state,out
 def test_causal_pivot_and_one_two_confirmation(self):
  prices=[10,11,12,11,10,11,12,13,14]
  for n in (1,2):
   _,rows=self.feed(prices,n)
   self.assertIsNone(rows[3]['high'])
   self.assertEqual(rows[4]['high'],dict(price=12,origin_at=2,confirmed_at=4))
   self.assertEqual(rows[6]['sides']['BULLISH']['count'],0)
   self.assertEqual(rows[7]['sides']['BULLISH']['allowed'],n==1)
   self.assertTrue(rows[8]['sides']['BULLISH']['allowed'])
 def test_equality_inside_reset_and_mirrored_sell(self):
  prices=[10,11,12,11,10,13,12,13,14]
  _,rows=self.feed(prices)
  self.assertEqual(rows[5]['sides']['BULLISH']['count'],1)
  self.assertEqual(rows[6]['sides']['BULLISH']['count'],0)
  self.assertFalse(rows[7]['sides']['BULLISH']['allowed'])
  self.assertTrue(rows[8]['sides']['BULLISH']['allowed'])
  _,mirror=self.feed([-p for p in prices])
  self.assertEqual([r['sides']['BULLISH']['allowed'] for r in rows],[r['sides']['BEARISH']['allowed'] for r in mirror])
 def test_forming_never_advances_or_qualifies(self):
  state,rows=self.feed([10,11,12,11,10,13])
  before=repr(state)
  observe(state,dict(close=14,timestamp=6,provisional=True),{})
  self.assertEqual(repr(state),before)
  self.assertFalse(check({'strategy_basis':'RENKO','swing_breakout_bricks':2},{'has_completed_brick':True},'BULLISH')['allowed'])
  signal={'has_completed_brick':True,'swing_breakout':rows[-1],'provisional':True}
  self.assertFalse(check({'strategy_basis':'RENKO','swing_breakout_bricks':1},signal,'BULLISH')['allowed'])
 def test_captured_legacy_configuration_is_preserved(self):
  self.assertTrue(check({'strategy_basis':'RENKO'},{},'BULLISH')['allowed'])
 def test_validation(self):
  for n in (0,101,1.5,True,'bad'):
   with self.assertRaises(ValueError):settings({'swing_breakout_bricks':n})
  self.assertEqual(settings({})['swing_breakout_bricks'],2)
 def test_inner_engine_persists_exact_evidence(self):
  config={'swing_breakout_bricks':2,'_brick_input':True,'strategy_basis':'CANDLESTICK','brick_mode':'Manual','manual_brick':1}
  engine=Engine(config,1)
  prices=[10,11,12,11,10,13,14]
  for i,p in enumerate(prices):
   row=engine.update(dict(timestamp=i+100,open=p-1,high=p,low=p-1,close=p))
  self.assertTrue(row['swing_breakout']['sides']['BULLISH']['allowed'])
  restored=Engine(config,1,engine.state)
  self.assertEqual(restored.state['swing_breakout'],engine.state['swing_breakout'])

class SubmissionSwingTests(unittest.TestCase):
 def test_current_publication_blocks_even_if_cached_signal_passed(self):
  from types import SimpleNamespace
  from .runner import Runner
  good={'has_completed_brick':True,'swing_breakout':{'sides':{'BULLISH':{'allowed':True,'required':2}}}}
  runner=SimpleNamespace(state={'run_id':'r','config':{'strategy_basis':'RENKO','swing_breakout_bricks':2,'renko_confirmation':'PRICE'},'last_signal':good},_price_export=('r',{'last':{'has_completed_brick':True}}))
  with self.assertRaisesRegex(ValueError,'WAITING_CONFIRMED_RENKO_SWING'):Runner.swing_entry_gate(runner,'BULLISH')
  runner._price_export=('r',{'last':good})
  self.assertTrue(Runner.swing_entry_gate(runner,'BULLISH')['allowed'])
 def test_count_freezes_reference_until_reset(self):
  state={'swing_breakout':{'rows':[],'high':{'price':12,'origin_at':1,'confirmed_at':3},'low':None,'attempts':{'BULLISH':{'reference':{'price':12,'origin_at':1,'confirmed_at':3},'count':1}}}}
  state['swing_breakout']['high']={'price':15,'origin_at':4,'confirmed_at':6}
  row=observe(state,{'close':14,'timestamp':7},{'swing_breakout_bricks':2})
  self.assertEqual(row['sides']['BULLISH']['reference']['price'],12)
  self.assertTrue(row['sides']['BULLISH']['allowed'])
  row=observe(state,{'close':13,'timestamp':8},{'swing_breakout_bricks':2})
  self.assertEqual(row['sides']['BULLISH']['reference']['price'],15)
  self.assertFalse(row['sides']['BULLISH']['allowed'])
