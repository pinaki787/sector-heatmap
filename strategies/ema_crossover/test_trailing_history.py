import unittest
from ema_crossover.trailing import settings,initial,advance
from ema_crossover.history import position_history
from ema_crossover.signals import rsi_cross

class Tests(unittest.TestCase):
 def config(self,mode='PERCENTAGE',step=10):return settings(dict(trailing_enabled=True,trailing_mode=mode,trailing_step=step))
 def q(self,bid,t=100):return dict(bid=bid,received_at=t,exchange_at=t)
 def test_cross_boundaries_and_relationships(self):
  self.assertEqual(rsi_cross(50,50,51,50),'BULLISH');self.assertEqual(rsi_cross(50,50,49,50),'BEARISH')
  for args in [(51,50,52,50),(49,50,48,50),(49,50,50,50),(None,50,51,50)]:self.assertIsNone(rsi_cross(*args))
 def test_disabled_and_required_points(self):
  self.assertIsNone(initial(None,None,settings({})))
  with self.assertRaises(ValueError):settings(dict(trailing_enabled=True,trailing_mode='POINTS'))
 def test_first_next_gap_and_monotonic(self):
  s=initial(100,.05,self.config())
  s,hit=advance(s,self.q(109),100);self.assertFalse(s['armed']);self.assertFalse(hit)
  s,hit=advance(s,self.q(110,101),101);self.assertEqual(s['stop'],100);self.assertEqual(s['next_trigger'],120)
  s,hit=advance(s,self.q(135,102),102);self.assertEqual(s['stop'],120);self.assertEqual(s['increment'],10)
  s,hit=advance(s,self.q(125,103),103);self.assertEqual(s['stop'],120);self.assertFalse(hit)
  s,hit=advance(s,self.q(119,104),104);self.assertTrue(hit);self.assertEqual(s['stop'],120)
  again,hit=advance(s,self.q(119,104),104);self.assertEqual(again,s);self.assertFalse(hit)
 def test_points_stale_and_reversed_exchange(self):
  s=initial(408.2,.1,self.config('POINTS',20))
  s,_=advance(s,self.q(448.2),100);self.assertEqual(s['stop'],428.2)
  with self.assertRaises(ValueError):advance(s,self.q(800),116)
  q=self.q(800,101);q['exchange_at']=99
  same,hit=advance(s,q,101);self.assertEqual(same,s);self.assertFalse(hit)
 def row(self,side,qty,price,life='a',mode='LIVE',tag='1'):
  return dict(lifecycle_id=life,mode=mode,strategy='Historical EMA',symbol='MCX:TESTCE',side=side,requested=qty,filled=qty,average_price=price,quantity_multiplier=10,lot_size=1,tag=tag,order_id=tag,updated_at=100,product='MARGIN',requested_type='MARKET',reason='TEST')
 def test_history_partial_weighted_exit_and_modes(self):
  rows=[self.row('BUY',3,100),self.row('SELL',1,110,tag='2'),self.row('SELL',1,120,tag='3'),self.row('BUY',1,90,mode='PAPER',tag='4'),self.row('BUY',1,90,life='b',tag='5')]
  result=position_history(rows);p=next(r for r in result if r['lifecycle_id']=='a' and r['mode']=='LIVE')
  self.assertEqual(p['status'],'PARTIAL EXIT');self.assertEqual(p['realized_pnl'],300);self.assertEqual(p['pnl_percent'],15);self.assertEqual(p['exit_order_ids'],['2','3']);self.assertEqual(p['strategy'],'Historical EMA');self.assertEqual(len(result),3)
 def test_legacy_never_adjacent_pair_and_unfilled(self):
  a=self.row('BUY',1,100,life=None);b=self.row('SELL',1,120,life=None,tag='2')
  for r in position_history([a,b]):self.assertIsNone(r['realized_pnl']);self.assertEqual(r['status'],'PAIRING UNAVAILABLE')
  r=self.row('BUY',0,None);self.assertEqual(position_history([r])[0]['status'],'UNFILLED')

