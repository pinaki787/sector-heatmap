import unittest
from direct import DirectStrategy
class DirectTests(unittest.TestCase):
    def test_fixed_crypto_size_independent_of_execution_frame(self):
        for frame in [1,5,30]:
            s=DirectStrategy(dict(underlying='BTCUSD',market='CRYPTO',timeframe=frame,reference_value=4600))
            self.assertEqual(s.spot_size,100)
            with self.assertRaises(ValueError):s.reset_contract({'symbol':'BTCUSD'},.4)
            with self.assertRaises(ValueError):s.reset_contract({'symbol':'ETHUSD'})
    def test_confirmed_flip_long_exit_short_without_delta(self):
        s=DirectStrategy(dict(underlying='BTCUSD',market='CRYPTO',timeframe=5,reference_value=46))
        actions=[]
        for i,price in enumerate([100,102,104,106,108,110,108,106,104,102,100,98,96,94]):
            actions+=s.update(dict(kind='underlying',timestamp=i*300,close=price))
        self.assertTrue(any(a['action']=='OPEN_LONG' for a in actions))
        self.assertTrue(any(a['action']=='CLOSE_LONG' for a in actions))
        short=s.selected_gate_entry();self.assertEqual(short['action'],'OPEN_SHORT')
        with self.assertRaises(ValueError):s.reset_contract({'symbol':'BTCUSD'})
    def test_optional_sma_direct_short(self):
        s=DirectStrategy(dict(underlying='BTCUSD',market='CRYPTO',timeframe=30,reference_value=46,sma_exit_enabled=True))
        s.position=dict(s.contract,side='SHORT')
        for i in range(30):s.update(dict(kind='sma',timestamp=i*60,close=100))
        self.assertEqual(s.update(dict(kind='sma',timestamp=1800,close=101))[0]['action'],'CLOSE_SHORT')

    def test_delivery_stock_never_opens_a_cash_short(self):
        s=DirectStrategy(dict(underlying='NSE:RELIANCE-EQ',market='NSE',timeframe=5,reference_value=12,product='CNC'))
        s.pending_direction=('SHORT',100);self.assertIsNone(s.selected_gate_entry());self.assertIsNone(s.position)
        s.pending_direction=('LONG',101);self.assertEqual(s.selected_gate_entry()['action'],'OPEN_LONG')
