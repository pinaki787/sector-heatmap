import unittest
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
from .signals import Engine,settings,supertrend_slope_observe
from .test_brick_basis import BASE,candles
from . import preferences

class SupertrendSlopeTests(unittest.TestCase):
 def gate(self,values,direction=-1,**extra):
  state={};cfg=settings(dict(supertrend_slope_enabled=True,**extra))
  return [supertrend_slope_observe(state,cfg,v,direction,10) for v in values]
 def test_rising_falling_flat(self):
  self.assertTrue(self.gate([100,102])[-1]['allowed'])
  self.assertTrue(self.gate([100,98],1)[-1]['allowed'])
  self.assertFalse(self.gate([100,100])[-1]['allowed'])
  self.assertFalse(self.gate([100,99])[-1]['allowed'])
 def test_threshold_normalized_per_observation(self):
  out=self.gate([100,102,104],supertrend_slope_bars=2,supertrend_slope_min_atr=.1)
  self.assertFalse(out[1]['allowed']);self.assertTrue(out[2]['allowed'])
  self.assertAlmostEqual(out[2]['slope_atr'],.2)
  self.assertFalse(self.gate([100,102],supertrend_slope_min_atr=.2)[-1]['allowed'])
 def test_flip_jump_does_not_pass(self):
  state={};cfg=settings(dict(supertrend_slope_enabled=True))
  supertrend_slope_observe(state,cfg,100,1,10)
  self.assertFalse(supertrend_slope_observe(state,cfg,120,-1,10)['allowed'])
  self.assertTrue(supertrend_slope_observe(state,cfg,121,-1,10)['allowed'])
 def test_validation_and_family_off(self):
  for field,value in [('supertrend_slope_bars',0),('supertrend_slope_bars',1.5),('supertrend_slope_bars',True),('supertrend_slope_min_atr',float('nan')),('supertrend_slope_enabled','true')]:
   with self.assertRaises(ValueError):settings({field:value})
  self.assertFalse(settings(dict(supertrend_slope_enabled=True,supertrend_family_enabled=False))['supertrend_slope_enabled'])
  self.assertFalse(settings({})['supertrend_slope_enabled'])
 def test_confirmed_bricks_resume_and_blocking(self):
  cfg={**BASE,'supertrend_slope_enabled':True,'supertrend_slope_min_atr':100}
  rows=candles([100,135,165,195,225])
  e=Engine(cfg);out=[e.update(c) for c in rows]
  events=[b for r in out for b in r['brick_events']]
  self.assertTrue(events);self.assertFalse(any(b['entry_direction'] for b in events))
  self.assertTrue(all('supertrend_slope_filter' in b for b in events))
  split=Engine(cfg);[split.update(c) for c in rows[:3]]
  resumed=Engine(cfg,state=deepcopy(split.state));tail=[resumed.update(c) for c in rows[3:]]
  self.assertEqual(tail,out[3:])
  before=deepcopy(e.state);self.assertIsNone(e.update({**candles([250])[0],'timestamp':rows[-1]['timestamp']+60,'is_forming':True}));self.assertEqual(e.state,before)
 def test_preferences_roundtrip(self):
  with TemporaryDirectory() as directory:
   p=Path(directory)/'preferences.json'
   fields={'supertrend-slope-enabled':True,'supertrend-slope-bars':3,'supertrend-slope-min-atr':.05}
   preferences.write(p,{'settings':fields},123)
   self.assertEqual(preferences.read(p)['settings'],fields)

 def test_supertrend_only_can_enter_after_slope_confirmation(self):
  cfg={**BASE,'supertrend_slope_enabled':True,'ema_fast_enabled':False}
  e=Engine(cfg)
  out=[e.update(c) for c in candles([100,135,165,195,225,255,285,315])]
  events=[b for r in out for b in r['brick_events']]
  entries=[b for b in events if b.get('entry_direction')]
  self.assertTrue(entries)
  self.assertTrue(all(b['supertrend_slope_filter']['allowed'] for b in entries))

 def test_projection_exit_does_not_suppress_execution_onset_both_directions(self):
  for prices,side,exit_name in [
   ([100,135,165,195,225,255,285,195,165,135,105],'BEARISH','BUY EXIT'),
   ([400,365,335,305,275,245,215,305,335,365,395],'BULLISH','SELL EXIT')]:
   cfg={**BASE,'supertrend_slope_enabled':True,'ema_fast_enabled':False}
   e=Engine(cfg);out=[e.update(c) for c in candles(prices)]
   exits=[i for i,r in enumerate(out) if any(b.get('lifecycle_event')==exit_name for b in r['brick_events'])]
   self.assertTrue(exits)
   i=exits[0];events=out[i]['brick_events'];exit_index=next(j for j,b in enumerate(events) if b.get('lifecycle_event')==exit_name)
   self.assertFalse(any(b.get('lifecycle_event') in ('BUY','SELL') for b in events[exit_index+1:]))
   following=out[i+1]['brick_events']
   entries=[b for b in events[exit_index+1:]+following if b.get('entry_direction')==side]
   self.assertEqual(len(entries),1)
   self.assertTrue(entries[0]['entry_qualified'])
   projected=[b for b in following if b.get('lifecycle_event')==('BUY' if side=='BULLISH' else 'SELL')]
   self.assertEqual(len(projected),1)
   self.assertFalse(any(b.get('entry_direction') for r in out[i+2:] for b in r['brick_events']))
