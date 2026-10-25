import unittest
from datetime import datetime,timedelta
from unittest.mock import patch
from sector_heatmap.market_calendar import IST
from sector_heatmap.stock_expiry_policy import require_options_allowed,EquityOnlyExpiry,stock_symbol
from sector_heatmap.handoff import fetch_fyers_chain
class StockExpiryTests(unittest.TestCase):
 def setUp(self):self.expiry='2026-10-27'
 def now(self,day):return datetime(2026,10,day,10,tzinfo=IST)
 def test_expiry_day_blocks_even_if_next_month_listed(self):
  with self.assertRaises(EquityOnlyExpiry):require_options_allowed(['2026-11-24',self.expiry],self.now(27))
 def test_day_before_blocks(self):
  with self.assertRaises(EquityOnlyExpiry):require_options_allowed([self.expiry,'2026-11-24'],self.now(26))
 def test_two_days_before_allowed(self):self.assertEqual(require_options_allowed([self.expiry],self.now(25)).isoformat(),self.expiry)
 def test_after_expiry_uses_new_month(self):self.assertEqual(require_options_allowed([self.expiry,'2026-11-24'],self.now(28)).isoformat(),'2026-11-24')
 def test_ist_boundary(self):
  from datetime import timezone
  with self.assertRaises(EquityOnlyExpiry):require_options_allowed([self.expiry],datetime(2026,10,25,18,30,tzinfo=timezone.utc))
 def test_missing_expiry_fails_closed(self):
  with self.assertRaises(ValueError):require_options_allowed([],self.now(25))
 def test_index_and_commodity_not_stock(self):
  self.assertFalse(stock_symbol('NSE:NIFTY50-INDEX'));self.assertFalse(stock_symbol('MCX:GOLD26DECFUT'));self.assertTrue(stock_symbol('NSE:TECHM-EQ'))
 def test_fyers_does_not_fetch_next_month(self):
  from unittest.mock import Mock
  client=Mock();client.optionchain.return_value={'s':'ok','data':{'expiryData':[{'date':'27-10-2026','expiry':'1793095200'},{'date':'24-11-2026','expiry':'1795514400'}]}}
  with self.assertRaises(EquityOnlyExpiry):fetch_fyers_chain(client,'NSE:TECHM-EQ',now=self.now(26))
  self.assertEqual(client.optionchain.call_count,1)
if __name__=='__main__':unittest.main()

