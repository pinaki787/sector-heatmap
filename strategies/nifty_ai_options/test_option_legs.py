import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from contextlib import nullcontext
from execution import Execution
from option_legs import OptionLegBook
NOW=2000000000
class API:
 def __init__(self):self.qty={};self.orders=[];self.fill_exits=False
 def positions(self):return dict(s='ok',netPositions=[dict(symbol=s,netQty=q,productType='MARGIN') for s,q in self.qty.items()])
 def orderbook(self):return dict(s='ok',orderBook=copy.deepcopy(self.orders))
 def funds(self):return dict(s='ok',fund_limit=[dict(id=10,equityAmount=1000000)])
 def place_order(self,data):
  o=dict(data,id=str(len(self.orders)+1),status=2 if data['side']==1 or self.fill_exits else 6,filledQty=data['qty'] if data['side']==1 or self.fill_exits else 0,tradedPrice=100)
  self.orders.append(o)
  if o['status']==2:self.qty[o['symbol']]=self.qty.get(o['symbol'],0)+o['qty']*o['side']
  return dict(s='ok',id=o['id'])
 def complete(self):
  for o in self.orders:
   if o['status']==6:
    o.update(status=2,filledQty=o['qty']);self.qty[o['symbol']]=self.qty.get(o['symbol'],0)+o['qty']*o['side']
def meta(symbol):return dict(lot_size=20,tick_size=.05,option_type='CE' if symbol.endswith('CE') else 'PE',expiry_epoch=NOW+86400)
def action(symbol,name,at):return dict(action=name,timestamp=at,position=dict(symbol=symbol,side='CE' if symbol.endswith('CE') else 'PE',option_type='CE' if symbol.endswith('CE') else 'PE',expiry=NOW+86400,entry_timestamp=at if name=='BUY' else NOW,underlying='BSE:SENSEX-INDEX'))
class OptionLegTests(unittest.TestCase):
 def guards(self):
  from contextlib import ExitStack
  stack=ExitStack()
  for target in ['sector_heatmap.chart_trade_admission.entry_lock','sector_heatmap.chart_trade_admission.mark_entry_attempt','sector_heatmap.chart_trade_ownership.assert_no_chart_entry_conflict']:
   stack.enter_context(patch(target,return_value=nullcontext()))
  stack.enter_context(patch('execution.time.time',return_value=NOW))
  stack.enter_context(patch('execution.time.sleep'))
  return stack
 def book(self,folder,api,live=False,management=False):
  base=Execution(api,'account',folder/'state',live=live,lots=1,product='MARGIN',master=meta,account_folder=folder,management_only=management)
  return OptionLegBook(base,folder/'runs'/'run',dict(account='account',execution_route='OPTIONS',execution_mode='LIVE' if live else 'PAPER'),quote=lambda s:dict(timestamp=NOW,ltp=100),clock=lambda:NOW)
 def test_paper_put_opens_before_old_call_close_and_journals_are_separate(self):
  with tempfile.TemporaryDirectory() as d,self.guards():
   folder=Path(d);api=API();b=self.book(folder,api)
   b.submit(action('BSE:CALLCE','BUY',NOW),dict(timestamp=NOW,ltp=100),now=NOW)
   b.submit(action('BSE:CALLCE','SELL',NOW+1),dict(timestamp=NOW,ltp=100),now=NOW)
   b.submit(action('BSE:PUTPE','BUY',NOW+1),dict(timestamp=NOW,ltp=90),now=NOW)
   self.assertEqual(len(b.state['positions']),2);self.assertEqual(b.state['position']['side'],'PE')
   b.poll(force=True);b.poll(force=True)
   self.assertEqual(b.state['position']['symbol'],'BSE:PUTPE');self.assertFalse(b.state['closing_legs'])
   events=[json.loads(x) for x in (folder/'runs/run/events.jsonl').read_text().splitlines()]
   self.assertEqual([r['action']['position']['symbol'] for r in events],['BSE:CALLCE'])
   self.assertEqual(api.orders,[]);b.close()
 def test_live_pending_call_does_not_block_put_and_survives_recovery(self):
  with tempfile.TemporaryDirectory() as d,self.guards():
   folder=Path(d);api=API();b=self.book(folder,api,live=True)
   b.submit(action('BSE:CALLCE','BUY',NOW),dict(timestamp=NOW,ltp=100),now=NOW)
   b.submit(action('BSE:CALLCE','SELL',NOW+1),dict(timestamp=NOW,ltp=100),now=NOW)
   b.poll(force=True)
   self.assertIsNotNone(next(iter(b.state['closing_legs'].values()))['pending'])
   b.submit(action('BSE:PUTPE','BUY',NOW+2),dict(timestamp=NOW,ltp=100),now=NOW)
   self.assertEqual(b.state['position']['symbol'],'BSE:PUTPE');self.assertEqual(len(b.state['positions']),2)
   before=len(api.orders);b.poll(force=True);self.assertEqual(len(api.orders),before)
   b.close();b=self.book(folder,api,live=True,management=True)
   self.assertEqual(len(b.state['positions']),2)
   api.complete();b.poll(force=True)
   self.assertFalse(b.state['closing_legs']);self.assertEqual(b.state['position']['symbol'],'BSE:PUTPE')
   self.assertEqual(len(api.orders),before)
   self.assertTrue((folder/'runs/run/markers.json').exists());b.close()
 def test_stop_does_not_report_flat_until_every_leg_is_closed(self):
  with tempfile.TemporaryDirectory() as d,self.guards():
   folder=Path(d);api=API();b=self.book(folder,api,live=True)
   b.submit(action('BSE:CALLCE','BUY',NOW),dict(timestamp=NOW,ltp=100),now=NOW)
   b.submit(action('BSE:CALLCE','SELL',NOW+1))
   b.submit(action('BSE:PUTPE','BUY',NOW+2),dict(timestamp=NOW,ltp=100),now=NOW)
   self.assertFalse(b.stop_all(force=True)['flat']);self.assertEqual(len(b.state['positions']),2)
   api.complete();self.assertTrue(b.stop_all(force=True)['flat']);self.assertFalse(b.state['positions']);b.close()

 def test_recovery_after_event_write_does_not_duplicate_journal_receipt(self):
  with tempfile.TemporaryDirectory() as d,self.guards():
   folder=Path(d);b=self.book(folder,API())
   fill=dict(id='exit-one',action=action('BSE:CALLCE','SELL',NOW),result=dict(simulated_fill=100),confirmed_at=NOW)
   slot=dict(origin=str(folder/'runs/run'),last_fill=fill,delivered=[])
   b._deliver(slot)
   slot['delivered']=[] # crash before durable delivery acknowledgement
   b._deliver(slot)
   rows=(folder/'runs/run/events.jsonl').read_text().splitlines()
   self.assertEqual(len(rows),1)
   self.assertEqual(len(json.loads((folder/'runs/run/markers.json').read_text())),1)
   b.close()
 def test_retained_entry_is_one_shot_and_invalidated_signal_is_not_replayed(self):
  with tempfile.TemporaryDirectory() as d,self.guards():
   folder=Path(d);b=self.book(folder,API())
   a=action('BSE:PUTPE','BUY',NOW);b.remember_entry(a)
   sent=[]
   b.dispatch_entries(lambda x:sent.append(x),lambda x:False)
   b.dispatch_entries(lambda x:sent.append(x),lambda x:True)
   self.assertEqual(sent,[])
   self.assertEqual(next(iter(b.state['entry_requests'].values()))['phase'],'CANCELLED')
   b.close()
