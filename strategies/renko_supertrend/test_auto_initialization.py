"""Document the current sizing contract; this does not introduce a new policy."""
import unittest
from copy import deepcopy
from .signals import Engine
from .test_brick_basis import BASE

def rows(ranges,start=1793140200,seconds=60):
    return [dict(timestamp=start+i*seconds,open=1000,close=1000,high=1000+r/2,low=1000-r/2) for i,r in enumerate(ranges)]

class AutoInitializationTests(unittest.TestCase):
    def engine(self,**overrides):
        return Engine({**BASE,"brick_mode":"Auto","atr_length":5,"factor":3,**overrides},.05)

    def test_first_five_true_ranges_freeze_before_regime_or_low_atr_is_ready(self):
        e=self.engine()
        out=[e.update(row) for row in rows([2,4,6,8,10])]
        self.assertTrue(all(r["box"] is None for r in out[:4]))
        self.assertEqual(out[-1]["box"],6)
        self.assertIsNone(e.state["brick_regime"]["value"])
        self.assertIsNone(e.state["brick_low"]["value"])
        for row in rows([100]*20,start=1793140500):e.update(row)
        self.assertEqual(e.state["brick_box"],6)
        self.assertGreater(e.state["brick_host_atr"]["value"],90)

    def test_factor_is_not_a_multiplier_for_the_initial_box(self):
        for factor in [1,3,7]:
            e=self.engine(factor=factor)
            for row in rows([2,4,6,8,10]):e.update(row)
            self.assertEqual(e.state["brick_box"],6)

    def test_resume_preserves_box_but_a_new_anchor_can_seed_a_different_box(self):
        e=self.engine()
        for row in rows([2,4,6,8,10]):e.update(row)
        resumed=Engine(e.raw_config,.05,deepcopy(e.state))
        for row in rows([100]*5,start=1793140500):resumed.update(row)
        self.assertEqual(resumed.state["brick_box"],6)
        other=self.engine()
        for row in rows([100]*5,start=1793140500):other.update(row)
        self.assertEqual(other.state["brick_box"],100)

    def test_nse_bse_divisor_is_symbol_scoped_other_symbols_use_same_seed(self):
        for symbol,expected in [("NSE:NIFTY50-INDEX",.5),("BSE:SENSEX-INDEX",.5),("MCX:TEST",6),("BTCUSD",6)]:
            e=self.engine(underlying=symbol)
            for row in rows([2,4,6,8,10]):e.update(row)
            self.assertEqual(e.state["brick_box"],expected)
