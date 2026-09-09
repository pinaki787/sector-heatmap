import os
import unittest
from unittest.mock import Mock, patch

from sector_heatmap.straddle_squareoff import StraddleSquareOffService


class Client:
    def positions(self):
        return {"s": "ok", "netPositions": [
            {"symbol": "NSE:TESTCE", "netQty": 65, "productType": "INTRADAY"},
            {"symbol": "NSE:TESTPE", "netQty": 65, "productType": "INTRADAY"},
            {"symbol": "NSE:OTHER", "netQty": 9, "productType": "INTRADAY"},
        ]}

    def orderbook(self):
        return {"s": "ok", "orderBook": []}

    def place_basket_orders(self, orders):
        self.orders = orders
        return {"s": "ok", "data": [{"id": "CE-EXIT"}, {"id": "PE-EXIT"}]}


class StraddleSquareOffTests(unittest.TestCase):
    def runner(self, mode="LIVE"):
        runner = Mock()
        runner.snapshot.return_value = {"name": "Test Straddle", "mode": mode, "position": {
            "ce_symbol": "NSE:TESTCE", "pe_symbol": "NSE:TESTPE", "quantity": 65, "entry_time": "entry-1",
        }}
        runner.stop.return_value = {"running": False}
        return runner

    def test_preview_targets_only_exact_runner_legs(self):
        runner, client = self.runner(), Client()
        preview = StraddleSquareOffService(lambda: "APP:token", {"sensex": runner}, client_factory=lambda: client).prepare("sensex")
        self.assertEqual([leg["symbol"] for leg in preview["legs"]], ["NSE:TESTCE", "NSE:TESTPE"])
        self.assertNotIn("NSE:OTHER", str(preview))
        runner.stop.assert_not_called()

    def test_paper_runner_cannot_prepare_broker_exit(self):
        service = StraddleSquareOffService(lambda: "APP:token", {"nifty": self.runner("PAPER")}, client_factory=Client)
        with self.assertRaises(PermissionError):
            service.prepare("nifty")

    def test_preview_reconciles_broker_quantity_when_saved_state_is_incomplete(self):
        runner, client = self.runner(), Client()
        runner.snapshot.return_value["position"].pop("quantity")
        preview = StraddleSquareOffService(lambda: "APP:token", {"sensex": runner}, client_factory=lambda: client).prepare("sensex")
        self.assertEqual([(leg["action"], leg["quantity"]) for leg in preview["legs"]], [("SELL", 65), ("SELL", 65)])

    def test_preview_covers_a_single_remaining_short_leg(self):
        runner, client = self.runner(), Client()
        client.positions = lambda: {"s": "ok", "netPositions": [
            {"symbol": "NSE:TESTCE", "netQty": -65, "productType": "INTRADAY"},
            {"symbol": "NSE:TESTPE", "netQty": 0, "productType": "INTRADAY"},
        ]}
        preview = StraddleSquareOffService(lambda: "APP:token", {"sensex": runner}, client_factory=lambda: client).prepare("sensex")
        self.assertEqual(preview["legs"], [{
            "symbol": "NSE:TESTCE", "quantity": 65, "action": "BUY_TO_COVER",
            "order_type": "MARKET", "product_type": "INTRADAY",
        }])

    @patch.dict(os.environ, {"SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS": "1"})
    def test_exact_confirmation_stops_runner_and_submits_two_sell_legs(self):
        runner, client = self.runner(), Client()
        service = StraddleSquareOffService(lambda: "APP:token", {"sensex": runner}, client_factory=lambda: client)
        preview = service.prepare("sensex")
        with self.assertRaises(ValueError):
            service.submit(preview["preview_id"], "wrong")
        result = service.submit(preview["preview_id"], preview["confirmation_phrase"])
        runner.stop.assert_called_once()
        self.assertEqual(result["status"], "PENDING")
        self.assertEqual(len(client.orders), 2)
        self.assertTrue(all(order["side"] == -1 for order in client.orders))


if __name__ == "__main__":
    unittest.main()
