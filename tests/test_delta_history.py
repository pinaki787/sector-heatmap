import tempfile,unittest,json,csv
from pathlib import Path
from sector_heatmap.delta_history import CandleArchive
class HistoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.a=CandleArchive(self.root/'history.sqlite3',self.root/'mirror');self.addCleanup(self.a.finalizer);self.p={'id':27,'symbol':'BTCUSD','contract_type':'perpetual_futures'}
 def candle(self,t=1000,price=100):return dict(timestamp=t,open=price,high=price+2,low=price-2,close=price+1,volume=10,is_forming=False)
 def test_restart_retains_history_deduplicates_and_separates_contracts_timeframes(self):
  for _ in range(2):self.a.ingest(self.p,'5m',[self.candle()],300,2000)
  option={'id':28,'symbol':'C-BTC-86000-031026','contract_type':'call_options','strike_price':'86000'};self.a.ingest(option,'5m',[self.candle(price=200)],300,2000);self.a.ingest(self.p,'15m',[self.candle(price=110)],900,2000)
  reopened=CandleArchive(self.a.path);self.addCleanup(reopened.finalizer);self.assertEqual(reopened.read('BTCUSD','5m')['count'],1);self.assertEqual(reopened.read(option['symbol'],'5m')['candles'][0]['open'],200);self.assertEqual(reopened.read('BTCUSD','15m')['candles'][0]['open'],110)
 def test_forming_excluded_and_completed_revision_audited(self):
  self.a.ingest(self.p,'5m',[self.candle(),self.candle(t=1900)],300,2000);self.assertEqual(self.a.read('BTCUSD','5m')['count'],1)
  self.a.ingest(self.p,'5m',[self.candle(price=105)],300,2001);data=self.a.read('BTCUSD','5m');self.assertEqual(data['revisions'],1);self.assertEqual(data['candles'][0]['open'],105);self.assertEqual(json.loads(self.a.db.execute('SELECT previous FROM revisions').fetchone()[0]),self.candle())
 def test_conflicting_same_response_and_identity_change_fail_without_overwrite(self):
  self.a.ingest(self.p,'5m',[self.candle()],300,2000)
  with self.assertRaises(ValueError):self.a.ingest(self.p,'5m',[self.candle(),self.candle(price=105)],300,2001)
  with self.assertRaises(ValueError):self.a.ingest({**self.p,'id':999},'5m',[self.candle(price=105)],300,2001)
  self.assertEqual(self.a.read('BTCUSD','5m')['candles'][0]['open'],100)
 def test_mirror_contains_only_public_completed_ohlcv_and_provenance(self):
  self.a.ingest(self.p,'5m',[self.candle()],300,2000);file=self.root/'mirror'/'DeltaIndia_BTCUSD_5m.csv';rows=list(csv.DictReader(file.read_text().splitlines()));self.assertEqual(len(rows),1);self.assertEqual(set(rows[0]),{'timestamp','open','high','low','close','volume'});meta=json.loads(file.with_suffix('.json').read_text());self.assertEqual(meta['environment'],'INDIA_PRODUCTION');self.assertTrue(meta['completed_only']);self.assertEqual(meta['count'],1)
 def test_mirror_failure_preserves_local_data_and_reports_error(self):
  block=self.root/'file';block.write_text('existing');self.a.mirror=block/'child';self.a.ingest(self.p,'5m',[self.candle()],300,2000);self.assertEqual(self.a.read('BTCUSD','5m')['count'],1);self.assertIsNotNone(self.a.mirror_error)
 def test_saved_history_has_no_executable_signal_and_execution_chart_does_not_fallback(self):
  from sector_heatmap.delta_india import DeltaIndia
  b=DeltaIndia(self.root/'paper.json',clock=lambda:2000);self.addCleanup(b.history.finalizer);b.history.ingest(self.p,'5m',[self.candle()],300,2000);data=b.saved_history('BTCUSD');self.assertIsNone(data['last_completed']);self.assertEqual(data['signal_policy'],'SAVED_HISTORY_ANALYSIS_ONLY')
  b.product=lambda _:(_ for _ in ()).throw(ValueError('offline'))
  with self.assertRaisesRegex(ValueError,'offline'):b.chart('BTCUSD')
