import tempfile,unittest
from pathlib import Path
from datetime import datetime
from sector_heatmap.screener_auto import eligible_rows
from sector_heatmap.handoff_schedule import Schedule
from sector_heatmap.market_calendar import IST
from test_handoff_allocation import idea

def report(status="COMPLETED"):
 return {"analysis_scopes":[{"scope":{"screener":{"status":status,"enabled":True,"auto_enabled":True}}}]}

class ScreenerAuto(unittest.TestCase):
 def test_scope_excludes_options_and_sector_only_names(self):
  stock={**idea(),"provenance":[{"kind":"SCREENER"}]}
  option={**stock,"kind":"LONG_OPTION"}
  self.assertEqual(eligible_rows([stock,option,idea()],report()),[stock])
 def test_every_incomplete_or_missing_scan_blocks(self):
  for status in ("RUNNING","UNAVAILABLE","DISABLED"):
   with self.assertRaises(ValueError):eligible_rows([idea()],report(status))
  with self.assertRaises(ValueError):eligible_rows([idea()],{})
 def test_disabled_inclusion_blocks(self):
  r=report();r["analysis_scopes"][0]["scope"]["screener"]["auto_enabled"]=False
  with self.assertRaises(ValueError):eligible_rows([],r)
 def test_scheduler_enforces_scope_and_allocates_top_five(self):
  with tempfile.TemporaryDirectory() as tmp:
   rows=[]
   for i in range(7):
    row=idea();row.update(symbol=f"NSE:S{i}-EQ",underlying=f"NSE:S{i}-EQ",provenance=[{"kind":"SCREENER"}],source_rank=i+1)
    rows.append(row)
   rows.insert(0,idea())
   s=Schedule(Path(tmp)/"s.db","owned","FYERS",lambda p:(rows,report()),lambda p:dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=10000,exposed_underlyings=[]))
   s.configure({"enabled":True,"mode":"MANUAL","candidate_scope":"SCREENER_EQUITY","capital":10000})
   out=s.step(datetime(2026,10,21,10,tzinfo=IST))
   self.assertEqual(len(out["plans"]),5)
   self.assertTrue(all(p["provenance"]==[{"kind":"SCREENER"}] for p in out["plans"]))
   self.assertLessEqual(float(out["allocated"]),10000)
 def test_bad_scope_rejected_without_activation(self):
  with tempfile.TemporaryDirectory() as tmp:
   s=Schedule(Path(tmp)/"s.db","owned","FYERS",lambda p:([],{}),lambda p:{})
   with self.assertRaises(ValueError):s.configure({"candidate_scope":"ALL"})
   self.assertFalse(s.policy()["enabled"])
