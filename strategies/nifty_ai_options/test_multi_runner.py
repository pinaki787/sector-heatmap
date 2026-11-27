import json,tempfile,unittest,multiprocessing,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from strategies.nifty_ai_options.multi_runner import *
from strategies.nifty_ai_options.direct_execution import DirectExecution
from strategies.nifty_ai_options.process_state import recover
from strategies.nifty_ai_options.run import atomic

def lock_probe(data,owner,out):
 with account_lock(owner,Path(data)):out.put(time.monotonic())

class MultiRunner(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.data=Path(self.tmp.name);self.owner='a'*32
 def config(self,symbol='MCX:GOLD-FUT',owner=None,mode='PAPER'):
  return dict(account=owner or self.owner,broker='FYERS',underlying=symbol,runner_scope=scope(symbol),execution_mode=mode,execution_route='DIRECT',lots=1,product='INTRADAY')
 def executor(self,symbol,owner=None):
  c=self.config(symbol,owner);root=runtime_root(c,self.data)
  api=Mock();master=Mock(return_value=dict(product_type='FUTURE',expiry_epoch=999999,lot_size=10,tick_size=.05))
  e=DirectExecution(api,c['account'],root,lots=1,product='INTRADAY',master=master)
  configure_executor(e,c,self.data);self.addCleanup(e.close)
  return e
 def action(self,symbol,name='OPEN_LONG'):
  return dict(action=name,timestamp=100 if name.startswith('OPEN') else 101,position=dict(symbol=symbol,underlying=symbol,execution_route='DIRECT',side='LONG',entry_timestamp=100,spot_brick=1,lot_size=10))
 def trade(self,e,symbol,name='OPEN_LONG'):
  return e.submit(self.action(symbol,name),dict(timestamp=100 if name.startswith('OPEN') else 101,ltp=100),now=100 if name.startswith('OPEN') else 101)
 def test_two_actual_paper_executors_same_account_different_instruments(self):
  a=self.executor('MCX:GOLD-FUT');b=self.executor('MCX:SILVER-FUT')
  self.trade(a,'MCX:GOLD-FUT');self.trade(b,'MCX:SILVER-FUT')
  self.assertNotEqual(a.path,b.path);self.assertEqual(a.state['position']['symbol'],'MCX:GOLD-FUT')
  self.trade(a,'MCX:GOLD-FUT','CLOSE_LONG')
  self.assertIsNone(a.state['position']);self.assertIsNotNone(b.state['position']);a.api.place_order.assert_not_called();b.api.place_order.assert_not_called()
 def test_same_instrument_exclusive_lock_and_scope_tamper(self):
  a=self.executor('MCX:GOLD-FUT')
  with self.assertRaises(BlockingIOError):self.executor('MCX:GOLD-FUT')
  c=self.config();c['runner_scope']=scope('MCX:OTHER')
  with self.assertRaisesRegex(ValueError,'scope'):runtime_root(c,self.data)
 def test_distinct_runners_cannot_own_same_traded_contract(self):
  a=self.executor('NSE:NIFTY50-INDEX');b=self.executor('NSE:NIFTYBANK-INDEX')
  a.state['position']=dict(symbol='NSE:SHAREDOPTION',quantity=10,fill_price=20);a.save()
  action=self.action('NSE:SHAREDOPTION')
  with self.assertRaisesRegex(ValueError,'Another runner owns'):b.submit(action,dict(timestamp=100,ltp=100),now=100)
  b.api.place_order.assert_not_called()
 def test_unknown_unidentified_pending_blocks_account_but_identified_other_can_proceed_paper(self):
  a=self.executor('MCX:GOLD-FUT');b=self.executor('MCX:SILVER-FUT')
  a.state['pending']=dict(stage='UNKNOWN');a.save()
  with self.assertRaisesRegex(ValueError,'Unidentified'):self.trade(b,'MCX:SILVER-FUT')
  a.state['pending']=dict(intent=self.action('MCX:GOLD-FUT'),stage='UNKNOWN');a.save()
  self.trade(b,'MCX:SILVER-FUT');self.assertIsNotNone(b.state['position']);self.assertEqual(a.state['pending']['stage'],'UNKNOWN')
 def test_partial_closing_detached_and_stop_exposure_still_owns_contract(self):
  a=self.executor('MCX:GOLD-FUT');b=self.executor('MCX:SILVER-FUT')
  p=dict(symbol='MCX:SILVER-FUT',quantity=3,fill_price=100)
  for key,value in [('position',p),('detached_position',p),('stop_verification_position',p),('closing_legs',{'x':dict(position=p,pending=dict(intent=dict(position=p)))})]:
   a.state={key:value};a.save()
   with self.assertRaisesRegex(ValueError,'Another runner owns'):self.trade(b,'MCX:SILVER-FUT')
 def test_other_account_does_not_block(self):
  a=self.executor('MCX:GOLD-FUT');b=self.executor('MCX:GOLD-FUT','b'*32)
  a.state['pending']=dict(stage='UNKNOWN');a.save();self.trade(b,'MCX:GOLD-FUT')
 def test_legacy_paths_preserved_and_retained_ownership_blocks_migration(self):
  c=self.config();c.pop('runner_scope');self.assertEqual(runtime_root(c,self.data),self.data/'runtime')
  atomic(self.data/'runtime'/self.owner/'delta-live.json',dict(pending=dict(key='unknown')))
  with self.assertRaisesRegex(ValueError,'Legacy'):assert_start(self.config(),self.data)
 def test_run_identity_cannot_select_another_instrument_or_account(self):
  d=self.data/'runs'/self.owner/'run-1';atomic(d/'config.json',self.config())
  self.assertEqual(selected_symbol(self.owner,dict(run_id='run-1'),self.data),'MCX:GOLD-FUT')
  with self.assertRaises(ValueError):selected_symbol(self.owner,dict(run_id='run-1',runner_symbol='MCX:SILVER-FUT'),self.data)
  with self.assertRaises(ValueError):selected_symbol(self.owner,dict(run_id='../run-1'),self.data)
 def test_recover_and_inventory_are_instrument_scoped(self):
  for name,sym in [('run-1','MCX:GOLD-FUT'),('run-2','MCX:SILVER-FUT')]:
   atomic(self.data/'runs'/self.owner/name/'config.json',self.config(sym))
  a,_=recover(self.owner,self.data,instrument='MCX:GOLD-FUT');self.assertEqual(a['id'],'run-1')
  self.assertEqual(len(inventory(self.owner,self.data)),2)
 def test_pending_reservation_survives_and_is_not_arbitrarily_released(self):
  class Fake:
   live=True
   def __init__(me):
    me.runner_config=self.config(mode='LIVE');me.runner_data=self.data;me.path=runtime_root(me.runner_config,self.data)/self.owner/'direct-live.json';me.state={};me.lots=1
   def save(me):atomic(me.path,me.state)
   @coordinated_submit
   def submit(me,action,quote):
    me.state['pending']=dict(stage='UNKNOWN',intent=action);me.save();raise RuntimeError('Unknown ack')
  f=Fake()
  with self.assertRaises(RuntimeError):f.submit(self.action('MCX:GOLD-FUT'),dict(ask=100))
  self.assertEqual(f.state['entry_reservation']['fill_price'],100)
  pending=list(positions(json.loads(f.path.read_text())))[0];self.assertEqual(reserve(pending),1020)
 def test_conservative_funding_reserves_other_legs_and_never_sends_when_insufficient(self):
  a=self.executor('MCX:GOLD-FUT');a.state['position']=dict(symbol='MCX:GOLD-FUT',quantity=10,fill_price=100);a.save()
  class Fake:
   live=True
   def __init__(me):
    me.runner_config=self.config('MCX:SILVER-FUT',mode='LIVE');me.runner_data=self.data;me.path=runtime_root(me.runner_config,self.data)/self.owner/'direct-live.json';me.state={};me.lots=1;me.sent=False
   def save(me):atomic(me.path,me.state)
   @coordinated_submit
   def submit(me,action,quote):me.sent=True
  # Seed LIVE ledger for the other account-owned instrument.
  atomic(a.path.with_name('direct-live.json'),a.state)
  f=Fake()
  with patch('strategies.nifty_ai_options.multi_runner.available',return_value=(1000,'INR')):
   with self.assertRaisesRegex(ValueError,'funds insufficient'):f.submit(self.action('MCX:SILVER-FUT'),dict(ask=100))
  self.assertFalse(f.sent)
 def test_account_entry_lock_serializes_processes(self):
  ctx=multiprocessing.get_context('fork');q=ctx.Queue()
  with account_lock(self.owner,self.data):
   p=ctx.Process(target=lock_probe,args=(str(self.data),self.owner,q));p.start();time.sleep(.1);self.assertTrue(q.empty());released=time.monotonic()
  p.join(3);self.assertEqual(p.exitcode,0);self.assertGreaterEqual(q.get(timeout=1),released)

 def test_exit_does_not_wait_for_another_instrument_entry_lock(self):
  a=self.executor('MCX:GOLD-FUT');self.trade(a,'MCX:GOLD-FUT')
  with account_lock(self.owner,self.data):self.trade(a,'MCX:GOLD-FUT','CLOSE_LONG')
  self.assertIsNone(a.state['position'])
 def test_start_capacity_counts_preparing_workers_and_duplicate_instrument(self):
  from strategies.nifty_ai_options.process_state import fingerprint
  import os
  for i in range(4):
   c=self.config('MCX:FUT'+str(i));d=self.data/'runs'/self.owner/('run-'+str(i))
   atomic(d/'config.json',c);atomic(d/'launching.json',dict(at=time.time(),pid=os.getpid(),start_ticks=fingerprint(os.getpid())))
  with self.assertRaisesRegex(ValueError,'capacity'):assert_start(self.config(),self.data)
  (self.data/'runs'/self.owner/'run-3'/'launching.json').unlink()
  assert_start(self.config(),self.data)
  with self.assertRaisesRegex(ValueError,'active runner'):assert_start(self.config('MCX:FUT0'),self.data)
 def test_journal_query_is_filtered_by_underlying_without_cross_position_pnl(self):
  from strategies.nifty_ai_options.trade_journal import connect,report
  db=connect(self.data,self.owner)
  for symbol,run in [('MCX:GOLD-FUT','run-1'),('MCX:SILVER-FUT','run-2')]:
   db.execute('INSERT INTO trades(id,account,mode,run_id,managed_run,symbol,underlying,status,currency) VALUES(?,?,?,?,?,?,?,?,?)',(run,self.owner,'PAPER',run,run,symbol,symbol,'CLOSED','INR'))
  db.commit();db.close()
  result=report(self.owner,'run-1',data=self.data,instrument='MCX:GOLD-FUT')
  self.assertEqual(result['total'],1);self.assertEqual(result['rows'][0]['underlying'],'MCX:GOLD-FUT')

 def test_two_active_process_records_recover_separately(self):
  record=dict(pid=123,start_ticks='x')
  for run,sym in [('run-1','MCX:GOLD-FUT'),('run-2','MCX:SILVER-FUT')]:
   d=self.data/'runs'/self.owner/run;atomic(d/'config.json',self.config(sym));atomic(d/'process.json',record)
  with patch('strategies.nifty_ai_options.process_state.identity',return_value=record):
   for sym,run in [('MCX:GOLD-FUT','run-1'),('MCX:SILVER-FUT','run-2')]:
    r,p=recover(self.owner,self.data,instrument=sym);self.assertEqual(r['id'],run);self.assertIsNone(p.poll())
 def test_stop_and_detach_only_touch_selected_instrument(self):
  from strategies.nifty_ai_options.position_control import PositionManager,enqueue
  from strategies.nifty_ai_options.manual_entry import runtime_identity
  managers=[];states=[]
  for i,sym in enumerate(['MCX:GOLD-FUT','MCX:SILVER-FUT']):
   c=dict(self.config(sym,mode='LIVE'),timeframe=1,runtime_session=str(i)*32)
   p=dict(symbol=sym,side='LONG',quantity=10,product='INTRADAY',entry_timestamp=50,fill_price=100)
   e=SimpleNamespace(position=dict(p),pending_direction=None)
   x=SimpleNamespace(state=dict(position=dict(p),pending=None,seen=[]),save=Mock())
   def send(action,x=x):x.state['position']=None;return dict(filled_quantity=10)
   def verify(position,flat=False,x=x):return dict(flat=x.state.get('position') is None)
   d=self.data/('control-'+str(i))
   m=PositionManager(c,d,e,x,verify=verify,attach=Mock(),submit=send,clock=lambda:100)
   managers.append((m,c,d));states.append(x.state)
  a,c,d=managers[0]
  enqueue(d,c,dict(runtime_identity(c,d,'LIVE'),operation='STOP',request_id='c'*32),now=100)
  self.assertTrue(a.poll());self.assertIsNone(states[0]['position']);self.assertIsNotNone(states[1]['position'])
  b,c,d=managers[1]
  enqueue(d,c,dict(runtime_identity(c,d,'LIVE'),operation='DETACH',request_id='d'*32),now=100)
  b.poll();self.assertIsNotNone(states[1]['detached_position']);self.assertIsNone(states[0].get('detached_position'))
 def test_native_uncertainty_exception_requires_exact_different_owned_intent(self):
  a=self.config('NSE:ONE',mode='LIVE');b=self.config('NSE:TWO',mode='LIVE')
  payload=dict(orderTag='tag',symbol='NSE_FNO:123',qty=10,side=1,type=2,limitPrice=10,validity='IOC',productType='MARGIN')
  p=dict(symbol=payload['symbol'],quantity=10,fill_price=10)
  path=runtime_root(a,self.data)/self.owner/'native-indian-live.json'
  atomic(path,dict(pending=dict(key='tag',payload=payload,intent=dict(position=p))))
  native=SimpleNamespace(service=SimpleNamespace(account=dict(id=self.owner)),_ai_instrument_context=(b,self.data))
  self.assertTrue(independent_native_intent(native,'tag',payload,'NSE_FNO:456'))
  self.assertFalse(independent_native_intent(native,'tag',payload,payload['symbol']))
  self.assertFalse(independent_native_intent(native,'tag',dict(payload,qty=11),'NSE_FNO:456'))
  self.assertFalse(independent_native_intent(native,'manual',payload,'NSE_FNO:456'))
  ticket=dict(correlationId='tag',exchangeSegment='NSE_FNO',securityId='123',quantity=10,transactionType='BUY',productType='MARGIN')
  self.assertTrue(independent_native_intent(native,'tag',ticket,'NSE_FNO:456',dhan_ticket=True))
  self.assertFalse(independent_native_intent(native,'tag',dict(ticket,securityId='999'),'NSE_FNO:456',dhan_ticket=True))

 def test_scoped_user_start_persists_instrument_claim_without_launching_in_test(self):
  from strategies.nifty_ai_options.ui_bridge import Service
  c=dict(self.config('MCX:GOLD-FUT'),market='MCX',reference_state='VERIFIED',accept_close_source_renko_approximation=True);c.pop('runner_scope')
  legacy=SimpleNamespace(snapshot=lambda:{})
  with patch('strategies.nifty_ai_options.ui_bridge.DATA',self.data),patch('strategies.nifty_ai_options.ui_bridge.configuration',return_value=c),patch('strategies.nifty_ai_options.release_state.require_ready'),patch('strategies.nifty_ai_options.ui_bridge.threading.Thread') as thread:
   service=Service(self.owner,legacy,instrument='MCX:GOLD-FUT');service.snapshot=lambda:dict(running=False)
   service.start(dict(mode='PAPER',start_requested=True))
   saved=json.loads((service.run['directory']/'config.json').read_text())
   self.assertEqual(saved['runner_scope'],scope('MCX:GOLD-FUT'))
   self.assertTrue((service.run['directory']/'launching.json').exists());thread.return_value.start.assert_called_once()
   second=Service(self.owner,legacy,instrument='MCX:GOLD-FUT');second.snapshot=lambda:dict(running=False)
   with self.assertRaisesRegex(ValueError,'active runner'):second.start(dict(mode='PAPER',start_requested=True))
 def test_available_funds_remain_selected_account_scoped_for_indian_direct_adapters(self):
  e=SimpleNamespace(runner_config=self.config(mode='LIVE'),api=SimpleNamespace(funds=lambda:dict(s='ok',fund_limit=[dict(id=10,equityAmount=5000)])))
  self.assertEqual(available(e,dict(symbol='NSE:ONE')),(5000,'INR'))

 def test_scoped_worker_requires_exact_parent_process_receipt_before_initialization(self):
  c=self.config();d=self.data/'run';d.mkdir()
  with self.assertRaisesRegex(ValueError,'launch receipt'):worker_admission(c,d,timeout=.001)
  record=dict(pid=os.getpid(),start_ticks='test');atomic(d/'process.json',record)
  with patch('strategies.nifty_ai_options.process_state.identity',return_value=record):worker_admission(c,d,timeout=.1)
  atomic(d/'process.json',dict(pid=os.getpid()+1,start_ticks='test'))
  with patch('strategies.nifty_ai_options.process_state.identity',return_value=record):
   with self.assertRaisesRegex(ValueError,'launch receipt'):worker_admission(c,d,timeout=.001)
  legacy=dict(c);legacy.pop('runner_scope');worker_admission(legacy,None)

if __name__=='__main__':unittest.main()
