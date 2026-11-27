import copy,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from strategies.nifty_ai_options.position_control import PositionManager,entry_guard,enqueue
from strategies.nifty_ai_options.manual_entry import runtime_identity
OWNER='a'*32;SESSION='b'*32
class ExternalIdleTests(unittest.TestCase):
 def setup(self,path,broker='FYERS',side='PE'):
  clock=[1000.]
  c=dict(account=OWNER,broker=broker,underlying='NSE:NIFTY50-INDEX',runtime_session=SESSION,execution_mode='LIVE',execution_route='OPTIONS',timeframe=1)
  p=dict(symbol='NSE:TESTPE',side=side,quantity=20,order_id='owned-entry',entry_timestamp=900,fill_price=100,underlying=c['underlying'])
  state=dict(position=copy.deepcopy(p),pending=None,positions=[copy.deepcopy(p)],closing_legs={},entry_requests={'old':dict(phase='WAITING_FOR_SOURCE')},entry_reservation={'held':True})
  executor=SimpleNamespace(state=state,live=True,save=Mock(),close=Mock(),submit=Mock())
  engine=SimpleNamespace(position=copy.deepcopy(p),pending_underlying_flip='old',pending_direction='PE')
  verify=Mock(side_effect=lambda owned,**kw:dict(flat=True,quantity=0,checked_at=clock[0],account=OWNER,broker=broker))
  manager=PositionManager(c,path,engine,executor,verify=verify,attach=Mock(),submit=Mock(),clock=lambda:clock[0])
  return c,p,executor,engine,verify,manager,clock
 def test_manual_full_close_stops_without_reentry_or_order(self):
  with tempfile.TemporaryDirectory() as d:
   c,p,x,e,v,m,t=self.setup(Path(d))
   self.assertTrue(m.poll());self.assertEqual(m.mode,'STOPPED');self.assertTrue(m.entry_blocked)
   self.assertIsNone(x.state['position']);self.assertFalse(x.state['positions']);self.assertFalse(x.state['closing_legs']);self.assertNotIn('entry_reservation',x.state)
   self.assertIsNone(e.pending_underlying_flip);self.assertTrue(e.entry_paused)
   self.assertEqual(x.state['entry_requests']['old']['phase'],'CANCELLED')
   x.submit.assert_not_called();m.submit.assert_not_called()
   self.assertEqual(m.request['source'],'BROKER_CONFIRMED_EXTERNAL_CLOSE');self.assertFalse(m.request['automatic_reentry'])
   self.assertFalse(m.poll());self.assertEqual(len((Path(d)/'events.jsonl').read_text().splitlines()),1)
 def test_all_four_brokers_use_bound_authoritative_proof(self):
  for broker in ('FYERS','DELTA_INDIA','DHAN','MOTILAL_OSWAL'):
   with self.subTest(broker=broker),tempfile.TemporaryDirectory() as d:
    c,p,x,e,v,m,t=self.setup(Path(d),broker)
    self.assertTrue(m.poll());self.assertEqual(m.request['broker'],broker);x.submit.assert_not_called()
 def test_open_partial_pending_and_failed_responses_do_not_clear(self):
  cases=[dict(flat=False,quantity=20),dict(flat=False,quantity=5),dict(flat=True),dict(flat='true',quantity=0),dict(flat=True,quantity=0,account='wrong'),dict(flat=True,quantity=0,checked_at=900),dict(flat=True,quantity=None)]
  for reply in cases:
   with self.subTest(reply=reply),tempfile.TemporaryDirectory() as d:
    c,p,x,e,v,m,t=self.setup(Path(d));v.side_effect=None;v.return_value=reply
    self.assertFalse(m.poll());self.assertEqual(x.state['position'],p);self.assertEqual(m.mode,'MANAGED');x.submit.assert_not_called()
  with tempfile.TemporaryDirectory() as d:
   c,p,x,e,v,m,t=self.setup(Path(d));v.side_effect=PermissionError('Unauthorized')
   self.assertFalse(m.poll());self.assertEqual(x.state['position'],p)
   for _ in range(10):m.poll()
   self.assertEqual(v.call_count,1)
 def test_pending_intent_and_manual_preparation_skip_broker_check(self):
  with tempfile.TemporaryDirectory() as d:
   c,p,x,e,v,m,t=self.setup(Path(d));x.state['pending']={'unknown':True}
   self.assertFalse(m.poll());v.assert_not_called();self.assertEqual(x.state['position'],p)
   x.state['pending']=None;self.assertFalse(m.poll(busy=True));v.assert_not_called()
 def test_one_closed_leg_does_not_stop_another_open_leg(self):
  with tempfile.TemporaryDirectory() as d:
   c,p,x,e,v,m,t=self.setup(Path(d));other=dict(p,symbol='NSE:TESTCE',side='CE',order_id='other')
   x.state['closing_legs']={'retired':dict(position=other,pending=None)}
   v.side_effect=lambda owned,**kw:dict(flat=owned['symbol']==p['symbol'],quantity=0 if owned['symbol']==p['symbol'] else 20)
   self.assertFalse(m.poll());self.assertEqual(x.state['position'],p);self.assertTrue(x.state['closing_legs'])
 def test_queued_stop_takes_precedence(self):
  with tempfile.TemporaryDirectory() as d:
   c,p,x,e,v,m,t=self.setup(Path(d));payload=dict(runtime_identity(c,Path(d),'LIVE'),operation='STOP',request_id='c'*32)
   enqueue(Path(d),c,payload,now=1000)
   # Explicit Stop uses its existing verification path, not inferred auto-idle.
   m.poll();self.assertNotEqual((m.request or {}).get('source'),'BROKER_CONFIRMED_EXTERNAL_CLOSE')
 def test_paper_never_consults_real_broker(self):
  with tempfile.TemporaryDirectory() as d:
   c,p,x,e,v,m,t=self.setup(Path(d));c['execution_mode']='PAPER';x.live=False
   self.assertFalse(m.poll());v.assert_not_called()
 def test_priced_fill_is_journaled_without_submitting(self):
  with tempfile.TemporaryDirectory() as d:
   c,p,x,e,v,m,t=self.setup(Path(d))
   x.reconcile_external_close=Mock(return_value=dict(broker_flat_confirmed=True,quantity=20,broker_order_at=990,broker_trade_at=991,exit_order='manual-close',fill_price=105,fill_time_basis='broker tradebook'))
   self.assertTrue(m.poll())
   row=json.loads((Path(d)/'events.jsonl').read_text().splitlines()[0])
   self.assertEqual(row['result']['fill_price'],105);self.assertEqual(row['result']['order_id'],'manual-close');x.submit.assert_not_called()
   markers=json.loads((Path(d)/'markers.json').read_text());self.assertEqual(len(markers),1);self.assertEqual(markers[0]['order_id'],'manual-close');self.assertTrue(markers[0]['external_exit'])
 def test_other_instrument_state_unchanged(self):
  with tempfile.TemporaryDirectory() as d:
   c,p,x,e,v,m,t=self.setup(Path(d));other=Path(d)/'unrelated.json';other.write_text('{"position":{"symbol":"OTHER"}}')
   before=other.read_bytes();self.assertTrue(m.poll());self.assertEqual(other.read_bytes(),before)

