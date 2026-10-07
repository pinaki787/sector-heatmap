from datetime import datetime,timezone
from decimal import InvalidOperation
from unittest.mock import patch
import unittest
from tests import test_delta_india as fixture
PRODUCT=fixture.PRODUCT
class ChartOptions(unittest.TestCase):
 def setUp(self):
  fixture.Tests.setUp(self);self.rows=[]
  self.b.chart=lambda *a:dict(last_completed=dict(timestamp=99690,cross_direction='BEARISH'))
  self.b.product=lambda s: next(r for r in self.rows if r['symbol']==s)
  self.b.catalog=lambda: {'instruments':self.rows}
  self.b.ticker=lambda s:dict(symbol=s,bid=100,ask=101,spot_price='100.4',exchange_at=self.req.now,received_at=self.req.now)
  base=self.b._metadata(PRODUCT);self.rows.append(base)
  for typ,prefix in [('call_options','C'),('put_options','P')]:
   for expiry in [self.req.now-1,self.req.now+100,self.req.now+200]:
    for strike in ['100','101']:
     self.rows.append(dict(base,id=len(self.rows)+30,symbol=f'{prefix}-{strike}-{expiry}',contract_type=typ,strike_price=strike,settlement_time=datetime.fromtimestamp(expiry,timezone.utc).isoformat()))
 def test_nearest_expiry_then_atm_and_both_buy(self):
  for d,prefix in [('BUY','C'),('SELL','P')]:
   r=self.b.chart_option('BTCUSD',d);self.assertEqual(r['symbol'],f'{prefix}-100-100100');self.assertEqual(r['side'],'buy')
 def test_expired_missing_and_stale_fail_closed(self):
  self.rows=[r for r in self.rows if r['contract_type']!='put_options']
  with self.assertRaisesRegex(ValueError,'No still-unexpired'):self.b.chart_option('BTCUSD','SELL')
  with patch.object(self.b,'ticker',return_value=dict(spot_price='100',exchange_at=self.req.now-20)):
   with self.assertRaisesRegex(ValueError,'expired'):self.b.chart_option('BTCUSD','BUY')
 def test_server_rechecks_symbol_side_reduce_and_paper(self):
  good=dict(chart_symbol='BTCUSD',chart_direction='SELL',symbol='P-100-100100',side='buy',chart_resolution='5m',chart_rsi_length=14,chart_ma_length=14,chart_ma_type='SMA',chart_signal_close=99990)
  self.b._chart_intent(good)
  for change in [dict(side='sell'),dict(symbol='BTCUSD'),dict(reduce_only=True)]:
   with self.assertRaisesRegex(ValueError,'selection changed'):self.b._chart_intent(good|change)
  self.b._chart_intent(good|dict(side='LONG'),paper=True)
 def test_strike_tie_lower_and_missing_spot(self):
  with patch.object(self.b,'ticker',return_value=dict(spot_price='100.5',exchange_at=self.req.now)):
   self.assertEqual(self.b.chart_option('BTCUSD','BUY')['strike'],'100')
  with patch.object(self.b,'ticker',return_value=dict(spot_price=None,exchange_at=self.req.now)):
   with self.assertRaisesRegex(ValueError,'spot'):self.b.chart_option('BTCUSD','BUY')

 def test_put_market_submit_uses_long_exact_contract_and_duplicate_guard(self):
  self.b.credentials=lambda:dict(DELTA_INDIA_API_KEY='fake-key',DELTA_INDIA_API_SECRET='fake-secret',DELTA_INDIA_ENABLE_LIVE_ORDERS='1')
  self.b.requester=fixture.LiveRequests()
  t=dict(mode='LIVE',request_id='chart-put-market-test',chart_symbol='BTCUSD',chart_direction='SELL',symbol='P-100-100100',side='buy',contracts=2,order_type='market_order',time_in_force='ioc',reduce_only=False,chart_resolution='5m',chart_rsi_length=14,chart_ma_length=14,chart_ma_type='EMA',chart_signal_close=99990)
  r=self.b.submit(t);self.assertEqual(r['status'],'closed');self.assertEqual(r['request']['side'],'buy');self.assertEqual(r['symbol'],'P-100-100100');self.assertNotIn('limit_price',r['request']);self.b.submit(t);self.assertEqual(self.b.requester.posts,1)

 def test_chart_manual_intent_ignores_absent_wrong_stale_and_used_signal(self):
  t=dict(chart_symbol='BTCUSD',chart_direction='SELL',symbol='P-100-100100',side='buy',chart_resolution='5m',chart_rsi_length=14,chart_ma_length=14,chart_ma_type='SMA',chart_signal_close=99000)
  with patch.object(self.b,'chart',side_effect=AssertionError('Manual entry must not fetch RSI signal')):
   self.b._chart_intent(t)
  self.assertEqual(t['entry_reason'],'MANUAL_DISCRETIONARY');self.assertNotIn('chart_signal',t);self.assertEqual(t['signal_direction'],'BEARISH')
 def test_call_without_qualifying_signal_posts_once_and_manages_exit(self):
  self.b.credentials=lambda:dict(DELTA_INDIA_API_KEY='fake-key',DELTA_INDIA_API_SECRET='fake-secret',DELTA_INDIA_ENABLE_LIVE_ORDERS='1');self.b.requester=fixture.LiveRequests()
  t=dict(mode='LIVE',request_id='chart-call-manual-test',chart_symbol='BTCUSD',chart_direction='BUY',symbol='C-100-100100',side='buy',contracts=1,order_type='market_order',time_in_force='ioc',reduce_only=False,chart_resolution='5m',chart_rsi_length=14,chart_ma_length=14,chart_ma_type='SMA',chart_signal_close=99000)
  r=self.b.submit(t);self.b.submit(t);self.assertEqual(self.b.requester.posts,1);self.assertEqual(r['symbol'],'C-100-100100');self.assertEqual(r['entry_reason'],'MANUAL_DISCRETIONARY');self.assertTrue(self.b.runner['running']);self.assertTrue(self.b.runner['config']['one_shot'])
