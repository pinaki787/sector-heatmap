import json,tempfile,unittest,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from contextlib import ExitStack
import direct_live,manual_entry
class FyersDirectRuntimeTests(unittest.TestCase):
 def run_worker(self,*,manual=False,live=False,reconfigure=False,closed_start=False,late_open=False,sma_recovery=False,disconnect_during_check=False,refresh_saved_session=False):
  prices=[100,102,104,106,108,110,108,106,104,102,100,98,96,94,92,90]
  base=1800000015;clock=[base-60 if closed_start else base];instances={};symbol='NSE:TEST-EQ'
  raw=Mock();raw.header='offline-socket-fixture';raw.get_profile.return_value={'s':'ok','data':{'fy_id':'offline-id'}}
  refreshed=Mock();refreshed.header='offline-refreshed-session';refreshed.get_profile.return_value={'s':'ok','data':{'fy_id':'offline-id'}}
  meta=dict(symbol=symbol,opening_minutes=0,closing_minutes=1440,product_type='STOCK',lot_size=1)
  class FakeSocket:
   def __init__(self,**kw):self.access_token=kw['access_token'];self.message=kw['on_message'];self.connected=kw['on_connect'];self.failure=kw['on_close'];instances['socket']=self;instances['reconnect']=kw['reconnect']
   def connect(self):
    if closed_start:self.failure('offline planned session closure')
    self.connected()
   def subscribe(self,**kw):pass
   def close_connection(self):instances['closed']=True
  class FakeQueue:
   def __init__(self,**kw):self.rows=[];self.index=0;self.idle=0
   def put_nowait(self,tick):self.rows.append(tick)
   def get(self,**kw):
    if closed_start and self.index==0 and self.idle<2:
     clock[0]=base-40+self.idle*20;self.idle+=1;raise direct_live.queue.Empty
    if self.index==len(prices):raise ValueError('offline fixture completed')
    clock[0]=base+self.index*60
    if refresh_saved_session and self.index==5:token_file.write_text('new-session')
    tick=dict(symbol=symbol,exch_feed_time=clock[0],ltp=prices[self.index])
    instances['socket'].message(tick)
    if reconfigure and self.index==5:
     from runtime_control import enqueue
     enqueue(folder/'run',config,dict(account_id=config['account'],broker='FYERS',run_id='run',runtime_session=config['runtime_session'],underlying=symbol,timeframe=5))
    if manual and self.index==0:
     expected=manual_entry.runtime_identity(config,folder/'run','LIVE' if live else 'PAPER')
     manual_entry.enqueue(folder/'run',expected,dict(expected,direction='LONG',request_id='c'*32),now=clock[0])
    self.index+=1
    return self.rows.pop(0)
  class FakeExecutor:
   def __init__(self,*args,**kwargs):
    self.state=dict(position=None,pending=None);self.actions=[];instances['executor']=self;instances['live']=kwargs['live']
   def submit(self,action,quote):
    self.actions.append(action)
    self.state['position']=dict(action['position'],quantity=1) if action['action'].startswith('OPEN_') else None
    return dict(simulated_fill=quote['ltp'],offline_fixture=True)
   def save(self):
    (folder/'executor-state.json').write_text(json.dumps(self.state))
   def close(self):pass
  def reader(symbol,frame,stamp):
   index=int((stamp-(base-15))/60)
   price=prices[index]
   return {},[[stamp,price,price,price,price,1]]
  import session_wait
  original_reconcile=session_wait.reconcile_bodies
  def reconcile(engine,*args,**kw):
   result=original_reconcile(engine,*args,**kw)
   if sma_recovery and engine.position:engine.session_sma_exit_pending=True
   return result
  original_atomic=direct_live.atomic;heartbeats=[]
  def capture_atomic(path,value):
   if Path(path).name=='heartbeat.json' and not value.get('terminal'):heartbeats.append(dict(value))
   return original_atomic(path,value)
  disconnect_triggered=[False]
  def broker_market_status(*args):
   if refresh_saved_session and clock[0]>=base+300 and args[0].api is raw:raise ValueError('old in-memory token expired')
   if disconnect_during_check and not disconnect_triggered[0] and clock[0]>=base+60:
    disconnect_triggered[0]=True;instances['socket'].failure('offline disconnect during broker status read')
   return (not closed_start or clock[0]>=base+(120 if late_open else 0)) and not (sma_recovery and base+5*60<=clock[0]<base+8*60)
  original_quote=manual_entry.LatestQuote;original_dispatch=manual_entry.ManualDispatcher
  with tempfile.TemporaryDirectory() as directory:
   folder=Path(directory)
   config=dict(account='a'*32,broker='FYERS',underlying=symbol,reference_symbol=symbol,market='NSE',execution_route='DIRECT',timeframe=1,reference_value=12,reference_session='offline fixture',reference_evidence='synthetic socket fixture only',lots=1,product='INTRADAY',accept_close_source_renko_approximation=True,runtime_session='b'*32)
   account_folder=folder/'.private/dashboard-login/accounts'/config['account']
   (account_folder/'home/.fyers').mkdir(parents=True)
   (account_folder/'credentials.json').write_text('{}')
   token_file=account_folder/'home/.fyers/token.json';token_file.write_text('old-session')
   path=folder/'config.json';path.write_text(json.dumps(config))
   with ExitStack() as stack:
    for target,value in [
     ('direct_live.ROOT',folder),
     ('direct_live.runtime_configuration',lambda config,output:config),
     ('direct_live.automatic_strategy',lambda engine,*args,**kw:engine),
     ('direct_live.client',lambda account:refreshed if refresh_saved_session and token_file.read_text()=='new-session' else raw),
     ('direct_live.inspect',lambda *args:dict(instrument=meta,account_sha256=__import__('hashlib').sha256(b'offline-id').hexdigest(),market_open=not closed_start)),
     ('direct_live.market_open',broker_market_status),
     ('session_wait.reconcile_bodies',reconcile),
     ('direct_live.FyersInstrumentMaster',lambda *args:lambda symbol:meta),
     ('direct_live.history',lambda *args:[[base-135,None,None,None,100,None],[base-75,None,None,None,100,None]]),
     ('direct_live.DirectExecution',FakeExecutor),
     ('direct_live.queue.Queue',FakeQueue),
     ('direct_live.time.time',lambda:clock[0]),
     ('direct_live.time.monotonic',lambda:clock[0]),
     ('direct_live.atomic',capture_atomic),
     ('confirmed_close.fyers_reader',lambda api:reader),
     ('manual_entry.LatestQuote',lambda symbol:original_quote(symbol,clock=lambda:clock[0])),
     ('manual_entry.ManualDispatcher',lambda *args,**kw:original_dispatch(*args,**kw,clock=lambda:clock[0])),
     ('fyers_apiv3.FyersWebsocket.data_ws.FyersDataSocket',FakeSocket)]:
     stack.enter_context(patch(target,value))
    stack.enter_context(patch.dict(os.environ,{'AI_RENKO_LIVE_ORDERS':'I_ACCEPT_REAL_ORDERS'}))
    with self.assertRaisesRegex(ValueError,'Stream disconnected' if disconnect_during_check else 'offline fixture completed'):
     direct_live.stream(SimpleNamespace(config=str(path),output=str(folder/'run'),live=live))
   self.assertFalse(instances['reconnect'])
   if closed_start:
    waiting=[h for h in heartbeats if h.get('market_state')=='WAITING_FOR_MARKET']
    self.assertGreaterEqual(len(waiting),2);self.assertTrue(all(h['manual_entry_capable'] is False for h in waiting))
    self.assertTrue(all(h['reconfigure_capable'] and h['runtime_session']==config['runtime_session'] for h in waiting))
   self.assertTrue(any(h.get('manual_entry_capable') and h.get('market_state')=='READY' for h in heartbeats))
   actions=instances['executor'].actions;names=[a['action'] for a in actions]
   if disconnect_during_check:
    self.assertTrue(disconnect_triggered[0]);self.assertEqual(actions,[]);self.assertIsNone(instances['executor'].state['position']);raw.place_order.assert_not_called();return
   if sma_recovery:
    self.assertTrue(any(a.get('reason')=='OPTIONAL_UNDERLYING_1M_SMA30' for a in actions));raw.place_order.assert_not_called();return
   self.assertIn('OPEN_LONG',names);self.assertIn('CLOSE_LONG',names);self.assertIn('OPEN_SHORT',names)
   close=names.index('CLOSE_LONG');self.assertEqual(names[close+1],'OPEN_SHORT')
   self.assertEqual(actions[close]['timestamp'],actions[close+1]['timestamp'])
   if reconfigure:self.assertEqual(json.loads((folder/'run/reconfigure.json').read_text())['phase'],'APPLIED');self.assertEqual(json.loads((folder/'run/config.json').read_text())['timeframe'],5)
   if refresh_saved_session:self.assertEqual(instances['socket'].access_token,refreshed.header);refreshed.get_profile.assert_called_once();refreshed.place_order.assert_not_called();raw._sector_pulse_ipv4_session.close.assert_called_once()
   self.assertEqual(instances['live'],live);self.assertTrue(instances['closed'])
   if manual:self.assertEqual(json.loads((folder/'run/manual-entry/latest.json').read_text())['phase'],'FILLED',json.loads((folder/'run/manual-entry/latest.json').read_text()))
   self.assertEqual(actions[0].get('manual_override',False),manual)
   raw.place_order.assert_not_called()
   heartbeat=json.loads((folder/'run/heartbeat.json').read_text())
   self.assertTrue(heartbeat['terminal']);self.assertEqual(heartbeat['mode'],'LIVE' if live else 'PAPER')
 def test_paper_direct_worker_enters_exits_and_reverses_offline(self):self.run_worker()
 def test_live_code_path_uses_only_fake_broker(self):self.run_worker(live=True)
 def test_manual_entry_is_managed_by_the_same_worker_exit_loop(self):self.run_worker(manual=True)

 def test_active_timeframe_change_is_consumed_during_continuous_quotes(self):self.run_worker(reconfigure=True)

 def test_closed_start_waits_then_trades_after_broker_open(self):self.run_worker(closed_start=True)

 def test_late_first_price_reconciles_body_cursor_and_preserves_worker(self):self.run_worker(closed_start=True,late_open=True)

 def test_reopening_sma_exit_submits_only_with_new_quote(self):self.run_worker(sma_recovery=True)

 def test_disconnect_during_market_status_read_cannot_submit_stale_decision(self):self.run_worker(disconnect_during_check=True)

 def test_running_worker_reuses_refreshed_saved_session_before_market_status(self):self.run_worker(refresh_saved_session=True)
