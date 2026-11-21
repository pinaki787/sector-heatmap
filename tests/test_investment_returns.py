import unittest
from datetime import date, datetime, time

from sector_heatmap.investment_returns import INDIA, calculate


class AnnualReturnsTests(unittest.TestCase):
    def data(self, prices):
        return {'chart': {'result': [{
            'meta': {'symbol': 'TEST.NS', 'instrumentType': 'EQUITY', 'exchangeTimezoneName': 'Asia/Kolkata'},
            'timestamp': [datetime.combine(date.fromisoformat(day), time(9, 15), INDIA).timestamp() for day, _ in prices],
            'indicators': {'quote': [{'close': [price for _, price in prices]}]},
        }]}}

    def test_ten_year_anchor_and_incomplete_horizons(self):
        data = self.data([
            ('2016-11-10', 50), ('2016-11-14', 80), ('2017-10-30', 100),
            ('2025-11-12', 125), ('2026-11-12', 150), ('2026-11-13', 1000),
        ])
        result = calculate(data, 'TEST.NS', date(2026, 11, 12))
        self.assertEqual(result['10'], {'return_pct': 200, 'from_date': '2016-11-10', 'to_date': '2026-11-12'})
        self.assertAlmostEqual(result['1']['return_pct'], 20)
        self.assertNotIn('9', result)
        self.assertEqual(calculate(data, 'OTHER.NS', date(2026, 11, 12)), {})

    def test_new_listing_has_no_ten_year_return(self):
        data = self.data([('2025-11-12', 100), ('2026-11-12', 130)])
        result = calculate(data, 'TEST.NS', date(2026, 11, 12))
        self.assertEqual(set(result), {'1'})
