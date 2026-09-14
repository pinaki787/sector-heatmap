from datetime import datetime
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sector_heatmap.fyers_execution import DailyRiskLedger, FyersExecutionService, available_funds


class FakeMaster:
    expiry_epoch = "1788422400"

    def lookup(self, symbols):
        return {symbol: {"lot_size": 50, "tick_size": 0.05, "expiry_epoch": self.expiry_epoch, "symbol": symbol} for symbol in symbols}


class FakeClient:
    def __init__(self, positions=None, orders=None):
        self.positions_data = positions or []
        self.orders_data = orders or []

    def get_profile(self):
        return {"s": "ok", "data": {"fy_id": "masked"}}

    def optionchain(self, data=None):
        expiry = {"date": "03-09-2026", "expiry": "1788422400", "expiry_flag": "W"}
        if data.get("strikecount") == 1:
            return {"s": "ok", "data": {"expiryData": [expiry], "optionsChain": []}}
        rows = [{"symbol": "NSE:TEST-EQ", "option_type": "", "strike_price": -1, "ltp": 100}]
        for symbol, strike, option_type, bid, ask in [
            ("CE95", 95, "CE", 5.5, 6.0), ("CE100", 100, "CE", 4.5, 4.8),
            ("PE95", 95, "PE", 0.8, 1.0), ("PE100", 100, "PE", 4.2, 4.4),
        ]:
            rows.append({
                "symbol": symbol, "fyToken": symbol, "strike_price": strike, "option_type": option_type,
                "ltp": (bid + ask) / 2, "bid": bid, "ask": ask, "oi": 1000, "volume": 200,
                "greeks": {"delta": 0.5, "gamma": 0.02, "theta": -1, "vega": 1, "iv": 18},
            })
        return {"s": "ok", "data": {"expiryData": [expiry], "optionsChain": rows}}

    def quotes(self, data=None):
        values = {"NSE:TEST-EQ": (99.9, 100.0), "NSE:TEST2-EQ": (199.9, 200.0), "CE95": (5.5, 6.0), "CE100": (4.5, 4.8), "PE95": (0.8, 1.0), "PE100": (4.2, 4.4)}
        return {"s": "ok", "d": [{"n": symbol, "v": {"lp": (bid + ask) / 2, "bid": bid, "ask": ask, "tt": 123}} for symbol, (bid, ask) in values.items() if symbol in data["symbols"].split(",")]}

    def funds(self):
        return {"s": "ok", "fund_limit": [{"id": 10, "title": "Available Balance", "equityAmount": 100000, "commodityAmount": 0}]}

    def positions(self):
        return {"s": "ok", "netPositions": self.positions_data}

    def orderbook(self):
        return {"s": "ok", "orderBook": self.orders_data}


def debit_proposal():
    return {
        "status": "ANALYSIS_ONLY", "label": "Bull call debit spread", "structure": "DEBIT", "direction": "BULLISH",
        "legs": [
            {"action": "BUY", "symbol": "CE95", "strike": 95, "option_type": "CE"},
            {"action": "SELL", "symbol": "CE100", "strike": 100, "option_type": "CE"},
        ],
    }


