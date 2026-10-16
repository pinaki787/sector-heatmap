import unittest
from sector_heatmap.exposure_guard import exclude_exposure,matches_exposure,open_exposures,same_underlying,exclude_handoff_cards


class ExposureGuardTests(unittest.TestCase):
    def test_selected_symbol_matches_cash_future_and_option_but_not_other_underlying(self):
        for derivative in ('NSE:NIFTY26O1923150CE','NSE:NIFTY26OCTFUT','NSE:NIFTY26102223150PE'):
            self.assertTrue(same_underlying('NSE:NIFTY50-INDEX',derivative))
        self.assertFalse(same_underlying('NSE:NIFTY50-INDEX','NSE:BANKNIFTY26OCT55000CE'))
        self.assertFalse(same_underlying('MCX:GOLD26OCTFUT','MCX:GOLDM26OCTFUT'))
        self.assertFalse(same_underlying('NSE:TEST-EQ','BSE:TEST-A'))
    def test_open_positions_and_pending_orders_are_ignored_by_analysis(self):
        candidates=[{'symbol':'NSE:NIFTY50-INDEX'},{'symbol':'NSE:NIFTYBANK-INDEX'},{'symbol':'MCX:CRUDEOIL26OCTFUT'}]
        good,ignored=exclude_exposure(candidates,[{'symbol':'NSE:NIFTY26O1923150CE','netQty':65}],
                                     [{'symbol':'MCX:CRUDEOIL26OCT6500CE','status':6}])
        self.assertEqual(good,[candidates[1]]);self.assertEqual(len(ignored),2)
    def test_zero_closed_rejected_orders_do_not_exclude(self):
        self.assertEqual(open_exposures([{'symbol':'X','netQty':0}],[{'symbol':'X','status':2},{'symbol':'X','status':5}]),[])
    def test_unverifiable_position_is_not_silently_ignored(self):
        with self.assertRaises(ValueError):open_exposures([{'symbol':'X','netQty':'unknown'}])
        with self.assertRaises(ValueError):matches_exposure('X',[{'netQty':1}])

    def test_all_cards_for_newly_exposed_underlying_are_removed_before_publish(self):
        candidates=[{'key':'one','symbol':'NSE:TEST-EQ'},{'key':'two','symbol':'NSE:OTHER-EQ'}]
        cards=[{'candidate_key':'one','kind':'EQUITY'},{'candidate_key':'one','kind':'LONG_OPTION'},{'candidate_key':'two','kind':'EQUITY'}]
        good,kept,ignored=exclude_handoff_cards(candidates,cards,[],[{'symbol':'NSE:TEST-EQ','status':6}])
        self.assertEqual(good,[candidates[1]]);self.assertEqual(kept,[cards[2]]);self.assertEqual(ignored,[candidates[0]])

    def test_unknown_order_state_cannot_silently_permit_another_entry(self):
        with self.assertRaisesRegex(ValueError,'order status'):open_exposures([],[{'symbol':'NSE:TEST-EQ','status':'UNKNOWN_STATE'}])
