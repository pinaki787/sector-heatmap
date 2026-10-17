import importlib.util, unittest
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
spec=importlib.util.spec_from_file_location('sizing',Path(__file__).with_name('manual_brick.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Inputs(unittest.TestCase):
 def test_selected_period_for_all_categories(self):
  for symbol,policy in [('MCX:TEST',{'master_regular_session':'0900-2330'}),('NSE:NIFTYBANK-INDEX',{'master_regular_session':'0915-1530'}),('BSE:TEST',{'master_regular_session':'0915-1530'}),('BTCUSD',{'session_exchange':'CRYPTO'})]:
   for length in [5,7,14]:self.assertEqual(m.rule(symbol,policy,atr_length=str(length))['atr_length'],length)
 def test_verified_session_duration_controls_reference_window_and_divisor(self):
  for symbol,bounds,minutes,divisor in [('NSE:TEST','0915-1530',375,12.5),('BSE:TEST','0915-1530',375,12.5),('MCX:TEST','0900-2330',870,29),('MCX:TEST','0900-2355',895,895/30)]:
   rule=m.rule(symbol,{'master_regular_session':bounds},atr_length=5)
   self.assertEqual(rule['reference_seconds'],minutes*60)
   self.assertEqual(rule['divisor'],divisor)
  for symbol in ['NSE:TEST','BSE:TEST','MCX:TEST']:
   with self.assertRaises(ValueError):m.rule(symbol,{},atr_length=5)
 def test_native_daily_session_reference_excludes_current_session(self):
  from datetime import timezone
  now=datetime(2026,10,16,22,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
  rows=[]
  for day in range(1,17):
   stamp=datetime(2026,10,day,tzinfo=timezone.utc).timestamp()
   rows.append([stamp,100,110,90,105,100])
  rule=m.rule('MCX:TEST',{'master_regular_session':'0900-2330'},atr_length=5)
  value=m.calculate_sessions(rows,rule,now)
  self.assertEqual(value['reference_bars'],15)
  self.assertEqual(value['manual_brick'],round(20/29,2))
  self.assertEqual(value['source_resolution'],'D')
  rows[-1]=[rows[-1][0],100,1,90,105]
  self.assertEqual(m.calculate_sessions(rows,rule,now)['reference_bars'],15)
  with self.assertRaises(ValueError):m.calculate_sessions([[rows[0][0]+60,100,110,90,105]],rule,now)
  with self.assertRaises(ValueError):m.calculate_sessions([[rows[0][0],100,1,90,105]],rule,now)
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
