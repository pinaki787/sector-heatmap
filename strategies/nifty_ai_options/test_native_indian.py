import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from native_indian import NativeIndianAdapter,NativeIndianExecution
class Native:
 def __init__(self,broker):
  self.broker=broker;self.product='MARGIN' if broker=='DHAN' else 'NORMAL'
  self.service=SimpleNamespace(account=dict(id='a'*32,broker=broker),book=lambda kind:dict(data=[]))
  self.sent=[];self.qty=0;self.partial=False
 def clock(self):return 100
 def contract(self,symbol):return dict(symbol=symbol,broker=self.broker,lot_size=1,tick_size=.05,option_type='CE',expiry='2026-12-16')
 def quote(self,symbol):return dict(symbol=symbol,exchange_at=100,received_at=100,bid=100,ask=101)
 def order(self,symbol,qty,side,quote):return dict(symbol=symbol,qty=qty,side=side,productType=self.product,limitPrice=quote['ask' if side==1 else 'bid'])
 def validate_order(self,order):pass
 def preflight(self,order,config):pass
 def positions(self):return [dict(symbol='NATIVE',productType=self.product,netQty=self.qty)] if self.qty else []
 def orders(self):
  if not self.sent:return []
  p=self.sent[-1]
  return [dict(p,id=str(len(self.sent)),status=6 if self.partial else 2,filledQty=1 if self.partial else p['qty'],tradedPrice=101)]
 def place(self,order):
  self.sent.append(dict(order))
  if not self.partial:self.qty+=order['qty']*order['side']
  return dict(s='ok',id=str(len(self.sent)))
