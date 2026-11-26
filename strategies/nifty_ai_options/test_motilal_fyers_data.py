import sqlite3,tempfile,unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from motilal_fyers_data import source_account,exact_option
class SplitDataTests(unittest.TestCase):
 def test_only_motilal_same_user_fyers_is_allowed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'registry.sqlite3'
   with sqlite3.connect(p) as db:
    db.execute('CREATE TABLE accounts(id TEXT,user_id TEXT,broker TEXT)')
    db.executemany('INSERT INTO accounts VALUES(?,?,?)',[('mo','u','MOTILAL_OSWAL'),('fy','u','FYERS'),('other','v','FYERS'),('dhan','u','DHAN')])
   self.assertEqual(source_account(p,'mo'),'fy')
   with self.assertRaises(PermissionError):source_account(p,'mo','other')
   with self.assertRaises(PermissionError):source_account(p,'dhan')
 def test_multiple_accounts_require_explicit_choice(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'registry.sqlite3'
   with sqlite3.connect(p) as db:
    db.execute('CREATE TABLE accounts(id TEXT,user_id TEXT,broker TEXT)')
    db.executemany('INSERT INTO accounts VALUES(?,?,?)',[('mo','u','MOTILAL_OSWAL'),('a','u','FYERS'),('b','u','FYERS')])
   with self.assertRaises(ValueError):source_account(p,'mo')
   self.assertEqual(source_account(p,'mo','b'),'b')
 def test_option_requires_exact_expiry_strike_side_exchange_and_lot(self):
  stamp=datetime(2026,12,18,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
  row=['']*18
  for i,v in {3:'10',8:str(stamp),9:'MCX:EXACTCE',13:'CRUDEOILM',15:'6000',16:'CE'}.items():row[i]=v
  meta=dict(exchange='MCX',underlying='CRUDEOILM',expiry='2026-12-18',strike=6000,option_type='CE',lot_size=10)
  self.assertEqual(exact_option(meta,[row]),'MCX:EXACTCE')
  for change in [dict(expiry='2026-12-17'),dict(strike=6100),dict(option_type='PE'),dict(lot_size=100),dict(exchange='BSE')]:
   with self.subTest(change=change),self.assertRaises(ValueError):exact_option(dict(meta,**change),[row])
  with self.assertRaises(ValueError):exact_option(meta,[row,row])
 def test_native_exchange_token_resolves_broker_name_alias_without_guessing(self):
  stamp=datetime(2026,11,26,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp();row=['']*18
  for i,v in {3:'20',8:str(stamp),9:'BSE:SENSEX26NOV84000CE',12:'1118969',13:'SENSEX',15:'84000.0',16:'CE'}.items():row[i]=v
  meta=dict(exchange='BSEFO',underlying='BSX',token=1118969,expiry='2026-11-26',strike=84000,option_type='CE',lot_size=20)
  self.assertEqual(exact_option(meta,[row]),row[9])
  with self.assertRaises(ValueError):exact_option(dict(meta,token=1118970),[row])


class DataReadTests(unittest.TestCase):
 def test_completed_cache_is_incremental_and_never_submits_orders(self):
  from motilal_fyers_data import MarketData
  from types import SimpleNamespace
  from unittest.mock import Mock,patch
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'.private/dashboard-login/registry.sqlite3';p.parent.mkdir(parents=True)
   with sqlite3.connect(p) as db:
    db.execute('CREATE TABLE accounts(id TEXT,user_id TEXT,broker TEXT)')
    db.executemany('INSERT INTO accounts VALUES(?,?,?)',[('mo','u','MOTILAL_OSWAL'),('fy','u','FYERS')])
   opening=datetime(2026,11,26,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
   now=[opening+121];api=Mock();native=SimpleNamespace(underlying=lambda s:dict(instrument='INDEX'),session_policy=lambda c:dict(session_open='09:15'))
   cfg=dict(account='mo',broker='MOTILAL_OSWAL',market_data_broker='FYERS',market_data_account='fy')
   data=MarketData(cfg,native,root,client=api,clock=lambda:now[0])
   replies=[dict(s='ok',candles=[[opening,100,101,99,100,1],[opening+60,100,102,100,101,1]]),dict(s='ok',candles=[[opening+120,101,103,101,102,1]])]
   with patch('sector_heatmap.fyers_history.history',side_effect=replies) as fetch:
    rows=data.candles('BSE:SENSEX-INDEX',1)
    self.assertEqual(len(rows),2);self.assertEqual(rows[-1]['broker'],'FYERS');self.assertEqual(rows[-1]['execution_broker'],'MOTILAL_OSWAL')
    data.candles('BSE:SENSEX-INDEX',1);self.assertEqual(fetch.call_count,1)
    now[0]+=60;rows=data.candles('BSE:SENSEX-INDEX',1)
    self.assertEqual(len(rows),3);self.assertEqual(fetch.call_args.args[1]['range_from'],str(int(opening+120)))
   api.place_order.assert_not_called()
 def test_stale_or_wrong_symbol_quote_cannot_be_used(self):
  from motilal_fyers_data import MarketData
  from unittest.mock import Mock
  data=object.__new__(MarketData);data.clock=lambda:100;data.last_quote={};data.symbol=lambda s:s;api=Mock();data.client=api
  for row in [dict(n='OTHER',s='ok',v=dict(lp=10,tt=100)),dict(n='EXACT',s='ok',v=dict(lp=10,tt=90))]:
   api.quotes.return_value=dict(s='ok',d=[row])
   with self.assertRaises(ValueError):data.price('EXACT')
  api.place_order.assert_not_called()

class ExactInstrumentTests(unittest.TestCase):
 def test_future_matches_exchange_token_expiry_lot_even_with_name_alias(self):
  from motilal_fyers_data import exact_instrument
  row=['']*18
  stamp=datetime(2026,12,18,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
  for i,v in {3:'10',8:str(stamp),9:'MCX:CRUDEOILM26DECFUT',12:'123',13:'CRUDEOILM',16:'XX'}.items():row[i]=v
  meta=dict(exchange='MCX',instrument='FUTCOM',underlying='BROKER_ALIAS',token=123,lot_size=10,expiry='2026-12-18')
  self.assertEqual(exact_instrument(meta,[row]),row[9])
  for change in [dict(token=124),dict(lot_size=100),dict(expiry='2026-12-19'),dict(exchange='NSE')]:
   with self.subTest(change=change),self.assertRaises(ValueError):exact_instrument(dict(meta,**change),[row])
  with self.assertRaises(ValueError):exact_instrument(meta,[row,row])
 def test_equity_requires_matching_isin_and_exchange_token(self):
  from motilal_fyers_data import exact_instrument
  row=['']*18
  for i,v in {3:'1',5:'INE123',9:'NSE:EXAMPLE-EQ',12:'321'}.items():row[i]=v
  meta=dict(exchange='NSE',instrument='EQ',token=321,lot_size=1,isin='INE123')
  self.assertEqual(exact_instrument(meta,[row]),row[9])
  for change in [dict(isin='OTHER'),dict(isin=None),dict(token=123)]:
   with self.assertRaises(ValueError):exact_instrument(dict(meta,**change),[row])

class MasterCacheTests(unittest.TestCase):
 def test_distinct_contracts_share_master_parse_and_replacement_is_revalidated(self):
  from motilal_fyers_data import MarketData
  from types import SimpleNamespace
  from unittest.mock import patch
  import csv,time
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);path=root/'source/.private/ema-band-masters/BSE_FO.csv';path.parent.mkdir(parents=True)
   stamp=datetime(2026,12,10,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
   def row(token,lot='20'):
    r=['']*18
    for i,v in {3:lot,8:str(stamp),9:'BSE:EXACT'+str(token),12:str(token),13:'SENSEX',15:'84000',16:'CE'}.items():r[i]=v
    return r
   with path.open('w') as f:csv.writer(f).writerows([row(1),row(2)])
   data=object.__new__(MarketData);data.symbols={};data.folder=root;data.clock=time.time
   data.native=SimpleNamespace(underlying=lambda s:dict(exchange='BSEFO',instrument='OPTIDX',token=int(s),underlying='BSX',expiry='2026-12-10',strike=84000,option_type='CE',lot_size=20))
   original=csv.reader
   with patch('motilal_fyers_data.csv.reader',wraps=original) as parse:
    self.assertEqual(data.symbol('1'),'BSE:EXACT1');self.assertEqual(data.symbol('2'),'BSE:EXACT2')
    self.assertEqual(parse.call_count,1)
    with path.open('w') as f:csv.writer(f).writerows([row(3,'200')])
    with self.assertRaises(ValueError):data.symbol('3')
    self.assertEqual(parse.call_count,2)
