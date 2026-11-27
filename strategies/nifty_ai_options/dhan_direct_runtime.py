from strategies.nifty_ai_options.multi_runner import runtime_root,configure_executor,worker_admission
"""User-started Dhan direct runtime: completed-unit signals, durable net reversals."""
import copy,json,time,os,hashlib
from pathlib import Path
try:
 from .native_live import Runtime as NativeRuntime
 from .native_indian import bound_native
 from .direct import DirectStrategy
 from .direct_execution import DirectExecution
 from .automatic_sizing import automatic_strategy,runtime_configuration
 from .chart_source import ChartSource
 from .run import ROOT,atomic
 from .position_control import PositionManager,entry_guard,EntryBlocked
 from .manual_entry import ManualDispatcher,ManualNotReady,automatic_actions,restore_unsubmitted,confirm_entry_fill,clear_entry_signal
 from .runtime_control import RuntimeControl
 from .reversal import execute,advance,suppress_pending,entered
except ImportError:
 from native_live import Runtime as NativeRuntime
 from native_indian import bound_native
 from direct import DirectStrategy
 from direct_execution import DirectExecution
 from automatic_sizing import automatic_strategy,runtime_configuration
 from chart_source import ChartSource
 from run import ROOT,atomic
 from position_control import PositionManager,entry_guard,EntryBlocked
 from manual_entry import ManualDispatcher,ManualNotReady,automatic_actions,restore_unsubmitted,confirm_entry_fill,clear_entry_signal
 from runtime_control import RuntimeControl
 from reversal import execute,advance,suppress_pending,entered

def make_executor(config,adapter,*,live=False,management_only=False,state_dir=None):
 executor=DirectExecution(adapter.api,config['account'],state_dir or runtime_root(config),
  live=live,lots=config['lots'],product=config['product'],master=adapter.metadata,
  account_folder=adapter.native.service.folder,margin=adapter.api.margin,management_only=management_only,broker=config['broker'])
 configure_executor(executor,config);adapter.api.bind(executor);return executor

def inspect(config,adapter):
 if config.get('_verification_only'):raise ValueError('Verification configuration cannot launch')
 proof=adapter.validate();meta=adapter.metadata(config['underlying']);rows=adapter.candles()
 if not rows:raise ValueError('Completed Dhan direct history unavailable')
 engine=DirectStrategy(config);engine.reset_contract(dict(meta,underlying=config['underlying']))
 # Starting before the session never submits or fabricates an executable quote.
 readiness=adapter.order_readiness(meta,meta['lot_size']*config['lots']) if config['execution_mode']=='LIVE' and adapter.session()['open'] else dict(read_only=True,orders_submitted=0,waiting_for_market=True)
 return dict(proof,readiness=readiness,history_rows=len(rows),source_timeframe=config['timeframe'],direct=meta,contracts={},spot_brick=engine.spot_size,read_only=True,orders_submitted=0)

