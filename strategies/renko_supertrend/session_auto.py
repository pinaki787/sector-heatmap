"""Versioned reference sizing. No network, runner lifecycle or order access.

Callers supply verified completed reference evidence. Reference-window selection
is explicit, so a session reference cannot be confused with a host-history seed.
Existing configurations without this policy remain legacy calculations.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

REVISION = "session-atr-scaled-v1"
LEGACY = "legacy-history-seed-v1"
IST = ZoneInfo("Asia/Kolkata")


def positive(value, label):
    if isinstance(value, bool):
        raise ValueError(label + " must be positive and finite.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(label + " must be positive and finite.") from None
    if not math.isfinite(number) or number <= 0:
        raise ValueError(label + " must be positive and finite.")
    return number


def selected(config):
    revision = config.get("auto_sizing_policy", LEGACY)
    if revision not in (LEGACY, REVISION):
        raise ValueError("Unknown Auto sizing policy; no legacy fallback.")
    return revision == REVISION and config.get("brick_mode") == "Auto" and config.get("strategy_basis") == "RENKO"


def session_spec(symbol, broker, policy):
    if not symbol or not broker:
        raise ValueError("Exact broker and signal symbol are required for session sizing.")
    if broker == "DELTA_INDIA":
        if not policy.get("seven_day_session") or policy.get("session_source") not in ("CONTINUOUS_CRYPTO", "EXPLICIT_USER_POLICY"):
            raise ValueError("Verified continuous Delta session policy required.")
        opening, duration = 0, 1440
    else:
        if not policy.get("session_source"):
            raise ValueError("Verified broker symbol session source required.")
        bounds = policy.get("master_regular_session", "")
        try:
            a, b = bounds.split("-")
            if len(a) != 4 or len(b) != 4 or not a.isdigit() or not b.isdigit():
                raise ValueError
            ah, am, bh, bm = int(a[:2]), int(a[2:]), int(b[:2]), int(b[2:])
            if not (0 <= ah < 24 and 0 <= am < 60 and 0 <= bh <= 24 and 0 <= bm < 60) or bh == 24 and bm:
                raise ValueError
            opening, end = ah * 60 + am, bh * 60 + bm
            duration = end - opening
            if duration <= 0:
                duration += 1440
            if not 0 < duration <= 1440:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("Verified broker regular-session boundaries required.") from None
    return dict(broker=broker, symbol=symbol, zone="Asia/Kolkata", opening_minutes=opening,
                session_minutes=duration, source=policy["session_source"])


def session_bounds(stamp, spec):
    dt = datetime.fromtimestamp(float(stamp), IST)
    opening = dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=spec["opening_minutes"])
    if spec["opening_minutes"] + spec["session_minutes"] > 1440 and dt < opening:
        opening -= timedelta(days=1)
    closing = opening + timedelta(minutes=spec["session_minutes"])
    return opening.timestamp(), closing.timestamp()


def completed_reference_bars(rows, windows, *, source_seconds, available_at):
    """Aggregate explicit verified windows only with every source candle present.

    The caller supplies session or other approved reference windows; this
    function never guesses a missing session, repairs gaps or chooses a window.
    """
    from .signals import completed
    seconds = positive(source_seconds, "Reference source interval")
    if int(seconds) != seconds:
        raise ValueError("Reference source interval must be whole seconds.")
    seconds = int(seconds)
    source = {r["timestamp"]: r for r in completed(rows) if r["timestamp"] + seconds <= available_at}
    result = []
    for start, end in sorted(windows):
        if end > available_at:
            continue
        if int(start) != start or int(end) != end or end <= start or (end - start) % seconds:
            raise ValueError("Reference window does not align with complete source intervals.")
        expected = list(range(int(start), int(end), seconds))
        if any(t not in source for t in expected):
            raise ValueError("Completed reference window has missing source candles; no synthetic coverage.")
        bars = [source[t] for t in expected]
        result.append(dict(timestamp=start, completed_at=end, open=bars[0]["open"],
                           high=max(r["high"] for r in bars), low=min(r["low"] for r in bars),
                           close=bars[-1]["close"], source_seconds=seconds, source_count=len(bars)))
    return result


def reference(session_bars, *, length, factor, available_at, input_basis):
    """Wilder ATR from explicit completed reference OHLC; no future observations.

    Every bar has timestamp (opening), completed_at, OHLC, and broker/source
    evidence. A caller must validate source coverage before providing a bar.
    """
    if isinstance(length, bool) or int(length) != length or not 1 <= int(length) <= 100:
        raise ValueError("Reference ATR length must be an integer from 1 to 100.")
    length = int(length)
    factor = positive(factor, "Base factor")
    if not input_basis:
        raise ValueError("Explicit reference-input basis required.")
    available_at = positive(available_at, "Reference availability boundary")
    unique = {}
    for raw in session_bars:
        if raw.get("is_forming"):
            continue
        row = {k: raw.get(k) for k in ("timestamp", "completed_at", "open", "high", "low", "close")}
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in row.values()):
            raise ValueError("Reference evidence requires finite opening/closing times and OHLC.")
        if row["completed_at"] <= row["timestamp"]:
            raise ValueError("Reference completion must follow its opening.")
        if row["completed_at"] > available_at:
            continue
        if min(row[k] for k in ("open", "high", "low", "close")) <= 0 or row["low"] > min(row["open"], row["close"]) or row["high"] < max(row["open"], row["close"]):
            raise ValueError("Invalid reference OHLC.")
        prior = unique.get(row["timestamp"])
        if prior is not None and prior != row:
            raise ValueError("Conflicting completed reference evidence.")
        unique[row["timestamp"]] = row
    bars = sorted(unique.values(), key=lambda r: r["timestamp"])
    if len(bars) < length:
        raise ValueError("Insufficient completed reference observations for ATR warmup.")
    if any(b["timestamp"] < a["completed_at"] for a, b in zip(bars, bars[1:])):
        raise ValueError("Reference intervals overlap.")
    previous = None
    atr = None
    seed = []
    for row in bars:
        tr = row["high"] - row["low"] if previous is None else max(row["high"] - row["low"], abs(row["high"] - previous), abs(row["low"] - previous))
        if atr is None:
            seed.append(tr)
            if len(seed) == length:
                atr = sum(seed) / length
        else:
            atr = (atr * (length - 1) + tr) / length
        previous = row["close"]
    positive(atr, "Completed reference ATR")
    return dict(revision=REVISION, input_basis=input_basis, atr_length=length, base_factor=factor,
                reference_atr=atr, session_reference=atr * factor, available_at=bars[-1]["completed_at"],
                reference_anchor=bars[0]["timestamp"], reference_count=len(bars),
                input_hash=sha256(json.dumps(bars, sort_keys=True, separators=(",", ":")).encode()).hexdigest())


def scale(ref, timeframe_seconds, spec, tick):
    if ref.get("revision") != REVISION:
        raise ValueError("Reference sizing version mismatch.")
    tick = positive(tick, "Native underlying minimum tick")
    seconds = positive(timeframe_seconds, "Selected timeframe")
    duration = positive(spec["session_minutes"], "Verified session duration") * 60
    if seconds > duration:
        raise ValueError("Selected timeframe exceeds the verified trading session.")
    raw = Decimal(str(positive(ref["session_reference"], "Session reference"))) * Decimal(str(seconds)) / Decimal(str(duration))
    # A Renko box is a calculation interval, not an executable order price.
    # Preserve its precision; apply the existing native minimum without falsely
    # snapping order prices or promising linear scaling below the minimum.
    box = max(Decimal(str(tick)), raw)
    return dict(raw_box=float(raw), box=float(box), native_tick=tick, minimum_tick_applied=raw < Decimal(str(tick)),
                timeframe_seconds=seconds, session_minutes=spec["session_minutes"],
                constraint="Native minimum tick; full calculation precision retained")


class FrozenReferences:
    """Account-local durable reference ledger; independent of selected timeframe.

    Existing references are returned verbatim across reloads/restarts. A new
    reference cannot silently revise an already frozen session. The caller can
    inspect a conflict and retain the original audit without reanchoring it.
    """
    def __init__(self, path):
        self.path = Path(path)

    def _key(self, spec, start, ref):
        return sha256(json.dumps([REVISION, spec, start, ref["input_basis"], ref["atr_length"], ref["base_factor"]], sort_keys=True).encode()).hexdigest()

    def freeze(self, spec, session_start, ref):
        import os
        from sector_heatmap.file_lock import lock_file, unlock_file
        from sector_heatmap.workspaces import private_write
        start, end = session_bounds(session_start, spec)
        if start != session_start:
            raise ValueError("Freeze requires the exact verified session opening.")
        if ref.get("revision") != REVISION or ref.get("available_at", float("inf")) > start:
            raise ValueError("Reference evidence must be complete before the target session begins.")
        positive(ref.get("session_reference"), "Session reference")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path.with_suffix(".lock"), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            lock_file(fd)
            ledger = json.loads(self.path.read_text()) if self.path.exists() else dict(revision=REVISION, references={})
            if ledger.get("revision") != REVISION:
                raise ValueError("Stored session sizing revision requires explicit migration.")
            key = self._key(spec, start, ref)
            existing = ledger["references"].get(key)
            frozen = {**deepcopy(ref), **deepcopy(spec), "reference_source":ref.get("source"), "session_start":start, "session_end":end,
                      "freeze_basis":"Verified completed reference evidence available before session opening"}
            if existing is not None:
                if existing != frozen:
                    raise ValueError("Completed reference changed after session freeze; original preserved, explicit review required.")
                return deepcopy(existing)
            ledger["references"][key] = frozen
            private_write(self.path, json.dumps(ledger, sort_keys=True, allow_nan=False))
            return deepcopy(frozen)
        finally:
            unlock_file(fd)
            os.close(fd)


def _store_path(adapter, broker, symbol, instrument_identity=None):
    override = getattr(adapter, "session_auto_root", None)
    if override is not None:
        root = Path(override)
    elif getattr(adapter, "service", None) is not None and getattr(adapter.service, "folder", None):
        root = Path(adapter.service.folder) / "renko-session-auto"
    elif getattr(adapter, "path", None):
        root = Path(adapter.path).parent / "renko-session-auto"
    elif getattr(adapter, "master_dir", None):
        root = Path(adapter.master_dir) / ".renko-session-auto"
    else:
        raise ValueError("Account-local session reference storage unavailable.")
    identity = sha256(json.dumps([broker, symbol, instrument_identity]).encode()).hexdigest()
    return root / (identity + ".json")


def _dated_spec(adapter, config, day):
    policy = dict(adapter.session_policy(config))
    broker = config.get("broker", "FYERS")
    if config["underlying"].startswith("MCX:") and policy.get("master_regular_session", "").startswith("0900-"):
        # Supported non-agricultural MCX contracts use the existing dated
        # exchange calendar, including evening-only holidays and DST changes.
        from sector_heatmap.motilal_calendar import trading_bounds
        at = datetime.combine(day, datetime.min.time(), IST).timestamp()
        opening, closing = trading_bounds(at)
        if opening == closing:
            return None
        policy.update(master_regular_session=f"{opening//60:02}{opening%60:02}-{closing//60:02}{closing%60:02}",
                      session_source="Verified dated MCX non-agricultural exchange calendar")
    return {**session_spec(config["underlying"], broker, policy), "instrument_identity":config.get("_session_auto_instrument_identity")}


def _load_reference_inputs(adapter, config, begin, now):
    custom = getattr(adapter, "session_auto_inputs", None)
    if custom:
        return custom(config, begin, now)
    broker = config.get("broker", "FYERS")
    if broker == "FYERS":
        from sector_heatmap.fyers_execution import _current_client
        from sector_heatmap.fyers_history import history
        from datetime import timezone
        today = datetime.fromtimestamp(now, IST).date()
        response = history(_current_client(), dict(symbol=config["underlying"], resolution="D", date_format=1,
                           range_from=str(today-timedelta(days=365)), range_to=str(today), cont_flag=0, oi_flag=1))
        if response.get("s") != "ok" or not isinstance(response.get("candles"), list):
            raise ValueError("Selected FYERS native completed-session reference unavailable.")
        result = []
        for raw in response["candles"]:
            stamp = float(raw[0])
            if int(stamp) != stamp or int(stamp) % 86400:
                raise ValueError("Native daily reference date identity is unverified.")
            day = datetime.fromtimestamp(stamp, timezone.utc).date()
            spec = _dated_spec(adapter, config, day)
            if spec is None:
                continue
            opening = datetime.combine(day, datetime.min.time(), IST).timestamp()+spec["opening_minutes"]*60
            closing = opening+spec["session_minutes"]*60
            if closing <= now:
                result.append(dict(timestamp=opening, completed_at=closing, open=float(raw[1]), high=float(raw[2]),
                                   low=float(raw[3]), close=float(raw[4])))
        return result, "Selected FYERS native completed-session OHLC; fixed contract, no continuous roll"
    source_config = {**config, "auto_sizing_policy": LEGACY, "timeframe": "5 minutes", "history_start": begin}
    source_config.pop("_session_auto_references", None)
    source_rows = adapter.candles(source_config)
    from .signals import completed
    source_rows = completed(source_rows)
    days = sorted({datetime.fromtimestamp(r["timestamp"], IST).date() for r in source_rows})
    windows = []
    for day in days:
        spec = _dated_spec(adapter, config, day)
        if spec is None:
            continue
        start = datetime.combine(day, datetime.min.time(), IST).timestamp()+spec["opening_minutes"]*60
        end = start+spec["session_minutes"]*60
        if end <= now:
            # An initial partial fetch cannot become a reference session.
            if day == days[0] and source_rows[0]["timestamp"] > start:
                continue
            windows.append((start, end))
    bars = completed_reference_bars(source_rows, windows, source_seconds=300, available_at=now)
    return bars, "Selected " + broker + " exact full-session aggregation of native five-minute OHLC; no gap repair"


def prepare(adapter, config, host_rows=()):
    """Populate the same persisted session references for charts and runners.

    No lifecycle/order methods are called. The policy is opt-in/versioned;
    missing reference evidence blocks it instead of reverting to host ATR.
    """
    if not selected(config):
        return
    clock = getattr(adapter, "clock", None)
    now = clock() if callable(clock) else adapter.delta.clock() if getattr(adapter, "delta", None) else __import__("time").time()
    broker = config.get("broker", "FYERS")
    today = datetime.fromtimestamp(now, IST).date()
    profile = (config["underlying"], broker, int(config["atr_length"]), float(config["factor"]), str(today))
    cached = getattr(adapter, "_session_auto_cache", {}).get(profile)
    if cached is not None:
        config["_session_auto_references"] = deepcopy(cached)
        config["_session_auto_instrument_identity"] = next(iter(cached.values()))["instrument_identity"]
        return
    identity = getattr(adapter, "session_auto_instrument_identity", None)
    if identity is None:
        if not hasattr(adapter, "underlying"):
            raise ValueError("Verified broker signal instrument identity required for session sizing.")
        row = adapter.underlying(config["underlying"])
        if isinstance(row, (list, tuple)) and len(row) > 9:
            identity = json.dumps([str(row[0]),str(row[9])])
        elif isinstance(row, dict):
            identity = json.dumps({k:row[k] for k in ("SEM_SMST_SECURITY_ID","SEM_EXM_EXCH_ID","SEM_SEGMENT","symbol","exchange","scripcode","token","instrument","expiry") if row.get(k) is not None},sort_keys=True)
        if not identity or identity == "{}":
            raise ValueError("Exact broker signal instrument identity is unavailable.")
    if config.get("_session_auto_instrument_identity") not in (None, identity):
        raise ValueError("Saved session sizing instrument identity changed; explicit new-run review required.")
    config["_session_auto_instrument_identity"] = identity
    oldest = min((r["timestamp"] for r in host_rows if not r.get("is_forming")), default=config.get("history_start", now-52*86400))
    inputs, source = _load_reference_inputs(adapter, config, min(oldest-30*86400, now-80*86400), now)
    inputs = [r for r in inputs if not r.get("is_forming") and r.get("completed_at", float("inf")) <= now]
    length = int(config["atr_length"])
    if len(inputs) < length:
        raise ValueError("Session Auto requires sufficient fully covered completed sessions for reference ATR; no host-seed fallback.")
    store = FrozenReferences(_store_path(adapter, broker, config["underlying"], identity))
    # Persist the canonical input anchor; later rolling source windows cannot
    # reseed the reference. Source revisions must be reviewed, never rewritten.
    source_path = store.path.with_name(store.path.stem + "-source.json")
    from sector_heatmap.workspaces import private_write
    import os
    from sector_heatmap.file_lock import lock_file, unlock_file
    source_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(source_path.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        lock_file(fd)
        persisted = json.loads(source_path.read_text()) if source_path.exists() else dict(revision=REVISION, bars=[])
        if persisted.get("revision") != REVISION:
            raise ValueError("Session reference source version requires explicit migration.")
        merged = {r["timestamp"]: r for r in persisted["bars"]}
        for row in inputs:
            normalized = {k: row[k] for k in ("timestamp", "completed_at", "open", "high", "low", "close")}
            previous = merged.get(row["timestamp"])
            if previous is not None and previous != normalized:
                raise ValueError("Completed session reference OHLC changed; frozen references preserved, explicit review required.")
            merged[row["timestamp"]] = normalized
        inputs = sorted(merged.values(), key=lambda r: r["timestamp"])
        anchor = persisted.get("anchor", inputs[0]["timestamp"])
        inputs = [r for r in inputs if r["timestamp"] >= anchor]
        private_write(source_path, json.dumps(dict(revision=REVISION, anchor=anchor, bars=inputs), sort_keys=True, allow_nan=False))
    finally:
        unlock_file(fd)
        os.close(fd)
    days = {datetime.fromtimestamp(r["timestamp"], IST).date() for r in inputs}
    days.update(datetime.fromtimestamp(r["timestamp"], IST).date() for r in host_rows)
    days.add(today)
    refs = {}
    for day in sorted(days):
        if day > today:continue
        spec = _dated_spec(adapter, config, day)
        if spec is None:
            continue
        start = datetime.combine(day, datetime.min.time(), IST).timestamp()+spec["opening_minutes"]*60
        prior = [r for r in inputs if r["completed_at"] <= start]
        if len(prior) < length:
            continue
        r = reference(prior, length=length, factor=config["factor"], available_at=start, input_basis="COMPLETED_FULL_SESSION_OHLC")
        r["source"] = source
        frozen = store.freeze(spec, start, r)
        refs[str(int(start))] = frozen
    latest = max((r["timestamp"] for r in host_rows if not r.get("is_forming")), default=now)
    if not refs or host_rows and not any(r["session_start"] <= latest < r["session_end"] for r in refs.values()):
        raise ValueError("Selected session reference is unavailable; no previous-session or host-seed fallback.")
    cache = getattr(adapter, "_session_auto_cache", {})
    cache[profile] = deepcopy(refs)
    adapter._session_auto_cache = {profile: cache[profile]}
    config["_session_auto_references"] = refs


def candle_source(original):
    from functools import wraps
    @wraps(original)
    def load(adapter, config):
        rows = original(adapter, config)
        if selected(config):
            prepare(adapter, config, rows)
        return rows
    return load


def for_observation(config, stamp, tick):
    if not selected(config):
        return None
    refs = config.get("_session_auto_references")
    if refs is None:
        raise ValueError("Session Auto reference evidence unavailable; no legacy fallback.")
    candidates = [r for r in refs.values() if r["session_start"] <= stamp < r["session_end"]]
    if not candidates:
        return None
    ref = candidates[0]
    from strategies.ema_crossover.runner import TIMEFRAMES
    return {**deepcopy(ref), **scale(ref, TIMEFRAMES[config["timeframe"]], ref, tick)}


def apply_observation(state, config, stamp, tick):
    ref = for_observation(config, stamp, tick)
    if ref is None:
        return None
    prior = state.get("session_auto")
    if prior and prior["session_start"] > ref["session_start"]:
        raise ValueError("Session reference cannot move backward after processing.")
    if prior and prior["session_start"] == ref["session_start"] and prior != ref:
        raise ValueError("Session sizing reference changed inside a frozen session; no reanchor.")
    if not prior or prior["session_start"] != ref["session_start"]:
        if not prior and state.get("count", 0) and state.get("brick_box") is not None:
            raise ValueError("Legacy engine cannot acquire session sizing without an explicit new-run rebuild.")
        state.update(session_auto=deepcopy(ref), brick_box=ref["box"], brick_level=None, brick_direction=0)
        # The new session starts from its first observed price. Never construct
        # a tradeable path across an unobserved overnight/session boundary.
        state["price_renko"] = {}
    return ref
