import unittest
from unittest.mock import Mock,patch
from sector_heatmap.fyers_execution import _PreviewReads
from tests import test_fyers_execution as fixtures
class PreviewReadsTests(unittest.TestCase):
 def test_deduplication_is_scoped_and_copies_results(self):
  c=Mock();c.funds.side_effect=lambda: {'s':'ok','amount':100};scope=_PreviewReads(c,clock=lambda:0,sleep=lambda _:None)
  first=scope.funds();first['amount']=0
  self.assertEqual(scope.funds()['amount'],100);self.assertEqual(c.funds.call_count,1)
  self.assertEqual(_PreviewReads(c,clock=lambda:0).funds()['amount'],100);self.assertEqual(c.funds.call_count,2)
 def test_market_and_account_snapshots_expire(self):
  tick=[0];c=Mock();c.quotes.return_value={'s':'ok'};c.funds.return_value={'s':'ok'}
  scope=_PreviewReads(c,clock=lambda:tick[0],sleep=lambda _:None)
  scope.quotes({'symbols':'A'});scope.funds();tick[0]=3;scope.quotes({'symbols':'A'});scope.funds()
  self.assertEqual(c.quotes.call_count,2);self.assertEqual(c.funds.call_count,1)
  tick[0]=6;scope.funds();self.assertEqual(c.funds.call_count,2)
 def test_failures_are_never_cached_and_mutations_unavailable(self):
  c=Mock();c.funds.return_value={'s':'error','code':-429};scope=_PreviewReads(c,clock=lambda:0,sleep=lambda _:None)
  scope.funds();scope.funds();self.assertEqual(c.funds.call_count,2)
  with self.assertRaises(AttributeError):scope.place_order({})
 def test_burst_is_paced(self):
  c=Mock();c.funds.return_value=c.positions.return_value={'s':'ok'};sleep=Mock()
  scope=_PreviewReads(c,clock=lambda:0,sleep=sleep);scope.funds();scope.positions();sleep.assert_called_once_with(.2)
 @patch('sector_heatmap.fyers_execution.load_config',return_value={'FYERS_ACCESS_TOKEN':'APP:token'})
 @patch('sector_heatmap.fyers_execution.time.sleep')
 def test_two_stock_batch_reads_account_once_and_next_operation_refreshes(self,*_):
  client=fixtures.FakeClient()
  for name in ('get_profile','funds','positions','orderbook','quotes'):setattr(client,name,Mock(wraps=getattr(client,name)))
  helper=fixtures.FyersExecutionTests();self.addCleanup(helper.doCleanups);service=helper.make_service(client)
  def item(symbol,stop,target):return {'broker':'fyers','underlying':symbol,'invalidation':stop,'quantity':1,'proposal':{'kind':'EQUITY','label':'test','direction':'BULLISH','quantity':1,'target':target},'daily_loss_limit':5000,'idea_risk_limit':2000,'risk_reserve':1000,'max_simultaneous_positions':3,'enforce_risk_controls':True}
  payload={'items':[item('NSE:TEST-EQ',95,110),item('NSE:TEST2-EQ',195,210)]}
  service.prepare_batch(payload)
  for name in ('get_profile','funds','positions','orderbook'):self.assertEqual(getattr(client,name).call_count,1,name)
  self.assertEqual(client.quotes.call_count,2)
  service.prepare_batch(payload)
  for name in ('get_profile','funds','positions','orderbook'):self.assertEqual(getattr(client,name).call_count,2,name)
if __name__=='__main__':unittest.main()
