import csv,gzip,io,json,tempfile,unittest
from pathlib import Path
from .test_historical_lots import at,contract,body
from .historical_lots import HistoricalLots,checked_lot,archive_master
from .nse_contract_lots import archive,source_url,contract_date
def master(**changes):
    row=dict(StockNm='NIFTY26O1923100CE',FinInstrmId='47167',FinInstrmNm='OPTIDX',TckrSymb='NIFTY',XpryDt='1476887400',StrkPric='2310000',OptnTp='CE',MinLot='65',NewBrdLotQty='65',StartDt='1473984000');row.update(changes)
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(row));w.writeheader();w.writerow(row);return gzip.compress(s.getvalue().encode())
class NseLots(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def stage(self,day='2026-10-16',**changes):return archive(self.root,day,master(**changes),source_url(day))
    def test_exact_contract_and_nse_encoding_and_audit(self):
        m=self.stage();r=HistoricalLots(self.root).resolve(contract(),at(16));p=r['lot_size_provenance'];self.assertEqual(r['lot_size'],65);self.assertEqual(checked_lot(dict(contract(),**r),at(16)),65);self.assertEqual(p['source_sha256'],m['source_sha256']);self.assertEqual(p['exchange_token'],'47167');self.assertEqual(p['source_row'],2);self.assertEqual(contract_date('1476887400'),'2026-10-19')
    def test_date_filename_and_no_implicit_regime_projection(self):
        self.stage();self.assertIsNone(HistoricalLots(self.root).resolve(contract(),at(17))['lot_size'])
        with self.assertRaises(ValueError):archive(self.root,'2026-10-16',master(),source_url('2026-10-17'))
    def test_exact_symbol_strike_side_and_expiry_must_agree(self):
        for change in ({'StockNm':'NIFTY26O1923150CE'},{'StrkPric':'2315000'},{'OptnTp':'PE'},{'XpryDt':'1477578600'}):
            with tempfile.TemporaryDirectory() as d:
                archive(d,'2026-10-16',master(**change),source_url('2026-10-16'));self.assertIsNone(HistoricalLots(d).resolve(contract(),at(16))['lot_size'])
    def test_lot_fields_conflict_fractional_nonpositive_rejected(self):
        for change in ({'MinLot':'75'},{'NewBrdLotQty':'65.5'},{'MinLot':'0','NewBrdLotQty':'0'},{'NewBrdLotQty':'NaN'}):
            with tempfile.TemporaryDirectory() as d:
                archive(d,'2026-10-16',master(**change),source_url('2026-10-16'));self.assertIsNone(HistoricalLots(d).resolve(contract(),at(16))['lot_size'])
    def test_corrupt_object_and_cross_provider_conflict_fail_closed(self):
        m=self.stage();archive_master(self.root,'NSE_FO',body(75),at(16));self.assertIsNone(HistoricalLots(self.root).resolve(contract(),at(16))['lot_size'])
        (self.root/m['source_file']).write_bytes(master(NewBrdLotQty='75'));self.assertIsNone(HistoricalLots(self.root).resolve(contract(),at(16))['lot_size'])
    def test_broker_and_exchange_agreement_resolves_same_lot(self):
        self.stage();archive_master(self.root,'NSE_FO',body(65),at(16));r=HistoricalLots(self.root).resolve(contract(),at(16));self.assertEqual(r['lot_size'],65);self.assertEqual(r['lot_size_provenance']['provider'],'NSE_MII_CONTRACT_MASTER')
    def test_html_redirect_or_wrong_schema_not_archived(self):
        with self.assertRaises((OSError,ValueError)):archive(self.root,'2026-10-16',b'<html>unavailable</html>',source_url('2026-10-16'))
if __name__=='__main__':unittest.main()
