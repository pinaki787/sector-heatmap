import unittest
from ema_crossover.signals import rsi_sma_series, rsi_exit_on_close
from ema_crossover.runner import configuration


def bars(prices):
    return [dict(timestamp=i*300,open=p,high=p,low=p,close=p) for i,p in enumerate(prices)]


class RsiSignalsTests(unittest.TestCase):
    def test_wilder_seed_and_simple_average(self):
        rows=rsi_sma_series(bars([100,102,101,103,102,104,101]),2,2)
        self.assertAlmostEqual(rows[2]['rsi'],100-100/3)
        self.assertIsNone(rows[2]['rsi_sma'])
        self.assertAlmostEqual(rows[3]['rsi'],100-100/7)
        self.assertAlmostEqual(rows[3]['rsi_sma'],(rows[2]['rsi']+rows[3]['rsi'])/2)
        self.assertEqual(rows[3]['direction'],'BULLISH')
        self.assertEqual(rows[6]['direction'],'BEARISH')

    def test_completed_only_no_lookahead_and_revised_forming_has_no_effect(self):
        candles=bars([100+(i%2) for i in range(80)]+[110])
        result=rsi_sma_series(candles)
        self.assertEqual(result[-1]['direction'],'BULLISH')
        forming=dict(timestamp=99999,open=110,high=110,low=1,close=1,is_forming=True)
        self.assertEqual(rsi_sma_series(candles+[forming]),result)
        self.assertEqual(rsi_sma_series(candles[:60]),result[:60])
        self.assertEqual(rsi_sma_series(bars([100+(i%2) for i in range(80)]+[80]))[-1]['direction'],'BEARISH')

    def test_flip_exit_equality_and_forming(self):
        self.assertTrue(rsi_exit_on_close(dict(rsi=40,rsi_sma=50,cross_direction='BEARISH'),'BULLISH'))
        self.assertTrue(rsi_exit_on_close(dict(rsi=60,rsi_sma=50,cross_direction='BULLISH'),'BEARISH'))
        for direction in ['BULLISH','BEARISH']:
            self.assertFalse(rsi_exit_on_close(dict(rsi=50,rsi_sma=50),direction))
            self.assertFalse(rsi_exit_on_close(dict(rsi=40,rsi_sma=50,is_forming=True),direction))
        self.assertTrue(all(c['direction'] is None for c in rsi_sma_series(bars([100]*100))))

    def test_configuration_rejects_legacy_strategy_and_spot_override(self):
        c=dict(strategy='RSI_BASED_EMA_V1',underlying='MCX:TESTFUT',lots=1,label='anything')
        self.assertEqual(configuration(c)['label'],'RSI based SMA')
        with self.assertRaises(ValueError):configuration(dict(c,strategy='EMA_CLOUD_MARKET_V3'))
        with self.assertRaises(ValueError):configuration(dict(c,spot_stop=100))
        with self.assertRaises(ValueError):rsi_sma_series([],True,14)

    def test_ema_of_rsi_uses_first_valid_rsi_seed_and_alpha(self):
        rows=rsi_sma_series(bars([100,102,101,103,102,104,101]),2,3,'EMA')
        self.assertIsNone(rows[1]['rsi_ma'])
        self.assertEqual(rows[2]['rsi_ma'],rows[2]['rsi'])
        self.assertAlmostEqual(rows[3]['rsi_ma'],rows[2]['rsi']+.5*(rows[3]['rsi']-rows[2]['rsi']))
        self.assertEqual(rows[3]['direction'],'BULLISH')
        self.assertEqual(rows[6]['direction'],'BEARISH')
        with self.assertRaises(ValueError):rsi_sma_series([],14,14,'WMA')

if __name__=='__main__':unittest.main()
