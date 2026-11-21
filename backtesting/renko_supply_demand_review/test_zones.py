import unittest
from zones import contexts,allowed,entry_distance
from strategies.renko_supertrend import zone_target
def bars():
 prices=[100,101]+[100]*14+[110,98,97,100,109]
 rows=[dict(timestamp=1800000000+i*300,open=p,high=p+1,low=p-1,close=p,volume=1) for i,p in enumerate(prices)]
 rows[16].update(high=112,low=109);rows[20].update(high=111,low=108)
 return rows
class Tests(unittest.TestCase):
 def test_every_prefix_matches_full_timeline(self):
  rows=bars();full=contexts(rows)
  for n in range(1,len(rows)+1):
   partial=contexts(rows[:n]);self.assertEqual(partial,{c["timestamp"]:full[c["timestamp"]] for c in rows[:n]})
 def test_zone_not_available_before_confirmation(self):
  rows=bars();c=contexts(rows)
  self.assertIsNone(c[rows[18]["timestamp"]]["before"]["supply"])
  self.assertIsNotNone(c[rows[18]["timestamp"]]["after"]["supply"])
  self.assertEqual(c[rows[18]["timestamp"]]["after"]["supply"]["confirmed_at"],rows[18]["timestamp"]+300)
 def test_existing_target_exit_and_same_candle_exclusion(self):
  rows=bars();c=contexts(rows);r=rows[20];z=c[r["timestamp"]]
  result=zone_target.assess_known(r,z["previous"],z["before"],dict(direction="BULLISH",opened_at=rows[19]["timestamp"]),r["timestamp"]+300)
  self.assertEqual(result["reason"],"SD_5M_ZONE_REJECTION")
  late=zone_target.assess_known(r,z["previous"],z["before"],dict(direction="BULLISH",opened_at=r["timestamp"]+60),r["timestamp"]+300)
  self.assertIsNone(late["reason"])
 def test_breakout_continues_instead_of_target_fill(self):
  rows=bars();c=contexts(rows);r=dict(rows[20],close=113,high=114);z=c[r["timestamp"]]
  result=zone_target.assess_known(r,z["previous"],z["before"],dict(direction="BULLISH",opened_at=rows[19]["timestamp"]),r["timestamp"]+300)
  self.assertEqual(result["state"],"CONFIRMED_BREAK_CONTINUE");self.assertIsNone(result["reason"])
 def test_filter_symmetric_at_threshold(self):
  known=dict(supply=dict(lower=110,upper=112,broken_at=None),demand=dict(lower=88,upper=90,broken_at=None))
  self.assertFalse(allowed(known,"BULLISH",109,2,1.))
  self.assertTrue(allowed(known,"BULLISH",108,2,1.))
  self.assertFalse(allowed(known,"BEARISH",91,2,1.))
  self.assertTrue(allowed(known,"BEARISH",92,2,1.))
 def test_inside_and_passed_zones(self):
  known=dict(supply=dict(lower=110,upper=112,broken_at=None),demand=None)
  self.assertFalse(allowed(known,"BULLISH",111,2,1.))
  self.assertTrue(allowed(known,"BULLISH",113,2,1.))
  self.assertTrue(allowed(known,"BEARISH",100,2,1.))
 def test_broken_zones_ignored_and_missing_atr_rejected(self):
  known=dict(supply=dict(lower=110,upper=112,broken_at=None),demand=None)
  self.assertFalse(allowed(known,"BULLISH",109,None,1.))
  known["supply"]["broken_at"]=1
  self.assertTrue(allowed(known,"BULLISH",109,2,1.))
 def test_target_assess_known_matches_production_full_history(self):
  rows=bars();c=contexts(rows);z=c[rows[-1]["timestamp"]];p=dict(direction="BULLISH",opened_at=rows[2]["timestamp"]);now=rows[-1]["timestamp"]+300
  self.assertEqual(zone_target.assess(rows,p,now),zone_target.assess_known(rows[-1],z["previous"],z["before"],p,now))
if __name__=="__main__":unittest.main()
