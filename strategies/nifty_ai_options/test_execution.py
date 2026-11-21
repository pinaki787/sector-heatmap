import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from execution import Execution
from live import Bars
NOW=1795059900
META=dict(lot_size=65,tick_size=.05,expiry_epoch='1795428600',option_type='CE')
POSITION=dict(symbol='NSE:NIFTY26NOV25850CE',option_type='CE',expiry='1795428600',entry_timestamp=NOW)
ACTION=dict(action='BUY',timestamp=NOW,position=POSITION)
class API:
    def __init__(self):self.sent=[];self.fail=False;self.partial=False;self.exposure=0;self.calls=0
    def positions(self):return dict(s='ok',netPositions=[] if not self.exposure else [dict(symbol=POSITION['symbol'],netQty=self.exposure,productType='MARGIN')])
    def orderbook(self):
        self.calls+=1
        return dict(s='ok',orderBook=[] if not self.sent else [dict(id='id1',status=2,filledQty=20 if self.partial else 65,tradedPrice=40)])
    def funds(self):return dict(s='ok',fund_limit=[dict(id=10,equityAmount=100000)])
    def place_order(self,data):
        self.sent.append(data)
        if self.fail:raise TimeoutError('simulated uncertain transport')
        return dict(s='ok',id='id1')
class Tests(unittest.TestCase):
    def create(self,folder,api,live=False):
        execution=Execution(api,'account',folder,live=live,lots=1,product='MARGIN',master=lambda s:META,account_folder=Path(folder))
        self.addCleanup(execution.close)
        return execution
    def test_paper_never_submits(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();e=self.create(folder,api)
            result=e.submit(ACTION,dict(timestamp=NOW,ltp=40),now=NOW)
            self.assertTrue(result['dry_run']);self.assertEqual(api.sent,[]);self.assertEqual(e.state['position']['quantity'],65)
    def test_stale_quote(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();e=self.create(folder,api)
            with self.assertRaises(ValueError):e.submit(ACTION,dict(timestamp=NOW-6,ltp=40),now=NOW)
            self.assertEqual(api.sent,[])
    def test_uncertain_retained_no_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();api.fail=True;e=self.create(folder,api,True)
            with self.assertRaises(RuntimeError):e.submit(ACTION,dict(timestamp=NOW,ltp=40),now=NOW)
            self.assertEqual(len(api.sent),1)
            self.assertEqual(json.loads(e.path.read_text())['pending']['stage'],'UNCERTAIN')
            with self.assertRaises(ValueError):e.submit(ACTION,dict(timestamp=NOW,ltp=40),now=NOW)
            self.assertEqual(len(api.sent),1)
    def test_uncertain_intent_blocks_a_different_signal_without_resubmission(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();api.fail=True;e=self.create(folder,api,True)
            with self.assertRaises(RuntimeError):e.submit(ACTION,dict(timestamp=NOW,ltp=40),now=NOW)
            with self.assertRaisesRegex(ValueError,'Pending or uncertain'):
                e.submit(dict(ACTION,timestamp=NOW+1),dict(timestamp=NOW+1,ltp=41),now=NOW+1)
            self.assertEqual(len(api.sent),1)

    def test_unresolved_chart_ownership_blocks_entry_before_broker_request(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'chart-trading.sqlite3'
            with sqlite3.connect(path) as db:
                db.execute('create table previews (id text,plan text,state text)')
                db.execute('insert into previews values (?,?,?)',('chart1',json.dumps(dict(account_id=Path(folder).name,broker='FYERS')),'SUBMITTED'))
            api=API();e=self.create(folder,api,True)
            with self.assertRaisesRegex(ValueError,'chart order owns'):
                e.submit(ACTION,dict(timestamp=NOW,ltp=40),now=NOW)
            self.assertEqual(api.sent,[]);self.assertIsNone(e.state['pending'])

    def test_full_fill(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();e=self.create(folder,api,True)
            with patch('execution.time.sleep'):
                result=e.submit(ACTION,dict(timestamp=NOW,ltp=40),now=NOW)
            self.assertEqual(result['filled_quantity'],65)
            self.assertIsNone(e.state['pending'])
    def test_verification_config_cannot_start_monitor(self):
        from live import stream
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory,patch('live.client') as broker:
            path=Path(directory)/'config.json';path.write_text(json.dumps({'_verification_only':True}))
            with self.assertRaisesRegex(ValueError,'Verification-only'):stream(SimpleNamespace(config=str(path),live=False))
            broker.assert_not_called()
    def test_live_capable_buy_and_owned_sell_with_fake_broker(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();e=self.create(folder,api,True)
            with patch('execution.time.sleep'):
                e.submit(ACTION,dict(timestamp=NOW,ltp=40),now=NOW)
                api.exposure=65
                e.submit(dict(ACTION,action='SELL',timestamp=NOW+1),dict(timestamp=NOW+1,ltp=41),now=NOW+1)
            self.assertEqual([p['side'] for p in api.sent],[1,-1]);self.assertIsNone(e.state['position']);self.assertIsNone(e.state['pending'])
    def test_partial_halts(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();api.partial=True;e=self.create(folder,api,True)
            with patch('execution.time.sleep'):
                with self.assertRaises(RuntimeError):e.submit(ACTION,dict(timestamp=NOW,ltp=40),now=NOW)
            self.assertEqual(e.state['pending']['stage'],'UNRESOLVED_FILL')
    def test_exposure_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();api.exposure=65;e=self.create(folder,api,True)
            with self.assertRaises(ValueError):e.submit(ACTION,dict(timestamp=NOW,ltp=40),now=NOW)
            self.assertEqual(api.sent,[])
    def test_mismatched_exit_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            api=API();e=self.create(folder,api)
            with self.assertRaises(ValueError):e.submit(dict(ACTION,action='SELL'),dict(timestamp=NOW,ltp=40),now=NOW)
    def test_bar_close_and_partial_discard(self):
        b=Bars(5)
        self.assertIsNone(b.update(NOW+20,100))
        self.assertIsNone(b.update(NOW+300,101))
        self.assertEqual(b.update(NOW+600,102),(NOW+300,101))
    def test_thirty_minute_options_source_uses_regular_session_anchor(self):
        from datetime import datetime
        from markets import IST
        opening=datetime(2026,11,19,9,15,tzinfo=IST).timestamp()
        bars=Bars(30)
        self.assertIsNone(bars.update(opening,100))
        self.assertIsNone(bars.update(opening+15*60,101))
        self.assertEqual(bars.update(opening+30*60,102),(opening,101))

    def test_gap_halts(self):
        b=Bars(1);b.update(NOW,100)
        with self.assertRaises(ValueError):b.update(NOW+120,101)
if __name__=='__main__':unittest.main(verbosity=2)
