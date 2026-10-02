import unittest

from sector_heatmap.delta_signals import delta_rsi_series
from strategies.ema_crossover.signals import rsi_sma_series


class DeltaTouchSignals(unittest.TestCase):
    def candles(self, wide=True):
        closes = [100, 102, 101, 103, 102, 105, 106, 107, 106, 104, 103, 102]
        return [dict(timestamp=i * 300 + 1, open=c, close=c,
                     high=c + (20 if wide else 0), low=c - (20 if wide else 0))
                for i, c in enumerate(closes)]

    def test_both_touch_directions_and_cross_priority(self):
        rows = delta_rsi_series(self.candles(), 3, 3, 'EMA')
        self.assertEqual(rows[6]['entry_direction'], 'BULLISH')
        self.assertEqual(rows[9]['entry_direction'], 'BEARISH')
        for i in (6, 9):
            self.assertIsNone(rows[i]['cross_direction'])
            self.assertEqual(rows[i]['entry_reason'], 'CANDLE_EXTREME_EMA_TOUCH')
            self.assertEqual(rows[i]['touch_evidence']['method'], 'CANDLE_EXTREME_DERIVED')
        self.assertEqual(rows[5]['entry_reason'], 'CROSSOVER')

    def test_exits_and_rsi_calculation_preserved(self):
        candles = self.candles()
        original = rsi_sma_series(candles, 3, 3, 'EMA')
        added = delta_rsi_series(candles, 3, 3, 'EMA')
        for before, after in zip(original, added):
            for field in ('rsi', 'rsi_ma', 'cross_direction', 'direction'):
                self.assertEqual(before[field], after[field])

    def test_no_touch_without_extreme_and_no_sma_touch(self):
        for candles, ma in ((self.candles(False), 'EMA'), (self.candles(), 'SMA')):
            rows = delta_rsi_series(candles, 3, 3, ma)
            self.assertTrue(all(r['entry_direction'] == r['cross_direction'] for r in rows))

    def test_forming_and_warmup_excluded(self):
        candles = self.candles()
        candles[-1]['is_forming'] = True
        rows = delta_rsi_series(candles, 3, 3, 'EMA')
        self.assertEqual(len(rows), len(candles) - 1)
        self.assertTrue(all(r['entry_direction'] is None for r in rows[:4]))

    def test_one_period_ema_cannot_bounce(self):
        rows = delta_rsi_series(self.candles(), 3, 1, 'EMA')
        self.assertTrue(all(r['entry_direction'] is None for r in rows))


if __name__ == '__main__':
    unittest.main()
