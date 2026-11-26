import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace as NS
from unittest.mock import patch
from motilal_direct import MotilalDirectAPI
class DirectBoundary(unittest.TestCase):
 def fixture(self,folder):
  owner='a'*32;self.now=1795667400
  meta=dict(symbol='MO:NSE:123',broker='MOTILAL_OSWAL',exchange='NSE',token=123,instrument='EQUITY',option_type='EQ',expiry=None,lot_size=1,tick_size=.05,underlying='EXAMPLE',isin='INE0001')
  self.quote=dict(bid=99.95,ask=100.05,ltp=100,exchange_at=self.now,ltp_exchange_at=self.now)
  path=Path(folder);db=sqlite3.connect(path/'intents.sqlite3')
  db.execute('CREATE TABLE intents(full_tag TEXT PRIMARY KEY,native_tag TEXT UNIQUE,body TEXT,state TEXT,order_id TEXT,created REAL)')
  db.execute('CREATE TABLE tickets(state TEXT)')
  @contextmanager
  def connect():
   try:
    with db:yield db
   finally:pass
  self.calls=[]
  def request(endpoint,body):self.calls.append(copy.deepcopy(body));return dict(uniqueorderid='fixture-1')
  service=NS(account=dict(id=owner,broker='MOTILAL_OSWAL'),folder=path,client=NS(profile=lambda:dict(usertype='InvestorClient',products=['VALUEPLUS','NORMAL'],exchanges=['NSE']),request=request),book=lambda kind:dict(data=[]),tickets=NS(db=connect))
  native=NS(service=service,clock=lambda:self.now,underlying=lambda s:dict(meta),quote=lambda s:dict(self.quote),positions=lambda:[],orders=lambda:[],funds=lambda exchange:100000,db=connect,live_enabled=lambda:True)
  config=dict(broker='MOTILAL_OSWAL',account=owner,underlying=meta['symbol'],market='NSE',execution_route='DIRECT',product='INTRADAY',lots=1)
  api=MotilalDirectAPI(native,config);api.adapter=NS(session=lambda:dict(open=True))
  order=api.prepare_order(dict(symbol=meta['symbol'],qty=1,side=1,type=2,productType='INTRADAY',limitPrice=0,stopPrice=0,validity='DAY',offlineOrder=False,orderTag='nai-fixture'))
  state_path=path/owner/'direct-live.json';state_path.parent.mkdir()
  e=NS(api=api,broker='MOTILAL_OSWAL',product='INTRADAY',lots=1,live=True,path=state_path,state=dict(position=None,pending=dict(stage='PREPARED',payload=order,intent=dict(action='OPEN_LONG'))))
  e.save=lambda:state_path.write_text(json.dumps(e.state));e.save()
  return api,native,e,order,db
 def test_prepared_buy_sell_are_market_near_tick_aligned_and_durable_before_post(self):
  with tempfile.TemporaryDirectory() as d:
   a,n,e,o,db=self.fixture(d)
   self.assertEqual(o['limitPrice'],100.10);self.assertEqual(a.payload(o)['producttype'],'VALUEPLUS');self.assertEqual(a.payload(o)['orderduration'],'IOC')
   sell=a.prepare_order(dict(o,side=-1));self.assertEqual(sell['limitPrice'],99.90)
   self.assertFalse(self.calls)
   a.bind(e);self.assertEqual(a.place_order(data=o)['id'],'fixture-1')
   self.assertEqual(e.state['pending']['stage'],'SUBMITTING')
   self.assertEqual(db.execute('select state from intents').fetchone()[0],'ACKNOWLEDGED')
   with self.assertRaises(PermissionError):a.place_order(data=o)
   self.assertEqual(len(self.calls),1)
 def test_moved_depth_and_stale_original_bound_block_without_repricing(self):
  with tempfile.TemporaryDirectory() as d:
   a,n,e,o,db=self.fixture(d);a.bind(e)
   self.quote['ask']=101
   with self.assertRaisesRegex(ValueError,'outside original cap'):a.place_order(data=o)
   self.assertEqual(self.calls,[])
   self.quote['ask']=100.05;self.now+=6
   with self.assertRaises(ValueError):a.place_order(data=o)
   self.assertEqual(self.calls,[])
 def test_unknown_result_cannot_be_repeated_after_restart(self):
  with tempfile.TemporaryDirectory() as d:
   a,n,e,o,db=self.fixture(d);a.bind(e)
   def fail(endpoint,body):self.calls.append(body);raise TimeoutError('unknown fixture')
   n.service.client.request=fail
   with self.assertRaises(TimeoutError):a.place_order(data=o)
   self.assertEqual(db.execute('select state from intents').fetchone()[0],'UNCERTAIN')
   e.state['pending']['stage']='PREPARED';e.save()
   with self.assertRaisesRegex(ValueError,'reconciliation'):a.place_order(data=o)
   self.assertEqual(len(self.calls),1)
 def test_short_close_requires_exact_negative_quantity_and_buys_only_owned_amount(self):
  with tempfile.TemporaryDirectory() as d:
   a,n,e,o,db=self.fixture(d);a.bind(e)
   e.state['position']=dict(symbol=o['symbol'],quantity=1,side='SHORT');e.state['pending']['intent']['action']='CLOSE_SHORT';e.save()
   n.positions=lambda:[dict(symbol=o['symbol'],netQty=-2,productType='VALUEPLUS')]
   with self.assertRaisesRegex(ValueError,'ownership'):a.place_order(data=o)
   n.positions=lambda:[dict(symbol=o['symbol'],netQty=-1,productType='VALUEPLUS')]
   self.assertEqual(a.place_order(data=o)['id'],'fixture-1');self.assertEqual(self.calls[0]['buyorsell'],'BUY')
 def test_unbound_disk_tampering_and_external_open_orders_block(self):
  with tempfile.TemporaryDirectory() as d:
   a,n,e,o,db=self.fixture(d)
   with self.assertRaises(PermissionError):a.place_order(data=o)
   a.bind(e);e.path.write_text('{}')
   with self.assertRaises(PermissionError):a.place_order(data=o)
   e.save();n.service.book=lambda kind:dict(data=[dict(exchange='NSE',symboltoken=123,orderstatus='PARTIAL')])
   with self.assertRaises(ValueError):a.place_order(data=o)
   self.assertFalse(self.calls)
