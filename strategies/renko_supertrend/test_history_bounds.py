import unittest
from unittest.mock import patch
import builtins
from .runner import analysis
BASE=dict(strategy_basis='RENKO',brick_mode='Manual',manual_brick=10,underlying='BTCUSD',timeframe='1 minute',session_deadline=None)
def candles(prices):
 return [dict(timestamp=1793140200+i*60,open=p,high=p+1,low=p-1,close=p) for i,p in enumerate(prices)]

class HistoryBoundTests(unittest.TestCase):
 def test_resume_scans_retained_timestamp_bounds_once(self):
  rows=candles([100+i%20 for i in range(2100)])
  saved=analysis(rows,BASE,.05)
  with patch('strategies.renko_supertrend.runner.min',wraps=builtins.min,create=True) as minimum:
   continued=analysis(rows,BASE,.05,saved)
  self.assertEqual(minimum.call_count,1)
  self.assertEqual(saved,continued)
