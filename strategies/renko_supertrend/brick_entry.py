"""Automatic Renko entry direction is owned by its completed signal brick."""
import math

def allowed(config,signal,direction):
    if config.get("strategy_basis")!="RENKO":return True
    if signal.get("provisional") or not signal.get("has_completed_brick"):return False
    from .swing_breakout import check
    if not check(config,signal,direction)['allowed']:return False
    opening,closing=signal.get("open"),signal.get("close")
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (opening,closing)):return False
    actual="BULLISH" if closing>opening else "BEARISH" if closing<opening else None
    return direction in ("BULLISH","BEARISH") and signal.get("brick_direction")==direction==actual
