import unittest
from sector_heatmap.delta_journal import snapshot
from sector_heatmap.delta_india import DeltaIndia
from tests import test_delta_india as fixture

class JournalSnapshots(unittest.TestCase):
 def data(self):
  rows=[dict(timestamp=300*(i+1),open=100+i,high=102+i,low=99+i,close=101+i,volume=7,is_forming=False) for i in range(30)]
  rows.append(dict(timestamp=9300,open=1000,high=2000,low=900,close=1500,volume=2,is_forming=True))
  return dict(symbol='BTCUSD',candles=rows)
 def settings(self):return dict(resolution='5m',interval_seconds=300,rsi_length=14,ma_type='EMA',ma_length=9,journal_bb=dict(length=20,deviation=2))
 def test_completed_ohlc_actual_bb_settings_population_deviation_and_manual_reason(self):
  s=snapshot(self.data(),self.settings(),9310,'MANUAL_DISCRETIONARY')
  self.assertEqual(s['candle']['timestamp'],9000);self.assertEqual(s['candle']['open'],129);self.assertEqual(s['rsi'],100);self.assertEqual(s['rsi_ma'],100)
  self.assertEqual(s['bollinger']['middle'],120.5);self.assertAlmostEqual(s['bollinger']['upper'],120.5+2*(33.25**.5))
  self.assertEqual(s['transition'],'MANUAL_NO_ENTRY_SIGNAL');self.assertIsNone(s['signal_price']);self.assertEqual(s['forming_candle_at_observation']['close'],1500)
 def test_research_evidence_completed_atr_momentum_and_bandwidth(self):
  cfg=self.settings()|dict(adx_enabled=True,adx_threshold=32,momentum_enabled=True)
  s=snapshot(self.data(),cfg,9310,'CROSSOVER')
  self.assertTrue(s['adx']['filter_enabled']);self.assertEqual(s['adx']['threshold'],32)
  self.assertTrue(s['momentum']['enabled']);self.assertEqual(s['atr']['value'],3);self.assertEqual(s['atr']['true_range'],3)
  self.assertEqual(len(s['recent_completed_candles']),15);self.assertTrue(all(r['timestamp']<=9000 for r in s['recent_completed_candles']))
  self.assertGreater(s['bollinger']['width_percent'],0);self.assertIsNotNone(s['bollinger']['percent_b'])
 def test_missing_settings_and_missing_historical_signal_do_not_invent_values(self):
  cfg=self.settings();cfg.pop('journal_bb');s=snapshot(self.data(),cfg,9310,'EXPLICIT_CLOSE');self.assertIsNone(s['bollinger']);self.assertIn('not recorded',s['bollinger_unavailable'])
  s=snapshot(self.data(),self.settings(),9600,'OPPOSITE_CROSSOVER',signal_close=123);self.assertIsNone(s['candle']);self.assertEqual(s['capture_kind'],'RECOVERED_HISTORY_OBSERVED_LATER')
 def test_recovered_context_has_observation_time_separate_from_original_candle(self):
  s=snapshot(self.data(),self.settings(),12000,'OPPOSITE_CROSSOVER',signal_close=9300)
  self.assertEqual(s['candle']['timestamp'],9000);self.assertEqual(s['observed_at'],12000);self.assertEqual(s['capture_kind'],'RECOVERED_HISTORY_OBSERVED_LATER')

class JournalLedger(unittest.TestCase):
 setUp=fixture.LiveTests.setUp
 def test_manual_entry_and_partial_exit_context_survive_reload(self):
  data=JournalSnapshots().data();self.b.chart=lambda *a,**k:data|dict(last_completed=None)
  t=self.payload|dict(mode='PAPER',side='LONG',journal_bb=dict(length=20,deviation=2))
  preview=self.b.preview(t);self.b.record_paper(dict(mode='PAPER',preview_id=preview['id']))
  entry=self.b.paper['trades'][0]['entry_context'];self.assertEqual(entry['reason'],'MANUAL_DISCRETIONARY');self.assertEqual(entry['bollinger']['length'],20)
  self.b._paper_reduce(1,'EXPLICIT_REDUCE_ONLY');self.assertEqual(self.b.paper['trades'][0]['exit_fills'][0]['event_context']['reason'],'EXPLICIT_REDUCE_ONLY')
  b=DeltaIndia(self.b.path,credentials=self.creds,requester=self.req,clock=lambda:self.req.now)
  self.assertEqual(b.paper['trades'][0]['entry_context'],entry);self.assertEqual(len(b.paper['trades'][0]['exit_fills']),1);self.assertEqual(b.paper['position']['contracts'],2)
 def test_live_order_context_persisted_before_actual_submission(self):
  self.b.chart=lambda *a,**k:JournalSnapshots().data()|dict(last_completed=None)
  order=self.b.submit(self.payload|dict(journal_bb=dict(length=20,deviation=2)))
  self.assertEqual(order['event_context']['reason'],'MANUAL_DISCRETIONARY');self.assertEqual(order['filled_contracts'],3)
  b=DeltaIndia(self.b.path,credentials=self.creds,requester=self.req,clock=lambda:self.req.now)
  self.assertEqual(b.live['orders'][order['request_id']]['event_context'],order['event_context'])

class PaperResume(unittest.TestCase):
 setUp=fixture.LiveTests.setUp
 def test_resume_retains_position_and_config_and_rejects_live(self):
  from unittest.mock import patch
  cfg=dict(mode='PAPER',symbol='BTCUSD',resolution='5m',rsi_length=14,ma_length=14,ma_type='EMA',contracts=3)
  self.b.live['runner_config']=cfg;self.b.paper['position']={'symbol':'BTCUSD','contracts':2,'entry_price':100}
  held=dict(self.b.paper['position']);self.b.chart=lambda *a:dict(last_completed=dict(timestamp=100))
  with patch('sector_heatmap.delta_india.threading.Thread') as thread:
   self.b.resume_paper_runner();thread.return_value.start.assert_called_once()
  self.assertEqual(self.b.paper['position'],held);self.assertEqual(self.b.runner['config'],cfg)
  self.b.runner['running']=False;self.b.live['runner_config']['mode']='LIVE'
  with self.assertRaises(ValueError):self.b.resume_paper_runner()

 def test_manual_paper_monitor_resume_preserves_one_shot_and_rejects_flat_reentry(self):
  from unittest.mock import patch
  cfg=dict(mode='PAPER',symbol='BTCUSD',resolution='5m',rsi_length=14,ma_length=14,ma_type='EMA',contracts=3,one_shot=True)
  self.b.live['runner_config']=cfg;self.b.paper['position']={'symbol':'BTCUSD','contracts':2,'entry_price':100}
  self.b.chart=lambda *a:dict(last_completed=dict(timestamp=100))
  with patch('sector_heatmap.delta_india.threading.Thread'):self.b.resume_paper_runner()
  self.assertTrue(self.b.runner['config']['one_shot']);self.assertEqual(self.b.paper['position']['contracts'],2)
  self.b.runner['running']=False;self.b.paper['position']=None
  with self.assertRaises(ValueError):self.b.resume_paper_runner()
