import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from price_action import gate
BASE=int(datetime(2026,10,23,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def rows():
 high=[102,103,106,104,103,104,107,105,104,105,108,106,105,106,109,107,106,107,110,108]
 return [dict(timestamp=BASE+i*300,high=h,low=h-3,close=h-1) for i,h in enumerate(high)]
class Tests(unittest.TestCase):
 def test_confirmed_bullish_structure(self):self.assertTrue(gate(rows(),'PA_HHHL2','BULLISH'))
 def test_confirmed_bearish_structure(self):
  r=[dict(x,high=200-x['low'],low=200-x['high'],close=200-x['close']) for x in rows()]
  self.assertTrue(gate(r,'PA_HHHL2','BEARISH'))
 def test_opposite_structure_blocked(self):self.assertFalse(gate(rows(),'PA_HHHL2','BEARISH'))
 def test_flat_overlap_blocked(self):
  r=[dict(timestamp=BASE+i*300,high=102,low=99,close=100) for i in range(10)]
  self.assertFalse(gate(r,'PA_OVERLAP04','BULLISH'))
 def test_warmup(self):self.assertFalse(gate(rows()[:4],'PA_HHHL2','BULLISH'))
 def test_empty(self):self.assertFalse(gate([],'PA_HHHL2','BULLISH'))
if __name__=='__main__':unittest.main()
