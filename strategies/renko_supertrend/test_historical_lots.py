import csv,io,json,tempfile,unittest
from datetime import datetime,date
from pathlib import Path
from .historical_lots import archive_master,HistoricalLots,checked_lot,IST
def at(day):return datetime(2026,10,day,11,tzinfo=IST).timestamp()
def contract():return dict(symbol='NSE:NIFTY26O1923100CE',strike=23100,expiry='2026-10-19',option_type='CE')
def body(lot=65):
    r=['101126101947167','NIFTY 19 Oct 26 23100 CE','14',str(lot),'0.05','','0915-1530','2026-10-09',str(int(datetime(2026,10,19,15,30,tzinfo=IST).timestamp())),contract()['symbol'],'10','11','47167','NIFTY','26000','23100.0','CE']
    stream=io.StringIO();csv.writer(stream).writerow(r);return stream.getvalue()
class LotPolicy(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def test_exact_contract_date_hash_and_provenance(self):
        m=archive_master(self.root,'NSE_FO',body(),at(16));result=HistoricalLots(self.root).resolve(contract(),at(16));self.assertEqual(result['lot_size'],65);p=result['lot_size_provenance'];self.assertEqual((p['effective_from'],p['effective_to'],p['snapshot_as_of']),('2026-10-16',)*3);self.assertEqual(p['source_sha256'],m['source_sha256']);self.assertEqual(p['source_row'],1);self.assertEqual(checked_lot(dict(contract(),**result),at(16)),65)
    def test_today_and_prior_snapshots_not_projected(self):
        archive_master(self.root,'NSE_FO',body(65),at(11));archive_master(self.root,'NSE_FO',body(75),at(25));resolver=HistoricalLots(self.root);r=resolver.resolve(contract(),at(16));self.assertIsNone(r['lot_size']);self.assertEqual(len(r['lot_size_gap']['available_exact_contract_snapshots']),2)
    def test_lot_regime_change_is_date_specific(self):
        archive_master(self.root,'NSE_FO',body(65),at(16));archive_master(self.root,'NSE_FO',body(75),at(17));r=HistoricalLots(self.root);self.assertEqual(r.resolve(contract(),at(16))['lot_size'],65);self.assertEqual(r.resolve(contract(),at(17))['lot_size'],75)
    def test_conflict_or_corrupt_master_withholds_lot(self):
        archive_master(self.root,'NSE_FO',body(65),at(16));archive_master(self.root,'NSE_FO',body(75),at(16));self.assertIsNone(HistoricalLots(self.root).resolve(contract(),at(16))['lot_size'])
    def test_tampered_object_is_not_trusted(self):
        m=archive_master(self.root,'NSE_FO',body(),at(16));(self.root/m['source_file']).write_text(body(100));self.assertIsNone(HistoricalLots(self.root).resolve(contract(),at(16))['lot_size'])
    def test_wrong_contract_metadata_not_substituted(self):
        archive_master(self.root,'NSE_FO',body(),at(16));c=contract();c['symbol']='NSE:NIFTY26O1923150CE';self.assertIsNone(HistoricalLots(self.root).resolve(c,at(16))['lot_size'])
    def test_bad_lot_and_future_row_rejected(self):
        for value in (0,-1,65.5):
            with tempfile.TemporaryDirectory() as d:
                archive_master(d,'NSE_FO',body(value),at(16));self.assertIsNone(HistoricalLots(d).resolve(contract(),at(16))['lot_size'])
    def test_archival_failure_does_not_break_live_master_refresh(self):
        from unittest.mock import patch
        from sector_heatmap.master_cache_maintenance import maintain
        from . import historical_lots
        with patch.object(historical_lots,'archive_master',side_effect=OSError('Fixture archive unavailable')):
            status=maintain([self.root],lambda url:body()*101,now=at(16))
        self.assertTrue((self.root/'.private/ema-band-masters/NSE_FO.csv').exists());self.assertTrue(status[self.root]['healthy']);self.assertEqual(status[self.root]['historical_archive']['NSE_FO']['status'],'FAILED')
    def test_explicit_sourced_period_can_cover_different_snapshot_date(self):
        m=archive_master(self.root,'NSE_FO',body(),at(11));raw={'contracts':{contract()['symbol']:dict(contract(),lot_size=65,effective_from='2026-10-09',effective_to='2026-10-19')}}
        evidence=self.root/'data/backtesting/fyers-contract-masters/evidence/declared-period.json';evidence.parent.mkdir();evidence.write_text(json.dumps(raw))
        from .historical_lots import digest
        manifest=next((self.root/'data/backtesting/fyers-contract-masters/manifests').glob('*/NSE_FO-*.json'));m['contract_validity']={contract()['symbol']:dict(source_url='https://public.fyers.in/sym_details/dated-metadata-fixture.json',source_file=str(evidence.relative_to(self.root)),source_sha256=digest(evidence.read_bytes()))};manifest.write_text(json.dumps(m))
        r=HistoricalLots(self.root).resolve(contract(),at(16));self.assertEqual(r['lot_size'],65);self.assertEqual(r['lot_size_provenance']['effective_from'],'2026-10-09');self.assertEqual(checked_lot(dict(contract(),**r),at(16)),65)
        self.assertIsNone(HistoricalLots(self.root).resolve(contract(),at(20))['lot_size'])
    def test_plain_lot_without_dated_proof_rejected(self):self.assertIsNone(checked_lot(dict(contract(),lot_size=65),at(16)))
if __name__=='__main__':unittest.main()
