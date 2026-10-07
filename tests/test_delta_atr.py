import unittest,json
from sector_heatmap import delta_trailing as t
class AtrTrailing(unittest.TestCase):
 def state(self,side='buy'):
  return t.initial(100,.5,10,side,t.settings(dict(trailing_enabled=True,trailing_mode='ATR',trailing_step=2))|dict(_trailing_atr=5,_trailing_atr_candle=300))
 def q(self,p,now):return dict(bid=p,ask=p,received_at=now,exchange_at=now)
 def test_wilder_completed_only(self):
  rows=[dict(timestamp=i*300,high=102+i,low=99+i,close=101+i,is_forming=False) for i in range(16)]
  rows[-1]['is_forming']=True
  a,stamp=t.atr_value(rows);self.assertEqual(a,3);self.assertEqual(stamp,4200)
  with self.assertRaises(ValueError):t.atr_value(rows[:14])
 def test_long_short_initial_stop_ratchet_widening_and_missing_atr(self):
  for side,price,stop in [('buy',120,110),('sell',80,90)]:
   s=self.state(side);self.assertEqual(float(s['stop']),90 if side=='buy' else 110);self.assertIsNone(t.target(s,10))
   s,hit=t.advance(s,self.q(price,1),1,5,600);self.assertFalse(hit);self.assertEqual(float(s['stop']),stop)
   s,hit=t.advance(s,self.q(price,2),2,20,900);self.assertEqual(float(s['stop']),stop)
   s=json.loads(json.dumps(s));s,hit=t.advance(s,self.q(stop,3),3,None,None);self.assertTrue(hit)
 def test_tighter_atr_and_stale_revision_duplicate_quote(self):
  s=self.state();s,_=t.advance(s,self.q(120,1),1,5,600)
  s,_=t.advance(s,self.q(120,2),2,3,900);self.assertEqual(float(s['stop']),114)
  s,_=t.advance(s,self.q(120,3),3,1,600);self.assertEqual(float(s['stop']),114)
  same,_=t.advance(s,self.q(140,3),3,1,1200);self.assertEqual(same,s)
  with self.assertRaises(ValueError):t.advance(s,self.q(140,0),30,5,1200)
 def test_invalid_distance_rejected_before_arming(self):
  with self.assertRaises(ValueError):t.initial(5,.5,10,'buy',t.settings(dict(trailing_enabled=True,trailing_mode='ATR',trailing_step=2))|dict(_trailing_atr=5))
from unittest.mock import patch
from tests import test_delta_atm_runner as fixture
class AtrRunner(unittest.TestCase):
 setUp=fixture.AtmOptionRunner.setUp
 config=fixture.AtmOptionRunner.config
 def signal(self,direction):
  now=self.req.now
  rows=[dict(timestamp=now-310-(20-i)*300,open=99,high=100,low=99,close=99.5,volume=1,is_forming=False) for i in range(21)]
  self.b.chart=lambda *a,**k:dict(symbol=a[0] if a else 'BTCUSD',candles=rows,last_completed=dict(timestamp=now-310,rsi_ma=50,cross_direction=direction,entry_direction=direction))
 def test_atr_option_stop_and_no_partial_targets(self):
  self.signal(None)
  with patch('sector_heatmap.delta_india.threading.Thread'):
   self.b.start_runner(self.config()|dict(trailing_enabled=True,trailing_mode='ATR',trailing_step=2))
  self.req.now+=300;self.signal('BULLISH');self.b.runner_tick();p=self.b.paper['position'];self.assertIsNotNone(p);self.assertEqual(float(p['trailing']['stop']),99)
  self.req.now+=2;self.signal(None)
  with patch.object(self.b,'ticker',side_effect=lambda s:dict(symbol=s,bid=107,ask=108,spot_price='100.4',received_at=self.req.now,exchange_at=self.req.now)):
   self.b.runner_tick()
  self.assertEqual(self.b.paper['position']['contracts'],10);self.assertEqual(float(self.b.paper['position']['trailing']['stop']),105)
  self.req.now+=2
  with patch.object(self.b,'ticker',side_effect=lambda s:dict(symbol=s,bid=104,ask=105,spot_price='100.4',received_at=self.req.now,exchange_at=self.req.now)):
   self.b.runner_tick()
  self.assertIsNone(self.b.paper['position']);self.assertEqual(self.b.paper['trades'][-1]['exit_fills'][-1]['reason'],'TRAILING_STOP')
 def test_live_pending_entry_persists_atr_for_restart_reconciliation(self):
  from tests.test_delta_india import LiveRequests
  from sector_heatmap.delta_india import DeltaIndia
  self.signal(None);self.b.credentials=lambda:dict(DELTA_INDIA_API_KEY='fake-key',DELTA_INDIA_API_SECRET='fake-secret',DELTA_INDIA_ENABLE_LIVE_ORDERS='1');self.b.requester=LiveRequests();self.b.requester.state='open';self.b.requester.unfilled=2
  with patch('sector_heatmap.delta_india.threading.Thread'):
   self.b.start_runner(self.config('LIVE')|dict(trailing_enabled=True,trailing_mode='ATR',trailing_step=2))
  self.req.now+=300;self.signal('BULLISH');self.b.runner_tick();self.assertIsNotNone(self.b.runner['pending'])
  b=DeltaIndia(self.b.path,credentials=self.b.credentials,requester=self.b.requester,clock=lambda:self.req.now)
  self.assertEqual(b.runner['config']['_trailing_atr'],1);self.assertTrue(b.runner['config']['_trailing_atr_symbol'].startswith('C-'))
