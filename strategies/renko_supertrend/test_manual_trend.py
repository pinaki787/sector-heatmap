import unittest
from . import manual_trend as m
from .signals import Engine,settings
from . import preferences
from tempfile import TemporaryDirectory
from pathlib import Path
class ManualTrend(unittest.TestCase):
 def config(self,**extra):return dict(manual_trend_enabled=True,manual_trend_bullish=100,manual_trend_bearish=100,manual_trend_closes=3,**extra)
 def rows(self,values):return [dict(timestamp=i*60,open=v,high=v+1,low=v-1,close=v) for i,v in enumerate(values)]
 def test_equal_markers_consecutive_and_reset(self):
  for values,direction,expected in [([101,102,103],'BULLISH',True),([99,98,97],'BEARISH',True),([101,100,102],'BULLISH',False),([101,99,102],'BULLISH',False),([99,101,98],'BEARISH',False),([100,100,100],'BULLISH',False)]:
   self.assertEqual(m.check(self.rows(values),self.config(),direction,60)['allowed'],expected)
 def test_gap_duplicate_forming(self):
  rows=self.rows([101,102,103]);rows[-1]['timestamp']=240
  self.assertFalse(m.check(rows,self.config(),'BULLISH',60)['allowed'])
  rows=self.rows([101,102]);self.assertFalse(m.check(rows+rows[-1:],self.config(),'BULLISH',60)['allowed'])
  rows=self.rows([101,102,103]);rows[-1]['is_forming']=True
  self.assertFalse(m.check(rows,self.config(),'BULLISH',60)['allowed'])
 def test_separate_markers_neutral_zone(self):
  c={**self.config(),'manual_trend_bullish':105,'manual_trend_bearish':95}
  for d in ['BULLISH','BEARISH']:self.assertFalse(m.check(self.rows([100]*3),c,d,60)['allowed'])
 def test_validation_and_disabled(self):
  self.assertTrue(m.check([],{},'BULLISH',60)['allowed'])
  for extra in [{'manual_trend_bullish':None},{'manual_trend_bullish':90},{'manual_trend_closes':1.5},{'manual_trend_closes':0},{'manual_trend_bearish':float('nan')}]:
   with self.assertRaises(ValueError):m.settings({**self.config(),**extra})
 def test_persistence_and_engine_completed_only(self):
  c=self.config();self.assertEqual(settings(c)['manual_trend_closes'],3)
  e=Engine({**c,'timeframe':'1 minute'});rows=self.rows([101,102,103])
  out=[e.update(r) for r in rows];self.assertEqual(out[-1]['manual_trend']['counts']['BULLISH'],3)
  self.assertIsNone(e.update(dict(timestamp=180,close=104,is_forming=True)))
  self.assertEqual(e.state['manual_trend_rows'][-1]['timestamp'],120)
  with TemporaryDirectory() as tmp:
   path=Path(tmp)/'settings.json';fields={k.replace('_','-'):v for k,v in c.items()}
   preferences.write(path,{'settings':fields},1)
   self.assertEqual(preferences.read(path)['settings'],fields)
 def test_apply_blocks_only_entries(self):
  e=dict(entry_qualified=True,entry_direction='BULLISH',supertrend_cross_direction='BEARISH',ema_exit_enabled=True)
  m.apply(e,m.check(self.rows([100]),self.config(),'BULLISH',60))
  self.assertFalse(e['entry_qualified']);self.assertEqual(e['supertrend_cross_direction'],'BEARISH');self.assertTrue(e['ema_exit_enabled'])

class SubmissionGate(ManualTrend):
 def test_live_price_must_retain_confirmed_zone(self):
  from .runner import Runner
  from types import SimpleNamespace
  rows=self.rows([101,102,103]);config={**self.config(),'timeframe':'1 minute'}
  adapter=SimpleNamespace(candles=lambda c:rows,live_price=lambda c,now:(101,now))
  fake=SimpleNamespace(state={'config':config},adapter=adapter,clock=lambda:180,history_rows=lambda rows:rows)
  Runner.manual_trend_entry_gate(fake,'BULLISH')
  adapter.live_price=lambda c,now:(100,now)
  with self.assertRaisesRegex(ValueError,'no longer retains'):Runner.manual_trend_entry_gate(fake,'BULLISH')
  with self.assertRaisesRegex(ValueError,'consecutive'):Runner.manual_trend_entry_gate(fake,'BEARISH')
  adapter.live_price=lambda c,now:(101,now-16)
  with self.assertRaisesRegex(ValueError,'Fresh'):Runner.manual_trend_entry_gate(fake,'BULLISH')
