import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
from zoneinfo import ZoneInfo
from dhan_direct import DhanDirectAPI,direct_metadata
class Client:
 client_id='client'
 def __init__(self):self.calls=[];self.unknown=False
 def request(self,method,path,body=None):
  self.calls.append((method,path,copy.deepcopy(body)))
  if path=='/fundlimit':return dict(dhanClientId='client',availableBalance=100000)
  if path=='/margincalculator':return dict(totalMargin=5000)
  if path=='/ip/getIP':return dict(primaryIP='127.0.0.1')
  if path=='/orders':
   if self.unknown:raise TimeoutError('fixture unknown')
   return dict(orderId='fixture-order')
  raise AssertionError(path)
class DhanDirectTests(unittest.TestCase):
 def fixture(self,folder):
  now=datetime(2026,11,26,10,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
  row=dict(SEM_SEGMENT='E',SEM_EXM_EXCH_ID='NSE',SEM_SMST_SECURITY_ID='123',SEM_INSTRUMENT_NAME='EQUITY')
  client=Client();native=SimpleNamespace(service=SimpleNamespace(account=dict(id='a'*32,broker='DHAN'),egress=lambda:'127.0.0.1'),clock=lambda:now,_rows=lambda:[row],_segment=lambda r:'NSE_EQ',underlying=lambda s:row)
  native._meta=lambda r:dict(symbol='NSE_EQ:123',security_id='123',exchange_segment='NSE_EQ',lot_size=1,tick_size=.05,quantity_multiplier=1)
  native.authenticated_client=lambda:client;native.live_enabled=lambda:True
  native._market=lambda meta:dict(bid=99,ask=101,last_price=100,exchange_at=now,received_at=now)
  native.positions=lambda:[];native.orders=lambda:[]
  config=dict(broker='DHAN',account='a'*32,underlying='NSE:EXAMPLE',market='NSE',execution_route='DIRECT',product='INTRADAY',lots=1)
  api=DhanDirectAPI(native,config)
  order=dict(symbol=config['underlying'],qty=1,side=1,type=2,productType='INTRADAY',limitPrice=0,stopPrice=0,validity='DAY',offlineOrder=False,orderTag='nai-fixture')
  path=Path(folder)/'state'/config['account']/'direct-live.json';path.parent.mkdir(parents=True,exist_ok=True)
  executor=SimpleNamespace(api=api,broker='DHAN',product='INTRADAY',lots=1,live=True,path=path,state=dict(position=None,pending=dict(stage='PREPARED',payload=order,intent=dict(action='OPEN_LONG',position=dict(side='LONG',symbol=config['underlying'])))))
  executor.save=lambda:path.write_text(json.dumps(executor.state));executor.save()
  return api,native,client,executor,order,row
 def test_market_intraday_payload_and_margin_use_exact_native_contract_without_placement(self):
  with tempfile.TemporaryDirectory() as d:
   api,n,c,e,o,r=self.fixture(d);body=api.payload(o)
   self.assertEqual((body['securityId'],body['exchangeSegment'],body['orderType'],body['productType'],body['price']),('123','NSE_EQ','MARKET','INTRADAY',0))
   self.assertEqual(api.margin(o),5000);self.assertEqual(api.funds()['fund_limit'][0]['equityAmount'],100000)
   self.assertFalse(any(path=='/orders' for _,path,_ in c.calls))
 def test_submission_requires_exact_persisted_intent_and_cannot_repeat(self):
  with tempfile.TemporaryDirectory() as d:
   api,n,c,e,o,r=self.fixture(d)
   with self.assertRaises(PermissionError):api.place_order(data=o)
   api.bind(e)
   self.assertEqual(api.place_order(data=o)['id'],'fixture-order')
   self.assertEqual(e.state['pending']['stage'],'SUBMITTING')
   with self.assertRaises(PermissionError):api.place_order(data=o)
   self.assertEqual(sum(path=='/orders' for _,path,_ in c.calls),1)
 def test_unknown_acknowledgement_and_changed_exposure_never_retries(self):
  with tempfile.TemporaryDirectory() as d:
   api,n,c,e,o,r=self.fixture(d);api.bind(e)
   n.positions=lambda:[dict(symbol='NSE_EQ:123',netQty=1,productType='INTRADAY')]
   with self.assertRaisesRegex(ValueError,'signed quantity'):api.place_order(data=o)
   self.assertFalse(any(path=='/orders' for _,path,_ in c.calls))
   n.positions=lambda:[];c.unknown=True
   with self.assertRaises(TimeoutError):api.place_order(data=o)
   with self.assertRaises(PermissionError):api.place_order(data=o)
   self.assertEqual(sum(path=='/orders' for _,path,_ in c.calls),1)
 def test_wrong_product_tampered_disk_and_closed_venue_block_submission(self):
  with tempfile.TemporaryDirectory() as d:
   api,n,c,e,o,r=self.fixture(d)
   with self.assertRaises(ValueError):api.payload(dict(o,productType='CNC'))
   api.bind(e);e.path.write_text('{}')
   with self.assertRaises(PermissionError):api.place_order(data=o)
   e.save();api.session=lambda:dict(open=False)
   with self.assertRaisesRegex(ValueError,'venue is closed'):api.place_order(data=o)
   self.assertFalse(any(path=='/orders' for _,path,_ in c.calls))
 def test_master_rejects_index_option_missing_or_expired_future(self):
  with tempfile.TemporaryDirectory() as d:
   api,n,c,e,o,r=self.fixture(d)
   for changes in [dict(SEM_SEGMENT='I'),dict(SEM_SEGMENT='D',SEM_INSTRUMENT_NAME='OPTSTK'),dict(SEM_SEGMENT='D',SEM_INSTRUMENT_NAME='FUTSTK',SEM_EXPIRY_DATE='2026-01-01')]:
    prior=dict(r);r.update(changes)
    with self.assertRaises(ValueError):direct_metadata(n,'NSE:EXAMPLE')
    r.clear();r.update(prior)

 def test_one_snapshot_is_reused_within_one_second_then_refreshed(self):
  from unittest.mock import Mock
  with tempfile.TemporaryDirectory() as d:
   api,n,c,e,o,r=self.fixture(d);clock=[n.clock()];n.clock=lambda:clock[0]
   n._market=Mock(side_effect=lambda meta:dict(bid=99,ask=101,last_price=100,exchange_at=clock[0],received_at=clock[0]))
   api.quote();api.quote();api.margin(o);self.assertEqual(n._market.call_count,1)
   clock[0]+=1;api.quote();self.assertEqual(n._market.call_count,2)

class DhanDirectSearchTests(unittest.TestCase):
 def test_stock_future_filtering_excludes_indices_and_options_before_limit(self):
  from dhan_direct import search_direct
  now=datetime(2026,11,26,10,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
  rows=[dict(SEM_SMST_SECURITY_ID=str(i),SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='D',SEM_INSTRUMENT_NAME='OPTIDX',SEM_TRADING_SYMBOL='NIFTY OPTION',SEM_EXPIRY_DATE='2026-12-10') for i in range(100)]
  rows.extend([dict(SEM_SMST_SECURITY_ID='200',SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='D',SEM_INSTRUMENT_NAME='FUTIDX',SEM_TRADING_SYMBOL='NIFTY FUT',SEM_EXPIRY_DATE='2026-12-10'),
   dict(SEM_SMST_SECURITY_ID='201',SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='I',SEM_INSTRUMENT_NAME='INDEX',SEM_TRADING_SYMBOL='NIFTY'),
   dict(SEM_SMST_SECURITY_ID='202',SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='E',SEM_INSTRUMENT_NAME='EQUITY',SEM_TRADING_SYMBOL='NIFTYETF')])
  def segment(r):return 'NSE_'+{'D':'FNO','E':'EQ','I':'INDEX'}[r['SEM_SEGMENT']]
  n=SimpleNamespace(clock=lambda:now,_rows=lambda:rows,_segment=segment,_meta=lambda r:dict(symbol=segment(r)+':'+r['SEM_SMST_SECURITY_ID'],lot_size=1,tick_size=.05))
  self.assertEqual([r['symbol'] for r in search_direct(n,'NIFTY','NSE_FUTURE')],['NSE_FNO:200'])
  self.assertEqual([r['symbol'] for r in search_direct(n,'NIFTY','NSE_EQUITY')],['NSE_EQ:202'])
  self.assertEqual(search_direct(n,'NIFTY','NSE_INDEX'),[])

class DhanDirectSizingMappingTests(unittest.TestCase):
 def test_native_ids_use_exact_exchange_token_and_explicit_master_asset(self):
  from native_indian import map_native_host
  host=dict(SEM_EXM_EXCH_ID='NSE',SEM_SMST_SECURITY_ID='200',SEM_INSTRUMENT_NAME='FUTIDX',SM_SYMBOL_NAME='NIFTY',SEM_EXPIRY_DATE='2026-12-10')
  config=dict(broker='DHAN',underlying='NSE_FNO:200')
  self.assertEqual(map_native_host(config,host),'NSE:NIFTYZ2026')
  with self.assertRaises(ValueError):map_native_host(dict(config,underlying='NSE_FNO:201'),host)
  with self.assertRaises(ValueError):map_native_host(config,dict(host,SM_SYMBOL_NAME=None))
  self.assertEqual(map_native_host(dict(broker='DHAN',underlying='NSE_EQ:202'),dict(SEM_EXM_EXCH_ID='NSE',SEM_SMST_SECURITY_ID='202',SEM_INSTRUMENT_NAME='EQUITY',SEM_SEGMENT='E',SEM_TRADING_SYMBOL='TCS')),'NSE:TCS')

class DirectProductTests(unittest.TestCase):
 def test_delivery_keeps_long_only_and_futures_reject_delivery(self):
  with tempfile.TemporaryDirectory() as folder:
   api,n,c,e,o,row=DhanDirectTests().fixture(folder)
   with self.assertRaisesRegex(ValueError,'supported product'):DhanDirectAPI(n,dict(api.config,product='CNC'))
   row.update(SEM_SEGMENT='D',SEM_INSTRUMENT_NAME='FUTSTK',SEM_EXPIRY_DATE='2026-12-10')
   with self.assertRaisesRegex(ValueError,'supported product'):DhanDirectAPI(n,dict(api.config,product='CNC'))
   future=DhanDirectAPI(n,dict(api.config,product='MARGIN'))
   self.assertEqual(future.payload(dict(o,productType='MARGIN'))['productType'],'MARGIN')
