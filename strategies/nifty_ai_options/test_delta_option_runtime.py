import json,tempfile,unittest,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from contextlib import ExitStack
import delta_live,manual_entry
class DeltaOptionRuntimeTests(unittest.TestCase):
 def run_worker(self,*,manual=False,live=False,hybrid=False):
  base=1800000015;clock=[base];instances={};under='BTCUSD'
  stages=list(zip([94,96,98,100,102,104,106]+[106]*8,[46,47,48,49,50,51,52,51,50,49,48,47,46,45,44]))
  delta=Mock();delta.clock.side_effect=lambda:clock[0]
  class FakeBroker:
   def __init__(self,delta,out,on_tick):self.callback=on_tick;self.symbols=set();self.started=False;self.quotes={};instances['broker']=self
   def publish(self,symbol,price,stamp):
    tick=dict(symbol=symbol,exch_feed_time=stamp,ltp=price);self.quotes[symbol]=tick;self.callback(tick)
   def subscribe(self,symbol,*args):
    self.symbols.add(symbol)
    if self.started and symbol!=under:
     stage=min(len(stages)-1,int((clock[0]-base)//60));self.publish(symbol,stages[stage][1],clock[0])
   def unsubscribe(self,symbol):self.symbols.discard(symbol)
   def start(self):self.started=True
   def stream_status(self):return dict(connected=True,generation=1)
   def tick(self,symbol):
    tick=self.quotes.get(symbol)
    if not tick or not 0<=clock[0]-tick['exch_feed_time']<=15:raise ValueError('fixture quote not fresh')
    return tick
   def quote(self,symbol):
    tick=self.tick(symbol);return dict(bid=tick['ltp'],ask=tick['ltp']+.1,exchange_at=tick['exch_feed_time'],received_at=tick['exch_feed_time'])
   def stop(self):instances['stopped']=True
  class FakeQueue:
   def __init__(self,**kw):self.rows=[];self.index=0
   def put_nowait(self,row):self.rows.append(row)
   def get(self,**kw):
    if self.rows:
     row=self.rows.pop(0);clock[0]=row['exch_feed_time'];return row
    stage=self.index//2;premium=self.index%2
    if stage==len(stages):raise ValueError('offline Delta option fixture completed')
    clock[0]=base+stage*60+premium;broker=instances['broker']
    symbol=next(s for s in broker.symbols if s!=under) if premium else under
    broker.publish(symbol,stages[stage][premium],clock[0])
    if manual and self.index==0:
     expected=manual_entry.runtime_identity(config,folder/'run','LIVE' if live else 'PAPER')
     manual_entry.enqueue(folder/'run',expected,dict(expected,direction='PE',request_id='c'*32),now=clock[0])
    self.index+=1;return self.rows.pop(0)
  class FakeExecutor:
   def __init__(self,*args,**kw):self.state=dict(position=None,pending=None);self.live=kw.get('live',False);self.actions=[];instances['executor']=self;instances['live']=kw['live']
   def submit(self,action,quote):
    self.actions.append(action);self.state['position']=dict(action['position'],quantity=1) if action['action']=='BUY' else None
    return dict(simulated_fill=quote['ask'],offline_fixture=True)
   def save(self):(folder/'executor-state.json').write_text(json.dumps(self.state))
   def close(self):pass
  def history(delta,symbol,*args):
   prices=[100,98,96,94,92] if symbol==under else [40,41,42,43,44,45];last=clock[0]//60*60-60
   return [[last-(len(prices)-1-i)*60,p,p+1,p-1,p,None] if hybrid else [last-(len(prices)-1-i)*60,None,None,None,p,None] for i,p in enumerate(prices)]
  def select(delta,under,side,*args,**kwargs):return dict(symbol='CALL' if side=='CE' else 'PUT',underlying=under,option_type=side,lot_size=1,expiry=base+86400),.2 if side=='CE' else -.2
  def read(path,params):
   stage=int((params['start']-(base-15))/60);price=stages[stage][0 if params['symbol']==under else 1]
   return dict(result=[dict(time=params['start'],open=price,high=price,low=price,close=price,volume=1)])
  delta._get.side_effect=read
  original_dispatch=manual_entry.ManualDispatcher
  with tempfile.TemporaryDirectory() as directory:
   folder=Path(directory);config=dict(account='a'*32,broker='DELTA_INDIA',underlying=under,market='CRYPTO',execution_route='OPTIONS',execution_mode='LIVE' if live else 'PAPER',timeframe=1,reference_value=46,lots=1,accept_close_source_renko_approximation=True,runtime_session='b'*32)
   if hybrid:config['calculation_mode']='HYBRID'
   path=folder/'config.json';path.write_text(json.dumps(config))
   with ExitStack() as stack:
    for target,value in [
     ('delta_live.runtime_configuration',lambda config,output:config),('delta_live.automatic_strategy',lambda engine,*args,**kw:engine),
     ('delta_live.bound_delta',lambda *args:delta),('delta_live.inspect',lambda *args:dict(instrument={})),
     ('delta_live.DeltaExecution',FakeExecutor),('delta_live.SourceBroker',FakeBroker),('delta_live.queue.Queue',FakeQueue),
     ('delta_live.history',history),('delta_live.select_option',select),('delta_live.live_readiness',Mock()),
     ('delta_live.ManualDispatcher',lambda *args,**kw:original_dispatch(*args,**kw,clock=lambda:clock[0]))]:
     stack.enter_context(patch(target,value))
    stack.enter_context(patch.dict(os.environ,{'AI_RENKO_LIVE_ORDERS':'I_ACCEPT_REAL_ORDERS'}))
    with self.assertRaisesRegex(ValueError,'offline Delta option fixture completed'):delta_live.stream(SimpleNamespace(config=str(path),output=str(folder/'run'),live=live))
   actions=instances['executor'].actions
   self.assertEqual(actions[0]['action'],'BUY');self.assertEqual(actions[0]['position']['side'],'PE' if manual else 'CE')
   self.assertEqual(actions[0].get('manual_override',False),manual)
   self.assertTrue(any(a['action']=='SELL' and a['reason']=='AI_RENKO_SUPERTREND_PREMIUM' for a in actions))
   self.assertEqual(instances['live'],live);self.assertTrue(instances['stopped']);delta._private.assert_not_called()
   if manual:self.assertEqual(json.loads((folder/'run/manual-entry/latest.json').read_text())['phase'],'FILLED')
 def test_automatic_option_entry_and_premium_exit(self):self.run_worker()
 def test_live_branch_is_mocked_and_sends_no_real_orders(self):self.run_worker(live=True)
 def test_manual_put_is_managed_by_normal_premium_exit(self):self.run_worker(manual=True)

class DeltaCompletedHybridOptionRuntimeTests(DeltaOptionRuntimeTests):
 def test_completed_unit_hybrid_option_execution_through_mock_worker(self):self.run_worker(hybrid=True)
