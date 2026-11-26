import json,tempfile,unittest
from pathlib import Path
import test_dhan_direct as fixtures
from dhan_direct_adapter import DhanDirectAdapter
from dhan_direct_runtime import Runtime,make_executor
from reversal import advance
from position_control import enqueue
from manual_entry import runtime_identity
class RuntimeTests(unittest.TestCase):
 def fixture(self,folder,live=False):
  root=Path(folder);api,n,client,unused,order,row=fixtures.DhanDirectTests().fixture(root/'boundary-fixture')
  n.service.folder=root/'account';n.service.folder.mkdir()
  n.account_identity='fixture-identity';n.start=lambda:None;n.subscribe=lambda *args:None
  config=dict(api.config,execution_mode='LIVE' if live else 'PAPER',timeframe=1,runtime_session='b'*32,reference_value=200,calculation_mode='CANDLES',entry_gate='underlying_flip',exit_supertrend='underlying',signal_source='UNDERLYING',indicator_length=5,indicator_factor=3)
  adapter=DhanDirectAdapter(config,n)
  now=int(n.clock());rows=[dict(timestamp=now-(30-i)*60,open=100+i,high=102+i,low=99+i,close=101+i,volume=1) for i in range(30)]
  adapter.candles=lambda *args,**kwargs:rows
  executor=make_executor(config,adapter,state_dir=root/'state',live=live)
  (root/'config.json').write_text(json.dumps(config))
  runtime=Runtime(config,root,adapter,executor,clock=n.clock,engine_factory=lambda engine,*args,**kwargs:engine)
  self.addCleanup(executor.close);self.addCleanup(runtime.close)
  return config,adapter,executor,runtime,client
 def test_completed_history_warms_without_historical_orders(self):
  with tempfile.TemporaryDirectory() as folder:
   c,a,x,r,client=self.fixture(folder)
   self.assertIsNone(x.state['position']);self.assertIsNone(r.engine.pending_direction)
   self.assertFalse(any(path=='/orders' for _,path,_ in client.calls))
 def test_paper_manual_position_and_stop_close_without_broker_submission(self):
  with tempfile.TemporaryDirectory() as folder:
   c,a,x,r,client=self.fixture(folder);r.source_ready=True
   r.submit(r.engine.manual_entry('SHORT',a.native.clock()))
   self.assertEqual(x.state['position']['side'],'SHORT')
   enqueue(Path(folder),c,dict(runtime_identity(c,folder,'PAPER'),operation='STOP',request_id='c'*32),now=a.native.clock())
   self.assertTrue(r.step());self.assertIsNone(x.state['position'])
   self.assertTrue(r.manager.request['simulated_flat_confirmed'])
   self.assertFalse(any(path=='/orders' for _,path,_ in client.calls))
 def test_opposite_signal_is_retained_until_paper_close_then_opens_once(self):
  with tempfile.TemporaryDirectory() as folder:
   c,a,x,r,client=self.fixture(folder);r.source_ready=True;now=a.native.clock()
   r.submit(r.engine.manual_entry('LONG',now))
   r.engine.pending_direction=('SHORT',now+1);r.engine.under_result=dict(direction=1)
   action=r.engine.exit(now+1,'AI_RENKO_SUPERTREND_UNDERLYING')[0]
   r.submit(action)
   self.assertIsNone(x.state['position']);self.assertIsNotNone(x.state['pending_reversal'])
   advance(r.engine,x,r.submit)
   self.assertEqual(x.state['position']['side'],'SHORT')
   advance(r.engine,x,r.submit)
   events=[json.loads(line) for line in (Path(folder)/'events.jsonl').read_text().splitlines()]
   self.assertEqual([e['action']['action'] for e in events if 'action' in e],['OPEN_LONG','CLOSE_LONG','OPEN_SHORT'])
   self.assertFalse(any(path=='/orders' for _,path,_ in client.calls))

 def test_mocked_live_cancelled_close_retains_signal_and_opens_opposite_only_after_flat(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as folder:
   c,a,x,r,client=self.fixture(folder,live=True);r.source_ready=True
   rows=[];quantity=[0];cancel_close=[True];original=client.request
   def request(method,path,body=None):
    if path!='/orders':return original(method,path,body)
    side=1 if body['transactionType']=='BUY' else -1
    cancelled=side==-1 and quantity[0]>0 and cancel_close[0]
    if cancelled:cancel_close[0]=False
    filled=0 if cancelled else body['quantity']
    row=dict(id=str(len(rows)+1),symbol='NSE_EQ:123',qty=body['quantity'],side=side,productType=body['productType'],orderTag=body['correlationId'],status=1 if cancelled else 2,filledQty=filled,tradedPrice=100)
    rows.append(row);quantity[0]+=filled*side
    return dict(orderId=row['id'])
   client.request=request
   a.native.orders=lambda:list(rows)
   a.native.positions=lambda:[dict(symbol='NSE_EQ:123',netQty=quantity[0],productType='INTRADAY')] if quantity[0] else []
   now=a.native.clock()
   with patch('direct_execution.time.sleep'):
    r.submit(r.engine.manual_entry('LONG',now));self.assertEqual(quantity[0],1)
    r.engine.pending_direction=('SHORT',now+1);r.engine.under_result=dict(direction=1)
    r.submit(r.engine.exit(now+1,'AI_RENKO_SUPERTREND_UNDERLYING')[0])
    self.assertEqual(quantity[0],1);self.assertIsNotNone(x.state['pending'])
    self.assertEqual(len(rows),2)
    r.poll_reconciliation();self.assertIsNone(x.state['pending'])
    self.assertEqual(x.state['position']['quantity'],1)
    advance(r.engine,x,r.submit)
    self.assertEqual(quantity[0],0);self.assertIsNone(x.state['position']);self.assertEqual(len(rows),3)
    advance(r.engine,x,r.submit)
    self.assertEqual(quantity[0],-1);self.assertEqual(x.state['position']['side'],'SHORT')
    self.assertEqual([p['side'] for p in rows],[1,-1,-1,-1])
    self.assertIsNone(x.state['pending_reversal'])
