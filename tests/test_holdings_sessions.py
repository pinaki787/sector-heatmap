import unittest
from datetime import datetime
from sector_heatmap.market_calendar import IST
from sector_heatmap.holdings_sessions import window

def stamp(value):return datetime.fromisoformat(value).replace(tzinfo=IST).timestamp()

class SessionsTests(unittest.TestCase):
 def test_equity_boundaries_and_weekend(self):
  for segment in ('NSE_EQ','BSE_EQ'):
   self.assertFalse(window(segment,stamp('2026-10-23T09:14'))['open'])
   self.assertTrue(window(segment,stamp('2026-10-23T09:15'))['open'])
   self.assertFalse(window(segment,stamp('2026-10-23T15:30'))['open'])
   self.assertEqual(window(segment,stamp('2026-10-24T12:00'))['next_open'],stamp('2026-10-26T09:15'))
 def test_holiday_and_commodity_partial_session(self):
  self.assertFalse(window('NSE_EQ',stamp('2026-10-20T12:00'))['open'])
  self.assertFalse(window('MCX_COMM',stamp('2026-10-20T12:00'),'NON_AGRI')['open'])
  self.assertEqual(window('MCX_COMM',stamp('2026-10-20T12:00'),'NON_AGRI')['next_open'],stamp('2026-10-20T17:00'))
  self.assertTrue(window('MCX_COMM',stamp('2026-10-20T18:00'),'NON_AGRI')['open'])
  self.assertFalse(window('MCX_COMM',stamp('2026-10-02T18:00'),'NON_AGRI')['open'])
 def test_product_specific_closing_and_dst(self):
  self.assertFalse(window('MCX_COMM',stamp('2026-10-23T17:00'),'AGRI')['open'])
  self.assertTrue(window('MCX_COMM',stamp('2026-10-23T20:59'),'INTERNATIONAL_AGRI')['open'])
  self.assertFalse(window('MCX_COMM',stamp('2026-10-23T21:00'),'INTERNATIONAL_AGRI')['open'])
  self.assertFalse(window('MCX_COMM',stamp('2026-10-23T23:30'),'NON_AGRI')['open'])
  self.assertTrue(window('MCX_COMM',stamp('2026-11-02T23:40'),'NON_AGRI')['open'])
 def test_unknown_calendar_or_contract_fails_closed(self):
  with self.assertRaises(ValueError):window('MCX_COMM',stamp('2026-10-23T12:00'))
  with self.assertRaises(ValueError):window('NSE_EQ',stamp('2027-01-04T12:00'))
