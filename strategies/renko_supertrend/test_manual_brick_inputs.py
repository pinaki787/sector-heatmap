import importlib.util, unittest
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
spec=importlib.util.spec_from_file_location('sizing',Path(__file__).with_name('manual_brick.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Inputs(unittest.TestCase):
 def test_selected_period_for_all_categories(self):
  for symbol,policy in [('MCX:TEST',{'master_regular_session':'0900-2330'}),('NSE:NIFTYBANK-INDEX',{}),('BSE:TEST',{}),('BTCUSD',{'session_exchange':'CRYPTO'})]:
   for length in [5,7,14]:self.assertEqual(m.rule(symbol,policy,atr_length=str(length))['atr_length'],length)
 def test_invalid_period_rejected(self):
  for length in [None,True,'',0,-1,1.5,'nan','inf',101]:
   with self.assertRaises(ValueError):m.rule('MCX:TEST',{'master_regular_session':'0900-2330'},atr_length=length)
 def test_selected_period_changes_wilder_result(self):
  now=datetime(2026,10,14,9,tzinfo=ZoneInfo('Asia/Kolkata'));rows=[]
  for day in range(10):
   opening=(now-timedelta(days=10-day)).timestamp();high=102 if day<7 else 120
   for n in range(29):rows.append(dict(timestamp=opening+n*1800,open=100,high=high,low=99,close=101))
  results=[]
  for length in [5,7]:
   rule=m.rule('MCX:TEST',{'master_regular_session':'0900-2330'},atr_length=length)
   out=m.calculate(rows,rule,1800,now.timestamp());results.append(out['manual_brick'])
   self.assertEqual(out['manual_brick'],round(out['reference_atr']/29,2))
  self.assertNotEqual(*results)
if __name__=='__main__':unittest.main()