class UnitMapping(unittest.TestCase):
 def test_mcx_lot_conversion_requires_explicit_native_units_and_exact_expiry_token(self):
  from motilal_fyers_data import exact_instrument
  from datetime import datetime
  from zoneinfo import ZoneInfo
  expiry=int(datetime(2026,12,4,23,55,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
  row=['']*17;row[3]='1';row[8]=str(expiry);row[9]='MCX:GOLDM26DECFUT';row[12]='575011';row[16]='XX'
  meta=dict(exchange='MCX',token=575011,instrument='FUTCOM',expiry='2026-12-04',lot_size=100,native_quantity_unit='LOTS',order_quantity_multiplier=100)
  with self.assertRaises(ValueError):exact_instrument(meta,[row])
  self.assertEqual(exact_instrument(meta,[row],native_lots=True),row[9])
  for changes in (dict(token=999),dict(expiry='2026-12-05'),dict(order_quantity_multiplier=1),dict(native_quantity_unit='UNITS')):
   with self.assertRaises(ValueError):exact_instrument(dict(meta,**changes),[row],native_lots=True)
 def test_bounded_tick_buffer_rejects_unlimited_values(self):
  from motilal_direct_proposal import propose
  meta=dict(symbol='MO:NSE:1',broker='MOTILAL_OSWAL',instrument='EQUITY',lot_size=1,tick_size=.05)
  q=dict(symbol=meta['symbol'],broker='MOTILAL_OSWAL',account='a'*32,bid=100,ask=100.05,exchange_at=100)
  args=dict(side='BUY',quantity=1,account='a'*32,now=100)
  self.assertEqual(propose(meta,q,buffer_ticks=2,**args)['limit_price'],100.15)
  for ticks in (True,0,6,100,.5):
   with self.assertRaises(ValueError):propose(meta,q,buffer_ticks=ticks,**args)
class SharedRuntime(unittest.TestCase):
 def test_motilal_paper_runtime_reverses_only_after_flat_without_native_orders(self):
  from motilal_direct_adapter import MotilalDirectAdapter
  from dhan_direct_runtime import make_executor,Runtime
  from reversal import advance
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);fixture=DirectBoundary();api,n,unused,order,db=fixture.fixture(d)
   n.account_identity='fixture';n.start=lambda:None;n.subscribe=lambda *args:None
   config=dict(api.config,execution_mode='PAPER',timeframe=1,runtime_session='b'*32,reference_value=200,calculation_mode='CANDLES',entry_gate='underlying_flip',exit_supertrend='underlying',signal_source='UNDERLYING',indicator_length=5,indicator_factor=3)
   adapter=object.__new__(MotilalDirectAdapter);adapter.config=config;adapter.native=n;adapter.account=config['account'];adapter.broker=config['broker'];adapter.product=config['product'];adapter.api=api;api.adapter=adapter
   adapter.market_data=NS(price=lambda symbol:(100,n.clock()))
   now=int(n.clock());adapter.candles=lambda *args,**kwargs:[dict(timestamp=now-(30-i)*60,open=100+i,high=102+i,low=99+i,close=101+i,volume=1) for i in range(30)]
   (root/'config.json').write_text(json.dumps(config))
   executor=make_executor(config,adapter,state_dir=root/'runtime')
   runtime=Runtime(config,root,adapter,executor,clock=n.clock,engine_factory=lambda engine,*args,**kwargs:engine)
   try:
    self.assertEqual(executor.broker,'MOTILAL_OSWAL');self.assertIsNone(executor.state['position'])
    runtime.source_ready=True;runtime.submit(runtime.engine.manual_entry('LONG',now))
    self.assertEqual(executor.state['position']['side'],'LONG')
    runtime.engine.pending_direction=('SHORT',now+1);runtime.engine.under_result=dict(direction=1)
    runtime.submit(runtime.engine.exit(now+1,'AI_RENKO_SUPERTREND_UNDERLYING')[0])
    self.assertIsNone(executor.state['position']);self.assertIsNotNone(executor.state['pending_reversal'])
    advance(runtime.engine,executor,runtime.submit)
    self.assertEqual(executor.state['position']['side'],'SHORT');self.assertEqual(fixture.calls,[])
   finally:runtime.close();executor.close()
class Precheck(unittest.TestCase):
 def test_pre_submit_rejection_cannot_leave_an_unknown_order_lock(self):
  from direct_execution import DirectExecution
  with tempfile.TemporaryDirectory() as d:
   fixture=DirectBoundary();a,n,unused,o,db=fixture.fixture(d)
   x=DirectExecution(a,a.config['account'],Path(d)/'runtime',live=True,lots=1,product='INTRADAY',master=a.master,margin=a.margin,broker='MOTILAL_OSWAL')
   a.bind(x);a.place_order=lambda **kw:(_ for _ in ()).throw(ValueError('Fresh depth moved; no post'))
   p=dict(symbol=o['symbol'],underlying=o['symbol'],execution_route='DIRECT',side='LONG',entry_timestamp=n.clock())
   action=dict(action='OPEN_LONG',timestamp=n.clock(),position=p)
   try:
    with self.assertRaisesRegex(ValueError,'no post'):x._submit(action,a.quote(),True,1,n.clock())
    self.assertIsNone(x.state['pending']);self.assertEqual(x.state['failed_intents'][-1]['stage'],'NOT_SUBMITTED');self.assertEqual(fixture.calls,[])
   finally:x.close()
class PreviewMapping(unittest.TestCase):
 def test_direct_preview_preserves_fyers_chart_identity_and_motilal_execution_owner(self):
  import ui_bridge
  adapter=NS(metadata=lambda symbol:dict(symbol=symbol),market_data=NS(symbol=lambda symbol:'NSE:EXAMPLE-EQ',account='f'*32))
  reference=dict(broker='MOTILAL_OSWAL',execution_route='DIRECT',underlying='MO:NSE:123',reference_value=None)
  with patch('native_indian.bound_native',return_value=adapter):
   result=ui_bridge.option_preview('a'*32,reference)
  self.assertEqual(result['underlying'],'MO:NSE:123');self.assertEqual(result['account_id'],'a'*32)
  self.assertEqual(result['market_data_underlying'],'NSE:EXAMPLE-EQ');self.assertEqual(result['market_data_account'],'f'*32)
  self.assertEqual(result['contracts'],{});self.assertEqual(result['orders_submitted'],0)
