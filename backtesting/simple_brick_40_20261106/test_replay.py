import importlib.util,unittest
from pathlib import Path
p=Path(__file__).with_name('replay.py');spec=importlib.util.spec_from_file_location('research',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CausalReplay(unittest.TestCase):
 def test_premium_selection_precedes_fill_and_range_lock_survives_exit(self):
  import datetime
  t=int(datetime.datetime(2026,10,1,9,15,tzinfo=m.IST).timestamp());rows=[]
  for i,(o,c) in enumerate([(100,110),(110,120),(120,100),(100,110),(110,120)]):
   rows.append(dict(timestamp=t+i*60,open=o,high=max(o,c),low=min(o,c),close=c,volume=1))
  quotes={};surface={}
  for i in range(7):
   at=t+i*60
   quotes[(at,'CALL',100.)]=(80,80,20,40,1,100)
   quotes[(at,'CALL',150.)]=(40,50,40,50,1,150)
   quotes[(at,'PUT',100.)]=(40,40,40,40,1,100)
   surface[(at,'CALL')]=[(100.,quotes[(at,'CALL',100.)]),(150.,quotes[(at,'CALL',150.)])]
   surface[(at,'PUT')]=[(100.,quotes[(at,'PUT',100.)])]
  quotes[(t+180,'CALL',100.)]=(20,20,20,20,1,100)
  result=m.simulate('manual',rows,['2026-10-01'],{'2026-10-01':{'manual':10}},quotes,surface)
  self.assertEqual(len(result['trades']),1)
  trade=result['trades'][0]
  self.assertEqual(trade['strike'],100)
  self.assertEqual(trade['selection_prior_close'],40)
  self.assertEqual(trade['entry_raw_open'],80)
  self.assertEqual(trade['reason'],'FIRST_COMPLETED_OPPOSITE_BRICK')
  self.assertEqual(trade['exit_at'],t+180)
  self.assertTrue(any(e['event']=='LOCK' for e in result['locks']))
  self.assertFalse(any(e['event']=='RELEASE' for e in result['locks']))
 def test_session_reference_is_causal_and_manual_changes_daily(self):
  _,days,_=m.load_underlying();sizes=m.refs(days)
  self.assertEqual(len(days),30)
  self.assertGreater(len({x['manual'] for x in sizes.values()}),1)
  for d,v in sizes.items():
   import datetime
   start=datetime.datetime.combine(datetime.date.fromisoformat(d),datetime.time(9,15),m.IST).timestamp()
   self.assertLess(v['reference_available_at'],start)
   self.assertAlmostEqual(v['auto'],v['reference_atr']/25)
   self.assertEqual(v['manual'],round(v['reference_atr']/12.5,2))
if __name__=='__main__':unittest.main()
