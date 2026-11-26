"""Native runtime integration using inert fake brokers; no network, process or order API."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import nullcontext
from native_live import Runtime
from native_indian import NativeIndianAdapter,NativeIndianExecution
from position_control import enqueue
from manual_entry import runtime_identity
from test_native_indian import Native
class NativeRuntimeTests(unittest.TestCase):
 def fixture(self,folder,broker='DHAN',live=False,descending=False):
  root=Path(folder);now=[2000.]
  n=Native(broker);n.clock=lambda:now[0];n.start=lambda:None;n.subscribe=lambda *a:None;n.live_price=lambda config,at:(130,now[0])
  n.quote=lambda symbol:dict(symbol=symbol,bid=100,ask=101,exchange_at=now[0],received_at=now[0])
  config=dict(account='a'*32,broker=broker,underlying='MCX:CRUDE',market='MCX',execution_route='OPTIONS',execution_mode='LIVE' if live else 'PAPER',product=n.product,lots=1,timeframe=1,runtime_session='b'*32,reference_value=200,calculation_mode='CANDLES',entry_gate='underlying_flip',exit_supertrend='underlying',signal_source='UNDERLYING',option_moneyness='ATM')
  a=NativeIndianAdapter(config,n);a.session=lambda at=None:dict(open=True,opening_minutes=540,closing_minutes=1435)
  rows=[dict(timestamp=i*60,open=(200-i if descending else 100+i),high=(201-i if descending else 101+i),low=(199-i if descending else 99+i),close=(200-i if descending else 100+i),volume=None) for i in range(30)]
  a.candles=lambda symbol=None,frame=None:list(rows)
  contract=dict(symbol='NATIVE',broker=broker,option_type='CE',expiry='2026-12-16',lot_size=1,tick_size=.05,underlying=config['underlying'],verified_native_selection=dict(broker=broker,account=config['account'],underlying=config['underlying'],symbol='NATIVE'))
  a.select=lambda side:dict(contract)
  a.selected=lambda holding:dict(holding,side='CE',meta=dict(contract),average_price=100)
  x=NativeIndianExecution(a,root/'state',live=live)
  (root/'config.json').write_text(json.dumps(config))
  r=Runtime(config,root,a,x,clock=lambda:now[0],engine_factory=lambda engine,*args,**kw:engine)
  self.addCleanup(r.close);self.addCleanup(x.close)
  return config,n,a,x,r,now,rows
 def setUp(self):
  guard=patch('native_indian.native_entry_admission',side_effect=lambda *a:nullcontext())
  guard.start();self.addCleanup(guard.stop)
 def command(self,root,c,operation,holding=None,identifier='c'*32):
  return enqueue(root,c,dict(runtime_identity(c,root,c['execution_mode']),operation=operation,request_id=identifier,**(dict(holding=holding) if holding else {})),now=2000)
 def test_selected_native_runtime_warms_exact_candles_without_historical_orders(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as folder:
    c,n,a,x,r,now,rows=self.fixture(folder,broker)
    self.assertEqual(r.engine.calculation_mode,'CANDLES')
    self.assertEqual(r.engine.under_ai.previous_close,rows[-1]['close'])
    self.assertFalse(r.step());self.assertEqual(n.sent,[]);self.assertIsNone(x.state['position'])
    h=json.loads((Path(folder)/'heartbeat.json').read_text());self.assertTrue(h['source_ready']);self.assertEqual(h['broker'],broker)
 def test_manual_stop_paper_closes_managed_holding_without_any_real_submission(self):
  with tempfile.TemporaryDirectory() as folder:
   c,n,a,x,r,now,rows=self.fixture(folder);r.source_ready=True
   action=r.engine.manual_entry('CE',2000);r.submit(action)
   self.assertIsNotNone(x.state['position']);self.command(Path(folder),c,'STOP')
   self.assertTrue(r.step());self.assertIsNone(x.state['position']);self.assertEqual(n.sent,[])
   self.assertTrue(r.manager.request['simulated_flat_confirmed']);self.assertFalse(r.manager.request['broker_flat_confirmed'])
 def test_detach_attach_same_live_mock_holding_never_sends_new_entry(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as folder:
    c,n,a,x,r,now,rows=self.fixture(folder,broker,True);r.source_ready=True
    r.submit(r.engine.manual_entry('CE',2000));self.assertEqual(len(n.sent),1)
    self.command(Path(folder),c,'DETACH');r.step()
    self.assertEqual(r.manager.mode,'DETACHED');self.assertIsNone(x.state['position']);self.assertEqual(n.qty,1)
    holding=dict(symbol='NATIVE',quantity=1,product=n.product)
    self.command(Path(folder),c,'ATTACH',holding,'d'*32);r.step()
    self.assertEqual(r.manager.mode,'ATTACHED');self.assertTrue(r.manager.entry_blocked)
    self.assertEqual(x.state['position']['symbol'],'NATIVE');self.assertEqual(len(n.sent),1)
 def test_stop_acceptance_prevents_manual_or_automatic_entry_submission(self):
  with tempfile.TemporaryDirectory() as folder:
   c,n,a,x,r,now,rows=self.fixture(folder,live=True);r.source_ready=True
   self.command(Path(folder),c,'STOP')
   result=r.submit(r.engine.manual_entry('CE',2000))
   self.assertEqual(result['reason'],'WAITING_FOR_POSITION_CONTROL');self.assertEqual(n.sent,[])
   self.assertTrue(r.step());self.assertEqual(n.sent,[])
 def test_stale_source_blocks_decisions_and_keeps_heartbeat_truthful(self):
  with tempfile.TemporaryDirectory() as folder:
   c,n,a,x,r,now,rows=self.fixture(folder)
   n.live_price=lambda config,at:(130,now[0]-20)
   self.assertFalse(r.step());self.assertFalse(r.source_ready);self.assertIn('stale',r.source_error);self.assertEqual(n.sent,[])

 def test_confirmed_candle_exit_uses_native_fill_then_flat_and_blocks_exit_only_reentry(self):
  for broker in ('DHAN','MOTILAL_OSWAL'):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as folder:
    c,n,a,x,r,now,rows=self.fixture(folder,broker,True,descending=True);r.source_ready=True
    self.assertEqual(r.engine.under_result['direction'],1)
    r.submit(r.engine.manual_entry('CE',2000))
    # Adverse state was established independently; it is not a new flip.
    r.engine.pending_underlying_flip=None;r.engine.entry_confirmation.clear()
    # A real completed host candle after the confirmed entry can close the Call.
    now[0]=2101
    row=dict(timestamp=2040,open=171,high=172,low=169,close=170.5,volume=None)
    event=dict(row,kind='underlying',symbol=c['underlying'],closed=True,closed_at=2100,available_at=2101,source_basis='PROVIDER_CONFIRMED_CLOSE',body_available=True)
    r.decisions(event)
    self.assertIsNone(x.state['position']);self.assertEqual(n.qty,0)
    self.assertEqual([p['side'] for p in n.sent],[1,-1])
    self.assertIsNone(r.engine.pending_underlying_flip)
 def test_completed_history_failure_recovers_without_hidden_entry_and_stop_still_works(self):
  with tempfile.TemporaryDirectory() as folder:
   c,n,a,x,r,now,rows=self.fixture(folder,live=True);r.source_ready=True
   r.submit(r.engine.manual_entry('CE',2000))
   a.candles=lambda *args,**kwargs:(_ for _ in ()).throw(ValueError('native history missing'))
   self.assertFalse(r.step());self.assertFalse(r.source_ready);self.assertIsNotNone(x.state['position'])
   self.command(Path(folder),c,'STOP')
   self.assertTrue(r.step());self.assertEqual(n.qty,0);self.assertEqual([p['side'] for p in n.sent],[1,-1])
 def test_deferred_confirmed_exit_waits_for_execution_quote_without_duplicate(self):
  from native_indian import NativeQuoteNotReady
  with tempfile.TemporaryDirectory() as folder:
   c,n,a,x,r,now,rows=self.fixture(folder,live=True);r.source_ready=True
   r.submit(r.engine.manual_entry('CE',2000));position=dict(r.engine.position)
   action=dict(action='SELL',timestamp=2001,position=position,reason='AI_RENKO_SUPERTREND_UNDERLYING')
   original=a.quote;a.quote=lambda symbol:(_ for _ in ()).throw(NativeQuoteNotReady('Waiting'))
   self.assertTrue(r.submit(action)['deferred']);self.assertIsNone(x.state['position']);self.assertEqual(len(x.state['positions']),1);self.assertEqual(len(n.sent),1)
   r.executor.poll(force=True);self.assertEqual(len(n.sent),1)
   a.quote=original;r.executor.poll(force=True);r.executor.poll(force=True)
   self.assertIsNone(x.state['position']);self.assertFalse(x.state['closing_legs']);self.assertEqual(len(n.sent),2)
