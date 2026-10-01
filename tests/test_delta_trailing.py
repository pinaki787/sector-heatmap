import unittest
from sector_heatmap import delta_trailing as t
from tests import test_delta_india as fixture

class CalculationTests(unittest.TestCase):
 def test_long_short_steps_whole_contract_splits_both_modes(self):
  for side in ('buy','sell'):
   for mode,step in [('PERCENTAGE',10),('POINTS',10)]:
    for n,split in [(1,[0,0,1]),(2,[1,0,1]),(3,[1,1,1]),(4,[1,1,2]),(10,[3,3,4])]:
     with self.subTest(side=side,mode=mode,n=n):
      s=t.initial(100,.5,n,side,t.settings(dict(trailing_enabled=True,trailing_mode=mode,trailing_step=step)));self.assertEqual(s['allocation'],split);self.assertIsNone(s['stop'])
      for level in (1,2,4):
       price=100+level*10 if side=='buy' else 100-level*10
       s,hit=t.advance(s,dict(bid=price,ask=price,received_at=level,exchange_at=level),level);self.assertFalse(hit);self.assertEqual(s['level'],level);self.assertEqual(float(s['stop']),100+(level-1)*10 if side=='buy' else 100-(level-1)*10)
      stop=float(s['stop']);s,hit=t.advance(s,dict(bid=stop,ask=stop,received_at=5,exchange_at=5),5);self.assertTrue(hit)
 def test_bid_for_long_ask_for_short_and_never_loosen(self):
  cfg=t.settings({'trailing_enabled':True});long=t.initial(100,.5,3,'buy',cfg);short=t.initial(100,.5,3,'sell',cfg)
  q=dict(bid=89,ask=111,received_at=1,exchange_at=1)
  self.assertFalse(t.advance(long,q,1)[0]['armed']);self.assertFalse(t.advance(short,q,1)[0]['armed'])
  for side,s,price,retrace in [('buy',long,125,115),('sell',short,75,85)]:
   s,_=t.advance(s,dict(bid=price,ask=price,received_at=2,exchange_at=2),2);stop=s['stop'];s,_=t.advance(s,dict(bid=retrace,ask=retrace,received_at=3,exchange_at=3),3);self.assertEqual(s['stop'],stop)
 def test_stale_reverse_duplicate_and_off(self):
  cfg=t.settings({});self.assertIsNone(t.initial(100,.5,3,'buy',cfg));s=t.initial(100,.5,3,'buy',t.settings({'trailing_enabled':True}))
  with self.assertRaises(ValueError):t.advance(s,dict(bid=120,ask=120,received_at=0,exchange_at=0),20)
  s,_=t.advance(s,dict(bid=120,ask=120,received_at=10,exchange_at=10),10)
  for received,exchange in [(10,10),(11,9)]:self.assertEqual(t.advance(s,dict(bid=150,ask=150,received_at=received,exchange_at=exchange),11)[0],s)
  for bad in (0,-1,None,True,float('nan')):
   with self.assertRaises(ValueError):t.settings(dict(trailing_enabled=True,trailing_step=bad))

