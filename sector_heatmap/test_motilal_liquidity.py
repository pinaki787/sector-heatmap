import unittest
from .motilal_analysis import native_liquidity
class LiquidityTests(unittest.TestCase):
    def test_fresh_native_fields_and_zero_are_retained(self):
        q=dict(ltp_exchange_at=100,ltp_received_at=101,open_interest=50000,cumulative_volume=0)
        self.assertEqual(native_liquidity(q,105),dict(oi=50000,volume=0))
    def test_depth_refresh_cannot_refresh_old_or_future_liquidity(self):
        for stamp in [80,110,None,float('nan')]:
            q=dict(ltp_exchange_at=stamp,ltp_received_at=105,depth_exchange_at=105,open_interest=50000,cumulative_volume=1000)
            self.assertEqual(native_liquidity(q,105),dict(oi=None,volume=None))
    def test_unavailable_native_fields_are_not_invented(self):
        for value in [-1,True,float('nan'),1.5,None]:
            q=dict(ltp_exchange_at=100,ltp_received_at=101,open_interest=value,cumulative_volume=value)
            self.assertEqual(native_liquidity(q,105),dict(oi=None,volume=None))
