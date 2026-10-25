"""Read-only Handoff fill journal and private position snapshots."""
from datetime import datetime
import hashlib,json,math,time
from pathlib import Path
import sqlite3
from .config import _atomic_private_write
from .market_calendar import IST

def positive(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0

class Observer:
    def __init__(self,folder,account,clock=time.time):
        self.folder,self.account,self.clock=Path(folder),account,clock
        self.path=self.folder/"source/.private/handoff-observer-state.json"
    def update(self,state):
        if state.get("positions_verified") is not True or state.get("orders_verified") is not True:
            raise ValueError("Fresh owned broker evidence is required for personal updates.")
        existed=self.path.exists()
        data=json.loads(self.path.read_text()) if existed else dict(order_history=[],position_summaries=[],last_positions=[])
        rows={r["tag"]:r for r in data.get("order_history",[])}
        schedule=self.folder/"handoff-schedule.sqlite3"
        with sqlite3.connect(schedule.as_uri()+"?mode=ro",uri=True) as db:
            receipts=[json.loads(r[0]) for r in db.execute("SELECT body FROM receipts")]
        fills=state.get("filled_orders",[])
        for receipt in receipts:
            plan=receipt["plan"];result=receipt.get("result") or {}
            entry_ids=set(map(str,result.get("order_ids",[])))
            for fill in fills:
                ident=str(fill["id"]);parent=str(fill.get("parent_id") or "")
                entry=ident in entry_ids and fill.get("leg_name") not in {"TARGET_LEG","STOP_LOSS_LEG"}
                exit_=(parent in entry_ids or (bool(result.get("preview_id")) and fill.get("correlation_id")==result.get("preview_id") and fill.get("leg_name") in {"TARGET_LEG","STOP_LOSS_LEG"}))
                if not entry and not exit_:continue
                symbol_matches=fill.get("symbol")==plan["symbol"]
                native_matches=(bool(plan.get("security_id")) and str(fill.get("security_id"))==str(plan["security_id"])
                    and fill.get("exchange_segment")==plan.get("exchange_segment"))
                if not symbol_matches and not native_matches:continue
                expected="BUY" if plan["kind"]=="LONG_OPTION" or plan["direction"]=="BULLISH" else "SELL"
                if not entry:expected="SELL" if expected=="BUY" else "BUY"
                if fill.get("side")!=expected or not positive(fill.get("filled")) or not positive(fill.get("price")):continue
                if fill["filled"]>plan["quantity"]:continue
                tag="handoff:"+ident+":"+("entry" if entry else "exit")
                old=rows.get(tag)
                if old and fill["filled"]<=old["filled"]:continue
                rows[tag]=dict(tag=tag,mode="LIVE",symbol=plan["symbol"],strategy="Analysis Handoff",
                    lifecycle_id=plan["fingerprint"],entry_side=1 if plan["kind"]=="LONG_OPTION" or plan["direction"]=="BULLISH" else -1,
                    is_entry=entry,side=expected,filled=fill["filled"],requested=fill.get("requested") or plan["quantity"],
                    average_price=fill["price"],filled_at=self.clock() if existed else 0,
                    reason=None if entry else "Broker-confirmed linked exit fill",
                    quote_currency="INR",quantity_multiplier=1)
        data["order_history"]=list(rows.values())[-1000:]
        positions=state.get("positions",[])
        previous=data.get("last_positions",[])
        stamp=datetime.fromtimestamp(self.clock(),IST)
        slot=stamp.replace(minute=stamp.minute//15*15,second=0,microsecond=0).isoformat()
        if positions or previous:
            summaries=data.setdefault("position_summaries",[])
            if not any(r["slot"]==slot for r in summaries):
                summaries.append(dict(slot=slot,time=self.clock(),positions=positions,daily_pnl=state.get("daily_pnl"),verified=True))
                data["position_summaries"]=summaries[-64:]
        data["last_positions"]=positions
        data["observed_at"]=self.clock()
        _atomic_private_write(self.path,json.dumps(data,allow_nan=False))
        return dict(confirmed_rows=len(rows),position_count=len(positions))
