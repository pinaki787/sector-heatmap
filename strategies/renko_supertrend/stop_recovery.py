"""Fail-closed identity for continuing an already-authorized Paper Stop only."""
from copy import deepcopy

def paper_stop_identity(state):
    c=state.get("config") or {};p=state.get("position") or {}
    if not (state.get("schema")==1 and state.get("run_id") and state.get("account_identity")
            and state.get("status") in ("DRAINING","RECOVERY_REQUIRED")
            and state.get("squareoff_requested") is True and state.get("accepting_entries") is False
            and not state.get("pending") and not state.get("positions")
            and c.get("mode")=="PAPER" and c.get("broker")=="DELTA_INDIA"
            and c.get("strategy_basis")=="RENKO" and c.get("renko_confirmation")=="PRICE"
            and p.get("exit_requested") is True and p.get("exit_reason")=="MANUAL_SQUARE_OFF"
            and p.get("run_id")==state["run_id"] and p.get("underlying_symbol")==c.get("underlying")
            and isinstance(p.get("quantity"),(int,float)) and not isinstance(p.get("quantity"),bool)
            and p["quantity"]>0 and p.get("symbol") and not p.get("entry_order_id")):
        raise ValueError("Only an existing identified Delta price-Renko Paper Stop with owned exposure and no pending order can recover.")
    related=[o for o in state.get("order_history",[]) if o.get("run_id")==state["run_id"] and o.get("symbol")==p["symbol"]]
    if any(o.get("mode")!="PAPER" or o.get("order_id") for o in related):
        raise ValueError("Current exposure has contradictory live-order evidence.")
    entries=[o for o in state.get("order_history",[]) if o.get("run_id")==state["run_id"] and o.get("is_entry") and o.get("symbol")==p["symbol"] and o.get("entry_event_at")==p.get("entry_event_at")]
    if not entries or any(o.get("mode")!="PAPER" or o.get("order_id") or o.get("status")!="FILLED" or not o.get("paper_order_id") for o in entries):
        raise ValueError("Paper entry evidence is missing, ambiguous, or contains a real broker order identity.")
    return deepcopy(dict(run_id=state["run_id"],account_identity=state["account_identity"],config=c,
                         position={k:p.get(k) for k in ("symbol","quantity","run_id","underlying_symbol","opened_at","entry_event_at","lifecycle_id")},
                         stop_requested=True))

def eligible(state):
    try:paper_stop_identity(state);return True
    except (ValueError,TypeError,KeyError):return False
