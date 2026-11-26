import json,tempfile,unittest
from pathlib import Path
from chart_source import ChartSource,read_source
from process_state import recover

class ChartSourceTests(unittest.TestCase):
    def setup_run(self,root):
        owner='a'*32;run='verification-seed';directory=root/'runs'/owner/run
        directory.mkdir(parents=True)
        (directory/'config.json').write_text(json.dumps(dict(account=owner,timeframe=1,_verification_only=True)))
        return owner,run,directory,ChartSource(directory/'chart-source')
    def test_exact_consumed_closes_and_fixed_brick_are_preserved_without_fake_ohlc(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);owner,run,directory,source=self.setup_run(root)
            seed=source.seed('EXACT',1,[[0,1,2,1,1.5,10],[60,1.5,3,1,2,10]],.25)
            source.append(dict(symbol='EXACT',kind='underlying',timestamp=120,close=3,source_basis='PROVIDER_CONFIRMED_CLOSE'),1)
            result=read_source(root,owner,run,'EXACT',1)
            self.assertEqual(result['rows'],[[0,None,None,None,1.5,None],[60,None,None,None,2,None],[120,None,None,None,3,None]])
            self.assertEqual(result['seed_sha256'],seed['seed_sha256']);self.assertEqual(result['brick'],.25)
            self.assertFalse(result['ohlc_available']);self.assertTrue(result['verification_only'])
            self.assertEqual(read_source(root,owner,run,'EXACT',1,after=60)['rows'],[[120,None,None,None,3,None]])
            self.assertEqual(recover(owner,root),(None,None))

    def test_wrong_owner_run_path_symbol_and_timeframe_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);owner,run,directory,source=self.setup_run(root)
            source.seed('EXACT',1,[[0,None,None,None,1,None]],.25)
            for bad_run,symbol,frame in [('../escape','EXACT',1),(run,'OTHER',1),(run,'EXACT',5)]:
                with self.assertRaises(ValueError):read_source(root,owner,bad_run,symbol,frame)
            with self.assertRaises(ValueError):read_source(root,'not-an-owner',run,'EXACT',1)

    def test_stream_hints_and_revised_closes_cannot_rewrite_chart_history(self):
        with tempfile.TemporaryDirectory() as folder:
            source=ChartSource(folder);source.seed('EXACT',1,[[60,None,None,None,1,None]],.25)
            with self.assertRaisesRegex(ValueError,'provider-confirmed'):source.append(dict(symbol='EXACT',timestamp=120,close=2),1)
            with self.assertRaisesRegex(ValueError,'revision/conflict'):source.append(dict(symbol='EXACT',timestamp=60,close=2,source_basis='PROVIDER_CONFIRMED_CLOSE'),1)
            self.assertEqual(json.loads(source.path('EXACT',1).read_text())['rows'],[[60,None,None,None,1,None]])

    def test_live_chart_replays_seed_then_exact_ordered_prices_not_later_candle_closes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);owner,run,directory,source=self.setup_run(root)
            source.seed('EXACT',1,[[0,None,None,None,100,None]],1)
            source.append(dict(symbol='EXACT',timestamp=60,close=999,source_basis='PROVIDER_CONFIRMED_CLOSE'),1)
            for sequence,at,price in [(1,75.1234,101),(2,75.1256,102)]:
                source.append_observation(dict(kind='price',symbol='EXACT',timestamp=75,available_at=at,close=price,sequence=sequence,source_basis='BROKER_LIVE_PRICE'),1)
            result=read_source(root,owner,run,'EXACT',1)
            self.assertEqual(result['source_basis'],'BROKER_SEED_AND_LIVE_PRICE')
            self.assertEqual([r[4] for r in result['rows']],[100,101,102])
            self.assertEqual([r[0] for r in read_source(root,owner,run,'EXACT',1,after=75.1234)['rows']],[75.1256])

    def test_incremental_reader_only_reads_appended_bytes_and_retains_partial_line(self):
        import chart_source as module
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);owner,run,directory,source=self.setup_run(root)
            source.seed('EXACT',1,[[0,None,None,None,100,None]],1)
            source.append_observation(dict(kind='price',symbol='EXACT',timestamp=75,available_at=75.1,close=101,sequence=1,source_basis='BROKER_LIVE_PRICE'),1)
            read_source(root,owner,run,'EXACT',1)
            path=next((directory/'chart-source').glob('*-observations.jsonl'))
            first=module._price_cache[path]['bytes_read']
            self.assertEqual(read_source(root,owner,run,'EXACT',1,after=75.1)['rows'],[])
            self.assertEqual(module._price_cache[path]['bytes_read'],first)
            event=dict(kind='price',symbol='EXACT',timestamp=76,available_at=76.1,close=102,sequence=2,source_basis='BROKER_LIVE_PRICE')
            encoded=json.dumps(event)
            with path.open('a') as out:out.write(encoded[:10])
            self.assertEqual(read_source(root,owner,run,'EXACT',1,after=75.1)['rows'],[])
            with path.open('a') as out:out.write(encoded[10:]+'\n')
            self.assertEqual(read_source(root,owner,run,'EXACT',1,after=75.1)['rows'],[[76.1,None,None,None,102,None]])
            self.assertEqual(module._price_cache[path]['sequence'],2)

    def test_contract_reseed_discards_prior_live_observations_but_size_rebuild_can_preserve_them(self):
        with tempfile.TemporaryDirectory() as folder:
            source=ChartSource(folder);rows=[[0,None,None,None,100,None]]
            source.seed('EXACT',1,rows,1)
            source.append_observation(dict(kind='price',symbol='EXACT',timestamp=75,available_at=75.1,close=101,sequence=1,source_basis='BROKER_LIVE_PRICE'),1)
            ledger=next(Path(folder).glob('*-observations.jsonl'))
            source.seed('EXACT',1,rows,2,preserve_observations=True);self.assertTrue(ledger.exists())
            source.seed('EXACT',1,rows,2);self.assertFalse(ledger.exists())

