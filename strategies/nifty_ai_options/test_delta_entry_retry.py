import json,tempfile,unittest
from decimal import Decimal
from unittest.mock import Mock,patch
from contextlib import nullcontext
from pathlib import Path
from delta_execution import DeltaExecution
from test_delta_execution import PRODUCT
from strategies.nifty_ai_options.delta_entry_policy import EntryNotReady,read_depth,sufficient_depth
class RetryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.d=Mock();self.d.clock.return_value=100;self.d.product.return_value=PRODUCT;self.d._position.return_value=0
  self.d._get.return_value=self.book()
  self.n=Mock();self.n.active_orders.return_value=[]
  self.e=DeltaExecution(self.d,'a'*32,self.tmp.name,contracts=2,live=True,native=self.n);self.addCleanup(self.e.close)
  self.calls=[];self.responses=['cancel','fill']
  def submit(*args,**kwargs):
   # Re-open persisted data: the attempt budget exists before the broker POST.
   saved=json.loads(self.e.path.read_text())
   self.assertEqual(saved['pending']['native_request_id'],args[4])
   self.assertEqual(saved['pending']['retry_used'],bool(self.calls))
   self.calls.append((args,kwargs))
  def reconcile(key):
   outcome=self.responses[len(self.calls)-1]
   return dict(status=2 if outcome=='fill' else 1,filledQty=2 if outcome=='fill' else 1 if outcome=='partial' else 0,id='order'+str(len(self.calls)),tradedPrice=101 if outcome=='fill' else None,symbol='BTCUSD',product_id=27,orderTag=key,native_status='closed' if outcome=='fill' else 'pending' if outcome=='unknown' else 'cancelled')
  self.n.submit.side_effect=submit;self.n.reconcile.side_effect=reconcile
  self.stack=[]
  for name,value in [('sector_heatmap.chart_trade_admission.entry_lock',nullcontext()),('sector_heatmap.chart_trade_admission.mark_entry_attempt',None),('sector_heatmap.chart_trade_ownership.assert_no_chart_entry_conflict',None)]:
   p=patch(name,return_value=value);p.start();self.addCleanup(p.stop)
 def book(self,ask='101',bid='100',size=100):
  return dict(result=dict(symbol='BTCUSD',last_updated_at=100000000,buy=[dict(price=bid,size=size)],sell=[dict(price=ask,size=size)]))
 def submit(self):
  return self.e.submit(dict(action='OPEN_LONG',timestamp=100,position=dict(symbol='BTCUSD',underlying='BTCUSD',product_id=27,side='LONG',entry_timestamp=100)),dict(symbol='BTCUSD',bid=99,ask=102,exchange_at=100,received_at=100))
 def test_direct_entry_selects_verified_leveraged_policy(self):
  from unittest.mock import patch
  action=dict(action='OPEN_LONG',timestamp=100,position=dict(symbol='BTCUSD',underlying='BTCUSD',product_id=27,side='LONG',entry_timestamp=100,execution_route='DIRECT'))
  self.responses=['fill']
  self.e.submit(action,dict(symbol='BTCUSD',bid=100,ask=101,exchange_at=100))
  self.assertEqual(self.calls[0][1]['collateral_policy'],'BROKER_CONFIGURED_MARGIN')
 def test_local_funds_rejection_clears_pending_without_retry(self):
  from strategies.renko_supertrend.delta_execution import EntryFundsRejected
  self.n.submit.side_effect=EntryFundsRejected(Decimal('368.45'),Decimal('166.24'),'USD')
  r=self.submit()
  self.assertEqual(r['reason'],'ENTRY_FUNDS_UNAVAILABLE');self.assertEqual(r['orders_submitted'],0)
  self.assertIsNone(self.e.state['pending']);self.assertIsNone(self.e.state['position'])
  self.n.submit.assert_called_once();self.n.reconcile.assert_not_called()
  saved=json.loads(self.e.path.read_text());self.assertEqual(saved['entry_attempts'][-1]['attempts'][-1]['required'],'368.45')
 def test_unavailable_read_only_margin_does_not_become_unknown_order(self):
  from strategies.renko_supertrend.delta_execution import EntryMarginUnavailable
  self.n.submit.side_effect=EntryMarginUnavailable('Leverage snapshot unavailable before submission')
  r=self.submit();self.assertEqual(r['reason'],'ENTRY_MARGIN_UNAVAILABLE')
  self.assertEqual(r['orders_submitted'],0);self.assertIsNone(self.e.state['pending'])
  self.n.submit.assert_called_once();self.n.reconcile.assert_not_called()
 def test_unknown_submission_error_keeps_pending(self):
  self.n.submit.side_effect=TimeoutError('unknown acknowledgement')
  with self.assertRaises(TimeoutError):self.submit()
  self.assertIsNotNone(self.e.state['pending']);self.n.submit.assert_called_once()
 def test_one_retry_after_confirmed_zero_fill_and_flat(self):
  r=self.submit();self.assertEqual(r['filled_quantity'],2);self.assertEqual(len(self.calls),2)
  self.assertEqual(self.calls[1][0][4],self.calls[0][0][4]+'_r1')
  self.assertEqual(self.calls[1][1]['order_type'],'market_order');self.assertNotIn('price_limit',self.calls[1][1]);self.assertIsNone(self.e.state['pending'])
 def test_no_third_attempt_and_no_phantom_position(self):
  self.responses=['cancel','cancel'];r=self.submit()
  self.assertTrue(r['terminal_no_fill']);self.assertEqual(len(self.calls),2);self.assertIsNone(self.e.state['pending']);self.assertIsNone(self.e.state['position']);self.assertEqual(len(self.e.state['seen']),1)
 def test_partial_or_unknown_never_retries(self):
  for outcome in ['partial','unknown']:
   with self.subTest(outcome=outcome):
    self.responses=[outcome];self.calls.clear();self.e.state=dict(position=None,pending=None,seen=[]);self.e.save()
    with self.assertRaises(RuntimeError):self.submit()
    self.assertEqual(len(self.calls),1);self.assertIsNotNone(self.e.state['pending'])
 def test_market_retry_uses_fresh_depth_without_old_limit(self):
  self.d._get.side_effect=[self.book(),self.book(ask='103')]
  r=self.submit();self.assertEqual(r['filled_quantity'],2);self.assertEqual(len(self.calls),2);self.assertEqual(self.calls[1][0][3]['ask'],103);self.assertNotIn('price_limit',self.calls[1][1]);self.assertIsNone(self.e.state['pending'])
 def test_existing_exposure_blocks_retry(self):
  self.d._position.return_value=1
  with self.assertRaises(RuntimeError):self.submit()
  self.assertEqual(len(self.calls),1);self.assertIsNotNone(self.e.state['pending'])
 def test_insufficient_depth_sends_no_order(self):
  self.d._get.return_value=self.book(size=1);r=self.submit()
  self.assertTrue(r['deferred']);self.assertEqual(self.calls,[]);self.assertIsNone(self.e.state['pending'])
 def test_stale_or_foreign_book_sends_no_order(self):
  for field,value in [('last_updated_at',90000000),('symbol','ETHUSD')]:
   self.d._get.return_value=self.book();self.d._get.return_value['result'][field]=value
   self.assertTrue(self.submit()['deferred']);self.assertEqual(self.calls,[])

