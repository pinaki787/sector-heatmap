"""Chart orders must preserve exact reviewed levels and selected-account identity."""
import unittest
from dataclasses import replace
from sector_heatmap.chart_trade_plan import build_plan, confirm_plan


class ChartTradePlanTests(unittest.TestCase):
    def setUp(self):
        self.account = {"id": "fyers-account", "broker": "FYERS"}
        self.contract = {"symbol": "NSE:TEST-OPTION", "tradable": True,
                         "tick_size": "0.05", "lot_size": 65,
                         "linked_exit_capability": "NATIVE_OCO",
                         "products": ["INTRADAY"]}
        self.quote = {"account_id": "fyers-account", "symbol": "NSE:TEST-OPTION",
                      "last_price": 25, "received_at": 100, "provider_at": 100}
        self.payload = {"account_id": "fyers-account", "broker": "FYERS",
                        "symbol": "NSE:TEST-OPTION", "side": "BUY", "quantity": 65,
                        "entry": "24.50", "stop_loss": "22.00", "target": "29.50",
                        "entry_type": "LIMIT", "limit_price": "24.50", "product": "INTRADAY"}

    def plan(self, payload=None, contract=None, quote=None, account=None, now=101):
        return build_plan(payload or self.payload, contract=contract or self.contract,
                          account=account or self.account, quote=quote or self.quote, now=now)

    def test_limit_buy_waits_below_market_and_keeps_exact_exits(self):
        plan = self.plan()
        self.assertEqual(plan.price_trigger, "AT_OR_BELOW")
        self.assertEqual(plan.stop_loss, "22.00")
        self.assertEqual(plan.target, "29.50")
        self.assertEqual(plan.quantity, 65)

    def test_stop_limit_buy_and_sell_have_directional_trigger_and_price_cap(self):
        buy = self.plan(dict(self.payload, entry="26", entry_type="STOP_LIMIT", limit_price="26.05"))
        self.assertEqual(buy.price_trigger, "AT_OR_ABOVE")
        sell = self.plan(dict(self.payload, side="SELL", entry="24", stop_loss="26",
                              target="20", entry_type="STOP_LIMIT", limit_price="23.95"))
        self.assertEqual(sell.price_trigger, "AT_OR_BELOW")

    def test_wrong_side_exits_or_unbounded_stop_limit_cannot_be_armed(self):
        for values in ({"stop_loss": 26}, {"target": 23}, {"entry": 25},
                       {"entry": 26, "limit_price": 26}, {"entry": 26, "limit_price": 30}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.plan(dict(self.payload, entry_type="STOP_LIMIT", **values))

    def test_account_symbol_expiry_and_quote_identity_are_verified(self):
        for values in ({"account_id": "another-account"}, {"symbol": "NSE:ANOTHER"}):
            with self.subTest(values=values), self.assertRaises((PermissionError, ValueError)):
                self.plan(dict(self.payload, **values))
        with self.assertRaises(PermissionError):
            self.plan(quote=dict(self.quote, account_id="another-account"))
        with self.assertRaises(ValueError):
            self.plan(contract=dict(self.contract, expires_at=100))
        for stamp in (90, 104, float("nan"), float("inf")):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                self.plan(quote=dict(self.quote, received_at=stamp))

    def test_stale_provider_price_and_already_crossed_limit_do_not_submit_immediately(self):
        with self.assertRaises(ValueError):
            self.plan(quote=dict(self.quote, provider_at=80))
        with self.assertRaises(ValueError):
            self.plan(quote={key:value for key,value in self.quote.items() if key!="provider_at"})
        with self.assertRaisesRegex(ValueError,"stop-limit"):
            self.plan(dict(self.payload,entry="26",limit_price="26"))
        with self.assertRaisesRegex(ValueError,"stop-limit"):
            self.plan(dict(self.payload,side="SELL",entry="24",limit_price="24",stop_loss="26",target="20"))

    def test_no_silent_tick_or_quantity_rounding(self):
        for values in ({"entry": "24.501"}, {"quantity": 64}, {"quantity": True},
                       {"quantity": 65.5}, {"stop_loss": float("nan")},
                       {"target": float("inf")}, {"entry": 0}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.plan(dict(self.payload, **values))

    def test_history_only_or_unprotected_contract_cannot_be_armed(self):
        for changes in ({"tradable": False}, {"linked_exit_capability": None},
                        {"products": ["CNC"]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.plan(contract=dict(self.contract, **changes))
        with self.assertRaises(ValueError):
            self.plan(account={"id": "yahoo", "broker": "YAHOO"})

    def test_changed_drawing_or_account_requires_another_confirmation(self):
        plan = self.plan()
        phrase = "CONFIRM " + plan.fingerprint()
        self.assertEqual(confirm_plan(plan, plan, phrase, expires_at=120, now=102), plan.terms())
        for updated in (replace(plan, stop_loss="21.00"), replace(plan, quantity=130),
                        replace(plan, account_id="another-account"), replace(plan, side="SELL"),
                        replace(plan, target="30.00"), replace(plan, product="MARGIN")):
            with self.subTest(updated=updated), self.assertRaises(ValueError):
                confirm_plan(plan, updated, phrase, expires_at=120, now=102)
        with self.assertRaises(ValueError):
            confirm_plan(plan, plan, phrase, expires_at=120, now=120)
        with self.assertRaises(PermissionError):
            confirm_plan(plan, plan, "yes", expires_at=120, now=102)


if __name__ == "__main__":
    unittest.main()