class FreshStartTests(unittest.TestCase):
 def test_live_ledger_lock_released_and_new_user_start_can_enter_in_isolation(self):
  from strategies.nifty_ai_options.direct_execution import DirectExecution
  from contextlib import nullcontext
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);old=root/'old';old.mkdir()
   api=Mock();meta=lambda s:dict(symbol=s,product_type='STOCK',lot_size=1,tick_size=.05)
   x=DirectExecution(api,OWNER,root/'state',live=True,lots=10,product='INTRADAY',master=meta,management_only=True)
   c=dict(account=OWNER,broker='FYERS',underlying='NSE:TEST-EQ',runtime_session=SESSION,execution_mode='LIVE',execution_route='DIRECT',timeframe=1)
   own=dict(symbol=c['underlying'],underlying=c['underlying'],execution_route='DIRECT',side='LONG',quantity=10,order_id='old',fill_price=100,entry_timestamp=900,spot_brick=1)
   x.state['position']=own;x.save()
   m=PositionManager(c,old,SimpleNamespace(position=own),x,verify=lambda p,**kw:dict(flat=True,quantity=0),attach=Mock(),submit=Mock(),clock=lambda:1000)
   self.assertTrue(m.poll());api.place_order.assert_not_called()
   x.close() # owning worker returns from poll and finally closes its OS lock
   y=DirectExecution(api,OWNER,root/'state',live=True,lots=10,product='INTRADAY',master=meta,account_folder=root,margin=Mock(return_value=100))
   self.addCleanup(y.close)
   new=root/'new';new.mkdir();fresh=dict(c,runtime_session='d'*32)
   engine=SimpleNamespace(position=None)
   manager=PositionManager(fresh,new,engine,y,verify=Mock(),attach=Mock(),submit=Mock())
   self.assertEqual(manager.mode,'MANAGED');self.assertFalse(manager.entry_blocked)
   with entry_guard(new,y):pass
   api.positions.side_effect=[dict(s='ok',netPositions=[]),dict(s='ok',netPositions=[dict(symbol=c['underlying'],netQty=10,productType='INTRADAY')])]
   api.orderbook.side_effect=[dict(s='ok',orderBook=[]),dict(s='ok',orderBook=[dict(id='fresh',status=2,filledQty=10,tradedPrice=100)])]
   api.funds.return_value=dict(s='ok',fund_limit=[dict(id=10,equityAmount=100000)])
   api.place_order.return_value=dict(s='ok',id='fresh')
   stamp=time.time();action=dict(action='OPEN_LONG',timestamp=stamp,position=dict(own,entry_timestamp=stamp))
   with patch('sector_heatmap.chart_trade_admission.entry_lock',return_value=nullcontext()),patch('sector_heatmap.chart_trade_admission.mark_entry_attempt'),patch('sector_heatmap.chart_trade_ownership.assert_no_chart_entry_conflict'),patch('strategies.nifty_ai_options.direct_execution.time.sleep'):
    receipt=y.submit(action,dict(timestamp=stamp,ltp=100),now=stamp)
   self.assertEqual(receipt['filled_quantity'],10);self.assertEqual(y.state['position']['order_id'],'fresh');self.assertEqual(api.place_order.call_count,1)

