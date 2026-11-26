import json,tempfile,unittest,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from contextlib import ExitStack
from datetime import datetime
from zoneinfo import ZoneInfo
import live,manual_entry
class FyersOptionRuntimeTests(unittest.TestCase):
 def run_worker(self,*,manual=False,real_branch=False,outside_session=False,market_closes=False,close_owned=False,entry_gate=None,signal_source=None,market='NSE',sma_only=False,hybrid=False):
  if signal_source:entry_gate='underlying_flip' if signal_source=='UNDERLYING' else 'underlying_trend_premium_flip'
  base=datetime(2026,11,25,20 if market=='MCX' else 9,15,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
  if outside_session:base-=3600
  step_seconds=2 if market_closes else 60
  clock=[base];instances={};under='MCX:CRUDEOILM26DECFUT' if market=='MCX' else 'NSE:NIFTY50-INDEX'
  stages=list(zip([94,96,98,100,102,104,106]+[106]*8,[46,47,48,49,50,51,52,51,50,49,48,47,46,45,44]))
  if entry_gate=='underlying_trend_premium_flip':
   stages=list(zip([94,96,98,100,102,104,106]+[106]*13,[40,38,36,34,32,30,28,30,34,38,42,46,50,48,44,40,36,32,28,24]))
  if signal_source=='UNDERLYING':
   stages=list(zip([94,96,98,100,102,104,106,108,110,112,114,112,108,104,100,96,92,88,84,80],[40]*20))
  if sma_only:
   active=[100,100,100,100,106,108,96,94,92,90,88,86,84,82,80]
   premiums=[40,40,40,40,46,48,36,34,32,30,28,26,24,22,20]
   stages=list(zip(active if signal_source=='UNDERLYING' else [100]*15,[40]*15 if signal_source=='UNDERLYING' else premiums))
  raw=Mock();raw.header='offline-socket-only';raw.get_profile.return_value={'s':'ok','data':{'fy_id':'offline-id'}}
  class FakeSocket:
   def __init__(self,**kw):self.message=kw['on_message'];self.connected=kw['on_connect'];self.symbols=set();instances['socket']=self
   def connect(self):self.connected()
   def subscribe(self,*,symbols,**kw):
    self.symbols.update(symbols)
    if len(symbols)==1 and symbols[0]!=under:
     stage=min(len(stages)-1,int((clock[0]-base)//step_seconds))
     self.message(dict(symbol=symbols[0],exch_feed_time=clock[0],ltp=stages[stage][1]))
   def unsubscribe(self,*,symbols,**kw):self.symbols.difference_update(symbols)
   def close_connection(self):instances['closed']=True
  class FakeQueue:
   def __init__(self,**kw):self.rows=[];self.index=0
   def put_nowait(self,row):self.rows.append(row)
   def get(self,**kw):
    if self.rows:
     row=self.rows.pop(0)[1];clock[0]=row['exch_feed_time'];return ('tick',row)
    stage=self.index//2;premium=self.index%2
    if stage==len(stages):raise ValueError('offline option fixture completed')
    clock[0]=base+stage*step_seconds+premium
    selected=[s for s in instances['socket'].symbols if s!=under] if premium else [under]
    for symbol in selected:instances['socket'].message(dict(symbol=symbol,exch_feed_time=clock[0],ltp=stages[stage][premium]))
    if manual and self.index==0:
     expected=manual_entry.runtime_identity(config,folder/'run','LIVE' if real_branch else 'PAPER')
     manual_entry.enqueue(folder/'run',expected,dict(expected,direction='PE',request_id='c'*32),now=clock[0])
    self.index+=1
    return self.rows.pop(0)
  class FakeExecutor:
   def __init__(self,*args,**kwargs):self.state=dict(position=None,pending=None);self.live=kwargs['live'];self.actions=[];instances['executor']=self;instances['live']=kwargs['live']
   def submit(self,action,quote):
    self.actions.append(action);self.state['position']=dict(action['position'],quantity=1) if action['action']=='BUY' else None
    return dict(simulated_fill=quote['ltp'],offline_fixture=True)
   def save(self):(folder/'executor-state.json').write_text(json.dumps(self.state))
   def close(self):pass
  def history(api,symbol,*args):
   if signal_source=='UNDERLYING' and symbol!=under:self.fail('Underlying-only worker must not request premium history')
   prices=[100,98,96,94,92] if symbol==under else [40,41,42,43,44,45]
   last=clock[0]//60*60-60
   return [[last-(len(prices)-1-i)*60,p,p+1,p-1,p,None] if sma_only or hybrid else [last-(len(prices)-1-i)*60,None,None,None,p,None] for i,p in enumerate(prices)]
  def choose(api,master,config,side):
   return dict(symbol=market+(':CALL' if side=='CE' else ':PUT'),option_type=side,underlying=under,expiry=base+86400,lot_size=1),.2 if side=='CE' else -.2
  def reader(symbol,frame,stamp):
   index=int((stamp-(base-15))/60);price=stages[index][0 if symbol==under else 1]
   opening=high=low=price
   if sma_only and ((signal_source=='UNDERLYING' and symbol==under) or (signal_source=='PREMIUM' and symbol!=under)):
    if index==3:opening=price+2;high=opening;low=price-1
    elif index==4:opening=price-6;low=opening
   return {},[[stamp,opening,high,low,price,1]]
  import confirmed_close
  original_confirm=confirmed_close.ConfirmedClose.confirm
  def diagnose_confirm(instance,event,*args,**kwargs):
   try:return original_confirm(instance,event,*args,**kwargs)
   except ValueError as error:raise ValueError(str(error)+' '+repr((event,args,kwargs))) from error
  original_quote=manual_entry.LatestQuote;original_dispatch=manual_entry.ManualDispatcher;original_fill=manual_entry.confirm_entry_fill
  with tempfile.TemporaryDirectory() as directory:
   folder=Path(directory);config=dict(account='a'*32,broker='FYERS',underlying=under,market=market,execution_route='OPTIONS',execution_mode='LIVE' if real_branch else 'PAPER',timeframe=1,reference_value=12,lots=1,product='INTRADAY',accept_close_source_renko_approximation=True,runtime_session='b'*32)
   if hybrid:config['calculation_mode']='HYBRID'
   if sma_only:config.update(supertrend_enabled=False,sma_band_entry=True,sma_band_exit=True,sma_band_period=2)
   if entry_gate:config['entry_gate']=entry_gate
   if signal_source:config.update(signal_source=signal_source,exit_supertrend='underlying' if signal_source=='UNDERLYING' else 'premium',band_price_basis='underlying' if signal_source=='UNDERLYING' else 'premium')
   account_folder=folder/'.private/dashboard-login/accounts'/config['account']
   (account_folder/'home/.fyers').mkdir(parents=True)
   (account_folder/'credentials.json').write_text('{}')
   token_file=account_folder/'home/.fyers/token.json';token_file.write_text('old-session')
   path=folder/'config.json';path.write_text(json.dumps(config))
   with ExitStack() as stack:
    for target,value in [
     ('live.ROOT',folder),('live.session_bounds',lambda symbol:(540,1435) if market=='MCX' else (555,930)),
     ('live.runtime_configuration',lambda config,output:config),('live.automatic_strategy',lambda engine,*args,**kw:engine),
     ('live.client',Mock(return_value=raw)),('live.validate_config',lambda *args:dict(account_sha256=__import__('hashlib').sha256(b'offline-id').hexdigest())),
     ('live.Master',Mock()),('live.choose',choose),('live.history',history),('live.Execution',FakeExecutor),
     ('live.queue.Queue',FakeQueue),('live.time.time',lambda:clock[0]),
     ('live.option_market_open',lambda *args:not ((market_closes and clock[0]>=base+2) or (close_owned and clock[0]>=base+7*60))),
     ('confirmed_close.fyers_reader',lambda api:reader),('confirmed_close.ConfirmedClose.confirm',diagnose_confirm),
     ('manual_entry.LatestQuote',lambda symbol:original_quote(symbol,clock=lambda:clock[0])),
     ('manual_entry.confirm_entry_fill',lambda *args:original_fill(*args,clock=lambda:clock[0])),
     ('manual_entry.ManualDispatcher',lambda *args,**kw:original_dispatch(*args,**kw,clock=lambda:clock[0])),
     ('fyers_apiv3.FyersWebsocket.data_ws.FyersDataSocket',FakeSocket)]:
     stack.enter_context(patch(target,value))
    if sma_only:stack.enter_context(patch('indicator.AIRenko.update',side_effect=AssertionError('Supertrend must not run')))
    stack.enter_context(patch.dict(os.environ,{'AI_RENKO_LIVE_ORDERS':'I_ACCEPT_REAL_ORDERS'}))
    expected='offline option fixture completed'
    with self.assertRaisesRegex(ValueError,expected):live.stream(SimpleNamespace(config=str(path),output=str(folder/'run'),live=real_branch))
   actions=instances['executor'].actions
   if close_owned:
    self.assertTrue(actions);self.assertEqual(actions[0]['action'],'BUY');self.assertFalse(any(a['action']=='SELL' for a in actions));self.assertIsNotNone(instances['executor'].state['position']);raw.place_order.assert_not_called();return
   if outside_session or market_closes:
    self.assertEqual(actions,[]);raw.place_order.assert_not_called();self.assertTrue(instances['closed']);return
   self.assertTrue(actions);self.assertEqual(actions[0]['action'],'BUY');self.assertEqual(actions[0]['position']['side'],'PE' if manual or sma_only and signal_source=='PREMIUM' else 'CE')
   self.assertEqual(actions[0].get('manual_override',False),manual)
   if not any(a['action']=='SELL' for a in actions):(Path('.private/changes/option-leg-overlap-20261126')/'fixture-failure-state.json').write_text(json.dumps(instances['executor'].state,indent=2))
   self.assertTrue(any(a['action']=='SELL' and (a['reason'].endswith('_SMA_BAND') if sma_only else a['reason']==('AI_RENKO_SUPERTREND_UNDERLYING' if signal_source=='UNDERLYING' else 'AI_RENKO_SUPERTREND_PREMIUM')) for a in actions))
   self.assertEqual(instances['live'],real_branch);self.assertTrue(instances['closed'])
   raw.place_order.assert_not_called()
   if manual:self.assertEqual(json.loads((folder/'run/manual-entry/latest.json').read_text())['phase'],'FILLED')
 def test_underlying_flip_then_premium_confirmation_buys_and_exits(self):self.run_worker()
 def test_live_branch_uses_only_fake_socket_and_executor(self):self.run_worker(real_branch=True)
 def test_manual_put_keeps_premium_strategy_exit(self):self.run_worker(manual=True)

 def test_outside_regular_session_tick_never_reaches_execution(self):self.run_worker(outside_session=True)
 def test_closed_market_blocks_price_driven_entry_before_time_candle_close(self):self.run_worker(market_closes=True)

 def test_regular_close_retains_owned_option_without_forced_exit_or_worker_stop(self):self.run_worker(close_owned=True)

 def test_underlying_only_entry_runs_through_worker(self):self.run_worker(entry_gate='underlying_flip')
 def test_premium_only_entry_runs_through_worker(self):self.run_worker(entry_gate='underlying_trend_premium_flip')

 def test_shared_underlying_mode_skips_premium_history_and_exits_from_underlying(self):self.run_worker(signal_source='UNDERLYING')
 def test_shared_premium_mode_enters_and_exits_from_premium(self):self.run_worker(signal_source='PREMIUM')

 def test_mcx_evening_worker_underlying_source(self):self.run_worker(market='MCX',signal_source='UNDERLYING')
 def test_mcx_evening_worker_premium_source(self):self.run_worker(market='MCX',signal_source='PREMIUM')
 def test_mcx_evening_worker_fake_live_branch(self):self.run_worker(market='MCX',real_branch=True)
 def test_mcx_evening_worker_closed_status_retains_position(self):self.run_worker(market='MCX',close_owned=True)
 def test_mcx_evening_worker_closed_status_prevents_entry(self):self.run_worker(market='MCX',market_closes=True)

 def test_sma_only_underlying_worker_never_evaluates_supertrend(self):self.run_worker(signal_source='UNDERLYING',sma_only=True)
 def test_sma_only_premium_worker_never_evaluates_supertrend(self):self.run_worker(signal_source='PREMIUM',sma_only=True)

class FyersCompletedHybridRuntimeTests(FyersOptionRuntimeTests):
 def test_completed_unit_hybrid_underlying_entry_exit_through_mock_worker(self):
  self.run_worker(signal_source='UNDERLYING',hybrid=True)
 def test_completed_unit_hybrid_premium_entry_exit_through_mock_worker(self):
  self.run_worker(signal_source='PREMIUM',hybrid=True)
