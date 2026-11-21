import unittest
from copy import deepcopy
from types import SimpleNamespace
from .brick_entry import allowed
from .test_trend_reentry import ContinuationSubmissionTests

class BrickEntryTests(unittest.TestCase):
 def test_direction_uses_actual_completed_body_even_with_supertrend_disabled(self):
  c=dict(strategy_basis='RENKO',supertrend_enabled=False)
  for side,opening,closing in [('BULLISH',100,110),('BEARISH',110,100)]:
   s=dict(has_completed_brick=True,open=opening,close=closing,brick_direction=side)
   self.assertTrue(allowed(c,s,side))
   self.assertFalse(allowed(c,s,'BEARISH' if side=='BULLISH' else 'BULLISH'))
   self.assertFalse(allowed(c,{**s,'open':closing,'close':opening},side))
   self.assertFalse(allowed(c,{**s,'provisional':True},side))
   self.assertFalse(allowed(c,{**s,'has_completed_brick':False},side))
 def test_every_broker_inherits_actual_execution_authorization_and_eligibility(self):
  from .runner import Runner
  from .delta_runner import DeltaRunner
  from sector_heatmap.dhan_strategy_service import DhanRenkoRunner
  from sector_heatmap.motilal_strategy_service import MotilalRunner
  for cls in (DeltaRunner,DhanRenkoRunner,MotilalRunner):
   self.assertIs(cls.fresh_cross,Runner.fresh_cross)
   self.assertIs(cls.validate_entry_authorization,Runner.validate_entry_authorization)

class SubmissionColorTests(ContinuationSubmissionTests):
 def test_opposite_brick_blocks_initial_and_reentry_for_every_broker(self):
  self.scenario();base=deepcopy(self.r.state)
  self.b.delta=SimpleNamespace(_inr_conversion=lambda:dict(rate=85))
  for broker in ('FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'):
   for reentry in (False,True):
    for side in ('BULLISH','BEARISH'):
     with self.subTest(broker=broker,reentry=reentry,side=side):
      self.r.state=deepcopy(base);self.r.signal=lambda:self.r.state['last_signal']
      self.r.state['config']['broker']=broker
      sig=self.r.state['last_signal'];opening=sig['close']+(10 if side=='BULLISH' else -10)
      sig.update(open=opening,high=max(opening,sig['close']),low=min(opening,sig['close']),
                 direction=side,brick_direction='BEARISH' if side=='BULLISH' else 'BULLISH',
                 trend_reentry=reentry,entry_qualified=True,entry_direction=side,cross_direction=side)
      self.r._candle_step()
      self.assertFalse(self.r.state.get('position'));self.assertFalse(self.r.state.get('order_history'))
      self.assertEqual(self.r.state['entry_assessments'][-1]['code'],'OPPOSITE_BRICK_ENTRY')
 def test_matching_brick_permits_paper_initial_and_reentry_for_every_broker(self):
  self.scenario();base=deepcopy(self.r.state)
  self.b.delta=SimpleNamespace(_inr_conversion=lambda:dict(rate=85))
  for broker in ('FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'):
   for reentry in (False,True):
    for side in ('BULLISH','BEARISH'):
     with self.subTest(broker=broker,reentry=reentry,side=side):
      self.r.state=deepcopy(base);self.r.signal=lambda:self.r.state['last_signal']
      self.r.state['config']['broker']=broker
      sig=self.r.state['last_signal'];opening=sig['close']+(-10 if side=='BULLISH' else 10)
      sig.update(open=opening,high=max(opening,sig['close']),low=min(opening,sig['close']),
                 direction=side,brick_direction=side,trend_reentry_direction=side,
                 trend_reentry=reentry,entry_qualified=True,entry_direction=side,cross_direction=side)
      self.r.state['renko_engine']['last']=deepcopy(sig)
      self.r._candle_step()
      self.assertIsNotNone(self.r.state.get('position'))
      self.assertEqual(self.r.state['position']['direction'],side)
      self.assertEqual(self.b.sent,[])
 def test_submission_rechecks_own_latest_price_brick(self):
  from .runner import Runner
  self.scenario()
  self.r.state['config']['renko_confirmation']='PRICE'
  self.r.state['run_id']='color-test'
  sig=self.r.state['last_signal']
  self.r._price_export=('color-test',{'last':{**sig,'open':sig['close']+10,'brick_direction':'BEARISH'}})
  for reentry in (False,True):
   sig['trend_reentry']=reentry
   with self.assertRaisesRegex(ValueError,'brick direction changed'):
    self.r.validate_entry_authorization(dict(direction='BULLISH',entry_mode='CONFIRMED'))

class ManualMetadataTests(unittest.TestCase):
 def test_manual_rows_are_identical_across_symbols_with_no_auto_warmup_leak(self):
  from .test_delta_integration import config,FakeBroker
  from .runner import analysis
  rows=FakeBroker().rows
  for basis in ('LEGACY','RENKO'):
   reference=None
   for symbol in ('BTCUSD','NSE:NIFTY50-INDEX','BSE:SENSEX-INDEX','MCX:CRUDEOIL26NOVFUT'):
    output=analysis(rows,{**config(symbol),'strategy_basis':basis},.05)['rows']
    if reference is None:reference=output
    self.assertEqual(reference,output)
    self.assertTrue(all(r['box']==10 for r in output))
