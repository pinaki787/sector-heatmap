"""Report provenance, independent from run update times and execution state."""
from datetime import datetime
import math

def report_freshness(output, source_slot, latest, now):
    report=output.get("report") or {}
    generated=report.get("generated_at")
    try:
        stamp=datetime.fromisoformat(generated)
        if stamp.tzinfo is None:raise ValueError()
        age=now-stamp.timestamp()
        recent=math.isfinite(age) and 0<=age<=900
    except (TypeError,ValueError,OverflowError):
        recent=False
    same=bool(latest and latest.get("slot")==source_slot)
    state="EMPTY" if not source_slot else "CURRENT" if recent and same and latest.get("state")=="COMPLETED" else "PARTIAL" if recent and same else "STALE"
    messages={
        "EMPTY":"No scheduled analysis has completed yet.",
        "CURRENT":"Latest completed analysis; broker execution checks still apply.",
        "PARTIAL":"Latest analysis is incomplete or under review. Retained findings are for reference.",
        "STALE":"Historical analysis retained for reference. A fresh completed scan is required before selection."
    }
    return dict(state=state,generated_at=generated,source_slot=source_slot,
                selectable=state=="CURRENT",message=messages[state])
