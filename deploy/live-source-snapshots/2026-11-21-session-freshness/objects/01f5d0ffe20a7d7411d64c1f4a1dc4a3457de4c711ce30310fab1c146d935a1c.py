"""Exercise parser price validation without starting the service or sending orders."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from sector_heatmap import web


class ParserOrderPreparationTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path(web.__file__).read_text())
        server = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_server")
        prepare = next(node for node in server.body if isinstance(node, ast.FunctionDef) and node.name == "prepare_trade_recommendation_order")
        self.client = Mock()
        self.client.get_profile.return_value = {"s": "ok"}
        self.client.quotes.return_value = {"d": [{"n": "BSE:SENSEX26O0872300PE", "v": {"lp": 523.6}}]}
        self.client.funds.return_value = {}
        scope = dict(vars(web))
        scope.update(
            load_config=lambda: {"FYERS_ACCESS_TOKEN": "test:test"},
            fyersModel=SimpleNamespace(FyersModel=lambda **kwargs: self.client),
            trade_recommendation_preview=lambda payload: {
                "parsed": {"action": "BUY", "entry": 530, "targets": [550]},
                "mapping": {"status": "EXACT", "contract": {
                    "symbol": "BSE:SENSEX26O0872300PE", "lot_size": 20, "tick_size": 0.05}},
                "trailing_plan": [],
            },
            parser_live_submission_enabled=True,
            parser_protection_enabled=lambda: False,
            parser_order_previews={},
        )
        exec(compile(ast.Module(body=[prepare], type_ignores=[]), web.__file__, "exec"), scope)
        self.prepare = scope[prepare.name]

    def test_sensex_stop_limit_prepares_exact_ticket_without_order(self):
        ticket = self.prepare({"lots": "1", "entry_mode": "STOP_LIMIT", "trigger_price": "530", "limit_price": "530.05"})
        self.assertEqual(ticket["status"], "PREVIEW_ONLY")
        self.assertEqual(ticket["order"]["qty"], 20)
        self.assertEqual(ticket["order"]["type"], 4)
        self.assertEqual(ticket["order"]["stopPrice"], 530)
        self.assertEqual(ticket["order"]["limitPrice"], 530.05)
        self.client.place_order.assert_not_called()

    def test_buy_stop_limit_rejects_limit_at_trigger(self):
        with self.assertRaisesRegex(ValueError, "limit must be above trigger"):
            self.prepare({"entry_mode": "STOP_LIMIT", "trigger_price": 530, "limit_price": 530})
        self.client.place_order.assert_not_called()

    def test_nonpositive_price_is_rejected_before_order(self):
        with self.assertRaisesRegex(ValueError, "finite and positive"):
            self.prepare({"entry_mode": "LIMIT", "limit_price": 0})
        self.client.place_order.assert_not_called()