class CandleChartSourceTests(unittest.TestCase):
 def test_real_ohlc_seed_and_completed_updates_ignore_intrabar_price(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);owner='a'*32;run='candle-source';directory=root/'runs'/owner/run
   directory.mkdir(parents=True)
   (directory/'config.json').write_text(json.dumps(dict(account=owner,timeframe=1,_verification_only=True,calculation_mode='CANDLES')))
   source=ChartSource(directory/'chart-source',calculation_mode='CANDLES')
   source.seed('EXACT',1,[[0,100,103,99,102,5]],1)
   source.append_observation(dict(kind='price',symbol='EXACT',timestamp=75,available_at=75.1,close=999,sequence=1,source_basis='BROKER_LIVE_PRICE'),1)
   source.append(dict(kind='underlying',symbol='EXACT',timestamp=60,open=102,high=104,low=101,close=103,volume=8,source_basis='PROVIDER_CONFIRMED_CLOSE'),1)
   result=read_source(root,owner,run,'EXACT',1)
   self.assertTrue(result['ohlc_available'])
   self.assertEqual(result['rows'],[[0,100,103,99,102,5],[60,102,104,101,103,8]])
   self.assertEqual(result['source_basis'],'PROVIDER_CONFIRMED_OHLC')
   with self.assertRaisesRegex(ValueError,'revision/conflict'):
    source.append(dict(kind='underlying',symbol='EXACT',timestamp=60,open=102,high=105,low=101,close=103,source_basis='PROVIDER_CONFIRMED_CLOSE'),1)
 def test_candles_cannot_manufacture_ohlc_from_close_only(self):
  with tempfile.TemporaryDirectory() as folder:
   source=ChartSource(folder,calculation_mode='CANDLES')
   with self.assertRaises(ValueError):source.seed('EXACT',1,[[0,None,None,None,100,None]],1)
