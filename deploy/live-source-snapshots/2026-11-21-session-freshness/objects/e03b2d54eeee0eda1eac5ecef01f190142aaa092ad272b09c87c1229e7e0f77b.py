"""Account/broker-local chart recurrence. Never calls a runner or order API."""
from copy import deepcopy
import hashlib
import json
import threading
import time
from .price_basis import observe

class LiveChart:
    def __init__(self, broker):
        self.broker=broker
        self.lock=threading.RLock()
        self.entries={}
        self.sequence=0
        self.generation=0
        previous=getattr(broker,"on_tick",None)
        def accepted(raw):
            with self.lock:
                self.sequence+=1
                self.accept({**raw,"observation_sequence":self.sequence},raw.get("received_at",time.time()))
            if previous:previous(raw)
        broker.on_tick=accepted

    def seed(self,key,engine,config,tick_size,replace=False):
        if config.get("strategy_basis")!="RENKO":return
        with self.lock:
            if key in self.entries and not replace:
                self.entries[key]["config"]={**deepcopy(config),"_run_id":key,"_stream_session":"chart"}
                return
            export=deepcopy(engine)
            last=next((b for row in reversed(export["rows"]) for b in reversed(row.get("brick_events",[]))),None)
            if not last:return
            box=last["box"]
            export["state"]["price_renko"]=dict(run_id=key,stream_session="chart",level=last["close"]/box,
                direction=1 if last["close"]>last["open"] else -1,last_exchange_at=export["last"]["timestamp"])
            display_rows=export["rows"]
            export["rows"]=display_rows[-500:]
            self.generation+=1
            self.entries[key]=dict(generation=self.generation,engine=export,config={**deepcopy(config),"_run_id":key,"_stream_session":"chart"},tick=tick_size,rows=display_rows,version=0)
            for old in list(self.entries)[:-4]:self.entries.pop(old,None)

    def accept(self,raw,received):
        with self.lock:
            for key,item in self.entries.items():
                if raw.get("symbol")!=item["config"]["underlying"]:continue
                rows=observe(item["engine"],item["config"],item["tick"],raw,received,0)
                if rows:
                    item["rows"]=(item["rows"]+rows)[-5000:]
                    item["version"]+=len(rows)

    def poll(self,config):
        # REST-only brokers supply accepted observations here. WebSocket brokers
        # already deliver every accepted observation through on_tick.
        if hasattr(self.broker,"tick"):return
        try:
            price,stamp=self.broker.live_price(config,time.time())
            self.accept(dict(symbol=config["underlying"],ltp=price,exch_feed_time=stamp),time.time())
        except (ValueError,RuntimeError):pass

    def revision(self,key):
        """Read display identity without copying its historical payload."""
        with self.lock:
            item=self.entries.get(key)
            return key+":"+str(item["generation"])+":"+str(item["version"]) if item else None

    def apply(self,key,response=None,revision=None):
        with self.lock:
            item=self.entries.get(key)
            if not item:return response
            current=key+":"+str(item["generation"])+":"+str(item["version"])
            if revision==current:return None
            if response is not None:
                if "response" not in item:
                    historical=[r for r in response["rows"] if r.get("confirmation_basis")!="ORDERED_LIVE_PRICE"]
                    live=[r for r in item["rows"] if r.get("confirmation_basis")=="ORDERED_LIVE_PRICE"]
                    item["rows"]=(deepcopy(historical)+live)[-5000:]
                item["response"]=deepcopy(response)
            if "response" not in item:return None
            incremental=False
            outgoing=item["rows"]
            prefix=key+":"+str(item["generation"])+":"
            if response is None and isinstance(revision,str) and revision.startswith(prefix):
                try:delta=item["version"]-int(revision[len(prefix):])
                except ValueError:delta=0
                if 0<delta<=len(item["rows"]):
                    outgoing=item["rows"][-delta:]
                    incremental=True
            result=deepcopy(item["response"])
            result.update(rows=deepcopy(outgoing),latest=deepcopy(item["engine"]["last"]),incremental=incremental,
                          live_price_confirmed=True,live_chart_revision=current)
            result["history"].update(analysis_revision=hashlib.sha256(result["live_chart_revision"].encode()).hexdigest(),
                display_latest=result["rows"][-1]["timestamp"],display_count=len(item["rows"]),
                intrabar_history="Full bricks confirm on accepted live prices; only the unfinished remainder is provisional.")
            return result

_creation_lock=threading.Lock()

def chart_for(broker):
    # Constructed during chart setup before subscription; owned by this adapter,
    # never a process-global symbol cache.
    with _creation_lock:
        if not hasattr(broker,"_live_renko_chart"):broker._live_renko_chart=LiveChart(broker)
        return broker._live_renko_chart
