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
