import unittest,tempfile,json
from pathlib import Path
from .chart_source import _band_tail,_band_cache,_price_tail,_price_cache
class SessionCacheTests(unittest.TestCase):
 def test_same_inode_rewritten_longer_signal_file_uses_fresh_session(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'signals.jsonl'
   p.write_text(json.dumps(dict(available_at=1,value=1))+'\n')
   self.assertEqual(_band_tail(p,None,epoch='old')[0]['value'],1)
   p.write_text(json.dumps(dict(available_at=2,value=1000000000000000000000))+'\n')
   self.assertEqual(_band_tail(p,None,epoch='new')[0]['value'],1000000000000000000000)
 def test_bad_complete_line_never_partially_mutates_cached_prefix(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'signals.jsonl';p.write_text('{"available_at":1}\n')
   _band_tail(p,None,epoch='run')
   with p.open('a') as f:f.write('{"available_at":2}\nBAD\n')
   with self.assertRaises(ValueError):_band_tail(p,None,epoch='run')
   self.assertEqual(len(_band_cache[(p,'run')]['rows']),1)
 def test_same_inode_reseeded_observations_do_not_reuse_old_byte_offset(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'observations.jsonl'
   def event(at,price):return dict(symbol='BTCUSD',available_at=at,close=price,sequence=1,source_basis='BROKER_LIVE_PRICE')
   p.write_text(json.dumps(event(2,100))+'\n')
   self.assertEqual(_price_tail(p,'BTCUSD',1,None,epoch='old')[0][0][4],100)
   p.write_text(json.dumps(event(3,10000000000000000000))+'\n')
   self.assertEqual(_price_tail(p,'BTCUSD',1,None,epoch='new')[0][0][4],10000000000000000000)
