import unittest

from sector_heatmap.equity_exit_plan import advance_exit_plan, build_equity_exit_plan


class EquityExitPlanTests(unittest.TestCase):
    def test_fixed_target_is_default_and_planning_only(self):
        plan = build_equity_exit_plan("BULLISH", 5, 100, 110)
        self.assertEqual(plan["target_quantity"], 5)
        self.assertEqual(plan["live_execution"], "NOT_IMPLEMENTED")

    def test_partial_fill_activates_completed_candle_supertrend_for_runner(self):
        plan = build_equity_exit_plan("BULLISH", 5, 100, 110, "PARTIAL_TARGET_SUPERTREND_7_2")
        self.assertEqual((plan["target_quantity"], plan["runner_quantity"]), (2, 3))
        self.assertEqual(plan["active_stop"], "STRUCTURAL_INVALIDATION")
        plan = advance_exit_plan(plan, "ENTRY_FILL_CONFIRMED")
        plan = advance_exit_plan(plan, "PARTIAL_TARGET_FILL_CONFIRMED")
        self.assertEqual(plan["state"], "SUPERTREND_ACTIVE")
        plan = advance_exit_plan(plan, "COMPLETED_CANDLE", {"completed": True, "supertrend_direction": "BEARISH"})
        self.assertEqual(plan["state"], "EXIT_SIGNAL_CONFIRMED")

    def test_supertrend_plan_rejects_invalid_quantity_and_forming_candle(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            build_equity_exit_plan("BEARISH", 1, 100, 90, "PARTIAL_TARGET_SUPERTREND_7_2")
        plan = build_equity_exit_plan("BEARISH", 4, 100, 90, "PARTIAL_TARGET_SUPERTREND_7_2")
        plan = advance_exit_plan(plan, "ENTRY_FILL_CONFIRMED")
        plan = advance_exit_plan(plan, "PARTIAL_TARGET_FILL_CONFIRMED")
        with self.assertRaisesRegex(ValueError, "completed candle"):
            advance_exit_plan(plan, "COMPLETED_CANDLE", {"completed": False, "supertrend_direction": "BULLISH"})


if __name__ == "__main__":
    unittest.main()
