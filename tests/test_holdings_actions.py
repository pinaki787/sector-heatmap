from contextlib import nullcontext
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from sector_heatmap.holdings_actions import HoldingActions
from sector_heatmap.holdings_analysis import review
from tests.test_holdings_analysis import candles,holding,NOW,SESSION

class ChartEvidenceTests(unittest.TestCase):
 def test_chart_matches_rule_seeds_and_excludes_forming_day(self):
  data=candles();row=holding(data)
  result=review(row,data,SESSION,NOW)
  chart=result['chart']
  for key in ('ema20','ema50','weekly_ema20','atr14','rsi14'):
   self.assertAlmostEqual(chart['series'][key][-1]['value'],result['evidence'][key],places=3)
  self.assertEqual(chart['last_session'],SESSION)
  self.assertTrue(all(c['time']<=SESSION for c in chart['candles']))
  self.assertAlmostEqual(chart['weekly_ema20'][-1]['value'],result['evidence']['weekly_ema20'],places=3)

class CurrentChartTests(unittest.TestCase):
 def test_current_chart_fetches_only_one_saved_row_without_analysis(self):
  from sector_heatmap.holdings_chart import current_chart
  calls=[]
  adapter=SimpleNamespace(broker='DHAN',candles=lambda row,now:(calls.append(row['symbol']) or candles()))
  result=current_chart(adapter,{'symbol':'NSE:TEST-EQ'},NOW)
  self.assertEqual(calls,['NSE:TEST-EQ'])
  self.assertTrue(result['chart']['candles'])
  self.assertIn('separately from the saved review',result['chart']['basis'])
 def test_no_data_and_invalid_ohlc_are_explicit_failures(self):
  from sector_heatmap.holdings_chart import current_chart
  adapter=SimpleNamespace(broker='DHAN',candles=lambda row,now:[])
  with self.assertRaisesRegex(ValueError,'no completed daily candles'):current_chart(adapter,{'symbol':'NSE:TEST-EQ'},NOW)
  adapter.candles=lambda row,now:[dict(timestamp=NOW-86400,open=100,high=50,low=90,close=100)]
  with self.assertRaisesRegex(ValueError,'inconsistent'):current_chart(adapter,{'symbol':'NSE:TEST-EQ'},NOW)

class ActionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.h=dict(securityId='42',exchange='ALL',tradingSymbol='TEST',totalQty=10,availableQty=10,avgCostPrice=80,mtf_qty=10,mtf_t1_qty=0,isin='abc')
  self.books={'/profile':{'dhanClientId':'123'},'/holdings':[self.h],'/positions':[],'/orders':[],'/forever/orders':[],'/super/orders':[],'/ip/getIP':{'primaryIP':'1.2.3.4'}}
  self.posts=[]
  def request(method,path,payload=None):
   if method=='GET':return self.books[path]
   self.posts.append((method,path,payload));return {'orderId':'order1','orderStatus':'PENDING'}
  client=SimpleNamespace(client_id='123',request=request)
  self.execution=SimpleNamespace(account={'id':'aid','live_enabled':True},folder=Path(self.tmp.name),_client=lambda:client,
    master=SimpleNamespace(resolve=lambda payload,now:dict(symbol='TEST',tick_size=.01)),execution_allowed=lambda:True,
    _submission_lock=lambda:nullcontext(),egress=lambda:'1.2.3.4')
  self.service=HoldingActions(self.execution,clock=lambda:NOW)
  self.report=dict(broker='DHAN',account_id='aid',as_of=datetime.fromtimestamp(NOW,timezone.utc).isoformat())
  self.row=dict(id='0',kind='DELIVERY_EQUITY',action='TRAIL',quantity=10,average_price=80,holding_type='MTF funded equity',
    symbol='NSE:TEST-EQ',native_identity=dict(securityId='42',exchangeSegment='NSE_EQ'),candidate_stop=95)
  self.quote=patch('sector_heatmap.holdings_actions.fresh_quote_snapshot',return_value=({'last_price':100},NOW));self.quote.start();self.addCleanup(self.quote.stop)
 def test_manual_exit_from_review_needed_uses_existing_fresh_broker_gates(self):
  row=dict(self.row,action='REVIEW_NEEDED',candidate_stop=None)
  with patch('sector_heatmap.holdings_actions.market_session',return_value={'status':'OPEN'}),patch('sector_heatmap.holdings_actions.fresh_quote_snapshot',return_value=({'last_price':100,'depth':{'buy':[{'price':99.9}]}},NOW)):
   plan=self.service.prepare(dict(self.report,as_of='2020-01-01T00:00:00+00:00'),row,{'manual_action':'EXIT','quantity':10})
   self.assertEqual(plan['ticket']['transactionType'],'SELL')
   self.assertEqual(plan['ticket']['quantity'],10)
   self.assertEqual(plan['endpoint'],'/orders')
   self.assertEqual(plan['decision_source'],'USER_MANUAL')
   self.assertEqual(row['action'],'REVIEW_NEEDED')
   self.assertFalse(self.posts)
   with self.assertRaisesRegex(ValueError,'full reviewed'):self.service.prepare(self.report,row,{'manual_action':'EXIT','quantity':2})
   plan=self.service.prepare(self.report,row,{'manual_action':'BOOK_PROFIT','quantity':2})
   self.assertEqual(plan['ticket']['quantity'],2)
   with self.assertRaises(ValueError):self.service.prepare(self.report,row,{'manual_action':'BOOK_PROFIT','quantity':11})
   with self.assertRaises(ValueError):self.service.prepare(self.report,dict(row,kind='OPEN_POSITION'),{'manual_action':'EXIT','quantity':10})
   self.assertFalse(self.posts)
 def test_preview_never_places_order_and_preserves_mtf(self):
  p=self.service.prepare(self.report,self.row,{})
  self.assertEqual(self.posts,[])
  self.assertEqual(p['ticket']['productType'],'MTF')
  self.assertEqual(p['ticket']['triggerPrice'],95)
  self.assertEqual(p['endpoint'],'/forever/orders')
  self.assertLessEqual(p['ticket']['price'],95)
 def test_stale_other_account_invalid_qty_or_existing_protection_block(self):
  for report,row,payload in ((dict(self.report,account_id='other'),self.row,{}),(dict(self.report,as_of='2020-01-01T00:00:00+00:00'),self.row,{}),(self.report,self.row,{'quantity':11}),(self.report,dict(self.row,action='HOLD'),{}),(self.report,dict(self.row,candidate_stop=101),{})):
   with self.assertRaises((ValueError,PermissionError)):self.service.prepare(report,row,payload)
  self.books['/forever/orders']=[dict(securityId='42',exchangeSegment='NSE_EQ',orderStatus='CONFIRM')]
  with self.assertRaisesRegex(ValueError,'existing'):self.service.prepare(self.report,self.row,{})
  self.assertFalse(self.posts)
 def test_confirmation_and_live_gate_then_exactly_once(self):
  p=self.service.prepare(self.report,self.row,{})
  with self.assertRaises(ValueError):self.service.submit(p['preview_id'],'wrong')
  self.execution.account['live_enabled']=False
  with self.assertRaises(PermissionError):self.service.submit(p['preview_id'],p['confirmation_phrase'])
  self.execution.account['live_enabled']=True
  self.assertEqual(self.service.submit(p['preview_id'],p['confirmation_phrase'])['status'],'PENDING')
  with self.assertRaises(ValueError):self.service.submit(p['preview_id'],p['confirmation_phrase'])
  self.assertEqual(len(self.posts),1)
 def test_state_drift_blocks_submission(self):
  p=self.service.prepare(self.report,self.row,{})
  self.h['availableQty']=9
  with self.assertRaises(ValueError):self.service.submit(p['preview_id'],p['confirmation_phrase'])
  self.assertFalse(self.posts)
 def test_uncertain_submission_is_journalled_and_cannot_repeat(self):
  p=self.service.prepare(self.report,self.row,{})
  c=self.execution._client()
  original=c.request
  def request(method,path,payload=None):
   if method=='POST':raise RuntimeError('timeout')
   return original(method,path,payload)
  c.request=request
  self.assertEqual(self.service.submit(p['preview_id'],p['confirmation_phrase'])['status'],'UNKNOWN')
  with self.assertRaises(ValueError):self.service.prepare(self.report,self.row,{})