class Runtime(NativeRuntime):
 def __init__(self,config,directory,adapter,executor,*,clock=time.time,engine_factory=automatic_strategy):
  self.config=config;self.directory=Path(directory);self.adapter=adapter;self.executor=executor;self.clock=clock
  self.chart=ChartSource(self.directory/'chart-source',calculation_mode=config.get('calculation_mode','RENKO'))
  self.engine=engine_factory(DirectStrategy(config),config,exposure=lambda:any(executor.state.get(k) for k in ('position','pending','detached_position')),chart_source=self.chart,config_path=self.directory/'config.json')
  self.last={};self.sequence=0;self.symbol=config['underlying'];self.quote_at=None;self.source_ready=False;self.history_ready=True;self.quote_ready=False;self.source_error=None;self.last_history=0;self.quote_waiting=None;self.markers=[];self.sma_last=-1
  self.journal=(self.directory/'events.jsonl').open('a')
  self.select();self.seed('underlying',config['underlying'],self.engine.spot_size)
  if config.get('sma_exit_enabled'):
   for row in adapter.candles(frame=1):self.engine.update(dict(kind='sma',timestamp=row['timestamp'],close=row['close']));self.engine.position=None;self.sma_last=row['timestamp']
  clear_entry_signal(self.engine);self.engine.entry_reset_at=clock()
  self.manual=ManualDispatcher(config,directory,config['execution_mode'],self.engine,executor,prepare=self.select,quote_ready=self.manual_quote_ready,submit=self.submit,clock=clock)
  self.control=RuntimeControl(config,directory,apply=self.change_timeframe,apply_mode=lambda mode:self.engine.config.update(display_mode=mode,exit_confirmation_mode='RENKO_BRICKS_ONLY' if mode=='RENKO' else 'HYBRID_COMPLETED_UNITS'))
  self.manager=PositionManager(config,directory,self.engine,executor,verify=adapter.verify if executor.live else lambda p,**kw:dict(flat=executor.state.get('position') is None),attach=self.attach,submit=self.submit,manual=self.manual,clock=clock)
 def change_timeframe(self,frame):
  self.chart.roll_timeframe([self.symbol],self.config['timeframe'],frame)
  self.engine.config['timeframe']=frame;self.adapter.config['timeframe']=frame
  for key in ('underlying','hybrid_candle_underlying'):self.engine.last_time.pop(key,None)
  self.manual.inbox.expected['timeframe']=frame;self.last_history=0
 def select(self,*args):
  if not self.engine.position:
   self.engine.reset_contract(dict(self.adapter.metadata(self.config['underlying']),underlying=self.config['underlying'],execution_route='DIRECT'))
  return self.symbol
 def attach(self,request):
  row=self.adapter.selected(request)
  return dict(self.engine.contract,side=row['side'],quantity=row['quantity'],product=row['product'],fill_price=row['average_price'],entry_timestamp=self.clock(),attached_existing=True)
 def fill_record(self,action,result,identity=None):
  if identity:
   events=self.directory/'events.jsonl'
   if events.exists():
    with events.open() as stream:
     if any(json.loads(line).get('direct_receipt')==identity for line in stream if line.strip()):return
  self.record(action=action,result=result,recorded_at=self.clock(),**(dict(direct_receipt=identity) if identity else {}));self.journal.flush();os.fsync(self.journal.fileno())
  path=self.directory/'markers.json';markers=json.loads(path.read_text()) if path.exists() else []
  if not identity or not any(r.get('receipt_id')==identity for r in markers):
   markers.append(dict(receipt_id=identity,timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=self.clock(),symbol=action['position']['symbol'],action=action['action'],price=result.get('fill_price',result.get('simulated_fill')),mode=self.config['execution_mode'],order_id=result.get('order_id'),confirmed=True))
   atomic(path,markers[-1000:])
 def poll_reconciliation(self):
  if not self.executor.state.get('pending'):return
  try:receipt=self.executor.reconcile_pending()
  except (ValueError,RuntimeError) as error:self.source_error=str(error);return
  if receipt and receipt.get('filled_quantity'):
   result=dict(order_id=receipt['order_id'],filled_quantity=receipt['filled_quantity'],fill_price=receipt['fill_price'])
   self.fill_record(receipt['action'],result,str(receipt['order_id'])+'|'+str(receipt['filled_quantity']))
  self.engine.position=copy.deepcopy(self.executor.state.get('position'))
 def submit(self,action):
  entry=action['action'].startswith('OPEN_')
  if entry and (not self.source_ready or self.control.entry_blocked or self.manager.entry_blocked):
   restore_unsubmitted(self.engine,self.executor,action);return dict(deferred=True,reason='WAITING_FOR_SOURCE_OR_CONTROL')
  if not self.adapter.session()['open']:
   restore_unsubmitted(self.engine,self.executor,action);return dict(deferred=True,reason='WAITING_FOR_MARKET')
  def send():
   quote=self.adapter.api.quote()
   if entry:
    with entry_guard(self.directory,self.executor):return self.executor.submit(action,quote,now=self.clock())
   return self.executor.submit(action,quote,now=self.clock())
  try:result=execute(self.engine,self.executor,action,send)
  except EntryBlocked:
   restore_unsubmitted(self.engine,self.executor,action);return dict(deferred=True,reason='WAITING_FOR_POSITION_CONTROL')
  if result.get('deferred'):restore_unsubmitted(self.engine,self.executor,action);return result
  self.fill_record(action,result);confirm_entry_fill(self.engine,self.executor,action,clock=self.clock);entered(self.executor,action);return result
 def decisions(self,event,allow_actions=True):
  self.record(event=event)
  if event['kind']=='price':self.chart.append_observation(event,self.config['timeframe'])
  else:self.chart.append(event,self.config['timeframe'])
  before=copy.deepcopy(self.engine.position);raw=self.chart.decide(self.engine,event)
  if not allow_actions:self.engine.position=before;clear_entry_signal(self.engine);raw=[]
  raw=suppress_pending(self.engine,self.executor,raw)
  for action in automatic_actions(self.engine,self.executor,self.manual,raw):self.submit(action)
  if event['kind']!='price':self.chart.append_bands(self.engine,event)
 def step(self):
  self.poll_reconciliation();now=self.clock()
  try:
   self.quote_ready=self.adapter.session()['open']
   if self.quote_ready:
    self.adapter.native.start();price,stamp=self.adapter.market_price(self.config['underlying'])
    if not 0<=now-stamp<=5:raise ValueError('Dhan direct source quote stale')
   self.source_error=None if self.quote_ready else 'Selected venue closed'
  except (ValueError,RuntimeError) as error:self.quote_ready=False;self.source_error=str(error)
  self.source_ready=self.quote_ready and self.history_ready
  if self.manager.poll(busy=bool(self.manual.pending)):return True
  if not self.manager.entry_blocked:self.control.poll(busy=bool(self.manual.pending or self.executor.state.get('pending')),position=bool(self.executor.state.get('position')))
  self.engine.entry_paused=self.manager.entry_blocked or self.control.entry_blocked
  if self.manager.blocked or not self.quote_ready:self.heartbeat();return False
  events=[];sma=[]
  if now-self.last_history>=10 or not self.history_ready:
   try:
    rows=self.adapter.candles();fresh=[r for r in rows if r['timestamp']>self.last.get(self.symbol,-1)]
    events=list(fresh)
    if self.config.get('sma_exit_enabled'):sma=[r for r in self.adapter.candles(frame=1) if r['timestamp']>self.sma_last]
   except (ValueError,RuntimeError) as error:self.history_ready=False;self.source_ready=False;self.source_error=str(error);self.heartbeat();return False
   self.history_ready=True;self.source_ready=True;self.last_history=now
  self.manual.poll()
  for row in events:
   event=dict(row,kind='underlying',symbol=self.symbol,source_basis='PROVIDER_CONFIRMED_CLOSE',closed=True,closed_at=row['timestamp']+self.config['timeframe']*60,available_at=now,host_open_verified=True,body_available=True)
   self.decisions(event,row is events[-1]);self.last[self.symbol]=row['timestamp']
  for row in sma:
   self.decisions(dict(row,kind='sma'),row is sma[-1]);self.sma_last=row['timestamp']
  if self.config.get('calculation_mode','RENKO') in ('RENKO','HYBRID'):
   self.sequence+=1;self.decisions(dict(kind='price',series='underlying',symbol=self.symbol,timestamp=stamp,available_at=now,exchange_at=stamp,close=price,sequence=self.sequence,source_basis='BROKER_LIVE_PRICE'))
  advance(self.engine,self.executor,self.submit);self.heartbeat();return False

def preflight(args):
 config=json.loads(Path(args.config).read_text());adapter=bound_native(config);proof=inspect(config,adapter)
 atomic(Path(args.output)/'preflight.json',proof);print(json.dumps(proof))

def stream(args):
 config=json.loads(Path(args.config).read_text());worker_admission(config,getattr(args,'output',None));live=bool(args.live)
 if config.get('_verification_only') or live!=(config.get('execution_mode')=='LIVE'):raise ValueError('Dhan direct saved/run mode mismatch')
 if live and os.getenv('AI_RENKO_LIVE_ORDERS')!='I_ACCEPT_REAL_ORDERS':raise ValueError('Explicit user Live Start gate required')
 if not config.get('_managed_resume'):config=runtime_configuration(args.config)
 adapter=bound_native(config);proof=adapter.validate()
 if config.get('_managed_resume') and config.get('_resume_account_identity')!=proof.get('account_identity'):raise ValueError('Dhan management resume account identity differs from captured ownership')
 executor=make_executor(config,adapter,live=live,management_only=config.get('_managed_resume',False));runtime=None
 try:
  runtime=Runtime(config,args.output,adapter,executor)
  while not runtime.step():time.sleep(1)
 finally:
  if runtime:runtime.close()
  executor.close()
