import unittest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
from review import simulate,filter_entry,stats
BASE=int(datetime(2026,10,23,10,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def bars():
 result=[]
 for i in range(5):
  price=100+i
  result.append(dict(timestamp=BASE+i*300,open=price,high=price+2,low=price-1,close=price+1,
   volume=0,ema10=100,ema30=100,host_atr=2,pine_direction=-1,entry_direction='BULLISH' if i==0 else None))
 return result
class FakeEngine:
 def __init__(self,*a):self.state={}
 def update(self,r):return dict(r)
class Tests(unittest.TestCase):
 def run_sim(self,rows,exit_reason=None):
  with patch('review.Engine',FakeEngine),patch('review.ema_proximity.check'),patch('review.exit_indicators.reason',side_effect=exit_reason or (lambda c,s,d:None)):
   return simulate(rows,dict(ema_exit_enabled=False),'Baseline')
 def test_next_open_entry(self):
  r=bars();result=self.run_sim(r)
  self.assertEqual(result['trades'][0]['entry_at'],r[1]['timestamp'])
  self.assertEqual(result['trades'][0]['entry_price'],r[1]['open'])
 def test_confirmed_exit_fills_next_open(self):
  r=bars()
  result=self.run_sim(r,lambda c,s,d:'EXIT' if s['timestamp']==r[2]['timestamp'] else None)
  self.assertEqual(result['trades'][0]['exit_at'],r[3]['timestamp'])
  self.assertEqual(result['trades'][0]['exit_price'],r[3]['open'])
 def test_missing_next_bar_cancels_entry(self):
  r=bars();r.pop(1)
  self.assertEqual(self.run_sim(r)['trades'],[])
 def test_cutoff_uses_open_not_future_close(self):
  r=bars()
  anchor=int(datetime(2026,10,23,15,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
  for i,row in enumerate(r):row['timestamp']=anchor+i*300
  result=self.run_sim(r)
  self.assertEqual(result['trades'][0]['exit_at'],r[2]['timestamp'])
  self.assertEqual(result['trades'][0]['exit_price'],r[2]['open'])
 def test_cost_drag_deducted_per_trade(self):
  self.assertEqual(stats([dict(gross_points=5)],2)['net_points'],3)
 def test_directional_efficiency_rejects_flat(self):
  r=[]
  for i in range(70):r.append(dict(timestamp=BASE+i*300,open=100,high=101,low=99,close=100,host_atr=2))
  self.assertFalse(filter_entry(r,'Efficiency025','BULLISH'))
 def test_filter_warmup(self):self.assertFalse(filter_entry(bars(),'Chop55','BULLISH'))
 def test_daily_cap_is_respected(self):
  r=[]
  for i in range(30):
   row=dict(bars()[0],timestamp=BASE+i*300,open=100+i,high=103+i,low=99+i,close=101+i,
    entry_direction='BULLISH' if i%2==0 else None)
   r.append(row)
  with patch('review.Engine',FakeEngine),patch('review.ema_proximity.check'),patch('review.exit_indicators.reason',return_value='EXIT'):
   result=simulate(r,dict(ema_exit_enabled=False),'Baseline',cap=2)
  self.assertEqual(len(result['trades']),2)
 def test_directional_filter_is_symmetric(self):
  for sign,direction in [(1,'BULLISH'),(-1,'BEARISH')]:
   r=[dict(timestamp=BASE+i*300,close=100+sign*i,high=101+sign*i,low=99+sign*i,host_atr=2) for i in range(70)]
   self.assertTrue(filter_entry(r,'Efficiency_ATR',direction))
 def test_realized_drawdown_accounts_for_costs(self):
  result=stats([dict(gross_points=5),dict(gross_points=-3),dict(gross_points=-2)],2)
  self.assertEqual(result['realized_drawdown_points'],9)
if __name__=='__main__':unittest.main()