class NativeIndianTests(unittest.TestCase):
 def setUp(self):
  from contextlib import nullcontext
  guard=patch('native_indian.native_entry_admission',side_effect=lambda *args:nullcontext())
  guard.start();self.addCleanup(guard.stop)
 def setup_adapter(self,broker):
  n=Native(broker);config=dict(broker=broker,account='a'*32,underlying='MCX:CRUDE',execution_route='OPTIONS',execution_mode='LIVE',product=n.product,lots=1,timeframe=1)
  adapter=NativeIndianAdapter(config,n);adapter.session=lambda at=None:dict(open=True,opening_minutes=540,closing_minutes=1435)
  return n,config,adapter
 def action(self,name='BUY',at=100):return dict(action=name,timestamp=at,position=dict(symbol='NATIVE',option_type='CE',expiry='2026-12-16',entry_timestamp=90,side='CE'))
 def test_native_paper_order_payload_and_account_scope_for_both_brokers(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as root:
    n,c,a=self.setup_adapter(broker);e=NativeIndianExecution(a,root);self.addCleanup(e.close)
    e.submit(self.action());self.assertEqual(e.state['position']['quantity'],1);self.assertEqual(n.sent,[])
    e.submit(self.action('SELL',101));self.assertIsNone(e.state['position']);self.assertEqual(n.sent,[])
 def test_mocked_live_entry_exit_confirms_actual_position_without_opposite_entry(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as root:
    n,c,a=self.setup_adapter(broker);e=NativeIndianExecution(a,root,live=True);self.addCleanup(e.close)
    e.submit(self.action());self.assertEqual(n.qty,1)
    e.submit(self.action('SELL',101));self.assertEqual(n.qty,0);self.assertIsNone(e.state['position'])
    self.assertEqual([r['side'] for r in n.sent],[1,-1])
 def test_unknown_or_partial_native_fill_blocks_duplicate_and_new_entry(self):
  with tempfile.TemporaryDirectory() as root:
   n,c,a=self.setup_adapter('DHAN');n.partial=True;e=NativeIndianExecution(a,root,live=True);self.addCleanup(e.close)
   with self.assertRaises(RuntimeError):e.submit(self.action())
   with self.assertRaisesRegex(ValueError,'Retained'):e.submit(self.action(at=101))
   self.assertEqual(len(n.sent),1);self.assertEqual(e.state['pending']['stage'],'UNRESOLVED_FILL')
 def test_wrong_account_product_or_alternate_history_fails_closed(self):
  n,c,a=self.setup_adapter('MOTILAL_OSWAL')
  for changes in (dict(account='b'*32),dict(broker='FYERS'),dict(product='MARGIN'),dict(fyers_history_enabled=True)):
   with self.subTest(changes=changes),self.assertRaises((ValueError,PermissionError)):NativeIndianAdapter(dict(c,**changes),n)
 def test_stale_quote_never_submits(self):
  with tempfile.TemporaryDirectory() as root:
   n,c,a=self.setup_adapter('DHAN');n.quote=lambda s:dict(symbol=s,exchange_at=90,received_at=100,bid=100,ask=101)
   e=NativeIndianExecution(a,root,live=True);self.addCleanup(e.close)
   with self.assertRaisesRegex(ValueError,'Fresh'):e.submit(self.action())
   self.assertEqual(n.sent,[]);self.assertIsNone(e.state['pending'])

class NativeSelectionTests(unittest.TestCase):
 setup_adapter=NativeIndianTests.setup_adapter
 def test_atm_selection_requires_paired_same_expiry_and_deterministic_tie(self):
  n,c,a=self.setup_adapter('DHAN');a.config.update(option_moneyness='ATM')
  n.live_price=lambda config,now:(105,now)
  rows=[dict(symbol=side+str(strike),expiry='2026-12-16',strike=strike,option_type=side,broker='DHAN',lot_size=1,tick_size=.05) for strike in (100,110) for side in ('CE','PE')]
  rows.append(dict(rows[0],symbol='UNPAIRED',expiry='2026-12-01'))
  a.option_rows=lambda:rows
  selected=a.select('CE')
  self.assertEqual(selected['symbol'],'CE100')
  self.assertEqual(selected['verified_native_selection']['account'],'a'*32)
  a.config.update(expiry_policy='explicit_listed',expiry='2026-12-01')
  with self.assertRaisesRegex(ValueError,'not currently listed'):a.select('CE')

class NativeGeometryTests(unittest.TestCase):
 def test_native_without_greeks_reuses_existing_geometry_and_requires_bound_contract(self):
  from core import Strategy
  for market in ('NSE','BSE','MCX'):
   for classification in ('ATM','OTM'):
    config=dict(account='a'*32,broker='DHAN',underlying=market+':HOST',market=market,timeframe=1,reference_value=200,option_moneyness=classification)
    engine=Strategy(config)
    contract=dict(symbol='NATIVE',option_type='CE',verified_native_selection=dict(broker='DHAN',account='a'*32,underlying=config['underlying'],symbol='NATIVE'))
    engine.reset_contract(contract)
    legacy=Strategy(dict(config,broker='FYERS'));legacy.reset_contract(dict(symbol='NATIVE',option_type='CE'),.23)
    self.assertEqual(engine.contract['option_brick'],legacy.contract['option_brick'])
    self.assertIsNone(engine.contract['selection_delta'])
    bad=dict(contract,verified_native_selection=dict(contract['verified_native_selection'],account='b'*32))
    with self.assertRaisesRegex(ValueError,'Verified native'):engine.reset_contract(bad)

class NativeSessionAndMappingTests(unittest.TestCase):
 def adapter(self,broker='DHAN',market='MCX'):
  n=Native(broker);n.underlying=lambda symbol:dict(SM_SYMBOL_NAME='CRUDEOILM')
  c=dict(account='a'*32,broker=broker,underlying=market+':HOST',market=market,execution_route='OPTIONS',product=n.product,execution_mode='PAPER',timeframe=1)
  return n,c,NativeIndianAdapter(c,n)
 def stamp(self,value):
  from datetime import datetime
  from zoneinfo import ZoneInfo
  return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
 def test_evening_holiday_short_session_seasonal_and_equity_close(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   n,c,a=self.adapter(broker)
   for time,expected in [('2026-11-24T16:59:00',False),('2026-11-24T17:00:00',True),('2026-12-25T19:00:00',False),('2026-01-01T17:00:00',False),('2026-03-10T23:40:00',False),('2026-11-25T23:40:00',True),('2026-11-25T23:55:00',False)]:
    with self.subTest(broker=broker,time=time):self.assertEqual(a.session(self.stamp(time))['open'],expected)
   for market in ('NSE','BSE'):
    n,c,a=self.adapter(broker,market)
    self.assertTrue(a.session(self.stamp('2026-11-25T15:29:00'))['open']);self.assertFalse(a.session(self.stamp('2026-11-25T15:30:00'))['open'])
 def test_unverified_calendar_or_commodity_cannot_inherit_evening_hours(self):
  n,c,a=self.adapter()
  with self.assertRaisesRegex(ValueError,'calendar'):a.session(self.stamp('2027-01-05T10:00:00'))
  n.underlying=lambda symbol:dict(SM_SYMBOL_NAME='COTTON')
  with self.assertRaisesRegex(ValueError,'category'):a.session(self.stamp('2026-11-25T19:00:00'))
 def test_native_futures_sizing_mapping_uses_verified_selected_contract_metadata(self):
  from native_indian import map_native_host
  common=dict(market='MCX')
  dhan=dict(common,broker='DHAN',underlying='MCX:CRUDEOILM-DEC2026-FUT')
  host=dict(SEM_EXM_EXCH_ID='MCX',SEM_INSTRUMENT_NAME='FUTCOM',SM_SYMBOL_NAME='CRUDEOILM',SEM_EXPIRY_DATE='2026-12-18 00:00:00',SEM_TRADING_SYMBOL='CRUDEOILM-DEC2026-FUT')
  self.assertEqual(map_native_host(dhan,host),'MCX:CRUDEOILMZ2026')
  mo=dict(common,broker='MOTILAL_OSWAL',underlying='MCX:123')
  meta=dict(exchange='MCX',instrument='FUTCOM',underlying='CRUDEOILM',expiry='2026-12-18',token=123)
  self.assertEqual(map_native_host(mo,meta),'MCX:CRUDEOILMZ2026')
  with self.assertRaisesRegex(ValueError,'token'):map_native_host(mo,dict(meta,token=456))
  with self.assertRaisesRegex(ValueError,'identity'):map_native_host(dhan,dict(host,SEM_TRADING_SYMBOL='OTHER'))
 def test_completed_history_retains_real_ohlc_and_unavailable_volume_and_rejects_gaps(self):
  n,c,a=self.adapter(market='NSE');now=self.stamp('2026-11-25T10:01:00');n.clock=lambda:now
  start=self.stamp('2026-11-25T09:30:00')
  rows=[dict(timestamp=start+i*60,open=100,high=102,low=99,close=101,volume=0,volume_available=False) for i in range(30)]
  n.candles=lambda config:rows
  result=a.candles();self.assertEqual(result[0]['high'],102);self.assertIsNone(result[0]['volume'])
  n.clock=lambda:self.stamp('2026-11-25T12:00:00')
  with self.assertRaisesRegex(ValueError,'stale'):a.candles()
  n.clock=lambda:now
  rows.insert(0,dict(rows[0],timestamp=start-120))
  with self.assertRaisesRegex(ValueError,'gap'):a.candles()


class NativeRecoveryTests(unittest.TestCase):
 setup_adapter=NativeIndianTests.setup_adapter
 action=NativeIndianTests.action
 setUp=NativeIndianTests.setUp
 def test_terminal_partial_exit_reconciles_exact_residual_without_resubmit_for_both_brokers(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as root:
    n,c,a=self.setup_adapter(broker);e=NativeIndianExecution(a,root,live=True);self.addCleanup(e.close)
    owned=dict(self.action()['position'],quantity=2,fill_price=101)
    e.state['position']=owned;n.qty=1
    order=dict(symbol='NATIVE',qty=2,side=-1,productType=n.product,orderTag='exact')
    e.state['pending']=dict(payload=order,intent=self.action('SELL'),order_id='one')
    n.orders=lambda:[dict(order,id='one',status=1,filledQty=1,tradedPrice=100)]
    e.reconcile_pending()
    self.assertEqual(e.state['position']['quantity'],1);self.assertIsNone(e.state['pending']);self.assertEqual(n.sent,[])
 def test_full_exit_fill_without_broker_flat_keeps_pending_and_blocks_new_entry(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as root:
    n,c,a=self.setup_adapter(broker);e=NativeIndianExecution(a,root,live=True);self.addCleanup(e.close)
    e.state['position']=dict(self.action()['position'],quantity=1);n.qty=1
    order=dict(symbol='NATIVE',qty=1,side=-1,productType=n.product,orderTag='exact')
    e.state['pending']=dict(payload=order,intent=self.action('SELL'),order_id='one')
    n.orders=lambda:[dict(order,id='one',status=2,filledQty=1,tradedPrice=100)]
    with self.assertRaisesRegex(ValueError,'quantity'):e.reconcile_pending()
    with self.assertRaisesRegex(ValueError,'Retained'):e.submit(self.action(at=102))
    self.assertIsNotNone(e.state['pending']);self.assertEqual(n.sent,[])
 def test_unknown_acknowledgement_never_resends(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as root:
    n,c,a=self.setup_adapter(broker);e=NativeIndianExecution(a,root,live=True);self.addCleanup(e.close)
    e.state['pending']=dict(payload=dict(symbol='NATIVE',qty=1,side=1,productType=n.product,orderTag='unknown'),intent=self.action())
    with self.assertRaisesRegex(ValueError,'uniquely'):e.reconcile_pending()
    self.assertEqual(n.sent,[]);self.assertIsNotNone(e.state['pending'])

class NativeBindingTests(unittest.TestCase):
 def test_registered_selected_brokers_construct_native_adapter_without_auth_or_orders(self):
  import sqlite3
  from native_indian import bound_native
  for broker,product,target in (('DHAN','MARGIN','sector_heatmap.dhan_execution.DhanExecutionService'),('MOTILAL_OSWAL','NORMAL','sector_heatmap.motilal_service.Service')):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as folder:
    root=Path(folder);registry=root/'.private/dashboard-login/registry.sqlite3';registry.parent.mkdir(parents=True)
    with sqlite3.connect(registry) as db:
     db.execute('create table accounts(id text,broker text,live_enabled integer)')
     db.execute('insert into accounts values(?,?,?)',('a'*32,broker,1))
    account=dict(id='a'*32,broker=broker,live_enabled=1)
    account_folder=registry.parent/'accounts'/account['id'];account_folder.mkdir(parents=True)
    service=SimpleNamespace(account=account,folder=account_folder)
    with patch('run.ROOT',root),patch(target,return_value=service) as constructor,patch('sector_heatmap.automation.AutomationPolicyService') as policy,patch.dict('os.environ',{'MOTILAL_ENABLE_LIVE_ORDERS':'0'}):
     policy.return_value.current.return_value={}
     adapter=bound_native(dict(account=account['id'],broker=broker,product=product,underlying='MCX:EXACT',execution_route='OPTIONS'))
    self.assertEqual(adapter.broker,broker);self.assertEqual(adapter.account,account['id']);constructor.assert_called_once()

class NativeAttachmentSelectionTests(unittest.TestCase):
 setup_adapter=NativeIndianTests.setup_adapter
 def test_native_holdings_expose_actual_lots_without_inventing_entry_price(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   n,c,a=self.setup_adapter(broker)
   a.option_rows=lambda:[dict(symbol='NATIVE',lot_size=2,option_type='CE',expiry='2026-12-16')]
   a.books=lambda:([dict(symbol='NATIVE',productType=n.product,netQty=4)],[])
   a.pending_external=lambda symbol:False
   rows=a.candidates()
   self.assertEqual(rows[0]['lots'],2);self.assertIsNone(rows[0]['average_price']);self.assertFalse(rows[0]['entry_cost_available'])
