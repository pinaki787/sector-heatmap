import hashlib
import unittest
from dataclasses import replace
from sector_heatmap.chart_trade_plan import ChartTradePlan
from sector_heatmap.chart_trade_reconciliation import reconcile_fyers

class FyersReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.plan=ChartTradePlan("a","FYERS","NSE:TEST","BUY",65,"25","22","30","LIMIT","25","INTRADAY",".05",65,"AT_OR_BELOW")
        self.tag="1:CH"+hashlib.sha256(b"preview").hexdigest()[:24]
        self.parent=dict(id="entry",symbol="NSE:TEST",side=1,productType="INTRADAY",qty=65,
                         filledQty=0,remainingQuantity=65,status=6,orderTag=self.tag,stopLoss=22,takeProfit=30,
                         type=1,limitPrice=25,stopPrice=0)
    def read(self,*children):
        return reconcile_fyers(self.plan,[self.parent,*children],"preview")
    def child(self,key,**changes):
        row=dict(id=key,parentId="entry",symbol="NSE:TEST",side=-1,productType="INTRADAY",
                 qty=65,filledQty=0,remainingQuantity=65,status=6,
                 type=3 if key=="stop" else 1,stopPrice=22 if key=="stop" else 0,
                 limitPrice=30 if key=="target" else 0)
        return dict(row,**changes)
    def filled(self,qty=65):
        self.parent.update(filledQty=qty,remainingQuantity=65-qty,status=2 if qty==65 else 6)
    def test_pending_is_not_a_fill_or_verified_protection(self):
        value=self.read()
        self.assertEqual(value["status"],"ENTRY_PENDING")
        self.assertFalse(value["protection_confirmed"])
        self.assertTrue(value["linked_prices_match"])
    def test_missing_or_duplicate_parent_never_guesses_by_symbol(self):
        self.assertEqual(reconcile_fyers(self.plan,[],"preview")["status"],"BROKER_STATUS_UNAVAILABLE")
        rows=[self.parent,dict(self.parent,id="another")]
        self.assertEqual(reconcile_fyers(self.plan,rows,"preview")["status"],"BROKER_STATUS_UNAVAILABLE")
    def test_exact_parent_id_avoids_other_orders_with_same_tag(self):
        rows=[self.parent,dict(self.parent,id="another",symbol="NSE:OTHER")]
        self.assertEqual(reconcile_fyers(self.plan,rows,"preview","entry")["status"],"ENTRY_PENDING")
    def test_fill_requires_two_owned_exits_at_marked_prices_and_full_quantity(self):
        self.filled()
        self.assertFalse(self.read(self.child("stop"))["protection_confirmed"])
        self.assertTrue(self.read(self.child("stop"),self.child("target"))["protection_confirmed"])
        for changes in (dict(parentId="other"),dict(side=1),dict(limitPrice=31),dict(remainingQuantity=64)):
            self.assertFalse(self.read(self.child("stop"),self.child("target",**changes))["protection_confirmed"])
    def test_partial_fill_exits_must_cover_only_the_filled_units(self):
        self.filled(20)
        self.assertFalse(self.read(self.child("stop"),self.child("target"))["protection_confirmed"])
        self.assertTrue(self.read(self.child("stop",qty=20,remainingQuantity=20),
                                  self.child("target",qty=20,remainingQuantity=20))["protection_confirmed"])
    def test_exit_fill_is_not_closed_until_sibling_cancelled(self):
        self.filled()
        target=self.child("target",filledQty=65,remainingQuantity=0,status=2)
        self.assertEqual(self.read(self.child("stop"),target)["status"],"EXIT_CANCELLATION_PENDING")
        self.assertEqual(self.read(self.child("stop",status=1),target)["status"],"CLOSED")
    def test_partial_entry_with_closed_fills_still_reports_pending_entry_remainder(self):
        self.filled(20)
        stop=self.child("stop",qty=20,remainingQuantity=0,status=1)
        target=self.child("target",qty=20,filledQty=20,remainingQuantity=0,status=2)
        self.assertEqual(self.read(stop,target)["status"],"ENTRY_REMAINDER_PENDING")
    def test_mismatched_parent_or_impossible_quantities_fail_closed(self):
        self.parent["symbol"]="NSE:OTHER"
        with self.assertRaises(ValueError):self.read()
        self.parent["symbol"]="NSE:TEST";self.parent["filledQty"]=80
        with self.assertRaises(ValueError):self.read()
    def test_cancelled_partial_entry_cannot_be_reported_as_no_fill(self):
        self.filled(20);self.parent.update(status=1,remainingQuantity=0)
        self.assertEqual(self.read()["filled_quantity"],20)
        self.assertIn("UNVERIFIED",self.read()["status"])
    def test_active_parent_must_account_for_every_reviewed_unit(self):
        self.parent.update(remainingQuantity=64)
        self.assertEqual(self.read()["status"], "BROKER_STATUS_UNAVAILABLE")
        self.filled(); self.parent.update(remainingQuantity=1)
        with self.assertRaises(ValueError): self.read()

    def test_exits_require_distinct_native_order_ids(self):
        self.filled()
        for target in (self.child("target", id="stop"), self.child("target", id="entry"),
                       self.child("target", id="")):
            value=self.read(self.child("stop"), target)
            self.assertFalse(value["protection_confirmed"])
            self.assertNotEqual(value["status"], "CLOSED")

    def test_inconsistent_linked_quantity_or_status_cannot_confirm_protection(self):
        self.filled()
        for changes in (dict(qty=100), dict(qty=64, remainingQuantity=64),
                        dict(status=2)):
            value=self.read(self.child("stop"), self.child("target", **changes))
            self.assertFalse(value["protection_confirmed"])
            self.assertNotEqual(value["status"], "CLOSED")

    def test_impossible_exit_quantity_raises_instead_of_confirming_protection(self):
        self.filled()
        with self.assertRaises(ValueError):
            self.read(self.child("stop"), self.child("target", filledQty=1, remainingQuantity=65))

    def test_filled_exit_status_requires_its_full_quantity(self):
        self.filled()
        value=self.read(self.child("stop", status=1),
                        self.child("target", filledQty=20, remainingQuantity=0, status=2))
        self.assertNotEqual(value["status"], "CLOSED")
        self.assertFalse(value["protection_confirmed"])

    def test_native_entry_terms_cannot_silently_diverge_from_chart_levels(self):
        for changes in (dict(type=2), dict(limitPrice=25.05), dict(stopPrice=24)):
            prior=dict(self.parent);self.parent.update(changes)
            value=self.read()
            self.assertEqual(value["status"],"BROKER_STATUS_UNAVAILABLE")
            self.assertFalse(value["protection_confirmed"])
            self.parent=prior

    def test_stop_limit_reconciliation_preserves_trigger_and_reviewed_cap(self):
        self.plan=replace(self.plan,entry_type="STOP_LIMIT",entry="25",limit_price="25.5")
        self.parent.update(type=4,stopPrice=25,limitPrice=25.5)
        self.assertEqual(self.read()["status"],"ENTRY_PENDING")
        self.parent["stopPrice"]=25.05
        self.assertEqual(self.read()["status"],"BROKER_STATUS_UNAVAILABLE")

if __name__=="__main__":unittest.main()
