import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from smc import build_facts,allows
BASE=int(datetime(2025,1,2,9,15,tzinfo=ZoneInfo("Asia/Kolkata")).timestamp())
def rows(highs):
 return [dict(timestamp=BASE+300*i,open=h-1,high=h,low=h-2,close=h-1,volume=1) for i,h in enumerate(highs)]
class Tests(unittest.TestCase):
 def test_pivot_requires_right_confirmation(self):
  r=rows([3,5,9,5,3]);f=build_facts(r,2)
  self.assertEqual(f[r[3]["timestamp"]]["highs"],[])
  self.assertEqual(f[r[4]["timestamp"]]["highs"][0]["at"],r[2]["timestamp"])
  self.assertEqual(f[r[4]["timestamp"]]["highs"][0]["confirmed_at"],r[4]["timestamp"]+300)
 def test_every_prefix_matches_full_history(self):
  r=rows([4,8,5,3,9,7,5,2,8,4,7,10,5,2,6])
  for k in (1,2,3):
   all_facts=build_facts(r,k)
   for n in range(1,len(r)+1):
    self.assertEqual(build_facts(r[:n],k),{x["timestamp"]:all_facts[x["timestamp"]] for x in r[:n]})
 def test_new_session_and_gaps_reset_levels(self):
  r=rows([3,5,9,5,3]);r.append(dict(r[-1],timestamp=r[-1]["timestamp"]+600))
  self.assertEqual(build_facts(r,2)[r[-1]["timestamp"]]["highs"],[])
 def test_actual_high_sweep_uses_previously_known_swing(self):
  r=rows([3,5,9,5,3]);r.append(dict(r[-1],timestamp=r[-1]["timestamp"]+300,high=10,close=8))
  f=build_facts(r,2)[r[-1]["timestamp"]]
  self.assertEqual(f["age_long_sweep"],0)
  self.assertFalse(allows(f,"BULLISH",8,1,dict(sweep=3)))
 def test_room_symmetric_and_no_resistance(self):
  f=dict(resistance=[105,110],support=[95,90])
  self.assertFalse(allows(f,"BULLISH",100,4,dict(room=1.5)))
  self.assertFalse(allows(f,"BEARISH",100,4,dict(room=1.5)))
  self.assertTrue(allows(f,"BULLISH",106,2,dict(room=1.5)))
  self.assertFalse(allows(f,"BULLISH",100,None,dict(room=1.5)))
 def test_structure_and_bos_do_not_infer_unknown_direction(self):
  f=dict(structure=0,bos=0)
  for d in ("BULLISH","BEARISH"):
   self.assertFalse(allows(f,d,100,1,dict(structure=True)))
   self.assertFalse(allows(f,d,100,1,dict(bos=True)))
 def test_sweep_timeout_and_delay(self):
  f=dict(age_long_sweep=2,age_short_sweep=3,bars=11)
  self.assertFalse(allows(f,"BULLISH",100,1,dict(sweep=3)))
  self.assertTrue(allows(f,"BEARISH",100,1,dict(sweep=3)))
  self.assertFalse(allows(f,"BULLISH",100,1,dict(delay=12)))
if __name__=="__main__":unittest.main()
