import copy
import unittest
from dataclasses import replace
from sector_heatmap.chart_trade_plan import ChartTradePlan
from sector_heatmap.chart_trade_native import native_bracket_order
from sector_heatmap.chart_trade_dhan_reconciliation import reconcile_dhan_super


class DhanChartReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.plan = ChartTradePlan("account", "DHAN", "NSE_FNO:123", "BUY", 65,
                                  "25", "22", "30", "LIMIT", "25", "INTRADAY",
                                  "0.05", 65, "AT_OR_BELOW")
        self.contract = dict(symbol=self.plan.symbol, security_id="123", exchange_segment="NSE_FNO")
        self.ticket = native_bracket_order(self.plan, self.contract, client_order_id="preview",
                                          broker_client_id="client")["body"]
        self.parent = dict(self.ticket, orderId="owned", legName="ENTRY_LEG",
                           orderStatus="TRADED", filledQty=65, remainingQuantity=0,
                           averageTradedPrice="24.95", legDetails=[
            dict(orderId="owned", legName=name, transactionType="SELL",
                 orderStatus="PENDING", price=price, totalQuatity=0, remainingQuantity=0)
            for name, price in (("STOP_LOSS_LEG", "22"), ("TARGET_LEG", "30"))])

    def read(self, rows=None, **kwargs):
        return reconcile_dhan_super(self.plan, self.contract, preview_id="preview",
                                    broker_client_id="client", rows=rows if rows is not None else [self.parent], **kwargs)

    def test_registered_full_quantity_is_distinct_from_exit_fill(self):
        result = self.read()
        self.assertEqual(result["status"], "POSITION_PROTECTED")
        self.assertTrue(result["protection_confirmed"])
        self.assertEqual(result["entry_fill_price"], "24.95")
        self.assertFalse(result["retry_allowed"])

    def test_pending_has_no_fill_or_protection(self):
        self.parent.update(orderStatus="PENDING", filledQty=0, remainingQuantity=65)
        result = self.read()
        self.assertEqual(result["status"], "ENTRY_PENDING")
        self.assertFalse(result["protection_confirmed"])
        self.assertNotIn("entry_fill_price", result)

    def test_closed_or_triggered_never_proves_exit_fill(self):
        for status in ("CLOSED", "PART_TRADED"):
            with self.subTest(status=status):
                self.parent["orderStatus"] = status
                self.assertNotEqual(self.read()["status"], "CLOSED")
                self.assertFalse(self.read()["protection_confirmed"])
        self.parent["orderStatus"] = "TRADED"
        self.parent["legDetails"][0]["orderStatus"] = "TRIGGERED"
        self.assertFalse(self.read()["protection_confirmed"])

    def test_exact_identity_role_and_prices_required(self):
        original = copy.deepcopy(self.parent)
        for key, value in (("dhanClientId", "foreign"), ("correlationId", "foreign"),
                           ("securityId", "456"), ("transactionType", "SELL"),
                           ("productType", "CNC"), ("price", "25.01"), ("legName", "TARGET_LEG")):
            with self.subTest(key=key):
                self.parent = dict(original, **{key:value})
                self.assertFalse(self.read(entry_order_id="owned")["protection_confirmed"])
        self.parent = original
        self.parent["legDetails"][0]["price"] = "22.01"
        self.assertFalse(self.read()["protection_confirmed"])

    def test_missing_duplicate_and_cross_day_evidence_never_resubmits(self):
        for rows in ([], [self.parent, self.parent], [None], {}):
            with self.subTest(rows=type(rows)):
                result = self.read(rows)
                self.assertEqual(result["status"], "BROKER_STATUS_UNAVAILABLE")
                self.assertFalse(result["retry_allowed"])

    def test_partial_fill_and_cancelled_partial_are_not_terminal(self):
        self.parent.update(orderStatus="PART_TRADED", filledQty=30, remainingQuantity=35)
        result = self.read()
        self.assertEqual(result["filled_quantity"], 30)
        self.assertEqual(result["pending_quantity"], 35)
        self.assertFalse(result["protection_confirmed"])
        self.parent["orderStatus"] = "CANCELLED"
        result = self.read()
        self.assertNotEqual(result["status"], "CANCELLED")
        self.assertEqual(result["pending_quantity"], 0)
        self.assertFalse(result["protection_confirmed"])

    def test_unfilled_terminal_and_malformed_quantities(self):
        self.parent.update(orderStatus="CANCELLED", filledQty=0, remainingQuantity=65)
        self.assertEqual(self.read()["status"], "CANCELLED")
        self.parent.update(filledQty=True)
        self.assertEqual(self.read()["status"], "BROKER_STATUS_UNAVAILABLE")
        self.parent.update(filledQty=0, remainingQuantity=64)
        self.assertEqual(self.read()["status"], "BROKER_STATUS_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
