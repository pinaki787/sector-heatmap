import unittest
from research import features,replay,valid
from source_snapshot.trailing_stop import advance
class Checks(unittest.TestCase):
 def test_completed_five_minute(self):
  rows=[dict(timestamp=i*60,open=100,high=101,low=99,close=100) for i in range(100)]
  fs=features(rows,300)
  self.assertIsNone(fs[68][0]);self.assertEqual(fs[69][0],2)
 def test_incomplete_five_minute_excluded(self):
  rows=[dict(timestamp=i*60,open=100,high=101,low=99,close=100) for i in range(70) if i!=5]
  self.assertIsNone(features(rows,300)[-1][0])
 def test_prefix_invariance(self):
  rows=[dict(timestamp=i*60,open=100+i%5,high=110+i%3,low=90-i%7,close=100+i%5) for i in range(150)]
  self.assertEqual(features(rows[:87],300),features(rows,300)[:87])
 def test_monotonic_bid_trail(self):
  c=dict(trailing_enabled=True,trailing_basis='OPTION_PREMIUM_PERCENT',trailing_distance=10)
  state,hit=advance(None,c,'BEARISH',100,1,1,1,1)
  state,hit=advance(state,c,'BEARISH',130,2,2,2,1)
  self.assertEqual(state['stop'],117)
  state,hit=advance(state,c,'BEARISH',116,3,3,3,1)
  self.assertTrue(hit);self.assertEqual(state['stop'],117)
 def test_invalid_ohlc(self):self.assertFalse(valid([0,100,90,95,100,1]))
 def test_zero_duration_rejected(self):
  t=dict(i=0,end_i=0)
  self.assertIsNone(replay(t,[],[],[],{},{}))
 def test_next_open_fill(self):
  rows=[dict(timestamp=i*60,open=100,high=110,low=90,close=100) for i in range(4)]
  t=dict(i=0,end_i=3,replacement_end_i=3,sign=1,at=0,contract={'symbol':'fake'})
  q={0:[0,100,110,100,110,1],60:[60,110,110,95,95,1],120:[120,90,90,90,90,1],180:[180,100,100,100,100,1]}
  v=dict(family='current',distance=.1);r=replay(t,rows,[],[],q,v,0)
  self.assertEqual(r['exit_i'],2);self.assertEqual(r['sold'],90)
if __name__=='__main__':unittest.main()
