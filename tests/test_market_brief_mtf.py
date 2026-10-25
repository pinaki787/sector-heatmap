import unittest,itertools,json,tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from sector_heatmap.market_brief_visual import sector_mtf_public,sector_public,caption,fallback_text,render,TF_ORDER
from sector_heatmap.analysis import mtf_alignment,STATE_LABELS
from sector_heatmap.market_calendar import IST
from sector_heatmap.sectors import SECTOR_DEFINITIONS
NOW=datetime(2026,10,25,16,0,tzinfo=IST)
def payload(states):
 frames={tf:dict(state=v,label=STATE_LABELS.get(v,"Unavailable"),last_updated="2026-10-23T15:15:00+05:30" if tf in {"15m","1h"} else "2026-10-23T05:30:00+05:30" if tf=="daily" else "2026-10-19T05:30:00+05:30",data_quality="MARKET CLOSED") for tf,v in zip(TF_ORDER,states)}
 return dict(generated_at=NOW.isoformat(),sectors=[dict(sector_id=SECTOR_DEFINITIONS[0].sector_id,timeframe_states=frames,mtf_alignment=mtf_alignment(frames))])
class MtfTests(unittest.TestCase):
 def result(self,p):return next(iter(sector_mtf_public(p,NOW).values()))
 def test_exact_dashboard_classification_for_all_complete_state_combinations(self):
  for states in itertools.product((-2,-1,0,1,2),repeat=4):
   p=payload(states);expected=mtf_alignment(p["sectors"][0]["timeframe_states"])
   self.assertEqual(self.result(p)["alignment"],expected)
 def test_full_bullish_bearish_and_mixed(self):
  for states,label in [((2,1,2,1),"FULL BULLISH ALIGNMENT"),((-2,-1,-2,-1),"FULL BEARISH ALIGNMENT"),((2,-2,0,-1),"MIXED")]:self.assertEqual(self.result(payload(states))["alignment"],label)
 def test_missing_frame_never_claims_full_alignment(self):
  p=payload((-2,-2,-2,-2));del p["sectors"][0]["timeframe_states"]["15m"]
  value=self.result(p);self.assertEqual(value["evidence"],"INCOMPLETE");self.assertEqual(value["alignment"],"BEARISH ALIGNMENT");self.assertIsNone(value["frames"]["15m"]["state"])
 def test_stale_frame_is_explicit_but_retains_dashboard_direction(self):
  p=payload((-2,-2,-2,-2));p["sectors"][0]["timeframe_states"]["1h"]["data_quality"]="STALE"
  value=self.result(p);self.assertEqual(value["alignment"],"FULL BEARISH ALIGNMENT");self.assertIn("STALE",value["evidence"]);self.assertIn("1h stale",value["issues"])
 def test_old_session_or_future_timestamp_is_stale(self):
  for timestamp in ("2026-10-22T15:15:00+05:30","2026-10-26T15:15:00+05:30"):
   p=payload((2,2,2,2));p["sectors"][0]["timeframe_states"]["15m"]["last_updated"]=timestamp
   self.assertEqual(self.result(p)["frames"]["15m"]["data_quality"],"STALE")
 def test_old_collector_is_stale_during_open_session(self):
  value=next(iter(sector_mtf_public(payload((2,2,2,2)),datetime(2026,10,26,10,0,tzinfo=IST)).values()))
  self.assertIn("STALE",value["evidence"])
 def test_invalid_or_missing_states_never_become_neutral(self):
  value=self.result(payload((None,None,None,None)));self.assertEqual(value["alignment"],"UNAVAILABLE");self.assertEqual(value["frames"]["daily"]["label"],"Unavailable")
 def test_strength_score_is_independent_from_alignment(self):
  sid=SECTOR_DEFINITIONS[0].sector_id;s=sector_public({"rows":[dict(sector_id=sid,score=95,asof="2026-10-23T15:15:00+05:30",rotation="IMPROVING")]},{},payload((-2,-2,-2,-2)),NOW)
  self.assertEqual(s["rows"][0]["score"],95);self.assertEqual(s["rows"][0]["mtf"]["alignment"],"FULL BEARISH ALIGNMENT")
 def test_snapshot_output_never_imports_unknown_private_fields(self):
  p=payload((2,2,2,2));p["sectors"][0]["positions"]="PRIVATE";p["capital"]=123456789
  result=sector_mtf_public(p,NOW);self.assertNotIn("PRIVATE",json.dumps(result));self.assertNotIn("123456789",json.dumps(result))
 def test_fourteen_sectors_render_and_fallback_fit_telegram_limits(self):
  from PIL import Image
  mtf=payload((-2,-2,-2,-2));template=mtf["sectors"][0]
  mtf["sectors"]=[{**template,"sector_id":d.sector_id} for d in SECTOR_DEFINITIONS]
  sec=sector_public({"rows":[dict(sector_id=d.sector_id,score=40,rotation="LAGGING",asof="2026-10-23T15:15:00+05:30") for d in SECTOR_DEFINITIONS]}, {},mtf,NOW)
  snap=dict(generated=NOW.isoformat(),sector_visual=sec)
  self.assertEqual(len(sec["rows"]),14);self.assertIn("15m",fallback_text(snap));self.assertIn("FULL BEARISH ALIGNMENT",fallback_text(snap));self.assertLessEqual(len(fallback_text(snap)),3900);self.assertLessEqual(len(caption(snap).encode("utf-16-le"))//2,1024)
  with tempfile.TemporaryDirectory() as f:
   path=Path(f)/"mtf.png";render(snap,path)
   with Image.open(path) as image:self.assertLess(image.width+image.height,10000);self.assertEqual(image.width,960)
 def test_dashboard_state_label_parity(self):
  for state,label in STATE_LABELS.items():self.assertEqual(self.result(payload((state,)*4))["frames"]["15m"]["label"],label)
 def test_recorded_alignment_mismatch_is_not_silently_accepted(self):
  p=payload((-2,-2,-2,-2));p["sectors"][0]["mtf_alignment"]="FULL BULLISH ALIGNMENT"
  value=self.result(p);self.assertEqual(value["alignment"],"FULL BEARISH ALIGNMENT");self.assertIn("label mismatch",value["issues"])
 def test_foreign_worker_fails_before_token_access(self):
  from sector_heatmap import combined_sector_worker as worker
  import os
  with tempfile.TemporaryDirectory() as f:
   p=Path(f)/"r.json";p.write_text(json.dumps(dict(account_id="foreign",broker="FYERS")))
   with patch.dict(os.environ,{"SECTOR_PULSE_WORKSPACE_ID":"owned"}),patch.object(worker,"owned_token") as token:
    with self.assertRaises(ValueError):worker.run(p,Path(f)/"out.json")
    token.assert_not_called()
if __name__=="__main__":unittest.main()
