import unittest
from dataclasses import replace
from sector_heatmap.chart_trade_plan import ChartTradePlan
from sector_heatmap.chart_trade_delta_exits import verify_delta_exits

class DeltaExitProofTests(unittest.TestCase):
    def setUp(self):
        self.plan=ChartTradePlan("a","DELTA_INDIA","BTCUSD","BUY",2,"99","95","110","LIMIT","99","MARGIN",".5",1,"AT_OR_BELOW")
        self.parent=dict(id=1,product_id=27,size=2,unfilled_size=0,state="closed")
        self.stop=dict(id=2,product_id=27,side="sell",bracket_order=True,reduce_only=True,
                       meta_data=dict(parent_type="position",parent_id=400),order_type="market_order",stop_order_type="stop_loss_order",stop_trigger_method="last_traded_price",
                       stop_price="95",size=2,unfilled_size=2,state="pending")
        self.target=dict(self.stop,id=3,stop_order_type="take_profit_order",stop_price="110")
        self.entry=dict(id=10,product_id=27,order_id=1,side="buy",size=2)
    def proof(self,orders=None,fills=None,position=2,parent=None):
        return verify_delta_exits(self.plan,parent or self.parent,
            orders if orders is not None else [self.stop,self.target],
            fills if fills is not None else [self.entry],position)
    def test_both_native_position_brackets_and_exact_owned_fills_prove_current_protection(self):
        result=self.proof()
        self.assertEqual(result["status"],"POSITION_PROTECTED")
        self.assertTrue(result["protection_confirmed"])
        self.assertEqual(result["open_quantity"],2)
    def test_wrong_price_trigger_quantity_or_missing_leg_cannot_prove_protection(self):
        for change in (dict(stop_price="111"),dict(stop_trigger_method="mark_price"),
                       dict(unfilled_size=1),dict(reduce_only=False),dict(bracket_order=False)):
            with self.subTest(change=change):
                self.assertFalse(self.proof([self.stop,dict(self.target,**change)])["protection_confirmed"])
        self.assertFalse(self.proof([self.stop])["protection_confirmed"])
    def test_unrelated_fills_are_detected_even_when_net_position_matches(self):
        extra=[dict(id=11,product_id=27,order_id=100,side="buy",size=1),
               dict(id=12,product_id=27,order_id=101,side="sell",size=1)]
        self.assertEqual(self.proof(fills=[self.entry,*extra])["status"],"POSITION_OWNERSHIP_CONFLICT")
    def test_flat_position_alone_cannot_be_claimed_as_exit_fill(self):
        self.assertEqual(self.proof(position=0)["status"],"POSITION_OWNERSHIP_CONFLICT")
    def test_closed_requires_exit_fills_flat_position_and_cancelled_sibling(self):
        target=dict(self.target,unfilled_size=0,state="closed")
        fill=dict(id=11,product_id=27,order_id=3,side="sell",size=2)
        result=self.proof([dict(self.stop,state="cancelled"),target],[self.entry,fill],0)
        self.assertEqual(result["status"],"CLOSED")
        self.assertFalse(result["protection_confirmed"])
        self.assertEqual(self.proof([self.stop,target],[self.entry,fill],0)["status"],"EXIT_CANCELLATION_PENDING")
    def test_partial_entry_and_partial_exit_match_residual_protection(self):
        parent=dict(self.parent,size=2,unfilled_size=1,state="open")
        entry=dict(self.entry,size=1)
        orders=[dict(self.stop,size=1,unfilled_size=1),dict(self.target,size=1,unfilled_size=1)]
        self.assertTrue(self.proof(orders,[entry],1,parent)["protection_confirmed"])
        closed=[dict(self.stop,size=1,unfilled_size=1,state="cancelled"),
                dict(self.target,size=1,unfilled_size=0,state="closed")]
        fill=dict(id=11,product_id=27,order_id=3,side="sell",size=1)
        self.assertEqual(self.proof(closed,[entry,fill],0,parent)["status"],"ENTRY_REMAINDER_PENDING")
    def test_duplicate_fills_are_deduplicated_but_conflicting_evidence_is_rejected(self):
        self.assertTrue(self.proof(fills=[self.entry,dict(self.entry)])["protection_confirmed"])
        with self.assertRaises(ValueError):
            self.proof(fills=[self.entry,dict(self.entry,size=1)])
    def test_short_position_uses_opposite_exit_side_and_signed_position(self):
        self.plan=replace(self.plan,side="SELL",stop_loss="110",target="95")
        self.stop.update(side="buy",stop_price="110");self.target.update(side="buy",stop_price="95")
        self.entry["side"]="sell"
        self.assertTrue(self.proof(position=-2)["protection_confirmed"])
    def test_incomplete_entry_fill_evidence_and_external_open_order_block_protection(self):
        self.assertEqual(self.proof(fills=[])["status"],"BROKER_STATUS_UNAVAILABLE")
        row=dict(id=99,product_id=27,state="open",bracket_order=False)
        self.assertEqual(self.proof([self.stop,self.target,row])["status"],"POSITION_OWNERSHIP_CONFLICT")

    def test_mark_price_is_verified_only_when_explicitly_chosen(self):
        self.plan=replace(self.plan,exit_trigger_method="mark_price")
        self.stop["stop_trigger_method"]="mark_price";self.target["stop_trigger_method"]="mark_price"
        self.assertTrue(self.proof()["protection_confirmed"])
        self.target["stop_trigger_method"]="last_traded_price"
        self.assertFalse(self.proof()["protection_confirmed"])
    def test_two_brackets_from_different_native_position_groups_do_not_prove_protection(self):
        self.target["meta_data"]=dict(parent_type="position",parent_id=999)
        self.assertFalse(self.proof()["protection_confirmed"])

if __name__=="__main__":unittest.main()