import test_runner as fixtures
class Integration(unittest.TestCase):
 start=fixtures.RunnerTests.start
 def setUp(self):
  fixtures.RunnerTests.setUp(self);self.c['mode']='PAPER';self.c.update(trailing_enabled=True,trailing_mode='PERCENTAGE',trailing_step=10)
  self.b.resolve=lambda c,d:dict(symbol='NSE:TESTCE',lot_size=10,quantity_multiplier=1,tick_size=.05)
  self.b.quote=lambda s:dict(bid=self.b.price,ask=self.b.price,received_at=self.b.now,exchange_at=self.b.now)
 def test_trailing_exit_one_position_row_no_duplicate(self):
  self.start();self.r.step();self.assertEqual(self.r.state['position']['trailing']['stop'],None)
  self.b.now+=1;self.b.price=11;self.r.step();self.assertEqual(self.r.state['position']['trailing']['stop'],10)
  self.b.now+=1;self.b.price=12;self.r.step();self.assertEqual(self.r.state['position']['trailing']['stop'],11)
  self.b.now+=1;self.b.price=10.5;self.r.step();self.assertIsNone(self.r.state['position'])
  self.r.step();self.assertEqual(len(self.r.state['order_history']),2)
  h=self.r.snapshot()['position_history'];self.assertEqual(len(h),1);self.assertEqual(h[0]['realized_pnl'],5);self.assertEqual(h[0]['status'],'CLOSED')
 def test_opposite_cross_exits_with_unarmed_trailing(self):
  self.start();self.r.step();self.b.now+=300;self.b.last_close=80;self.r.step()
  self.assertIsNone(self.r.state['position']);self.assertEqual(self.r.state['order_history'][-1]['reason'],'RSI_CLOSE_EXIT')
 def test_continued_relation_consumed_once_and_reconnect(self):
  self.c['trailing_enabled']=False;self.start()
  original=self.r.signal
  self.r.signal=lambda:{**original(),'cross_direction':None}
  self.r.step();self.assertIsNone(self.r.state['position'])
  self.r.signal=original;self.r.step();self.assertIsNone(self.r.state['position'])
  self.b.now+=300;self.r.step();self.assertIsNotNone(self.r.state['position'])
 def test_reconnect_does_not_replay_completed_opposite_cross(self):
  self.c['trailing_enabled']=False;stream=dict(connected=True,generation=1);self.b.stream_status=lambda:dict(stream)
  self.start();self.r.step();stream['connected']=False;self.b.now+=300;self.b.last_close=80;self.r.step()
  stream.update(connected=True,generation=2);self.r.step();self.assertIsNotNone(self.r.state['position'])
  self.b.now+=300;self.r.step();self.assertIsNone(self.r.state['position'])
 def test_partial_confirmed_owned_quantity_and_durable_trailing_exit(self):
  self.c['mode']='LIVE';self.start();self.r.step();fixtures.RunnerTests.fill(self,4,1);self.r.step()
  self.assertEqual(self.r.state['position']['quantity'],4);self.assertEqual(self.r.state['position']['trailing']['entry'],10)
  self.b.now+=1;self.b.price=11;self.r.step();self.b.now+=1;self.b.price=9;self.r.step()
  self.assertEqual(self.r.state['pending']['order']['qty'],4);self.assertEqual(len(self.b.sent),2)
  fixtures.RunnerTests.fill(self,2,1);self.r.step();self.assertEqual(self.r.state['position']['quantity'],2)
  self.r.step();self.assertEqual(self.r.state['pending']['order']['qty'],2)
  with self.assertRaisesRegex(ValueError,'not uniquely reconciled'):self.r.step()
  self.assertEqual(len(self.b.sent),3)
 def test_lot_aware_targets_both_modes_gaps_and_remaining_trail(self):
  from ema_crossover.trailing import allocation
  for mode,step in [('PERCENTAGE',10),('POINTS',1)]:
   for lots in (1,2,3,4,10):
    with self.subTest(mode=mode,lots=lots):
     self.c.update(mode='PAPER',lots=lots,trailing_mode=mode,trailing_step=step);self.b.price=10;self.b.now+=300
     self.start();self.r.step();self.assertEqual(self.r.state['position']['trailing']['allocation'],allocation(lots))
     self.b.now+=1;self.b.price=13;self.r.step()
     split=allocation(lots);self.assertEqual(self.r.state['position']['quantity'],(lots-split[0])*10)
     self.b.now+=1;self.r.step();self.assertEqual(self.r.state['position']['quantity'],split[2]*10)
     count=len(self.r.state['order_history']);self.b.now+=1;self.r.step();self.assertEqual(len(self.r.state['order_history']),count)
     self.b.now+=1;self.b.price=11.5;self.r.step();self.assertIsNone(self.r.state['position'])
     trade=self.r.snapshot()['position_history'][0];self.assertEqual(trade['entry_filled'],lots*10);self.assertEqual(trade['exit_filled'],lots*10);self.assertEqual(trade['status'],'CLOSED')
     self.r.stop()
 def test_partial_target_restart_preserves_stage_fill_and_no_auto_start(self):
  from ema_crossover.runner import Runner
  self.c['lots']=3;self.start();self.r.step();self.b.now+=1;self.b.price=11;self.r.step()
  saved=self.r.state['position'];self.assertEqual(saved['quantity'],20);self.assertEqual(saved['trailing']['target_filled'],{'1':10})
  reloaded=Runner(self.b,self.r.path,lambda:self.b.now);self.assertFalse(reloaded.state['running']);self.assertEqual(reloaded.state['position']['trailing']['target_filled'],{'1':10})
  self.r.step();self.assertEqual(self.r.state['position']['quantity'],20)
