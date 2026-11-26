"""One explicit Stop/Detach request for a stopped AI job; never starts entries.

The existing execution ledger lock is held throughout. Unknown fills are never
retried. A new Attach uses a dedicated held-position management runtime instead.
"""
import json,time,threading
from pathlib import Path
from types import SimpleNamespace
try:
 from .run import ROOT,client,ok,atomic
 from .position_control import PositionManager
 from .position_brokers import FyersPositions,DeltaPositions
 from .manual_entry import LatestQuote,ManualNotReady
except ImportError:
 from run import ROOT,client,ok,atomic
 from position_control import PositionManager
 from position_brokers import FyersPositions,DeltaPositions
 from manual_entry import LatestQuote,ManualNotReady

def execute(args):
 config=json.loads(Path(args.config).read_text());out=Path(args.output);live=args.live
 if config.get('_verification_only'):raise ValueError('Verification configuration cannot operate a position')
 import os
 if live and os.getenv('AI_RENKO_LIVE_ORDERS')!='I_ACCEPT_REAL_ORDERS':raise ValueError('Explicit live position-control gate is required')
 if live!=(config.get('execution_mode')=='LIVE'):raise ValueError('Position-control mode differs from saved run')
 command=json.loads((out/'position-controls/command.json').read_text())
 if command.get('operation') not in ('STOP','DETACH'):raise ValueError('Only Stop or Detach can run without an active strategy worker')
 raw=delta=executor=socket=broker=None;quote=None;quotes={};subscribed=set()
 try:
  if config['broker']=='FYERS':
   try:
    from .live import Reads,Master
    from .markets import FyersInstrumentMaster,fyers_market_open
    from .execution import Execution
    from .direct_execution import DirectExecution
   except ImportError:
    from live import Reads,Master
    from markets import FyersInstrumentMaster,fyers_market_open
    from execution import Execution
    from direct_execution import DirectExecution
   proof=out/'preflight/preflight.json'
   if not proof.exists():proof=out/'preflight.json'
   account_hash=json.loads(proof.read_text())['account_sha256']
   raw=client(config['account']);api=Reads(raw)
   master=FyersInstrumentMaster(out/'control-master') if config['execution_route']=='DIRECT' else Master(out/'control-master')
   cls=DirectExecution if config['execution_route']=='DIRECT' else Execution
   executor=cls(api,account_hash,ROOT/'.private/nifty-ai-options/runtime',live=live,lots=config['lots'],product=config['product'],master=master,account_folder=ROOT/'.private/dashboard-login/accounts'/config['account'],management_only=True)
   view=FyersPositions(api,config,master,account_hash)
   def get_quote(symbol):
    nonlocal socket
    if not fyers_market_open(api,master(symbol)):raise ManualNotReady('Execution market is closed')
    if symbol not in quotes:
     quotes[symbol]=LatestQuote(symbol)
     if socket is not None:socket.subscribe(symbols=[symbol],data_type='SymbolUpdate')
    if socket is None:
     from fyers_apiv3.FyersWebsocket import data_ws
     def connected():socket.subscribe(symbols=list(quotes),data_type='SymbolUpdate')
     def received(tick):
      current=quotes.get(tick.get('symbol'))
      if current:current.accept(tick)
     socket=data_ws.FyersDataSocket(access_token=raw.header,log_path=str(out),litemode=False,write_to_file=False,reconnect=False,on_connect=connected,on_message=received)
     threading.Thread(target=socket.connect,daemon=True).start()
    return quotes[symbol].get()
   def submit(action):
    try:current=get_quote(action['position']['symbol'])
    except ManualNotReady:return dict(deferred=True)
    return executor.submit(action,current)
  elif config['broker'] in ('DHAN','MOTILAL_OSWAL'):
   try:from .native_indian import bound_native,NativeIndianExecution
   except ImportError:from native_indian import bound_native,NativeIndianExecution
   view=bound_native(config)
   direct=config.get('execution_route')=='DIRECT'
   if direct:
    try:from .dhan_direct_runtime import make_executor
    except ImportError:from dhan_direct_runtime import make_executor
    executor=make_executor(config,view,live=live,management_only=True)
   else:executor=NativeIndianExecution(view,ROOT/'.private/nifty-ai-options/runtime',live=live,management_only=True)
   get_quote=lambda symbol:None
   def submit(action):
    if not view.session()['open']:return dict(deferred=True)
    return executor.submit(action,view.api.quote()) if direct else executor.submit(action)
  elif config['broker']=='DELTA_INDIA':
   try:
    from .delta_adapter import bound_delta
    from .delta_execution import DeltaExecution
    from .delta_live import SourceBroker
   except ImportError:
    from delta_adapter import bound_delta
    from delta_execution import DeltaExecution
    from delta_live import SourceBroker
   delta=bound_delta(config['account'],ROOT/'.private/nifty-ai-options/native-delta'/config['account']/('LIVE' if live else 'PAPER'))
   executor=DeltaExecution(delta,config['account'],ROOT/'.private/nifty-ai-options/runtime',live=live,contracts=config['lots'],management_only=True)
   view=DeltaPositions(delta,config,executor.native)
   def get_quote(symbol):
    nonlocal broker
    if broker is None:
     broker=SourceBroker(delta,out,lambda tick:None)
     broker.subscribe(symbol,config['timeframe']*60);subscribed.add(symbol);broker.start()
    elif symbol not in subscribed:
     broker.subscribe(symbol,config['timeframe']*60);subscribed.add(symbol)
    return dict(broker.quote(symbol),symbol=symbol)
   def submit(action):
    try:current=get_quote(action['position']['symbol'])
    except ValueError:return dict(deferred=True)
    return executor.submit(action,current)
  else:raise ValueError('Selected broker has no AI position-control adapter')
  if config.get('execution_route','OPTIONS')=='OPTIONS':
   try:from .option_legs import OptionLegBook
   except ImportError:from option_legs import OptionLegBook
   executor=OptionLegBook(executor,out,config,quote=get_quote,clock=lambda:time.time())
  engine=SimpleNamespace(position=executor.state.get('position'))
  verify=view.verify if live else lambda owned,**kw:dict(flat=executor.state.get('position') is None if kw.get('flat') is True else False)
  manager=PositionManager(config,out,engine,executor,verify=verify,attach=lambda holding:None,submit=submit)
  deadline=time.monotonic()+120
  while time.monotonic()<deadline:
   if manager.poll():return
   if manager.request and manager.request.get('phase') in ('DETACHED','REJECTED','RECOVERY_REQUIRED'):return
   time.sleep(.5)
  if manager.request:manager.update('RECOVERY_REQUIRED',error='Position-control timed out; broker flat state is not confirmed. Exposure and intents are retained.',broker_flat_confirmed=False)
 except Exception as error:
  root=out/'position-controls'
  current=root/'latest.json'
  if current.exists():
   receipt=json.loads(current.read_text())
   if receipt.get('phase') not in ('STOPPED','DETACHED','ATTACHED'):
    receipt.update(phase='RECOVERY_REQUIRED',error=str(error),broker_flat_confirmed=False,updated_at=time.time())
    atomic(current,receipt);atomic(root/'receipts'/(receipt['request_id']+'.json'),receipt)
  raise
 finally:
  if socket:
   try:socket.close_connection()
   except Exception:pass
  if broker:broker.stop()
  if executor:executor.close()
  if raw:raw._sector_pulse_ipv4_session.close()
  if delta:delta.requester.close()
