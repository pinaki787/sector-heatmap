import json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from sector_heatmap import sector_detail_bridge as bridge

class Charts(unittest.TestCase):
 def candles(self):
  return [dict(timestamp=100000+i*900,close=100+i) for i in range(212)]
 def test_matches_exact_snapshot_and_excludes_later_bars(self):
  rows=self.candles();stamp=datetime.fromtimestamp(rows[-2]["timestamp"],timezone.utc).isoformat()
  result=bridge.chart_series(rows,stamp)
  self.assertEqual(len(result),60);self.assertEqual(result[-1]["timestamp"],rows[-2]["timestamp"])
  self.assertEqual(result[-1]["close"],310);self.assertIsInstance(result[-1]["ema200"],float)
 def test_missing_bar_or_insufficient_history_cannot_be_presented_as_a_chart(self):
  rows=self.candles()
  for stamp in (None,"invalid",datetime.fromtimestamp(100001,timezone.utc).isoformat()):
   with self.assertRaises(ValueError):bridge.chart_series(rows,stamp)
 def test_invalid_prices_fail_closed(self):
  rows=self.candles();rows[-1]["close"]=float("nan")
  with self.assertRaises(ValueError):bridge.chart_series(rows,datetime.fromtimestamp(rows[-1]["timestamp"],timezone.utc).isoformat())

class Details(unittest.TestCase):
 def setUp(self):
  bridge._CACHE.clear()
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.user=dict(id="owner",admin=False,features=["sectors"])
  self.account=dict(id="a"*32,broker="FYERS",port=8102,live_enabled=False)
  self.store=Mock();self.store.path=self.root/"registry.sqlite3"
  self.store.session.return_value=self.user;self.store.account.return_value=self.account
  self.store.folder.return_value=self.root
  self.base=dict(status="DELAYED",mode="intraday",sectors=[dict(sector_id="pharma",rank=9,overall_score=41,
   constituent_movers=[dict(ticker="TEST",change=1)],timeframe_states={"daily":dict(last_updated="2026-10-19T00:00:00+05:30",data_quality="DELAYED",score=38)})])
 def tearDown(self):self.tmp.cleanup()
 def test_owner_snapshot_rank_and_movers_preserved_with_verified_candles(self):
  response=SimpleNamespace(returncode=0,stdout=json.dumps(dict(ok=True,series=dict(daily=[dict(timestamp=123,close=100,ema20=99,ema50=98,ema200=97)]))))
  with patch.object(bridge,"_get",return_value=self.base),patch.object(bridge.subprocess,"run",return_value=response) as run:
   result=bridge.details(self.root,self.store,self.user,self.account["id"],"private-session","pharma")
  self.assertEqual(result["sector"]["rank"],9);self.assertEqual(result["sector"]["overall_score"],41)
  self.assertEqual(result["sector"]["constituent_movers"],self.base["sectors"][0]["constituent_movers"])
  self.assertEqual(result["sector"]["timeframe_states"]["daily"]["score"],38)
  self.assertTrue(result["read_only"]);self.assertEqual(len(result["sector"]["timeframe_states"]["daily"]["series"]),1)
  self.assertNotIn("private-session",str(run.call_args));self.assertNotIn("series",self.base["sectors"][0]["timeframe_states"]["daily"])
 def test_permission_and_current_session_checked_before_any_broker_request(self):
  self.store.session.return_value=dict(id="other",admin=True)
  with patch.object(bridge,"_get") as get:
   with self.assertRaises(PermissionError):bridge.details(self.root,self.store,self.user,self.account["id"],"token","pharma")
   get.assert_not_called()
 def test_unassigned_user_cannot_read(self):
  self.store.session.return_value=dict(id="owner",admin=False,features=[])
  with self.assertRaises(PermissionError):bridge.details(self.root,self.store,self.user,self.account["id"],"token","pharma")
 def test_native_read_never_switches_to_fyers(self):
  self.account["broker"]="DHAN"
  with patch.object(bridge,"_get",return_value={"sector":{"sector_id":"pharma"}}) as get:
   bridge.details(self.root,self.store,self.user,self.account["id"],"token","pharma")
   self.assertIn("/api/dhan/sector-analysis/detail?",get.call_args.args[2])
