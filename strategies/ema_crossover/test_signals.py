import unittest
from signals import series, exit_on_close


def candles(prices):
    return [dict(timestamp=1000+i*300,open=p,high=p,low=p,close=p,volume=1) for i,p in enumerate(prices)]


class SignalsTest(unittest.TestCase):
    def test_crossovers_no_lookahead(self):
        data=candles([100]*100+[110]+[120]*50+[80])
        result=series(data)
        self.assertEqual(result[100]['direction'],'BULLISH')
        self.assertEqual(result[101]['direction'],'BULLISH')
        self.assertEqual(result[-1]['direction'],'BEARISH')
        self.assertEqual(series(data[:110]),result[:110])
    def test_duplicates_forming_conflicts(self):
        data=candles([100]*100)
        self.assertEqual(series(data[::-1]+data),series(data))
        self.assertEqual(series(data+[dict(data[-1],timestamp=999999,close=900,is_forming=True)]),series(data))
        with self.assertRaises(ValueError):series(data+[dict(data[-1],close=101)])
    def test_invalid_parameters(self):
        for fast,slow in [(30,10),(1,101),(True,30)]:
            with self.assertRaises(ValueError):series([],fast,slow)

    def test_signal_ignores_ema_ordering(self):
        up=series(candles([200-i*.4 for i in range(100)]+[170]))[-1]
        self.assertLess(up['fast'],up['slow']);self.assertEqual(up['direction'],'BULLISH')
        down=series(candles([100+i*.4 for i in range(100)]+[130]))[-1]
        self.assertGreater(down['fast'],down['slow']);self.assertEqual(down['direction'],'BEARISH')
    def test_exit_uses_ema10_only_and_ignores_wicks_equality_forming(self):
        c=dict(close=99,fast=100,slow=50,high=120,low=80)
        self.assertTrue(exit_on_close(c,'BULLISH'))
        self.assertFalse(exit_on_close(c,'BEARISH'))
        self.assertTrue(exit_on_close(dict(c,close=101,slow=200),'BEARISH'))
        self.assertFalse(exit_on_close(dict(c,close=100),'BULLISH'))
        self.assertFalse(exit_on_close(dict(c,close=100),'BEARISH'))
        self.assertFalse(exit_on_close(dict(c,is_forming=True),'BULLISH'))

if __name__=='__main__':unittest.main()
