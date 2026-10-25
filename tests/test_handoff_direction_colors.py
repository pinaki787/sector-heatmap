import unittest
from sector_heatmap.handoff_cards import direction_palette
class DirectionColors(unittest.TestCase):
 def test_bearish_red(self):
  for value in ("BEARISH","SELL","short"," PE "):
   self.assertEqual(direction_palette(value),("#B4233A","#FFF0F2"))
 def test_bullish_green(self):
  for value in ("BULLISH","BUY","long","CE"):
   self.assertEqual(direction_palette(value),("#167A51","#EDF8F1"))
 def test_wait_neutral(self):
  for value in ("WAIT",None,"UNAVAILABLE"):
   self.assertEqual(direction_palette(value),("#735C24","#FFF8E7"))
