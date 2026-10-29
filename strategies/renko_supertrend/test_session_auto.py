import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo
from .session_auto import REVISION, FrozenReferences, reference, scale, selected, session_bounds, session_spec

IST=ZoneInfo("Asia/Kolkata")
def stamp(day):return datetime(2026,10,day,tzinfo=IST).timestamp()
def bars():return [dict(timestamp=stamp(day),completed_at=stamp(day+1),open=1000,high=1050,low=950,close=1000) for day in range(1,7)]
def crypto():return session_spec("BTCUSD","DELTA_INDIA",dict(seven_day_session=True,session_source="CONTINUOUS_CRYPTO"))
def ref():return reference(bars(),length=5,factor=3,available_at=stamp(7),input_basis="COMPLETED_SESSION_OHLC")

class SessionAutoTests(unittest.TestCase):
 def test_legacy_config_never_silently_migrates(self):
  c=dict(brick_mode="Auto",strategy_basis="RENKO")
  self.assertFalse(selected(c));self.assertTrue(selected({**c,"auto_sizing_policy":REVISION}))
  with self.assertRaisesRegex(ValueError,"Unknown"):selected({**c,"auto_sizing_policy":"unknown"})
 def test_wilder_reference_uses_only_closed_evidence(self):
  r=ref();self.assertEqual(r["reference_atr"],100);self.assertEqual(r["session_reference"],300)
  future=dict(timestamp=stamp(7),completed_at=stamp(8),open=1000,high=2000,low=500,close=1000)
  self.assertEqual(reference(bars()+[future],length=5,factor=3,available_at=stamp(7),input_basis="COMPLETED_SESSION_OHLC"),r)
  revised=bars();revised[-1]["high"]=1550
  r2=reference(revised,length=5,factor=3,available_at=stamp(7),input_basis="COMPLETED_SESSION_OHLC")
  self.assertEqual(r2["reference_atr"],200);self.assertEqual(r2["session_reference"],600)
 def test_ist_crypto_day_boundary_is_exactly24_hours(self):
  spec=crypto();start,end=session_bounds(stamp(7)+3600,spec)
  self.assertEqual((start,end),(stamp(7),stamp(8)));self.assertEqual(spec["session_minutes"],1440)
  self.assertEqual(session_bounds(stamp(8),spec),(stamp(8),stamp(9)))
 def test_verified_indian_symbol_session_and_overnight_bounds(self):
  spec=session_spec("NSE:NIFTY50-INDEX","DHAN",dict(master_regular_session="0915-1530",session_source="INSTRUMENT_MASTER"))
  self.assertEqual(spec["session_minutes"],375)
  self.assertEqual(session_bounds(stamp(7)+10*3600,spec),(stamp(7)+9.25*3600,stamp(7)+15.5*3600))
  night=session_spec("MCX:TEST","FYERS",dict(master_regular_session="0900-0130",session_source="VERIFIED_DATE_CALENDAR"))
  self.assertEqual(session_bounds(stamp(8)+3600,night),(stamp(7)+9*3600,stamp(8)+1.5*3600))
  with self.assertRaises(ValueError):session_spec("NSE:TEST","DHAN",{})
 def test_one_five_thirty_scale_same_reference_without_host_seed(self):
  r=ref();out=[scale(r,t*60,crypto(),.001)["box"] for t in (1,5,30)]
  self.assertAlmostEqual(out[1],out[0]*5);self.assertAlmostEqual(out[2],out[0]*30)
  self.assertEqual(out,[300/1440,300*5/1440,300*30/1440])
 def test_tick_minimum_is_explicit_and_not_order_price_rounding(self):
  r={**ref(),"session_reference":100}
  for t in (1,5):
   value=scale(r,t*60,crypto(),.5);self.assertEqual(value["box"],.5);self.assertTrue(value["minimum_tick_applied"])
  value=scale(r,1800,crypto(),.5);self.assertFalse(value["minimum_tick_applied"]);self.assertEqual(value["box"],100/48)
 def test_freeze_reload_and_timeframe_changes_preserve_reference(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/"references.json";a=FrozenReferences(path).freeze(crypto(),stamp(7),ref());before=path.read_bytes()
   b=FrozenReferences(path).freeze(crypto(),stamp(7),ref());self.assertEqual(a,b);self.assertEqual(path.read_bytes(),before)
   self.assertAlmostEqual(scale(a,300,crypto(),.001)["box"],5*scale(b,60,crypto(),.001)["box"])
 def test_revision_after_freeze_is_blocked_without_overwriting_audit(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/"references.json";store=FrozenReferences(path);store.freeze(crypto(),stamp(7),ref());before=path.read_bytes()
   with self.assertRaisesRegex(ValueError,"changed after session freeze"):store.freeze(crypto(),stamp(7),{**ref(),"session_reference":400})
   self.assertEqual(path.read_bytes(),before)
 def test_future_reference_cannot_be_frozen_for_earlier_session(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaisesRegex(ValueError,"before the target session"):FrozenReferences(Path(tmp)/"r.json").freeze(crypto(),stamp(6),ref())
 def test_missing_warmup_conflicting_bars_and_unsupported_frame_block(self):
  with self.assertRaisesRegex(ValueError,"warmup"):reference(bars()[:4],length=5,factor=3,available_at=stamp(7),input_basis="SESSION")
  with self.assertRaisesRegex(ValueError,"Conflicting"):reference(bars()+[{**bars()[0],"high":1051}],length=5,factor=3,available_at=stamp(7),input_basis="SESSION")
  with self.assertRaises(ValueError):scale(ref(),2*86400,crypto(),.5)

 def test_reference_window_coverage_is_exact_no_fabricated_missing_candles(self):
  from .session_auto import completed_reference_bars
  start=stamp(7)
  rows=[dict(timestamp=start+i*300,open=100,high=102,low=99,close=101) for i in range(12)]
  value=completed_reference_bars(rows,[(start,start+3600)],source_seconds=300,available_at=start+3600)
  self.assertEqual(value[0]["source_count"],12)
  self.assertEqual(value[0]["completed_at"],start+3600)
  with self.assertRaisesRegex(ValueError,"missing source"):
   completed_reference_bars(rows[:-1],[(start,start+3600)],source_seconds=300,available_at=start+3600)
  self.assertEqual(completed_reference_bars(rows,[(start,start+3600)],source_seconds=300,available_at=start+3599),[])
 def test_reference_coverage_rejects_unaligned_partial_source_intervals(self):
  from .session_auto import completed_reference_bars
  with self.assertRaisesRegex(ValueError,"does not align"):
   completed_reference_bars([],[(stamp(7),stamp(7)+3700)],source_seconds=300,available_at=stamp(8))


class PreparedEngineTests(unittest.TestCase):
 def adapter(self,tmp,broker="DELTA_INDIA",symbol="BTCUSD"):
  class Adapter:
   session_auto_root=Path(tmp)
   session_auto_instrument_identity="VERIFIED-TEST-INSTRUMENT"
   now=stamp(7)+12*3600
   def clock(self):return self.now
   def session_policy(self,c):
    if broker=="DELTA_INDIA":return dict(seven_day_session=True,session_source="CONTINUOUS_CRYPTO")
    return dict(master_regular_session="0915-1530",session_source="VERIFIED_BROKER_SYMBOL_MASTER")
   def session_auto_inputs(self,c,begin,now):
    result=bars()+[dict(timestamp=stamp(7),completed_at=stamp(8),open=1000,high=1100,low=900,close=1000)]
    if broker!="DELTA_INDIA":
     result=[dict(r,timestamp=r["timestamp"]+9.25*3600,completed_at=r["timestamp"]+15.5*3600) for r in result]
    return result,"Selected fake broker completed full-session OHLC"
  return Adapter()
 def config(self,frame="1 minute",broker="DELTA_INDIA",symbol="BTCUSD"):
  from .test_brick_basis import BASE
  return {**BASE,"underlying":symbol,"broker":broker,"timeframe":frame,"brick_mode":"Auto","atr_length":5,"factor":3,"auto_sizing_policy":REVISION,"ema_fast_enabled":False}
 def host(self,day=7):
  return [dict(timestamp=stamp(day)+10*3600+i*60,open=1000+i,high=1002+i,low=999+i,close=1001+i) for i in range(3)]
 def test_shared_preparation_and_engine_one_five_thirty_parity(self):
  from .session_auto import prepare
  from .runner import analysis
  with tempfile.TemporaryDirectory() as tmp:
   adapter=self.adapter(tmp);out=[]
   for frame in ["1 minute","5 minutes","30 minutes"]:
    c=self.config(frame);prepare(adapter,c,self.host());e=analysis(self.host(),c,.05)
    out.append(e["last"]["session_auto"])
   self.assertEqual({r["input_hash"] for r in out},{out[0]["input_hash"]})
   self.assertAlmostEqual(out[1]["box"],out[0]["box"]*5);self.assertAlmostEqual(out[2]["box"],out[0]["box"]*30)
   self.assertEqual(out[0]["session_reference"],300)
 def test_indian_brokers_share_formula_and_verified_session_duration(self):
  from .session_auto import prepare
  from .runner import analysis
  with tempfile.TemporaryDirectory() as tmp:
   for broker in ["FYERS","DHAN","MOTILAL_OSWAL"]:
    adapter=self.adapter(tmp,broker,"NSE:NIFTY50-INDEX");c=self.config("5 minutes",broker,"NSE:NIFTY50-INDEX")
    prepare(adapter,c,self.host());e=analysis(self.host(),c,.05)
    self.assertEqual(e["last"]["box"],300*5/375)
    self.assertEqual(e["last"]["session_auto"]["session_minutes"],375)
 def test_restart_and_later_host_history_anchor_cannot_reseed_box(self):
  from .session_auto import prepare
  from .runner import analysis
  with tempfile.TemporaryDirectory() as tmp:
   a=self.adapter(tmp);c=self.config();prepare(a,c,self.host());e=analysis(self.host(),c,.05)
   other=self.adapter(tmp);d=self.config();prepare(other,d,self.host()[1:]);resumed=analysis(self.host(),d,.05,saved=deepcopy(e))
   self.assertEqual(e["last"],resumed["last"])
   rebuilt=analysis(self.host()[1:],d,.05)
   self.assertEqual(e["last"]["box"],rebuilt["last"]["box"])
 def test_next_session_references_completed_day_and_price_first_tick_is_baseline(self):
  from .session_auto import prepare
  from .runner import analysis
  from .price_basis import observe
  with tempfile.TemporaryDirectory() as tmp:
   adapter=self.adapter(tmp);c=self.config();prepare(adapter,c,self.host());e=analysis(self.host(),c,.05)
   before=e["state"]["brick_box"];at=stamp(7)+12*3600
   self.assertEqual(observe(e,c,.05,dict(ltp=1003,exch_feed_time=at),at+.1,1),[])
   adapter.now=stamp(8)+1;prepare(adapter,c,self.host(8))
   self.assertEqual(observe(e,c,.05,dict(ltp=1100,exch_feed_time=adapter.now),adapter.now+.1,1),[])
   self.assertGreater(e["state"]["brick_box"],before)
   self.assertEqual(e["state"]["session_auto"]["session_start"],stamp(8))
   self.assertEqual(observe(e,c,.05,dict(ltp=1000,exch_feed_time=at),adapter.now+.1,1),[])
   self.assertEqual(e["state"]["session_auto"]["session_start"],stamp(8))
 def test_missing_new_policy_reference_blocks_instead_of_using_old_host_seed(self):
  from .runner import analysis
  with self.assertRaisesRegex(ValueError,"reference evidence unavailable"):
   analysis(self.host(),self.config(),.05)
 def test_production_broker_candle_paths_all_use_shared_reference_preparation(self):
  from .runner import Broker as FyersBroker
  from .delta_broker import Broker as DeltaBroker
  from sector_heatmap.dhan_strategy_broker import Broker as DhanBroker
  from sector_heatmap.motilal_strategy_broker import Broker as MotilalBroker
  for broker in [FyersBroker,DeltaBroker,DhanBroker,MotilalBroker]:self.assertTrue(hasattr(broker.candles,"__wrapped__"))
