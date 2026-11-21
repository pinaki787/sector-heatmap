import unittest
from .signals import settings
from .rsi_level import apply
class RsiLevelTests(unittest.TestCase):
    def test_strict_thresholds_and_warmup(self):
        cfg=settings(dict(rsi_level_enabled=True,rsi_bullish_above=55))
        for direction,value,passing in [('BULLISH',55,False),('BULLISH',55.1,True),('BEARISH',40,False),('BEARISH',39.9,True),('BULLISH',None,False),('BEARISH',45,False)]:
            entry=dict(entry_qualified=True,entry_direction=direction)
            apply(entry,{},dict(rsi14=value),direction,cfg)
            self.assertEqual(entry['entry_qualified'],passing)
            self.assertEqual(entry['rsi_level_pass'],passing)
    def test_disabled_preserves_entry(self):
        entry=dict(entry_qualified=True)
        apply(entry,{},dict(rsi14=None),'BULLISH',settings({}))
        self.assertTrue(entry['entry_qualified'])
    def test_validation(self):
        for payload in [dict(rsi_bullish_above=float('nan')),dict(rsi_bearish_below=101),dict(rsi_bullish_above=40),dict(rsi_level_enabled=1)]:
            with self.assertRaises(ValueError):settings(payload)

    def test_saved_preferences_preserve_levels(self):
        import tempfile
        from pathlib import Path
        from .preferences import write,read
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            fields={'rsi-level-enabled':True,'rsi-bullish-above':55,'rsi-bearish-below':35}
            write(path,{'settings':fields},1)
            self.assertEqual(read(path)['settings'],fields)
    def test_level_only_direction(self):
        from .indicator_selection import qualify
        cfg=settings(dict(supertrend_enabled=False,ema_fast_enabled=False,ema_slow_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,rsi_level_enabled=True))
        self.assertEqual(qualify(cfg,100,100,100,0,True,False,None,{'rsi14':51})[:2],(-1,True))
        self.assertEqual(qualify(cfg,100,100,100,0,True,False,None,{'rsi14':39})[:2],(1,True))
        self.assertFalse(qualify(cfg,100,100,100,0,True,False,None,{'rsi14':45})[1])


class RsiRangeTests(__import__('unittest').TestCase):
    def test_inclusive_bounds_and_neutral_gap(self):
        from .rsi_level import matches,apply
        from .signals import settings
        c=settings(dict(rsi_level_enabled=True,rsi_level_mode='BETWEEN'))
        for direction,lo,hi in [('BULLISH',60,80),('BEARISH',35,40)]:
            for value in (lo,(lo+hi)/2,hi):self.assertTrue(matches(value,direction,c))
            for value in (lo-.01,hi+.01,None,float('nan')):self.assertFalse(matches(value,direction,c))
            entry=dict(entry_qualified=True,entry_direction=direction)
            apply(entry,{},dict(rsi14=lo-.01),direction,c)
            self.assertFalse(entry['entry_qualified'])
        self.assertFalse(matches(50,'BULLISH',c))
        self.assertFalse(matches(50,'BEARISH',c))
    def test_invalid_ranges(self):
        from .signals import settings
        for payload in [dict(rsi_level_mode='BAD'),dict(rsi_bullish_min=81),dict(rsi_bearish_max=61),dict(rsi_bullish_max=float('nan'))]:
            with self.assertRaises(ValueError):settings(payload)
    def test_rsi_only_direction(self):
        from .signals import settings
        from .indicator_selection import qualify
        c=settings(dict(rsi_level_enabled=True,rsi_level_mode='BETWEEN',supertrend_enabled=False,ema_fast_enabled=False,ema_slow_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False))
        for value,direction in [(60,-1),(80,-1),(35,1),(40,1),(50,0),(90,0)]:
            self.assertEqual(qualify(c,100,100,100,0,True,True,None,dict(rsi14=value))[0],direction)
    def test_preferences_roundtrip(self):
        import tempfile
        from .preferences import write,read
        with tempfile.TemporaryDirectory() as folder:
            path=folder+'/prefs.json'
            fields={'rsi-level-mode':'BETWEEN','rsi-bullish-min':62,'rsi-bullish-max':78,'rsi-bearish-min':32,'rsi-bearish-max':38}
            write(path,{'settings':fields},1)
            self.assertEqual(read(path)['settings'],fields)
