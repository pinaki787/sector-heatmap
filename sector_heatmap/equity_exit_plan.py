"""Planning-only cash-equity exit plans; contains no broker mutations."""

import math


def build_equity_exit_plan(direction, quantity, entry, target, mode="FIXED_TARGET"):
    direction = str(direction).upper()
    quantity = int(quantity)
    if direction not in {"BULLISH", "BEARISH"} or quantity < 1:
        raise ValueError("A valid direction and positive whole-share quantity are required.")
    if mode == "FIXED_TARGET":
        return {"mode": mode, "quantity": quantity, "target_quantity": quantity,
                "runner_quantity": 0, "state": "WAIT_ENTRY_FILL", "live_execution": "NOT_IMPLEMENTED"}
    if mode != "PARTIAL_TARGET_SUPERTREND_7_2":
        raise ValueError("Unsupported cash-equity exit plan.")
    target_quantity = math.floor(quantity * 0.5)
    runner_quantity = quantity - target_quantity
    if target_quantity < 1 or runner_quantity < 1:
        raise ValueError("Partial target requires at least two whole shares.")
    return {
        "mode": mode, "quantity": quantity, "target_quantity": target_quantity,
        "runner_quantity": runner_quantity, "entry": float(entry), "partial_target": float(target),
        "direction": direction, "state": "WAIT_ENTRY_FILL", "active_stop": "STRUCTURAL_INVALIDATION",
        "supertrend": {"period": 7, "multiplier": 2.0, "completed_candles_only": True},
        "exit_rule": "Confirmed bearish Supertrend flip" if direction == "BULLISH" else "Confirmed bullish Supertrend flip",
        "live_execution": "NOT_IMPLEMENTED",
    }


def advance_exit_plan(plan, event, candle=None):
    """Advance only on explicit fill/completed-candle evidence."""
    updated = dict(plan)
    state = updated["state"]
    if event == "ENTRY_FILL_CONFIRMED" and state == "WAIT_ENTRY_FILL":
        updated["state"] = "ACTIVE_INITIAL_STOP"
    elif event == "PARTIAL_TARGET_FILL_CONFIRMED" and state == "ACTIVE_INITIAL_STOP" and updated["mode"] != "FIXED_TARGET":
        updated["state"] = "SUPERTREND_ACTIVE"
        updated["active_stop"] = "SUPERTREND_7_2"
    elif event == "COMPLETED_CANDLE" and state == "SUPERTREND_ACTIVE":
        if not candle or not candle.get("completed"):
            raise ValueError("Supertrend evaluation requires a completed candle.")
        flipped_against = candle.get("supertrend_direction") == ("BEARISH" if updated["direction"] == "BULLISH" else "BULLISH")
        if flipped_against:
            updated["state"] = "EXIT_SIGNAL_CONFIRMED"
    else:
        raise ValueError("Exit-plan event is invalid for the current state.")
    return updated
