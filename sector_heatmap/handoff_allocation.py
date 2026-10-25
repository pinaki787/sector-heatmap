"""Broker-independent Handoff ranking, bounded allocation and durable claims.

This module has no broker order methods and cannot arm live execution.
Prices must be validated execution-contract prices supplied by an owned adapter.
"""
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import hashlib
import json
from pathlib import Path
import sqlite3

BROKERS = {"FYERS", "DHAN", "MOTILAL_OSWAL"}


def amount(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a price or amount.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Finite numeric amount required.") from None
    if not result.is_finite() or result <= 0:
        raise ValueError("Positive finite amount required.")
    return result


def normalized_score(row):
    c = row.get("conviction") or {}
    if str(c.get("rating", "")).upper() != "HIGH":
        raise ValueError("Only high-conviction recommendations are eligible.")
    score, maximum = amount(c.get("score")), amount(c.get("maximum_score"))
    if score > maximum:
        raise ValueError("Conviction score exceeds its scale.")
    return score / maximum


def identity(row):
    """Ignore report time and prose; unchanged contract/levels stay duplicates."""
    numeric = {k: str(amount(row[k]).normalize()) for k in ("entry", "stop", "target")}
    value = {k: row[k] for k in ("underlying", "symbol", "kind", "direction")}
    value.update(numeric)
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate(row):
    row = dict(row)
    if row.get("kind") not in {"EQUITY", "LONG_OPTION"}:
        raise ValueError("Only cash equity and bought stock options are eligible.")
    if row.get("direction") not in {"BULLISH", "BEARISH"}:
        raise ValueError("A directional recommendation is required.")
    if not all(isinstance(row.get(k), str) and row[k].strip() for k in ("underlying", "symbol")):
        raise ValueError("Exact underlying and execution contract required.")
    if row.get("validated") is not True:
        raise ValueError("Fresh owned-broker contract and protection validation required.")
    entry, stop, target = (amount(row[k]) for k in ("entry", "stop", "target"))
    # LONG_OPTION is always a bought option, including a bearish Put.
    long = row["kind"] == "LONG_OPTION" or row["direction"] == "BULLISH"
    if not (stop < entry < target if long else target < entry < stop):
        raise ValueError("Execution stop and target are on the wrong side of entry.")
    lot = row.get("lot_size", 1)
    if isinstance(lot, bool) or not isinstance(lot, int) or lot < 1 or row["kind"] == "EQUITY" and lot != 1:
        raise ValueError("Valid broker master lot size required.")
    row["lot_size"] = lot
    row["score_fraction"] = str(normalized_score(row))
    row["fingerprint"] = identity(row)
    return row


def rank(rows, *, exposed=(), seen=(), top=5):
    """Select new high-conviction ideas independently of available capital."""
    if isinstance(top,bool) or not isinstance(top,int) or not 1<=top<=5:
        raise ValueError("At most five high-conviction ideas are allowed.")
    blocked, remembered = set(exposed), set(seen)
    eligible, excluded = [], []
    for source in rows:
        try:
            row = validate(source)
            if row["underlying"] in blocked:
                raise ValueError("Underlying already has a position, holding or pending order.")
            if row["fingerprint"] in remembered:
                raise ValueError("Unchanged recommendation already reported or claimed.")
            eligible.append(row)
        except (ValueError, KeyError) as e:
            excluded.append({"symbol": source.get("symbol"), "reason": str(e)})
    from .handoff_priority import priority_key
    eligible.sort(key=priority_key)
    selected, underlyings = [], set()
    for row in eligible:
        if row["underlying"] in underlyings:
            excluded.append({"symbol": row["symbol"], "reason": "One recommendation per underlying; higher-ranked idea preferred."})
            continue
        underlyings.add(row["underlying"])
        if len(selected) < top:
            selected.append(row)
    return selected, excluded


def allocate(rows, *, capital=100000, used=0, funds=None, exposed=(), seen=(), top=5):
    """Rank unique underlyings; reserve one lot/options first, then equal cash.

    Missing broker state must be rejected by the caller, never treated as flat.
    Capital is full notional/premium, not leveraged broker buying power.
    """
    cap = amount(capital)
    if isinstance(used, bool):
        raise ValueError("Invalid used capital.")
    used = Decimal(str(used))
    if not used.is_finite() or used < 0:
        raise ValueError("Used capital must be finite and nonnegative.")
    available = max(Decimal(0), cap - used)
    if funds is not None:
        cash = Decimal(str(funds))
        if isinstance(funds, bool) or not cash.is_finite() or cash < 0:
            raise ValueError("Available funds must be finite and nonnegative.")
        available = min(available, cash)
    if not isinstance(top, int) or isinstance(top, bool) or not 1 <= top <= 5:
        raise ValueError("At most five high-conviction ideas are allowed.")
    selected, excluded = rank(rows, exposed=exposed, seen=seen, top=top)
    option_total = sum((amount(r["entry"]) * r["lot_size"] for r in selected if r["kind"] == "LONG_OPTION"), Decimal(0))
    # Preserve ranking and never silently borrow from the pool to fund options.
    if option_total > available:
        return {"plans": [], "excluded": excluded, "available": str(available),
                "allocated": "0", "unallocated": str(available),
                "blocked": "One lot per selected option exceeds remaining capital."}
    remaining = available - option_total
    equities = [r for r in selected if r["kind"] == "EQUITY"]
    share = (remaining / len(equities)).quantize(Decimal(".01"),rounding=ROUND_FLOOR) if equities else Decimal(0)
    plans = []
    for row in selected:
        qty = row["lot_size"] if row["kind"] == "LONG_OPTION" else int((share / amount(row["entry"])).to_integral_value(rounding=ROUND_FLOOR))
        if qty < 1:
            excluded.append({"symbol": row["symbol"], "reason": "Equal equity allocation cannot fund one share."})
            continue
        plans.append({**row, "quantity": qty, "lots": 1 if row["kind"] == "LONG_OPTION" else None,
                      "allocation": str(amount(row["entry"]) * qty),
                      "allocation_limit": str(share if row["kind"]=="EQUITY" else amount(row["entry"])*qty),
                      "conviction_out_of_ten": str((Decimal(row["score_fraction"]) * 10).quantize(Decimal(".01")))})
    allocated = sum((Decimal(r["allocation"]) for r in plans), Decimal(0))
    # One-lot quantities stay fixed. Unused whole-share cash can cover a fresh
    # premium quote; cash budgets are recomputed after options are confirmed.
    options=[r for r in plans if r["kind"]=="LONG_OPTION"]
    if options:
        slack=((available-allocated)/len(options)).quantize(Decimal(".01"),rounding=ROUND_FLOOR)
        for option in options:option["allocation_limit"]=str(Decimal(option["allocation"])+slack)
    return {"plans": plans, "excluded": excluded, "available": str(available),
            "allocated": str(allocated), "unallocated": str(available - allocated), "blocked": None}


class Claims:
    """Transactional no-replay claims. Uncertain submissions retain reservations."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS claims(account TEXT, fingerprint TEXT, underlying TEXT, amount TEXT, state TEXT, PRIMARY KEY(account,fingerprint))")
    def db(self):
        return sqlite3.connect(self.path, timeout=15)
    def reserve(self, account, plan, cap=100000):
        if not isinstance(account, str) or not account:
            raise ValueError("Owned broker account required.")
        value = amount(plan.get("allocation_limit",plan["allocation"]))
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM claims WHERE account=? AND fingerprint=?", (account, plan["fingerprint"])).fetchone():
                raise ValueError("Recommendation already claimed; no replay.")
            if db.execute("SELECT 1 FROM claims WHERE account=? AND underlying=? AND state IN (?,?,?)", (account, plan["underlying"], "RESERVED", "UNCERTAIN", "OPEN")).fetchone():
                raise ValueError("Underlying already reserved or uncertain.")
            used = sum((Decimal(r[0]) for r in db.execute("SELECT amount FROM claims WHERE account=? AND state<>?", (account, "CLOSED"))), Decimal(0))
            if used + value > amount(cap):
                raise ValueError("Shared allocation pool exhausted.")
            db.execute("INSERT INTO claims VALUES(?,?,?,?,?)", (account, plan["fingerprint"], plan["underlying"], str(value), "RESERVED"))
    def not_submitted(self, account, fingerprint):
        """Release only a reservation whose submit boundary was never crossed."""
        with self.db() as db:
            row=db.execute("SELECT state FROM claims WHERE account=? AND fingerprint=?",(account,fingerprint)).fetchone()
            if not row or row[0]!="RESERVED":
                raise ValueError("Only an unsubmitted reservation can be released.")
            db.execute("UPDATE claims SET state='CLOSED' WHERE account=? AND fingerprint=? AND state='RESERVED'",(account,fingerprint))
    def confirmed(self, account, fingerprint, notional=None):
        with self.db() as db:
            db.execute("UPDATE claims SET state=? WHERE account=? AND fingerprint=? AND state IN (?,?)", ("OPEN", account, fingerprint, "RESERVED", "UNCERTAIN"))
            if notional is not None:
                db.execute("UPDATE claims SET amount=? WHERE account=? AND fingerprint=? AND state='OPEN'",(str(amount(notional)),account,fingerprint))
    def unsettled(self, account):
        with self.db() as db:
            return bool(db.execute("SELECT 1 FROM claims WHERE account=? AND state IN (?,?) LIMIT 1",(account,"RESERVED","UNCERTAIN")).fetchone())
    def settle_confirmed(self, account, exposed_underlyings):
        with self.db() as db:
            rows=db.execute("SELECT fingerprint,underlying FROM claims WHERE account=? AND state=?", (account,"OPEN")).fetchall()
            for fingerprint,underlying in rows:
                if underlying not in set(exposed_underlyings):
                    db.execute("UPDATE claims SET state=? WHERE account=? AND fingerprint=?", ("CLOSED",account,fingerprint))
    def uncertain(self, account, fingerprint):
        with self.db() as db:
            db.execute("UPDATE claims SET state=? WHERE account=? AND fingerprint=? AND state=?", ("UNCERTAIN", account, fingerprint, "RESERVED"))