class NativeBoundTests(unittest.TestCase):
 def native(self):
  import threading
  from strategies.renko_supertrend.delta_execution import Execution
  d=Mock();d.lock=threading.RLock();d.runner={};d.live={};d.product.return_value=PRODUCT;d.clock.return_value=100;d._position.return_value=0
  d._private.return_value=dict(result=[dict(asset_symbol='USD',available_balance='100000')])
  d.submit.side_effect=lambda payload,runner:payload
  n=Execution(d);n.authenticate=Mock();n.active_orders=Mock(return_value=[])
  return n,d
 def test_buy_limit_never_exceeds_original_boundary(self):
  n,d=self.native();q=dict(symbol='BTCUSD',bid=100,ask=101,exchange_at=100,received_at=100)
  result=n.submit('BTCUSD',2,1,q,'retry','BTCUSD','TEST',reduce_only=False,price_limit='101')
  self.assertEqual(Decimal(result['limit_price']),Decimal('101'))
 def test_sell_limit_never_drops_below_original_boundary(self):
  n,d=self.native();q=dict(symbol='BTCUSD',bid=100,ask=101,exchange_at=100,received_at=100)
  result=n.submit('BTCUSD',2,-1,q,'retry','BTCUSD','TEST',reduce_only=False,price_limit='100')
  self.assertEqual(Decimal(result['limit_price']),Decimal('100'))
 def test_price_outside_boundary_does_not_submit(self):
  n,d=self.native();q=dict(symbol='BTCUSD',bid=100,ask=102,exchange_at=100,received_at=100)
  with self.assertRaises(ValueError):n.submit('BTCUSD',2,1,q,'retry','BTCUSD','TEST',reduce_only=False,price_limit='101')
  d.submit.assert_not_called()