class UnpricedJournalTests(unittest.TestCase):
 def test_verified_flat_closes_journal_without_inventing_price_or_profit(self):
  from strategies.nifty_ai_options.trade_journal import sync_account,report
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);run=root/'runs'/OWNER/'run';run.mkdir(parents=True)
   c=dict(account=OWNER,broker='FYERS',underlying='NSE:TEST-EQ',execution_mode='LIVE')
   p=dict(symbol='NSE:TEST-EQ',quantity=10,side='LONG',order_id='owned-entry')
   (run/'config.json').write_text(json.dumps(c))
   opened=dict(action=dict(action='OPEN_LONG',timestamp=1,position=p),result=dict(order_id='owned-entry',fill_price=100,filled_quantity=10,filled_at=1))
   closed=dict(action=dict(action='EXTERNAL_FLAT',timestamp=2,position=p),result=dict(broker_flat_confirmed=True,orders_submitted=0),broker_reconciliation=dict(account=OWNER,broker='FYERS',symbol=p['symbol'],quantity=0,checked_at=2))
   events=run/'events.jsonl';events.write_text(json.dumps(opened)+'\n'+json.dumps(dict(closed,broker_reconciliation=dict(closed['broker_reconciliation'],account='wrong')))+'\n')
   sync_account(OWNER,root);self.assertEqual(report(OWNER,data=root)['rows'][0]['status'],'OPEN')
   with events.open('a') as out:out.write(json.dumps(closed)+'\n')
   sync_account(OWNER,root);sync_account(OWNER,root);row=report(OWNER,data=root)['rows'][0]
   self.assertEqual(row['status'],'CLOSED');self.assertIsNone(row['exit_premium']);self.assertIsNone(row['gross_profit']);self.assertIn('exact fill unavailable',row['exit_time_basis'])
