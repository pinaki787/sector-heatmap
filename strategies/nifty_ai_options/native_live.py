from strategies.nifty_ai_options.multi_runner import runtime_root,configure_executor,worker_admission
"""Selected Dhan/Motilal AI runner. No shared runner start/stop or source fallback."""
import json,os,time
from pathlib import Path
from types import SimpleNamespace
try:
 from .run import ROOT,atomic
 from .native_indian import bound_native,NativeIndianExecution,NativeQuoteNotReady
 from .core import Strategy
 from .chart_source import ChartSource
 from .automatic_sizing import runtime_configuration,automatic_strategy
 from .manual_entry import ManualDispatcher,ManualNotReady,automatic_actions,restore_unsubmitted,confirm_entry_fill,confirmed_flat_entry,clear_entry_signal
 from .position_control import PositionManager,entry_guard,EntryBlocked
except ImportError:
 from run import ROOT,atomic
 from native_indian import bound_native,NativeIndianExecution,NativeQuoteNotReady
 from core import Strategy
 from chart_source import ChartSource
 from automatic_sizing import runtime_configuration,automatic_strategy
 from manual_entry import ManualDispatcher,ManualNotReady,automatic_actions,restore_unsubmitted,confirm_entry_fill,confirmed_flat_entry,clear_entry_signal
 from position_control import PositionManager,entry_guard,EntryBlocked

def inspect(config,adapter):
 if config.get('_verification_only'):raise ValueError('Verification configurations cannot launch a native runner')
 if config.get('broker') not in ('DHAN','MOTILAL_OSWAL') or config.get('execution_route')!='OPTIONS':raise ValueError('Explicit selected native bought-options route required')
 if config.get('execution_mode') not in ('PAPER','LIVE'):raise ValueError('Explicit execution mode required')
 if isinstance(config.get('lots'),bool) or not isinstance(config.get('lots'),int) or config['lots']<1:raise ValueError('Positive whole lots required')
 proof=adapter.validate();contracts={side:adapter.select(side) for side in ('CE','PE')}
 if contracts['CE']['expiry']!=contracts['PE']['expiry']:raise ValueError('Native expiry changed during preflight')
 rows=adapter.candles()
 if not rows:raise ValueError('Native source unavailable')
 engine=Strategy(config)
 for c in contracts.values():
  engine.reset_contract(c)
  if config['execution_mode']=='LIVE':adapter.order_readiness(c,c['lot_size']*config['lots'])
  if config.get('signal_source')=='PREMIUM':adapter.candles(c['symbol'])
 return dict(read_only=True,orders_submitted=0,broker=config['broker'],account_id=config['account'],account_identity=proof['account_identity'],underlying=config['underlying'],contracts=contracts,resolved_expiry=contracts['CE']['expiry'],source_timeframe=config['timeframe'],calculation_mode=config.get('calculation_mode','RENKO'),history_rows=len(rows),session=adapter.session(),native_source=True,spot_brick=engine.spot_size)

def preflight(args):
 config=json.loads(Path(args.config).read_text());adapter=bound_native(config)
 summary=inspect(config,adapter)
 atomic(Path(args.output)/'preflight.json',summary)
 print(json.dumps(summary))
 # The process owns this adapter's capture only; no existing service is interrupted.

