import unittest
from datetime import datetime,timedelta
from sector_heatmap.rsi_table import IST,session_bounds,period_end,aggregate_6h,RsiTable,TIMEFRAMES
from strategies.ema_crossover.signals import rsi_sma_series

class RsiTableTests(unittest.TestCase):
 def test_six_hour_session_anchor_complete_buckets_and_forming_exclusion(self):
  day=datetime(2026,10,1,9,tzinfo=IST);raw=[[int((day+timedelta(minutes=30*i)).timestamp()),100+i,102+i,99+i,101+i,1] for i in range(29)]
  rows=aggregate_6h(raw,'MCX:CRUDEOILM26OCTFUT',day.replace(hour=20).timestamp())
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['timestamp'],day.timestamp());self.assertEqual(rows[0]['closed_at'],day.replace(hour=15).timestamp());self.assertEqual(rows[0]['close'],112)
  rows=aggregate_6h(raw,'MCX:CRUDEOILM26OCTFUT',day.replace(hour=23,minute=31).timestamp());self.assertEqual(len(rows),3);self.assertEqual(rows[-1]['closed_at'],day.replace(hour=23,minute=30).timestamp())
  with self.assertRaises(ValueError):aggregate_6h(raw[:5]+raw[6:],'MCX:CRUDEOILM26OCTFUT',day.replace(hour=23,minute=31).timestamp())
 def test_nse_anchor_and_short_closing_bucket(self):
  day=datetime(2026,10,1,9,15,tzinfo=IST);raw=[[int((day+timedelta(minutes=30*i)).timestamp()),100,102,99,101,1] for i in range(13)]
  rows=aggregate_6h(raw,'NSE:NIFTY50-INDEX',day.replace(hour=16).timestamp());self.assertEqual(len(rows),2);self.assertEqual(rows[0]['closed_at'],day.replace(hour=15).timestamp());self.assertEqual(rows[1]['closed_at'],day.replace(hour=15,minute=30).timestamp())
 def test_calendar_completion_and_dst_session_close(self):
  day=datetime(2026,10,1,tzinfo=IST);self.assertEqual(period_end('NSE:SBIN-EQ',day.timestamp(),'1M'),datetime(2026,11,1,tzinfo=IST).timestamp());self.assertEqual(period_end('NSE:SBIN-EQ',day.timestamp(),'1W'),datetime(2026,10,5,tzinfo=IST).timestamp());self.assertEqual(session_bounds('MCX:GOLD26DECFUT',datetime(2026,12,1).date())[1].minute,55)
 def test_shared_cache_and_warmup_unavailable(self):
  class Client:
   calls=0
   def history(self,data):self.calls+=1;return {'s':'ok','candles':[]}
  client=Client();service=RsiTable();now=datetime(2026,10,1,20,tzinfo=IST).timestamp()
  first=service.snapshot(client,'NSE:SBIN-EQ',14,14,'SMA',now);self.assertEqual([r['timeframe'] for r in first['rows']],[t[0] for t in TIMEFRAMES]);self.assertTrue(all(r['rsi'] is None and r['status']=='Unavailable' for r in first['rows']));service.snapshot(client,'NSE:SBIN-EQ',14,14,'EMA',now+1);self.assertEqual(client.calls,7)
 def test_selected_ma_exact_values_and_forming_excluded(self):
  now=datetime(2026,10,1,20,tzinfo=IST).timestamp();start=datetime(2026,9,25,9,15,tzinfo=IST)
  raw=[[int((start+timedelta(minutes=5*i)).timestamp()),100,103,97,100+(i%5)-2,1] for i in range(100)]
  raw.append([now,100,1000,99,1000,1])
  class Service(RsiTable):
   def history(self,*args):return raw,now
  for ma in ('SMA','EMA'):
   actual=Service().snapshot(None,'MCX:CRUDEOILM26OCTFUT',14,14,ma,now)['rows'][0];expected=rsi_sma_series([dict(zip(('timestamp','open','high','low','close','volume'),r)) for r in raw[:-1]],14,14,ma)[-1]
   self.assertEqual(actual['rsi'],expected['rsi']);self.assertEqual(actual['rsi_ma'],expected['rsi_ma'])
