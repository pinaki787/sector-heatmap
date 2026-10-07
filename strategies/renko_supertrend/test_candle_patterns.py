import unittest
from .candle_patterns import matches

def bars(pairs):
    return [dict(timestamp=i*60,open=o,close=c,high=max(o,c)+1,low=min(o,c)-1) for i,(o,c) in enumerate(pairs)]
class PatternTests(unittest.TestCase):
    def test_engulfing_harami_and_star_symmetric(self):
        for pairs,name in [([(104,100),(99,105)],'ENGULFING'),([(104,100),(101,103)],'HARAMI'),([(120,100),(98,100),(100,112)],'STAR_INTRADAY')]:
            bull=matches(bars(pairs),True,{})
            bear=matches(bars([(200-o,200-c) for o,c in pairs]),False,{})
            self.assertTrue(any(name in p for p in bull),bull);self.assertTrue(any(name in p for p in bear),bear)
            self.assertEqual(matches(bars(pairs),False,{}),[])
    def test_doji_equal_body_and_same_direction_do_not_engulf(self):
        for pairs in [[(104,100),(104,100)],[(104,100),(100,104)],[(104,100),(102,102)],[(100,104),(99,105)]]:
            self.assertEqual(matches(bars(pairs),True,{}),[])
    def test_harami_requires_body_inside_not_just_wicks(self):
        self.assertEqual(matches(bars([(104,100),(99,103)]),True,{}),[])
    def test_selected_pattern_is_respected(self):
        self.assertEqual(matches(bars([(104,100),(101,103)]),True,dict(retest_harami=False)),[])
    def test_star_requires_small_middle_and_midpoint_recovery(self):
        for pairs in [[(120,100),(98,110),(100,112)],[(120,100),(98,100),(100,109)]]:
            self.assertNotIn('MORNING_STAR_INTRADAY',matches(bars(pairs),True,{}))