class RunnerTrailingTests(unittest.TestCase):
 setUp=fixture.LiveTests.setUp
 arm=fixture.LiveTests.arm
 cross=fixture.LiveTests.cross
 # Reuse the mocked broker fixture, not any real credentials or financial endpoints.
 def arm_trailing(self,mode='LIVE',n=3,side='buy',step_mode='POINTS',step=10):
  from unittest.mock import patch
  with patch('threading.Thread'):
   self.b.start_runner(dict(mode=mode,symbol='BTCUSD',contracts=n,resolution='5m',direction='BOTH',trailing_enabled=True,trailing_mode=step_mode,trailing_step=step))
  self.cross('BULLISH' if side=='buy' else 'BEARISH');self.b.runner_tick()
  p=self.b.live['runner_position'] if mode=='LIVE' else self.b.paper['position'];return p
 def quote(self,price):self.req.now+=2;self.req.bid=price;self.req.ask=price
 def test_long_short_partial_targets_stop_actual_contracts(self):
  for side in ('buy','sell'):
   with self.subTest(side=side):
    if side=='sell':self.setUp()
    p=self.arm_trailing(side=side);entry=float(p['entry_price']);sign=1 if side=='buy' else -1
    self.quote(entry+10*sign);self.b.runner_tick();p=self.b.live['runner_position'];self.assertEqual(p['contracts'],2);self.assertEqual(p['trailing']['target_filled'],{'1':1});self.assertEqual(float(p['trailing']['stop']),entry)
    self.quote(entry+20*sign);self.b.runner_tick();p=self.b.live['runner_position'];self.assertEqual(p['contracts'],1);self.assertEqual(p['trailing']['target_filled'],{'1':1,'2':1})
    self.quote(entry+10*sign);self.b.runner_tick();self.assertIsNone(self.b.live['runner_position']);self.assertEqual(self.req.position,0);self.assertEqual(self.req.posts,4)
 def test_price_gap_stages_no_duplicate_reduce_orders_and_partial_fill(self):
  p=self.arm_trailing(n=10);self.req.unfilled=1;self.req.state='cancelled';self.quote(141);self.b.runner_tick();p=self.b.live['runner_position'];self.assertEqual(p['contracts'],8);self.assertEqual(p['trailing']['target_filled'],{'1':2})
  self.req.unfilled=0;self.quote(141);self.b.runner_tick();p=self.b.live['runner_position'];self.assertEqual(p['trailing']['target_filled']['1'],3);self.assertEqual(p['contracts'],7)
  self.quote(141);self.b.runner_tick();self.assertEqual(self.b.live['runner_position']['contracts'],4);self.assertEqual(self.b.live['runner_position']['trailing']['target_filled']['2'],3)
  calls=self.req.posts;self.quote(141);self.b.runner_tick();self.assertEqual(self.req.posts,calls)
 def test_pending_target_then_restart_reconciliation_applies_once(self):
  from sector_heatmap.delta_india import DeltaIndia
  p=self.arm_trailing(n=4);self.req.state='open';self.req.unfilled=1;self.quote(111);self.b.runner_tick();self.assertIsNotNone(self.b.runner['pending']);posts=self.req.posts
  self.quote(121);self.b.runner_tick();self.assertEqual(self.req.posts,posts)
  self.b.stop_runner();pending=self.b.live['orders'][self.b.runner['pending']];r=self.req.orders[pending['client_order_id']];r.update(state='cancelled',unfilled_size=0);self.req.position-=1
  b=DeltaIndia(self.b.path,credentials=self.creds,requester=self.req,clock=lambda:self.req.now);self.assertFalse(b.runner['running']);self.assertTrue(b._settle_runner());self.assertEqual(b.live['runner_position']['contracts'],3);self.assertEqual(b.live['runner_position']['trailing']['target_filled'],{'1':1});b._settle_runner();self.assertEqual(b.live['runner_position']['contracts'],3)
 def test_stop_partial_exit_latches_and_retries_only_remaining(self):
  p=self.arm_trailing(n=3);self.quote(131);self.b.runner_tick();self.quote(131);self.b.runner_tick();self.assertEqual(self.b.live['runner_position']['contracts'],1)
  self.req.unfilled=1;self.req.state='cancelled';self.quote(121);self.b.runner_tick();self.assertTrue(self.b.live['runner_position']['trailing']['exit_latched']);self.assertEqual(self.b.live['runner_position']['contracts'],1)
  self.req.unfilled=0;self.quote(140);self.b.runner_tick();self.assertIsNone(self.b.live['runner_position']);self.assertEqual(self.req.position,0)
 def test_paper_native_quantity_pnl_and_short_points(self):
  for side in ('buy','sell'):
   with self.subTest(side=side):
    if side=='sell':self.setUp()
    p=self.arm_trailing(mode='PAPER',n=3,side=side);entry=p['entry_price'];sign=1 if side=='buy' else -1
    self.quote(entry+10*sign);self.b.runner_tick();self.assertEqual(self.b.paper['position']['contracts'],2)
    self.quote(entry+20*sign);self.b.runner_tick();self.assertEqual(self.b.paper['position']['contracts'],1)
    self.quote(entry+10*sign);self.b.runner_tick();self.assertIsNone(self.b.paper['position']);trade=self.b.paper['trades'][0];self.assertEqual(trade['contracts'],3);self.assertAlmostEqual(trade['realized_pnl'],.04);self.assertEqual(len(trade['exit_fills']),3);self.assertEqual(self.req.posts,0)
 def test_opposite_cross_closes_all_residual_and_off_no_quote_poll(self):
  p=self.arm_trailing();self.quote(111);self.b.runner_tick();self.assertEqual(self.b.live['runner_position']['contracts'],2)
  self.cross('BEARISH');self.req.bid=105;self.req.ask=106;self.b.runner_tick();self.assertIsNone(self.b.live['runner_position']);self.assertEqual(self.req.position,0)
  self.b.stop_runner();self.arm('LIVE');self.cross('BULLISH');self.b.runner_tick()
  def forbidden(symbol):raise AssertionError('Trailing OFF must not poll executable quotes while holding.')
  self.b.ticker=forbidden;self.b.runner_tick()
 def test_broker_quantity_mismatch_blocks_target(self):
  self.arm_trailing();self.req.position=4;self.quote(111)
  with self.assertRaisesRegex(ValueError,'differs'):self.b.runner_tick()
  self.assertEqual(self.req.posts,1)
 def test_actual_native_splits_one_two_three_four_ten_both_modes(self):
  for side in ('buy','sell'):
   for mode in ('PERCENTAGE','POINTS'):
    for n,split in [(1,[0,0,1]),(2,[1,0,1]),(3,[1,1,1]),(4,[1,1,2]),(10,[3,3,4])]:
     with self.subTest(side=side,mode=mode,n=n):
      self.setUp();p=self.arm_trailing(n=n,side=side,step_mode=mode);entry=float(p['entry_price']);increment=float(p['trailing']['increment']);sign=1 if side=='buy' else -1
      self.quote(entry+increment*sign);self.b.runner_tick();self.assertEqual(self.b.live['runner_position']['contracts'],n-split[0])
      self.quote(entry+increment*2*sign);self.b.runner_tick();self.assertEqual(self.b.live['runner_position']['contracts'],split[2]);self.assertEqual(self.b.live['runner_position']['trailing']['allocation'],split)
 def test_opposite_cross_has_priority_over_partial_target(self):
  self.arm_trailing(n=10);self.cross('BEARISH');self.req.bid=141;self.req.ask=141;self.b.runner_tick();self.assertIsNone(self.b.live['runner_position']);self.assertEqual(self.req.posts,2);last=list(self.b.live['orders'].values())[-1];self.assertEqual(last['request']['size'],10);self.assertEqual(last['execution_reason'],'EXIT')
 def test_rejected_target_stops_instead_of_repeated_retry(self):
  self.arm_trailing();self.req.reject=True;self.quote(111)
  with self.assertRaisesRegex(ValueError,'insufficient_margin'):self.b.runner_tick()
  self.assertEqual(self.req.posts,2);self.assertIsNone(self.b.runner['pending']);self.assertEqual(self.b.live['runner_position']['contracts'],3)
