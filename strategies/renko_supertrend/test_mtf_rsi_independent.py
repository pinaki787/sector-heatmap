import unittest
from . import mtf_rsi
class Independent(unittest.TestCase):
 def test_ranges(self):
  c=mtf_rsi.settings(dict(timeframe='1 minute',rsi_htf_1_enabled=True,rsi_htf_2_enabled=True,rsi_htf_3_enabled=True,
   rsi_level_mode='BETWEEN',rsi_bullish_min=60,rsi_bullish_max=80,rsi_bearish_min=35,rsi_bearish_max=40,
   rsi_htf_2_bullish_min=65,rsi_htf_3_bearish_max=37))
  prepared={f:dict(times=[3600],points=[dict(timestamp=3600-900,closed_at=3600,rsi14=60)]) for f in mtf_rsi.frames(c)}
  gate=mtf_rsi.assess(prepared,c,'BULLISH',3600)
  self.assertEqual([s['allowed'] for s in gate['slots']],[True,False,True])
  self.assertEqual(gate['slots'][1]['levels']['rsi_bullish_min'],65)
  self.assertEqual(c['rsi_bullish_min'],60)
  for i in mtf_rsi.SLOTS:
   levels=mtf_rsi.slot_levels(c,i)
   for direction,prefix in [('BULLISH','rsi_bullish_'),('BEARISH','rsi_bearish_')]:
    self.assertTrue(mtf_rsi.matches(levels[prefix+'min'],direction,levels))
    self.assertTrue(mtf_rsi.matches(levels[prefix+'max'],direction,levels))
 def test_old_and_threshold(self):
  c=dict(rsi_level_mode='THRESHOLD',rsi_bullish_above=55,rsi_bearish_below=40)
  self.assertFalse(mtf_rsi.matches(55,'BULLISH',mtf_rsi.slot_levels(c,1)))
  self.assertTrue(mtf_rsi.matches(56,'BULLISH',mtf_rsi.slot_levels(c,1)))
  self.assertTrue(mtf_rsi.matches(39,'BEARISH',mtf_rsi.slot_levels(c,3)))
 def test_invalid_disabled_override(self):
  for value in [float('nan'),True,-1,101]:
   with self.assertRaises(ValueError):mtf_rsi.settings({'rsi_htf_2_bullish_min':value})
 def test_preferences(self):
  from . import preferences
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as d:
   values={'rsi-htf-2-enabled':False,'rsi-htf-2-bullish-min':'66','rsi-htf-2-bullish-max':'79'}
   preferences.write(Path(d)/'preferences.json',{'settings':values},1)
   self.assertEqual(preferences.read(Path(d)/'preferences.json')['settings'],values)

 def test_touching_main_ranges(self):
  from .signals import settings
  c=settings(dict(rsi_level_enabled=True,rsi_level_mode='BETWEEN',rsi_bearish_min=35,rsi_bearish_max=40,rsi_bullish_min=40,rsi_bullish_max=70))
  self.assertTrue(mtf_rsi.matches(40,'BULLISH',c))
  self.assertTrue(mtf_rsi.matches(40,'BEARISH',c))
  with self.assertRaises(ValueError):settings(dict(rsi_bearish_max=41,rsi_bullish_min=40))
