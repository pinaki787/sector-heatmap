import tempfile, unittest
from pathlib import Path
from sector_heatmap.handoff_allocation import allocate, identity, Claims
def idea(symbol="NSE:A-EQ", kind="EQUITY", score=6, maximum=6, entry=100, lot=1):
 return dict(symbol=symbol,underlying=symbol,kind=kind,direction="BULLISH",entry=entry,stop=entry*.9,target=entry*1.2,lot_size=lot,validated=True,conviction=dict(rating="High",score=score,maximum_score=maximum))
class AllocationTests(unittest.TestCase):
 def test_option_first_equities_equal(self):
  result=allocate([idea("OPT","LONG_OPTION",entry=100,lot=100),idea("A",entry=100),idea("B",entry=200)])
  self.assertEqual([r["quantity"] for r in result["plans"]],[450,225,100])
  self.assertEqual(result["allocated"],"100000")
 def test_cash_quote_headroom_uses_assigned_budget_without_exceeding_pool(self):
  result=allocate([idea("A",entry=333),idea("B",entry=777)],capital=10000)
  for row in result["plans"]:
   self.assertEqual(float(row["allocation_limit"]),5000)
   self.assertLessEqual(float(row["allocation"]),float(row["allocation_limit"]))
  self.assertLessEqual(sum(float(r["allocation_limit"]) for r in result["plans"]),10000)
 def test_confirmed_fill_releases_unused_quote_headroom_but_keeps_fingerprint(self):
  with tempfile.TemporaryDirectory() as tmp:
   claims=Claims(Path(tmp)/"claims.db")
   plan=allocate([idea("A",entry=60000)])["plans"][0]
   claims.reserve("owned",plan)
   claims.confirmed("owned",plan["fingerprint"],notional=60000)
   other=allocate([idea("B",entry=100)],used=60000)["plans"][0]
   claims.reserve("owned",other)
   with self.assertRaises(ValueError):claims.reserve("owned",plan)
 def test_normalized_ranking(self):
  a=idea("A",score=6,maximum=7);b=idea("B",score=5,maximum=6)
  self.assertEqual(allocate([b,a])["plans"][0]["symbol"],"A")
 def test_top_five(self):
  self.assertEqual(len(allocate([idea(str(i)) for i in range(8)])["plans"]),5)
 def test_exposure_excluded(self):
  self.assertFalse(allocate([idea("A")],exposed=["A"])["plans"])
 def test_no_duplicate_recommendation(self):
  row=idea("A");self.assertFalse(allocate([row],seen=[identity(row)])["plans"])
 def test_existing_allocations_reduce_pool(self):
  self.assertEqual(allocate([idea()],used=90000)["allocated"],"10000")
 def test_options_cannot_exceed_pool(self):
  r=allocate([idea("O","LONG_OPTION",entry=1000,lot=200)])
  self.assertFalse(r["plans"]);self.assertIsNotNone(r["blocked"])
 def test_invalid_protection_skipped(self):
  row=idea();row["stop"]=101;self.assertFalse(allocate([row])["plans"])
 def test_one_underlying_no_duplicate_product(self):
  a=idea("A");b=idea("OPTION","LONG_OPTION",lot=10);b["underlying"]="A"
  self.assertEqual(len(allocate([a,b])["plans"]),1)
 def test_no_approximate_lots(self):
  row=idea("O","LONG_OPTION",lot=1.5);self.assertFalse(allocate([row])["plans"])
 def test_moderate_excluded(self):
  row=idea();row["conviction"]["rating"]="Moderate";self.assertFalse(allocate([row])["plans"])
 def test_repeated_submissions_and_restart_blocked(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/"claims.db";r=allocate([idea()])["plans"][0];Claims(path).reserve("owned",r)
   with self.assertRaises(ValueError):Claims(path).reserve("owned",r)
 def test_uncertain_keeps_capital_reserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=Claims(Path(tmp)/"claims.db");a=allocate([idea("A")])["plans"][0];c.reserve("owned",a);c.uncertain("owned",a["fingerprint"])
   with self.assertRaises(ValueError):c.reserve("owned",allocate([idea("B")])["plans"][0])
 def test_account_isolation(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=Claims(Path(tmp)/"claims.db");a=allocate([idea()])["plans"][0];c.reserve("one",a);c.reserve("two",a)
