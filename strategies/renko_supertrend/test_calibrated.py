import tempfile,unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from . import calibrated,preferences
from .signals import Engine
from .risk import hard_exit
from .runner import Runner,BaseRunner,configuration
from .test_runner import FakeBroker
NOW=int(datetime(2026,10,23,10,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def rows(flat=False):
 return [dict(timestamp=NOW-(7-i)*300,open=100 if flat else 100+i*10,high=105 if flat else 105+i*10,low=99 if flat else 99+i*10,close=102 if flat else 102+i*10,volume=0) for i in range(7)]
def config(**changes):
 return dict(strategy='RENKO_SUPERTREND_V1',underlying='NSE:NIFTY50-INDEX',timeframe='5 minutes',lots=1,mode='PAPER',
 exit_policy='OPPOSITE_CONFIRMED_SIGNAL',calibrated_enabled=True,**changes)
class CalibratedTests(unittest.TestCase):
 def test_legacy_default_off(self):
  self.assertFalse(calibrated.settings({})['calibrated_enabled'])
  self.assertTrue(calibrated.check([],{} )['allowed'])
 def test_progress_and_flat_overlap(self):
  self.assertTrue(calibrated.check(rows(),config())['allowed'])
  self.assertFalse(calibrated.check(rows(True),config())['allowed'])
 def test_gap_and_session_fail_closed(self):
  r=rows();r[-1]['timestamp']+=300
  self.assertEqual(calibrated.check(r,config())['reason'],'WAITING_CALIBRATED_HISTORY')
  r=rows();r[0]['timestamp']-=86400
  self.assertEqual(calibrated.check(r,config())['reason'],'WAITING_CALIBRATED_SESSION')
 def test_warmup(self):self.assertFalse(calibrated.check(rows()[:3],config())['allowed'])
 def test_plan_direction_and_freeze(self):
  c=config();a=calibrated.plan(c,100,2,'BULLISH');b=calibrated.plan(c,100,2,'BEARISH')
  self.assertEqual((a['spot_stop'],a['spot_target']),(94,103))
  self.assertEqual((b['spot_stop'],b['spot_target']),(106,97))
  c['calibrated_stop_atr']=10
  self.assertEqual(a['spot_stop'],94)
 def test_per_position_levels_survive_config_changes(self):
  p=dict(calibrated_levels=calibrated.plan(config(),100,2,'BULLISH'))
  self.assertEqual(hard_exit(94,'BULLISH',calibrated.effective({},p)),'SPOT_STOP_EXIT')
  self.assertEqual(hard_exit(103,'BULLISH',calibrated.effective({},p)),'SPOT_TARGET_EXIT')
  self.assertEqual(calibrated.effective(dict(spot_stop=80),{} )['spot_stop'],80)
 def test_invalid_atr_never_invents_level(self):
  for v in (0,float('nan'),None):
   with self.assertRaises(ValueError):calibrated.plan(config(),100,v,'BULLISH')
 def test_scope_and_absolute_conflicts(self):
  for changes in (dict(underlying='NSE:TEST-EQ'),dict(timeframe='1 minute'),dict(intrabar_entries=True),dict(spot_stop=90)):
   c=config();c.update(changes)
   with self.assertRaises(ValueError):calibrated.compatible(c)
 def test_boolean_and_parameter_validation(self):
  for values in (dict(calibrated_enabled='yes'),dict(calibrated_overlap_pairs=2.5),dict(calibrated_overlap_max=1.1),dict(calibrated_stop_atr=0)):
   with self.assertRaises(ValueError):calibrated.settings(values)
 def test_engine_gate_matches_shared_check(self):
  e=Engine(config(ema_third_enabled=False,rsi_slope_enabled=False,retest_enabled=False))
  for r in rows(True):last=e.update(r)
  self.assertFalse(last['entry_qualified']);self.assertEqual(last['entry_diagnostic'],'WAITING_CALIBRATED_OVERLAP')
  self.assertFalse(last['calibrated_filter']['allowed'])
 def test_saved_preferences_roundtrip_baseline_and_calibrated(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'settings.json';s=dict(symbol='NSE:NIFTY50-INDEX',timeframe='5 minutes',mode='BACKTEST',**{k.replace('_','-'):v for k,v in calibrated.DEFAULTS.items()})
   s['calibrated-enabled']=True;preferences.write(p,dict(settings=s),100)
   self.assertTrue(preferences.read(p)['settings']['calibrated-enabled'])
   s['calibrated-enabled']=False;preferences.write(p,dict(settings=s),101)
   self.assertFalse(preferences.read(p)['settings']['calibrated-enabled'])
 def test_runner_config_captures_profile(self):
  c=configuration(config());self.assertTrue(c['calibrated_enabled']);self.assertEqual(c['calibrated_stop_atr'],3)
 def test_submit_attaches_frozen_levels_without_broker_submission(self):
  with tempfile.TemporaryDirectory() as folder:
   b=FakeBroker();b.now=NOW;b.rows=rows();r=Runner(b,Path(folder)/'state.json',lambda:b.now)
   self.addCleanup(r.release)
   c=configuration(config(ema_proximity_enabled=False,ema_momentum_enabled=False,higher_timeframe_enabled=False))
   r.state.update(config=c,last_signal=dict(timestamp=NOW-300,host_atr=2,close=162,direction='BULLISH',calibrated_filter=calibrated.check(rows(),c)),renko_engine=dict(last=dict(host_atr=2)),run_id='test')
   with patch.object(r,'sideways_entry_gate',return_value=True),patch.object(r,'deadline'),patch.object(r,'manual_trend_entry_gate'),patch.object(BaseRunner,'submit',side_effect=lambda order,p,reason:p):
    result=r.submit(dict(symbol='NSE:TESTCE',side=1,qty=20),dict(direction='BULLISH',symbol='NSE:TESTCE'),'ENTRY')
   self.assertEqual(result['calibrated_levels']['spot_stop'],156)
   self.assertEqual(result['calibrated_levels']['spot_target'],165)
   self.assertEqual(b.sent,[])
 def test_final_preflight_rejects_already_hit_frozen_boundary(self):
  with tempfile.TemporaryDirectory() as folder:
   b=FakeBroker();b.now=NOW;b.rows=rows();r=Runner(b,Path(folder)/'state.json',lambda:b.now);self.addCleanup(r.release)
   r.state['config']=configuration(config())
   p=dict(direction='BULLISH',calibrated_levels=calibrated.plan(config(),162,2,'BULLISH'))
   b.live_price=lambda c,now:(166,now)
   with self.assertRaisesRegex(ValueError,'boundary already reached'):r.validate_entry_authorization(p)
   self.assertEqual(b.sent,[])
if __name__=='__main__':unittest.main()
