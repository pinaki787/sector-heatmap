import unittest,sys,datetime,importlib.util
from pathlib import Path
p=Path(__file__).with_name('research.py');spec=importlib.util.spec_from_file_location('study',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReplayTest(unittest.TestCase):
 def setUp(self):
  self.t=int(datetime.datetime(2026,10,19,9,15,tzinfo=m.Z).timestamp())
  self.rows=[dict(timestamp=self.t+i*60,open=23000 if i<6 else 23100,high=23110,low=22990,close=23000,volume=100) for i in range(16)]
  self.host=[dict(timestamp=self.t,close=23010),dict(timestamp=self.t+300,close=22990)]
  self.sig=[dict(entry_direction='BULLISH',entry_qualified=True,direction='BULLISH',ema10=23000,ema30=23000,host_atr=20,ema_gap=1,_exit_ema=23000),dict(entry_direction=None,entry_qualified=False,direction='BULLISH',ema10=23000,ema30=23000,host_atr=20,ema_gap=0,_exit_ema=23000)]
  self.c=dict(timeframe='5 minutes',max_trades=2,ema_exit_enabled=True,ema_exit_length=30,ema_slow_exit_enabled=False,supertrend_exit_enabled=False,sideways_enabled=False,ema_proximity_enabled=False,ema_fast_length=10,trailing_enabled=False)
  self.q={(self.t+i*60,'CALL',23000.):dict(open=100 if i<10 else 80,close=100 if i<10 else 80,volume=100) for i in range(16)}
 def run_case(self):return m.simulate(self.rows,self.host,self.sig,self.c,self.q,{'2026-10-19'},0)
 def test_next_open_fixed_strike_and_costs(self):
  r=self.run_case();self.assertTrue(r['valid']);t=r['trades'][0];self.assertEqual(t['entry_at'],self.t+300);self.assertEqual(t['exit_at'],self.t+600);self.assertEqual(t['strike'],23000);self.assertEqual(t['gross'],-1300);self.assertLess(t['net'],t['gross'])
 def test_missing_held_contract_invalidates_not_fabricates(self):
  del self.q[self.t+7*60,'CALL',23000.];r=self.run_case();self.assertFalse(r['valid']);self.assertEqual(r['problems'][0]['type'],'MISSING_HELD_CONTRACT')
 def test_no_entry_at_arming_boundary(self):
  self.host[0]['timestamp']=self.t-300;r=self.run_case();self.assertFalse(r['trades'])
if __name__=='__main__':unittest.main()

