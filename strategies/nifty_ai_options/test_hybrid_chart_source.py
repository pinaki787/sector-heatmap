import unittest,tempfile,json
from pathlib import Path
from chart_source import ChartSource,read_source,_price_cache
class HybridChartTests(unittest.TestCase):
 def setup(self,folder):
  root=Path(folder);owner='a'*32;run='hybrid-offline';d=root/'runs'/owner/run;d.mkdir(parents=True)
  (d/'config.json').write_text(json.dumps(dict(account=owner,timeframe=1,market='CRYPTO',calculation_mode='HYBRID',_verification_only=True)))
  source=ChartSource(d/'chart-source','HYBRID');source.seed('EXACT',1,[[0,100,100,100,100,1]],1)
  return root,owner,run,d,source
 def append(self,source,at,price,seq,available=None):
  source.append_observation(dict(kind='price',symbol='EXACT',timestamp=at,available_at=available or at+.1,close=price,sequence=seq,source_basis='BROKER_LIVE_PRICE'),1)
 def test_captured_forming_ohlc_matches_accepted_prices_and_is_not_labelled_completed(self):
  with tempfile.TemporaryDirectory() as folder:
   root,owner,run,d,s=self.setup(folder)
   self.append(s,61,101,1);self.append(s,62,103,2);self.append(s,63,100,3)
   result=read_source(root,owner,run,'EXACT',1)
   self.assertEqual(result['rows'],[[0,100,100,100,100,1],[60,101,103,100,100,None]])
   self.assertEqual(result['confirmed_through'],0)
   self.assertEqual(result['provisional_at'],60)
   self.assertEqual(result['source_basis'],'BROKER_CONFIRMED_AND_OBSERVED_FORMING')
 def test_repeated_cursor_updates_only_forming_bar_and_rereads_no_unchanged_bytes(self):
  with tempfile.TemporaryDirectory() as folder:
   root,owner,run,d,s=self.setup(folder);self.append(s,61,101,1)
   read_source(root,owner,run,'EXACT',1)
   path=next((d/'chart-source').glob('*-observations.jsonl'));before=_price_cache[(path,'hybrid')]['bytes_read']
   self.assertEqual(read_source(root,owner,run,'EXACT',1,after=60)['rows'],[[60,101,101,101,101,None]])
   self.assertEqual(_price_cache[(path,'hybrid')]['bytes_read'],before)
   self.append(s,62,102,2)
   self.assertEqual(read_source(root,owner,run,'EXACT',1,after=60)['rows'][-1][4],102)
 def test_provider_confirmation_replaces_observed_forming_ohlc(self):
  with tempfile.TemporaryDirectory() as folder:
   root,owner,run,d,s=self.setup(folder);self.append(s,61,101,1)
   s.append(dict(kind='underlying',symbol='EXACT',timestamp=60,open=99,high=102,low=98,close=100,source_basis='PROVIDER_CONFIRMED_CLOSE'),1)
   result=read_source(root,owner,run,'EXACT',1)
   self.assertNotIn('provisional_at',result)
   self.assertEqual(result['rows'][-1],[60,99,102,98,100,None])
 def test_gap_keeps_hybrid_source_waiting_for_previous_confirmation(self):
  with tempfile.TemporaryDirectory() as folder:
   root,owner,run,d,s=self.setup(folder);self.append(s,121,103,1)
   self.assertEqual(read_source(root,owner,run,'EXACT',1)['hybrid_source_state'],'WAITING_FOR_PREVIOUS_CANDLE')
