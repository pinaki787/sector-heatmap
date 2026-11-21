import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from grid import RULES,gate
BASE=int(datetime(2026,10,23,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
def rows(sign=1):
 return [dict(timestamp=BASE+i*300,open=1000+sign*i,close=1000+sign*i+.1*sign,
  high=1002+sign*i,low=999+sign*i,host_atr=3,adx=25+i*.1,ema30=1000+sign*i*.3,
  supertrend=1000+sign*i*.5,pine_direction=-sign,box=10,rsi14=60 if sign>0 else 40) for i in range(70)]
class Tests(unittest.TestCase):
 def test_all_declared_rules_return_boolean(self):
  for name in RULES:
   with self.subTest(name=name):self.assertIsInstance(gate(rows(),name,'BULLISH'),bool)
 def test_efficiency_is_symmetric(self):
  name=next(n for n,r in RULES.items() if r['family']=='efficiency' and r['floor']==.8)
  self.assertTrue(gate(rows(),name,'BULLISH'));self.assertTrue(gate(rows(-1),name,'BEARISH'))
 def test_flat_efficiency_blocked(self):
  r=rows()
  for x in r:x['close']=1000
  name=next(n for n,c in RULES.items() if c['family']=='efficiency')
  self.assertFalse(gate(r,name,'BULLISH'))
 def test_volatility_floor_blocks_quiet_market(self):
  r=rows();r[-1]['host_atr']=.3
  name=next(n for n,c in RULES.items() if c['family']=='efficiency' and c['floor']==.8)
  self.assertFalse(gate(r,name,'BULLISH'))
 def test_band_switch_not_slope(self):
  r=rows();r[-1]['pine_direction']=1
  name=next(n for n,c in RULES.items() if c['family']=='st_slope')
  self.assertFalse(gate(r,name,'BULLISH'))
 def test_unknown_rule_rejected(self):
  with self.assertRaises(KeyError):gate(rows(),'unknown','BULLISH')
 def test_warmup_controls_do_not_add_price_conditions(self):
  names=[n for n,c in RULES.items() if c['family']=='warmup_control']
  for n in names:self.assertTrue(gate(rows(),n,'BULLISH'))
 def test_insufficient_history_blocks(self):
  for n,c in RULES.items():
   if c['family']!='baseline':self.assertFalse(gate(rows()[:1],n,'BULLISH'))
if __name__=='__main__':unittest.main()