class Runtime:
 def __init__(self,config,directory,adapter,executor,*,clock=time.time,engine_factory=automatic_strategy):
  self.config=config;self.directory=Path(directory);self.adapter=adapter;self.executor=executor;self.clock=clock
  try:from .option_legs import OptionLegBook
  except ImportError:from option_legs import OptionLegBook
  self.executor=executor=OptionLegBook(executor,directory,config,quote=lambda symbol:None,ready=lambda:adapter.session()['open'] and (self.source_ready or self.executor.state.get('management_mode')=='STOPPING'),clock=clock)

  self.chart=ChartSource(self.directory/'chart-source',calculation_mode=config.get('calculation_mode','RENKO'))
  self.engine=engine_factory(Strategy(config),config,exposure=lambda:any(executor.state.get(k) for k in ('position','positions','pending','detached_position')),chart_source=self.chart,config_path=self.directory/'config.json')
  self.last={};self.sequence=0;self.symbol=None;self.quote_at=None;self.source_ready=False;self.history_ready=True;self.quote_ready=False;self.source_error=None;self.last_history=0;self.quote_waiting=None;self.markers=[]
  self.journal=(self.directory/'events.jsonl').open('a')
  self.seed('underlying',config['underlying'],self.engine.spot_size)
  if not config.get('_managed_resume'):self.select()
  self.sma_last=-1
  if config.get('sma_exit_enabled'):
   for row in adapter.candles(frame=1):
    self.engine.update(dict(kind='sma',timestamp=row['timestamp'],close=row['close']));self.engine.position=None;self.sma_last=row['timestamp']
  clear_entry_signal(self.engine);self.engine.entry_reset_at=clock()
  self.manual=ManualDispatcher(config,directory,config['execution_mode'],self.engine,executor,prepare=self.select,quote_ready=self.manual_quote_ready,submit=self.submit,clock=clock)
  try:from .runtime_control import RuntimeControl
  except ImportError:from runtime_control import RuntimeControl
  self.control=RuntimeControl(config,directory,apply=self.change_timeframe,apply_mode=lambda mode:self.engine.config.update(display_mode=mode,exit_confirmation_mode='RENKO_BRICKS_ONLY' if mode=='RENKO' else 'HYBRID_COMPLETED_UNITS'))
  self.manager=PositionManager(config,directory,self.engine,executor,verify=adapter.verify if executor.live else self.paper_verify,attach=self.attach,submit=self.submit,manual=self.manual,clock=clock)
 def change_timeframe(self,frame):
  old=self.config['timeframe']
  self.chart.roll_timeframe([s for s in (self.config['underlying'],self.symbol) if s],old,frame)
  self.engine.config['timeframe']=frame;self.adapter.config['timeframe']=frame
  for key in ('underlying','premium','hybrid_candle_underlying','hybrid_candle_premium'):self.engine.last_time.pop(key,None)
  self.manual.inbox.expected['timeframe']=frame;self.last_history=0
 def paper_verify(self,owned,*,flat=False):
  return dict(flat=self.executor.state.get('position') is None)
 def seed(self,kind,symbol,brick):
  rows=self.adapter.candles(symbol)
  values=[[r['timestamp'],r['open'],r['high'],r['low'],r['close'],r.get('volume')] for r in rows]
  self.chart.seed(symbol,self.config['timeframe'],values,brick)
  self.engine.last_time.pop(kind,None)
  import copy
  saved=None
  if kind=='premium':
   saved=(getattr(self.engine,'pending_underlying_flip',None),getattr(self.engine,'pending_underlying_flip_source_at',None),copy.deepcopy(self.engine.entry_confirmation))
   clear_entry_signal(self.engine)
  for r in rows:self.engine.update(dict(r,kind=kind));self.engine.position=None
  if saved:
   clear_entry_signal(self.engine)
   self.engine.pending_underlying_flip,self.engine.pending_underlying_flip_source_at,self.engine.entry_confirmation=saved
  self.last[symbol]=rows[-1]['timestamp'];self.chart.seed_bands(self.engine)
 def select(self,side=None,contract=None):
  side=side or (self.engine.signal_side() or 'PE')
  old=self.symbol;contract=contract or self.adapter.select(side)
  self.engine.reset_contract(contract);self.symbol=contract['symbol']
  self.adapter.native.subscribe(self.symbol,self.config['timeframe']*60)
  if self.config.get('signal_source')=='PREMIUM' or self.config.get('supertrend_enabled',True) and self.config.get('entry_gate')!='underlying_flip':
   self.seed('premium',self.symbol,self.engine.contract['option_brick'])
  return old
 def attach(self,request):
  row=self.adapter.selected(request);contract=dict(row['meta'],underlying=self.config['underlying'],verified_native_selection=dict(broker=self.config['broker'],account=self.config['account'],underlying=self.config['underlying'],symbol=row['symbol']))
  self.select(row['side'],contract)
  return dict(self.engine.contract,side=row['side'],quantity=row['quantity'],product=row['product'],fill_price=row['average_price'],entry_timestamp=self.clock(),attached_existing=True)
 def manual_quote_ready(self):
  if not self.source_ready or not self.adapter.session()['open']:raise ManualNotReady('Waiting for the selected native venue/source')
  self.adapter.quote(self.symbol);return self.clock()
 def record(self,**value):
  self.journal.write(json.dumps(value)+'\n');self.journal.flush()
 def submit(self,action):
  if action['action']=='BUY':self.executor.remember_entry(action)
  if action['action']=='SELL' and action.get('reason')!='USER_STOP_SQUARE_OFF':
   self.quote_waiting=None
   return self.executor.request_exit(action)
  if action['action']=='BUY' and self.control.entry_blocked:
   restore_unsubmitted(self.engine,self.executor,action);return dict(deferred=True,reason='WAITING_FOR_HANDOVER')
  if (not self.source_ready and action.get('reason')!='USER_STOP_SQUARE_OFF') or not self.adapter.session()['open']:
   restore_unsubmitted(self.engine,self.executor,action)
   if action['action']=='SELL':self.quote_waiting=action
   return dict(deferred=True,reason='WAITING_FOR_SOURCE')
  try:
   if action['action']=='BUY':
    with entry_guard(self.directory,self.executor):result=self.executor.submit(action)
   else:result=self.executor.submit(action)
  except NativeQuoteNotReady as error:
   restore_unsubmitted(self.engine,self.executor,action)
   if action['action']=='SELL':self.quote_waiting=action
   self.source_error=str(error)
   return dict(deferred=True,reason='WAITING_FOR_SOURCE')
  except EntryBlocked:
   restore_unsubmitted(self.engine,self.executor,action);return dict(deferred=True,reason='WAITING_FOR_POSITION_CONTROL')
  if result.get('deferred'):
   restore_unsubmitted(self.engine,self.executor,action);self.record(action=action,result=result);return result
  self.record(action=action,result=result)
  if (self.directory/'markers.json').exists():self.markers=json.loads((self.directory/'markers.json').read_text())
  self.markers.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=self.clock(),symbol=action['position']['symbol'],action=action['action'],price=result.get('fill_price',result.get('simulated_fill')),mode=self.config['execution_mode'],order_id=result.get('order_id'),confirmed=True))
  atomic(self.directory/'markers.json',self.markers[-1000:])
  confirm_entry_fill(self.engine,self.executor,action,clock=self.clock)
  if action['action']=='SELL':self.quote_waiting=None
  return result
 def decisions(self,event,allow_actions=True):
  self.record(event=event)
  if event['kind']=='price':self.chart.append_observation(event,self.config['timeframe'])
  else:self.chart.append(event,self.config['timeframe'])
  import copy
  before=copy.deepcopy(self.engine.position)
  raw=self.chart.decide(self.engine,event)
  if not allow_actions:
   self.engine.position=before;clear_entry_signal(self.engine);raw=[]
  try:from .option_legs import retain_pending_actions
  except ImportError:from option_legs import retain_pending_actions
  raw=retain_pending_actions(self.engine,self.executor,raw)
  actions=automatic_actions(self.engine,self.executor,self.manual,raw)
  if event['kind']!='price':self.chart.append_bands(self.engine,event)
  for action in actions:
   if action['action']=='SELECT':
    if not self.executor.state.get('position') and not self.executor.state.get('pending') and not self.manager.entry_blocked:
     self.select(action['side'])
     entry=confirmed_flat_entry(self.engine,self.executor)
     if entry:self.submit(entry)
   else:self.submit(action)
  self.executor.poll()
 def heartbeat(self):
  state=dict(exit_waiting_for_quote=self.quote_waiting is not None,moving_bands=self.engine.band.snapshot(self.engine.config),market_state='OPEN' if self.adapter.session()['open'] else 'WAITING_FOR_MARKET',updated_at=self.clock(),runtime_session=self.config['runtime_session'],position=self.executor.state.get('position'),pending=self.executor.state.get('pending'),position_control=self.manager.status(),manual_entry_capable=self.source_ready and not self.manager.entry_blocked and not self.control.entry_blocked and not self.executor.state.get('position'),broker=self.config['broker'],account=self.config['account'],underlying=self.config['underlying'],timeframe=self.config['timeframe'],calculation_mode=self.config.get('calculation_mode','RENKO'),source_ready=self.source_ready,source_error=self.source_error,market_session=self.adapter.session(),native_sizing=getattr(self.engine,'native_sizing_status',None))
  atomic(self.directory/'heartbeat.json',state)
 def step(self):
  was_pending=bool(self.executor.state.get('pending'));self.executor.poll()
  if was_pending and not self.executor.state.get('pending'):self.engine.position=__import__('copy').deepcopy(self.executor.state.get('position'));__import__('strategies.nifty_ai_options.zone_targets',fromlist=['reconciled']).reconciled(self.engine,self.executor)
  try:
   self.quote_ready=bool(self.adapter.session()['open'])
   if self.quote_ready:
    self.adapter.native.start();price,stamp=self.adapter.market_price(self.config['underlying']) if hasattr(self.adapter,'market_price') else self.adapter.native.live_price(self.config,self.clock())
    if not 0<=self.clock()-stamp<=5:raise ValueError('Native underlying source quote stale')
   self.source_error=None if self.quote_ready else 'Selected venue closed'
  except (ValueError,RuntimeError) as error:self.quote_ready=False;self.source_error=str(error)
  self.source_ready=self.quote_ready and self.history_ready
  if self.manager.poll(busy=bool(self.manual.pending)):return True
  if not self.manager.entry_blocked:self.control.poll(busy=bool(self.manual.pending or self.executor.state.get('pending')),position=bool(self.executor.state.get('position')))
  self.engine.entry_paused=self.manager.entry_blocked or self.control.entry_blocked
  if self.manager.blocked or not self.quote_ready:self.heartbeat();return False
  now=self.clock();events=[];sma=[]
  if now-self.last_history>=10 or not self.history_ready:
   sources=[('underlying',self.config['underlying'])]
   if self.symbol and (self.config.get('signal_source')=='PREMIUM' or self.config.get('supertrend_enabled',True) and self.config.get('entry_gate')!='underlying_flip'):sources.append(('premium',self.symbol))
   try:
    for kind,symbol in sources:
     rows=self.adapter.candles(symbol)
     fresh=[r for r in rows if r['timestamp']>self.last.get(symbol,-1)]
     for row in fresh:events.append((kind,symbol,row,row is fresh[-1]))
    if self.config.get('sma_exit_enabled'):sma=[r for r in self.adapter.candles(frame=1) if r['timestamp']>self.sma_last]
   except (ValueError,RuntimeError) as error:
    self.history_ready=False;self.source_ready=False;self.source_error=str(error);self.heartbeat();return False
   self.history_ready=True;self.source_ready=True;self.last_history=now
  self.manual.poll()
  if self.quote_waiting:self.submit(self.quote_waiting)
  for kind,symbol,row,latest in sorted(events,key=lambda item:(item[2]['timestamp'],item[0])):
   if kind=='premium' and symbol!=self.symbol:continue
   event=dict(row,kind=kind,source_basis='PROVIDER_CONFIRMED_CLOSE',closed=True,closed_at=row['timestamp']+self.config['timeframe']*60,available_at=now,host_open_verified=True,body_available=True)
   self.decisions(event,allow_actions=latest)
   self.last[symbol]=row['timestamp']
  for row in sma:
   event=dict(kind='sma',timestamp=row['timestamp'],close=row['close']);self.record(event=event)
   old=self.engine.position
   actions=self.engine.update(event)
   if row is not sma[-1]:
    self.engine.position=old;clear_entry_signal(self.engine)
   else:
    for action in automatic_actions(self.engine,self.executor,self.manual,actions):self.submit(action)
   self.sma_last=row['timestamp']
  if self.config.get('calculation_mode','RENKO') in ('RENKO','HYBRID'):
   sources=[('underlying',self.config['underlying'])]
   if self.symbol and (self.config.get('signal_source')=='PREMIUM' or self.config.get('supertrend_enabled',True) and self.config.get('entry_gate')!='underlying_flip'):sources.append(('premium',self.symbol))
   for kind,symbol in sources:
    try:price,stamp=self.adapter.market_price(symbol) if hasattr(self.adapter,'market_price') else self.adapter.native.live_price(dict(self.config,underlying=symbol),now)
    except (ValueError,RuntimeError) as error:self.source_ready=False;self.source_error=str(error);self.heartbeat();return False
    if not 0<=now-stamp<=5:self.source_ready=False;self.source_error='Native source quote stale';self.heartbeat();return False
    self.sequence+=1
    self.decisions(dict(kind='price',series=kind,symbol=symbol,timestamp=stamp,available_at=now,exchange_at=stamp,close=price,sequence=self.sequence,source_basis='BROKER_LIVE_PRICE'))
  if not self.executor.state.get('position') and not self.executor.state.get('pending') and not self.manager.entry_blocked and not self.control.entry_blocked:
   target=self.engine.signal_side()
   if target and (self.engine.contract or {}).get('option_type')!=target:self.select(target)
   action=confirmed_flat_entry(self.engine,self.executor)
   if action:self.submit(action)
  try:from .option_legs import entry_valid
  except ImportError:from option_legs import entry_valid
  self.executor.dispatch_entries(self.submit,lambda action:entry_valid(self.engine,action))
  self.heartbeat();return False
 def close(self):
  self.journal.close()
  if hasattr(self.engine,'close_native_sizing'):self.engine.close_native_sizing()

def stream(args):
 config=json.loads(Path(args.config).read_text());worker_admission(config,getattr(args,'output',None));live=bool(args.live)
 if config.get('_verification_only'):raise ValueError('Verification configurations cannot run')
 if live!=(config.get('execution_mode')=='LIVE'):raise ValueError('Native saved/run mode mismatch')
 if live and os.getenv('AI_RENKO_LIVE_ORDERS')!='I_ACCEPT_REAL_ORDERS':raise ValueError('Explicit native Live Start gate required')
 if not config.get('_managed_resume'):config=runtime_configuration(args.config)
 adapter=bound_native(config);proof=adapter.validate()
 if config.get('_managed_resume') and config.get('_resume_account_identity')!=proof.get('account_identity'):raise ValueError('Native management resume account identity mismatch')
 executor=NativeIndianExecution(adapter,runtime_root(config),live=live,management_only=config.get('_managed_resume',False))
 configure_executor(executor,config)
 runtime=None
 try:
  runtime=Runtime(config,args.output,adapter,executor)
  while not runtime.step():time.sleep(1)
 finally:
  if runtime:runtime.close()
  executor.close()