class NativeMarketTests(unittest.TestCase):
 native=NativeBoundTests.native
 def test_market_entry_has_no_limit_and_keeps_ioc(self):
  for side in [1,-1]:
   n,d=self.native();q=dict(symbol='BTCUSD',bid=100,ask=101,exchange_at=100,received_at=100)
   result=n.submit('BTCUSD',2,side,q,'market','BTCUSD','TEST',reduce_only=False,order_type='market_order')
   self.assertEqual(result['order_type'],'market_order');self.assertEqual(result['time_in_force'],'ioc');self.assertNotIn('limit_price',result);self.assertFalse(result['reduce_only'])
 def test_direct_market_exit_preserves_reduce_only_without_limit(self):
  for side in [1,-1]:
   n,d=self.native();q=dict(symbol='BTCUSD',bid=100,ask=101,exchange_at=100,received_at=100)
   result=n.submit('BTCUSD',2,side,q,'market','BTCUSD','TEST',reduce_only=True,order_type='market_order')
   self.assertTrue(result['reduce_only']);self.assertEqual(result['order_type'],'market_order');self.assertNotIn('limit_price',result)
 def test_market_execution_cannot_carry_a_limit(self):
  n,d=self.native();q=dict(symbol='BTCUSD',bid=100,ask=101,exchange_at=100,received_at=100)
  with self.assertRaises(ValueError):n.submit('BTCUSD',2,1,q,'market','BTCUSD','TEST',reduce_only=False,order_type='market_order',price_limit='102')
  d.submit.assert_not_called()

class ManualMarketPathTests(unittest.TestCase):
 setUp=RetryTests.setUp
 book=RetryTests.book
 def test_manual_override_uses_market_and_retains_exit_ownership(self):
  action=dict(action='OPEN_LONG',timestamp=100,position=dict(symbol='BTCUSD',underlying='BTCUSD',product_id=27,side='LONG',entry_timestamp=100,manual_override=True))
  r=self.e.submit(action,dict(symbol='BTCUSD',bid=99,ask=102,exchange_at=100,received_at=100))
  self.assertEqual(r['filled_quantity'],2)
  self.assertTrue(all(kwargs['order_type']=='market_order' for args,kwargs in self.calls))
  self.assertTrue(self.e.state['position']['manual_override']);self.assertEqual(self.e.state['position']['quantity'],2)
  self.assertIsNone(self.e.state['pending'])

if __name__=='__main__':unittest.main()

class DurableFillEvidenceTests(unittest.TestCase):
 setUp=RetryTests.setUp
 book=RetryTests.book
 submit=RetryTests.submit
 def test_full_fill_is_durable_before_a_worker_callback_can_fail(self):
  self.responses=['fill'];self.e.fill_evidence_path=Path(self.tmp.name)/'confirmed-fills.jsonl'
  result=self.submit()
  record=json.loads(self.e.fill_evidence_path.read_text())
  self.assertEqual(record['result']['order_id'],result['order_id'])
  self.assertEqual(record['result']['filled_at'],100)
  self.assertEqual(json.loads(self.e.path.read_text())['position']['quantity'],2)
  self.assertEqual(record['source'],'VALIDATED_NATIVE_BROKER_FILL')
 def test_unknown_result_never_creates_confirmed_fill_evidence(self):
  self.responses=['unknown'];self.e.fill_evidence_path=Path(self.tmp.name)/'confirmed-fills.jsonl'
  with self.assertRaises(RuntimeError):self.submit()
  self.assertFalse(self.e.fill_evidence_path.exists())
