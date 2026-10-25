import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from datetime import datetime
from .motilal_history_seed import Seed,IST,source_settings,verified_minutes,aggregate,exact_history_symbol

class HistorySeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.aid='a'*32;self.target=dict(id='b'*32);self.now=datetime(2026,10,15,19,45,tzinfo=IST).timestamp()
        self.meta=dict(symbol='MO:MCX:101',exchange='MCX',underlying='CRUDEOILM',expiry='2026-10-19')
        self.store=Mock();self.store.folder.side_effect=lambda a:self.root/a['id'];self.store.account.return_value=dict(id=self.aid,broker='FYERS')
        folder=self.root/self.aid;master=folder/'source/.private/ema-band-masters/MCX_COM.csv';master.parent.mkdir(parents=True)
        row=['']*17;row[8]=str(datetime(2026,10,19,23,30,tzinfo=IST).timestamp());row[9]='MCX:CRUDEOILM26OCTFUT';row[13]='CRUDEOILM';row[16]='XX';master.write_text(','.join(row))
        token=folder/'home/.fyers/token.json';token.parent.mkdir(parents=True);token.write_text(json.dumps(dict(app_id='TEST',access_token='TEST')))
        import os;os.utime(master,(self.now,self.now))
        self.opening=int(self.now)//300*300-300
        self.client=Mock();self.client.history.return_value=dict(s='ok',candles=[[self.opening+i*60,100,102,99,101,20] for i in range(5)])
        self.seed=Seed(self.store,dict(id='OWNER'),self.target,clock=lambda:self.now,client_factory=lambda a,b:self.client)
        self.config=dict(fyers_history_enabled=True,fyers_history_account_id=self.aid)
    def tearDown(self):self.tmp.cleanup()
    def test_off_makes_no_request_and_cannot_silently_fallback(self):
        with self.assertRaises(ValueError):self.seed.candles(dict(fyers_history_enabled=False),self.meta,60,'09:00')
        self.client.history.assert_not_called()
    def test_exact_symbol_cached_archive_excludes_credentials(self):
        rows=self.seed.candles(self.config,self.meta,60,'09:00');self.assertEqual(len(rows),5)
        self.seed.candles(self.config,self.meta,60,'09:00');self.client.history.assert_called_once()
        args=self.client.history.call_args[0][0];self.assertEqual(args['symbol'],'MCX:CRUDEOILM26OCTFUT');self.assertEqual(args['cont_flag'],'0')
        archive=next((self.root/self.target['id']).rglob('*.json'));text=archive.read_text();self.assertNotIn('access_token',text);self.assertNotIn('TEST',text)
        self.assertEqual(json.loads(text)['source'],'FYERS_EXPLICIT_HISTORY')
    def test_foreign_owner_is_rejected(self):
        self.store.account.side_effect=PermissionError('Other owner')
        with self.assertRaises(PermissionError):self.seed.candles(self.config,self.meta,60,'09:00')
        self.client.history.assert_not_called()
    def test_wrong_contract_month_is_rejected(self):
        with self.assertRaises(ValueError):self.seed.candles(self.config,dict(self.meta,expiry='2026-11-19'),60,'09:00')
        self.client.history.assert_not_called()
    def test_checksum_tampering_is_rejected(self):
        self.seed.candles(self.config,self.meta,60,'09:00');p=next((self.root/self.target['id']).rglob('*.json'));d=json.loads(p.read_text());d['candles'][0]['close']=999;p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):self.seed.candles(self.config,self.meta,60,'09:00')
    def test_gaps_do_not_generate_higher_timeframe_candles(self):
        rows=verified_minutes(self.client.history.return_value['candles'],self.now)
        self.assertEqual(len(aggregate(rows,300,'09:00',self.now)),1);self.assertEqual(aggregate(rows[:2]+rows[3:],300,'09:00',self.now),[])
    def test_bad_ohlc_conflicts_and_forming_bars(self):
        row=[self.opening,100,102,99,101,20]
        with self.assertRaises(ValueError):verified_minutes([row,[self.opening,100,103,99,101,20]],self.now)
        with self.assertRaises(ValueError):verified_minutes([[self.opening,100,98,99,101,20]],self.now)
        self.assertEqual(verified_minutes([[int(self.now)//60*60,100,102,99,101,20]],self.now),[])
    def test_boolean_and_explicit_account_are_required(self):
        with self.assertRaises(ValueError):source_settings(dict(fyers_history_enabled='true'))
        with self.assertRaises(ValueError):source_settings(dict(fyers_history_enabled=True))

    def test_bad_candles_remain_archived_and_only_valid_tail_is_used(self):
        raw=self.client.history.return_value['candles'];raw[1]=[self.opening+60,100,98,99,101,20]
        rows=self.seed.candles(self.config,self.meta,60,'09:00');self.assertEqual(len(rows),3);self.assertGreater(rows[0]['timestamp'],self.opening+60)
        archive=json.loads(next((self.root/self.target['id']).rglob('*.json')).read_text());self.assertEqual(len(archive['rejected_candles']),1);self.assertEqual(len(archive['candles']),4)
    def test_bse_history_alias_requires_exchange_token_family_and_isin(self):
        row=['']*17;row[9]='BSE:RELIANCE-A';row[12]='500325';row[13]='RELIANCE';row[5]='INE002A01018'
        native=dict(exchange='BSE',token=500325,underlying='RELIANCE',isin='INE002A01018',history_symbol='BSE:RELIANCE-EQ')
        self.assertEqual(exact_history_symbol(native,[row]),'BSE:RELIANCE-A')
        with self.assertRaises(ValueError):exact_history_symbol(dict(native,isin='WRONG'),[row])
    def test_duplicate_volume_keeps_prices_but_never_invents_volume(self):
        raw=self.client.history.return_value['candles'];raw.append([self.opening,100,102,99,101,99]);rows=verified_minutes(raw,self.now)
        self.assertEqual(len(rows),5);self.assertIsNone(rows[0]['volume']);self.assertFalse(rows[0]['volume_available'])
        bars=aggregate(rows,300,'09:00',self.now);self.assertEqual(len(bars),1);self.assertIsNone(bars[0]['volume']);self.assertFalse(bars[0]['volume_available'])
    def test_conflicting_price_duplicates_are_recorded_as_gap(self):
        raw=self.client.history.return_value['candles'];raw.append([self.opening,100,103,99,101,20]);rejected=[];rows=verified_minutes(raw,self.now,rejected)
        self.assertEqual(len(rows),4);self.assertEqual(len(rejected),1);self.assertNotIn(self.opening,[r['timestamp'] for r in rows])

    def test_targeted_refetch_repairs_prices_and_retains_original_bad_evidence(self):
        raw=[list(r) for r in self.client.history.return_value['candles']];raw[1]=[self.opening+60,100,98,99,101,20]
        self.client.history.side_effect=[dict(s='ok',candles=raw),dict(s='ok',candles=[[self.opening+60,100,102,99,101,20]])]
        rows=self.seed.candles(self.config,self.meta,60,'09:00');self.assertEqual(len(rows),5)
        d=json.loads(next((self.root/self.target['id']).rglob('*.json')).read_text());self.assertEqual(d['rejected_candles'],[]);self.assertEqual(len(d['original_rejected_candles']),1);self.assertTrue(d['repair_attempts'][0]['repaired'])
        self.assertEqual(self.client.history.call_args[0][0]['range_from'],str(self.opening+60))
