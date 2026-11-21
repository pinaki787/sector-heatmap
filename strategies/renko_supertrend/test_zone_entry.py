import unittest,tempfile,math
from pathlib import Path
from unittest.mock import patch
from . import zone_entry,zone_target,preferences
from .runner import Runner,configuration
from .test_runner import FakeBroker
from .test_calibrated import NOW,config
def bars():
 prices=[100,101]+[100]*14+[110,98,97,100,109]
 rows=[dict(timestamp=NOW-(len(prices)-i)*300,open=p,high=p+1,low=p-1,close=p,volume=1) for i,p in enumerate(prices)]
 rows[16].update(high=112,low=109);rows[20].update(high=111,low=108)
 return rows
def enabled(**kw):return dict(zone_entry_enabled=True,zone_entry_min_atr=1.,zone_entry_rearm=True,**kw)
class Tests(unittest.TestCase):
 def test_legacy_off_and_boolean_validation(self):
  self.assertTrue(zone_entry.assess([],{},None,None,None,NOW)['allowed'])
  for c in (dict(zone_entry_enabled='true'),dict(zone_entry_rearm=1),dict(zone_entry_min_atr=float('nan')),dict(zone_entry_min_atr=0)):
   with self.assertRaises(ValueError):zone_entry.settings(c)
 def test_scope_does_not_restrict_execution_mode(self):
  for mode in ('PAPER','LIVE'):
   c=configuration({**config(),'mode':mode,'zone_entry_enabled':True})
   self.assertTrue(c['zone_entry_enabled'])
  with self.assertRaises(ValueError):zone_entry.compatible(dict(zone_entry_enabled=True,underlying='BTCUSD',timeframe='1 minute'))
 def test_symmetric_clearance_and_boundaries(self):
  known=dict(supply=dict(lower=110,upper=112,broken_at=None),demand=dict(lower=88,upper=90,broken_at=None))
  for d,p,expected in [('BULLISH',109,False),('BULLISH',108,True),('BULLISH',111,False),('BULLISH',113,True),('BEARISH',91,False),('BEARISH',92,True)]:
   self.assertEqual(zone_entry.check_known(known,enabled(),d,p,2)['allowed'],expected)
 def test_no_active_zone_and_invalid_evidence(self):
  self.assertTrue(zone_entry.check_known({},enabled(),'BULLISH',100,2)['allowed'])
  for atr in (None,0,float('nan')):
   self.assertFalse(zone_entry.check_known({},enabled(),'BULLISH',100,atr)['allowed'])
 def test_fresh_signal_source_and_future_candle_exclusion(self):
  r=bars();q=zone_entry.assess(r,enabled(),'BULLISH',109,2,NOW,signal_at=NOW-300)
  self.assertFalse(q['allowed']);self.assertEqual(q['source_at'],NOW-300)
  r.append(dict(r[-1],timestamp=NOW,high=150,close=140,is_forming=True))
  self.assertEqual(q,zone_entry.assess(r,enabled(),'BULLISH',109,2,NOW,signal_at=NOW-300))
  with self.assertRaises(ValueError):zone_entry.assess(r,enabled(),'BULLISH',109,2,NOW+300)
  with self.assertRaises(ValueError):zone_entry.assess(bars(),enabled(),'BULLISH',109,2,NOW,signal_at=NOW-600)
 def test_warmup_fail_closed(self):
  with self.assertRaises(ValueError):zone_entry.assess(bars()[-7:],enabled(),'BULLISH',109,2,NOW)
 def test_preferences_round_trip(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'prefs.json';v=dict(symbol='NSE:NIFTY50-INDEX',timeframe='5 minutes',mode='LIVE',**{k.replace('_','-'):x for k,x in enabled().items()})
   preferences.write(p,dict(settings=v),NOW)
   self.assertEqual(preferences.read(p)['settings'],v)
 def runner(self,path,rearm=True):
  b=FakeBroker();b.rows=bars();b.now=NOW;b.live_price=lambda c,now:(109,now)
  r=Runner(b,path,lambda:b.now);self.addCleanup(r.release)
  r.state.update(config=configuration(config(zone_entry_enabled=True,zone_entry_rearm=rearm)),last_signal=dict(timestamp=NOW-300,host_atr=2),renko_engine=dict(state=dict(ema_qualified='BULLISH',chart_qualified='BULLISH')))
  return r,b
 def test_blocked_setup_rearms_without_submitting(self):
  with tempfile.TemporaryDirectory() as d:
   r,b=self.runner(Path(d)/'state.json')
   with self.assertRaisesRegex(ValueError,'ZONE_CLEARANCE'):r.zone_entry_gate('BULLISH')
   self.assertIsNone(r.state['renko_engine']['state']['ema_qualified']);self.assertEqual(b.sent,[])
   b.live_price=lambda c,now:(108,now)
   self.assertTrue(r.zone_entry_gate('BULLISH')['allowed'])
 def test_rearm_choice_off_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   r,b=self.runner(Path(d)/'state.json',False)
   with self.assertRaises(ValueError):r.zone_entry_gate('BULLISH')
   self.assertEqual(r.state['renko_engine']['state']['ema_qualified'],'BULLISH')
 def test_final_authorization_checks_zone_before_order(self):
  with tempfile.TemporaryDirectory() as d:
   r,b=self.runner(Path(d)/'state.json')
   with self.assertRaisesRegex(ValueError,'ZONE_CLEARANCE'):r.validate_entry_authorization(dict(direction='BULLISH'))
   self.assertEqual(b.sent,[])
 def test_stale_quote_blocks_without_clearing_qualification(self):
  with tempfile.TemporaryDirectory() as d:
   r,b=self.runner(Path(d)/'state.json');b.live_price=lambda c,now:(108,now-16)
   with self.assertRaisesRegex(ValueError,'Fresh underlying'):r.zone_entry_gate('BULLISH')
   self.assertEqual(r.state['renko_engine']['state']['ema_qualified'],'BULLISH')
 def test_native_backtest_blocks_before_option_selection(self):
  from . import backtest as bt
  from .test_backtest import BacktestTests,Source,FakeEngine
  source=Source();request=BacktestTests().request()
  request['settings'].update(timeframe='5 minutes',zone_entry_enabled=True,zone_entry_rearm=True)
  with patch.object(bt,'Engine',FakeEngine),patch.object(bt.ema_proximity,'check',return_value={}),patch.object(bt.zone_entry,'check_known',return_value=dict(allowed=False,reason='WAITING_OPPOSING_ZONE_CLEARANCE')) as gate:
   from datetime import date
   r=bt.run(request,source,date(2026,10,25))
  self.assertTrue(gate.called);self.assertEqual(source.selected,[]);self.assertEqual(r['trades'],[])
if __name__=='__main__':unittest.main()
