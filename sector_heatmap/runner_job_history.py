"""Per-submission history beside the owned runner state; never authorizes execution."""
import hashlib
import json
import os
from pathlib import Path

def record(state_path, state):
    if not state.get("started_at"):
        return
    identity = str(state.get("run_id") or state["started_at"])
    folder = Path(state_path).with_suffix(".jobs")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (hashlib.sha256(identity.encode()).hexdigest() + ".json")
    row = {key: state.get(key) for key in ("run_id", "started_at", "config", "status", "running", "message", "trades_used", "realized_pnl")}
    row.update(job_id=identity, has_position=bool(state.get("position")), has_pending_order=bool(state.get("pending")))
    try:
        old = json.loads(target.read_text())
    except FileNotFoundError:
        old = {}
    comparable = {k:v for k,v in old.items() if k != "last_changed_at"}
    if comparable == row:
        return
    row["last_changed_at"] = state.get("updated_at")
    temporary = target.with_suffix(".tmp")
    with temporary.open("w") as handle:
        os.chmod(temporary, 0o600)
        json.dump(row, handle, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)

def read(state_path):
    folder = Path(state_path).with_suffix(".jobs")
    rows = [json.loads(p.read_text()) for p in folder.glob("*.json")]
    return sorted(rows, key=lambda r:r.get("started_at") or 0, reverse=True)

def record_legacy(state_path, state):
    """Normalize legacy timestamps without changing its execution state."""
    from datetime import datetime
    started=state.get("started_at") or state.get("run_started_at")
    if not started:return
    if isinstance(started,str):
        started=datetime.fromisoformat(started.replace("Z","+00:00")).timestamp()
    record(state_path,{**state,"started_at":started,"updated_at":__import__("time").time()})