class FyersExecutionTests(unittest.TestCase):
    def test_available_funds_uses_only_fyers_available_balance_row(self):
        response = {"s": "ok", "fund_limit": [
            {"id": 1, "title": "Total Balance", "equityAmount": 99999.8, "commodityAmount": 0},
            {"id": 3, "title": "Clear Balance", "equityAmount": 99999.8, "commodityAmount": 0},
            {"id": 6, "title": "Fund Transfer", "equityAmount": 100000, "commodityAmount": 0},
            {"id": 10, "title": "Available Balance", "equityAmount": 99999.8, "commodityAmount": 0},
        ]}
        self.assertEqual(available_funds(response), 99999.8)

    def make_service(self, client):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return FyersExecutionService(
            client_factory=lambda *_: client, master=FakeMaster(), cm_master=FakeMaster(),
            ledger=DailyRiskLedger(Path(temporary.name) / "ledger.json"),
            now=lambda: datetime(2026, 8, 30, 10, 0).astimezone(),
        )

    def payload(self):
        return {
            "broker": "fyers", "underlying": "NSE:TEST-EQ", "expiry": "2026-09-03",
            "proposal": debit_proposal(), "invalidation": 94, "lots": 1,
            "daily_loss_limit": 5000, "idea_risk_limit": 2000, "risk_reserve": 1000,
            "enforce_risk_controls": True, "enforce_minimum_reward_to_risk": True,
            "minimum_reward_to_risk": 1,
        }

    def test_screener_order_preview_fails_closed_when_market_is_not_open(self):
        payload = self.payload()
        payload["require_market_open"] = True
        with self.assertRaisesRegex(RuntimeError, "market state is closed"):
            self.make_service(FakeClient()).prepare(payload)

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_long_equity_preview_uses_exact_cash_contract_and_fresh_quote(self, _):
        payload = {
            "broker": "fyers", "underlying": "NSE:TEST-EQ", "invalidation": 95, "quantity": 10,
            "proposal": {"kind": "EQUITY", "label": "Equity long limit", "direction": "BULLISH", "quantity": 10, "target": 108},
            "daily_loss_limit": 5000, "idea_risk_limit": 2000, "risk_reserve": 1000,
        }
        preview = self.make_service(FakeClient()).prepare(payload)
        self.assertEqual(preview["instrument"]["kind"], "EQUITY")
        self.assertEqual(preview["instrument"]["contracts"][0]["symbol"], "NSE:TEST-EQ")
        self.assertEqual(preview["order_policy"]["product_type"], "INTRADAY")
        self.assertTrue(preview["submission_eligible"])

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_delivery_equity_uses_exact_cnc_product(self, _):
        payload = {
            "broker": "fyers", "underlying": "NSE:TEST-EQ", "invalidation": 95, "quantity": 10,
            "cash_product": "CNC",
            "proposal": {"kind": "EQUITY", "label": "Equity delivery", "direction": "BULLISH", "quantity": 10, "target": 108},
            "daily_loss_limit": 5000, "idea_risk_limit": 2000, "risk_reserve": 1000,
        }
        preview = self.make_service(FakeClient()).prepare(payload)
        self.assertEqual(preview["order_policy"]["product_type"], "CNC")
        self.assertEqual(preview["instrument"]["margin"]["status"], "DELIVERY_CASH_FUNDED")

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_batch_preview_risk_sizes_and_full_cash_scales_every_item(self, _):
        def item(symbol, stop, target):
            return {"broker": "fyers", "underlying": symbol, "invalidation": stop, "quantity": 1,
                    "proposal": {"kind": "EQUITY", "label": "Screener long", "direction": "BULLISH", "quantity": 1, "target": target},
                    "daily_loss_limit": 5000, "idea_risk_limit": 2000, "risk_reserve": 1000, "max_simultaneous_positions": 3,
                    "enforce_risk_controls": True}
        preview = self.make_service(FakeClient()).prepare_batch({"items": [item("NSE:TEST-EQ", 95, 110), item("NSE:TEST2-EQ", 195, 210)]})
        self.assertEqual(preview["aggregate"]["selected_count"], 2)
        self.assertEqual(preview["allocation"]["margin_assumption"], "NONE_FULL_CASH")
        self.assertLessEqual(preview["aggregate"]["cash_reserved"], preview["aggregate"]["available_funds"])
        self.assertLessEqual(preview["aggregate"]["total_worst_case_risk"], preview["aggregate"]["available_new_risk"])
        self.assertTrue(all(item["instrument"]["quantity"] >= 1 for item in preview["items"]))

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_partial_trail_is_previewed_but_live_entry_is_blocked(self, _):
        payload = {
            "broker": "fyers", "underlying": "NSE:TEST-EQ", "invalidation": 95, "quantity": 5,
            "exit_plan_mode": "PARTIAL_TARGET_SUPERTREND_7_2",
            "proposal": {"kind": "EQUITY", "label": "Equity long", "direction": "BULLISH", "quantity": 5, "target": 108},
            "daily_loss_limit": 5000, "idea_risk_limit": 2000, "risk_reserve": 1000,
        }
        preview = self.make_service(FakeClient()).prepare(payload)
        self.assertEqual(preview["instrument"]["exit_plan"]["target_quantity"], 2)
        self.assertEqual(preview["instrument"]["exit_plan"]["runner_quantity"], 3)
        self.assertFalse(preview["submission_eligible"])

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_prepare_refreshes_profile_chain_quote_account_and_risk(self, _):
        preview = self.make_service(FakeClient()).prepare(self.payload())
        self.assertEqual(preview["broker"], "FYERS")
        self.assertEqual(preview["instrument"]["reward_to_risk"], 2.33)
        self.assertTrue(preview["profile_validated"])
        self.assertTrue(preview["submission_eligible"])
        self.assertEqual(preview["order_policy"]["execution_mode"], "NORMAL")
        self.assertEqual(preview["order_policy"]["holding_product"], "OVERNIGHT")
        self.assertEqual(preview["order_policy"]["product_type"], "MARGIN")
        self.assertFalse(preview["order_policy"]["is_expiry_day"])
        self.assertTrue(preview["confirmation_phrase"].startswith("CONFIRM FYERS-"))
        self.assertFalse(preview["live_submission_enabled"])

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_open_positions_require_declared_risk(self, _):
        service = self.make_service(FakeClient(positions=[{"symbol": "NSE:X-EQ", "netQty": 1, "realized_profit": -500}]))
        with self.assertRaisesRegex(RuntimeError, "Declare their current worst-case"):
            service.prepare(self.payload())

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_user_enabled_daily_limit_is_not_clamped_to_a_hidden_cap(self, _):
        payload = self.payload(); payload["daily_loss_limit"] = 6000
        preview = self.make_service(FakeClient()).prepare(payload)
        self.assertEqual(preview["daily_risk_ledger"]["hard_daily_loss_limit"], 6000)

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_master_expiry_must_match_fresh_chain(self, _):
        master = FakeMaster(); master.expiry_epoch = "1789027200"
        service = self.make_service(FakeClient()); service.master = master
        with self.assertRaisesRegex(RuntimeError, "master expiry"):
            service.prepare(self.payload())

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_tampered_spread_orientation_is_rejected(self, _):
        payload = self.payload()
        payload["proposal"]["legs"] = [
            {"action": "BUY", "symbol": "CE100", "strike": 100, "option_type": "CE"},
            {"action": "SELL", "symbol": "CE95", "strike": 95, "option_type": "CE"},
        ]
        with self.assertRaisesRegex(ValueError, "do not match"):
            self.make_service(FakeClient()).prepare(payload)

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    def test_market_preference_and_fractional_lots_fail_closed(self, _):
        payload = self.payload(); payload["order_type"] = "MARKET"
        with self.assertRaisesRegex(ValueError, "Market-order"):
            self.make_service(FakeClient()).prepare(payload)
        payload = self.payload(); payload["lots"] = 1.5
        with self.assertRaisesRegex(ValueError, "whole number"):
            self.make_service(FakeClient()).prepare(payload)

    @patch("sector_heatmap.fyers_execution.load_config", return_value={"FYERS_ACCESS_TOKEN": "APP:token"})
    @patch.dict(os.environ, {"SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS": "0"}, clear=False)
    def test_submission_is_disabled_by_default(self, _):
        service = self.make_service(FakeClient())
        preview = service.prepare(self.payload())
        with self.assertRaisesRegex(PermissionError, "disabled"):
            service.submit(preview["preview_id"], preview["confirmation_phrase"])


if __name__ == "__main__":
    unittest.main()
