from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from sector_heatmap.dhan_account_reports import DhanAccountReports,period_start,reconstruct,IST,trade_time,FEES

def fill(side,qty,price,stamp='2026-10-27 10:00:00',trade='1',product='INTRADAY',**extra):
 return dict(dhanClientId='123',exchangeTradeId=trade,securityId='2885',exchangeSegment='NSE_EQ',tradingSymbol='RELIANCE',transactionType=side,tradedQuantity=qty,tradedPrice=price,exchangeTime=stamp,productType=product,**{f:0 for f in FEES})|extra
NOW=datetime(2026,10,27,18,0,tzinfo=IST)
class ReportsTests(TestCase):
 def test_ist_periods_and_indian_financial_year(self):
  self.assertEqual(period_start('weekly',NOW)[1].date().isoformat(),'2026-10-26')
  self.assertEqual(period_start('monthly',NOW)[1].day,1)
  self.assertEqual(period_start('annual',datetime(2026,3,31,20,tzinfo=IST))[1].date().isoformat(),'2025-04-01')
  self.assertEqual(trade_time('2026-10-26T20:00:00+00:00').date().isoformat(),'2026-10-27')
 def test_partial_fills_long_short_realized_and_reported_fees(self):
  rows=[fill('BUY',5,100,trade='1',brokerageCharges=5),fill('SELL',3,110,'2026-10-27 11:00:00','2',brokerageCharges=3),fill('SELL',4,90,'2026-10-27 12:00:00','3',brokerageCharges=4),fill('BUY',2,80,'2026-10-27 13:00:00','4',brokerageCharges=2)]
  r=reconstruct(rows,'123',period_start('daily',NOW)[1],NOW)
  self.assertTrue(r['complete']);self.assertEqual(r['summary']['gross_pnl'],30)
  self.assertEqual(r['summary']['net_pnl'],16);self.assertEqual(len(r['records']),3)
 def test_missing_fees_do_not_become_zero_net(self):
  a=fill('BUY',1,100);a.pop('serviceTax')
  r=reconstruct([a,fill('SELL',1,110,'2026-10-27 11:00:00','2')],'123',period_start('daily',NOW)[1],NOW)
  self.assertEqual(r['summary']['gross_pnl'],10);self.assertIsNone(r['summary']['net_pnl'])
 def test_missing_acquisition_cost_cannot_be_fabricated(self):
  r=reconstruct([fill('SELL',2,120,product='CNC')],'123',period_start('annual',NOW)[1],NOW)
  self.assertFalse(r['supported']);self.assertIsNone(r['summary']['gross_pnl']);self.assertTrue(r['warnings'])
 def test_period_excludes_earlier_closures_but_keeps_opening_lots(self):
  rows=[fill('BUY',1,100,'2026-10-26 10:00:00','1'),fill('SELL',1,110,'2026-10-26 11:00:00','2')]
  r=reconstruct(rows,'123',period_start('daily',NOW)[1],NOW);self.assertTrue(r['complete']);self.assertEqual(r['summary']['gross_pnl'],0)
 def test_empty_verified_history_is_zero_but_failed_history_is_unavailable(self):
  client=Mock(client_id='123');client.request.side_effect=lambda method,path:{'dhanClientId':'123'} if path=='/profile' else []
  service=SimpleNamespace(_client=lambda:client,account={'id':'owned'},credential_digest='one')
  report=DhanAccountReports(service,now=lambda:NOW)
  r=report.realized('daily');self.assertTrue(r['supported']);self.assertEqual(r['summary']['gross_pnl'],0)
  report.cache.clear();client.request.side_effect=RuntimeError('history offline')
  with self.assertRaises(RuntimeError):report.realized('daily')
  client.request.side_effect=lambda method,path:{'dhanClientId':'123'} if path=='/profile' else (_ for _ in ()).throw(RuntimeError('history offline'))
  r=report.realized('daily');self.assertFalse(r['supported']);self.assertIsNone(r['summary']['gross_pnl'])
 def test_positions_are_owned_and_missing_pnl_is_not_zero(self):
  rows=[dict(dhanClientId='123',netQty=1,securityId='2885',tradingSymbol='RELIANCE',costPrice=100,realizedProfit=None,unrealizedProfit=None)]
  client=Mock(client_id='123');client.request.side_effect=lambda method,path:rows if path=='/positions' else {'dhanClientId':'123','availableBalance':1000}
  report=DhanAccountReports(SimpleNamespace(_client=lambda:client,account={'id':'owned'}))
  r=report.positions();self.assertEqual(len(r['positions']),1);self.assertIsNone(r['pnl']);self.assertIsNone(r['positions'][0]['pl'])
  rows[0]['dhanClientId']='other'
  with self.assertRaises(PermissionError):report.positions()
 def test_history_pagination_duplicates_and_tenant_check(self):
  row=fill('BUY',1,100);client=Mock(client_id='123');client.request.side_effect=[[row],[row]]
  report=DhanAccountReports(SimpleNamespace(account={'id':'owned'}))
  with self.assertRaisesRegex(ValueError,'repeated'):report.history(client,NOW.date(),NOW.date())
  client.request.side_effect=[[row|{'dhanClientId':'other'}]]
  with self.assertRaises(PermissionError):report.history(client,NOW.date(),NOW.date())
 def test_future_and_nonfinite_fills_fail_closed(self):
  for row in [fill('BUY',1,'NaN'),fill('BUY',1,100,'2026-10-28 09:30:00')]:
   with self.assertRaises(ValueError):reconstruct([row],'123',period_start('daily',NOW)[1],NOW)
 def test_zero_trade_ids_use_order_fill_identity_without_collapsing_unrelated_orders(self):
  first=fill('BUY',1,100,trade='0',orderId='one',exchangeOrderId='one')
  second=fill('SELL',1,110,'2026-10-27 11:00:00','0',orderId='two',exchangeOrderId='two')
  client=Mock(client_id='123');client.request.side_effect=[[first,second],[]]
  report=DhanAccountReports(SimpleNamespace(account={'id':'owned'}))
  rows,pages=report.history(client,NOW.date(),NOW.date());self.assertEqual(len(rows),2);self.assertEqual(pages,2)
 def test_daily_total_uses_authoritative_realized_and_never_unrealized(self):
  client=Mock(client_id='123')
  def request(method,path):
   if path=='/profile':return {'dhanClientId':'123'}
   if path=='/positions':return [dict(dhanClientId='123',netQty=0,realizedProfit=25,unrealizedProfit=999)]
   if path=='/fundlimit':return {'dhanClientId':'123'}
   return []
  client.request.side_effect=request
  service=SimpleNamespace(_client=lambda:client,account={'id':'own'},credential_digest='same')
  report=DhanAccountReports(service,now=lambda:NOW);r=report.realized('daily')
  self.assertEqual(r['summary']['gross_pnl'],25);self.assertIsNone(r['summary']['net_pnl']);self.assertEqual(r['basis'],'Dhan current-session position book')
 def test_historical_report_job_is_permission_scoped_and_cancellable(self):
  from sector_heatmap.job_http import operation
  from sector_heatmap.section_permissions import allowed
  self.assertEqual(operation('/api/dhan/account-reports/analyze'),('ANALYSIS','broker'))
  self.assertTrue(allowed({'features':['broker']},'/api/dhan/account-reports/analyze'))
  self.assertFalse(allowed({'features':['trade-parser']},'/api/dhan/account-reports/analyze'))
  from sector_heatmap.persistent_jobs import JobCancelled
  from unittest.mock import patch
  client=Mock(client_id='123');report=DhanAccountReports(SimpleNamespace(account={'id':'own'}))
  with patch('sector_heatmap.dhan_account_reports.checkpoint',side_effect=JobCancelled):
   with self.assertRaises(JobCancelled):report.history(client,NOW.date(),NOW.date())
  client.request.assert_not_called()
 def test_rate_limit_retries_only_safe_history_reads_with_cancellable_wait(self):
  from sector_heatmap.dhan_execution import DhanAPIError
  from unittest.mock import patch
  client=Mock(client_id='123');client.request.side_effect=[DhanAPIError('rate',True,rate_limited=True),[]]
  report=DhanAccountReports(SimpleNamespace(account={'id':'own'}))
  with patch('sector_heatmap.dhan_account_reports.time.sleep') as sleep,patch('sector_heatmap.dhan_account_reports.checkpoint'):
   rows,pages=report.history(client,NOW.date(),NOW.date())
  self.assertEqual(rows,[]);self.assertEqual(client.request.call_count,2);self.assertEqual(sleep.call_count,20)
  self.assertTrue(all(call.args[0]=='GET' and call.args[1].startswith('/trades/') for call in client.request.call_args_list))
 def test_bad_seed_row_does_not_invent_period_pnl_or_hide_unrelated_verified_fills(self):
  rows=[fill('BUY',1,0,'2026-10-26 10:00:00',product='CNC',securityId='other'),fill('BUY',1,100),fill('SELL',1,110,'2026-10-27 11:00:00','2')]
  r=reconstruct(rows,'123',period_start('daily',NOW)[1],NOW);self.assertTrue(r['complete']);self.assertEqual(r['summary']['gross_pnl'],10)
  bad=fill('BUY',1,0);r=reconstruct([bad],'123',period_start('daily',NOW)[1],NOW);self.assertFalse(r['complete']);self.assertIsNone(r['summary']['gross_pnl'])
