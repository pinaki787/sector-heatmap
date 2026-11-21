"""Isolated public WebSocket ingestion sample; no credentials, runners or orders."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util,json,time,threading,ssl,hashlib
import websocket,certifi
root=Path.cwd();out=root/".private/chart-order-rollouts/delta-chart-channel-order-20261119"
source=root/".private/dashboard-login/accounts/a6ef4c9bcecd21d54c4a07e2b9b137a7/source/strategies/renko_supertrend/delta_broker.py"
spec=importlib.util.spec_from_file_location("strategies.renko_supertrend.channel_probe_owner",source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
b=module.Broker.__new__(module.Broker);b.delta=SimpleNamespace(clock=time.time);b.lock=threading.RLock()
b.symbols={"PAXGUSD"};b.candle_resolutions={60:"1m",300:"5m",1800:"30m"}
b.ticks={};b.quotes={};b.forming_bars={};callbacks=[];b.on_tick=lambda raw:callbacks.append(raw["exch_feed_time"])
report={"scope":"Isolated current-owner ingest method on public PAXGUSD1m/5m/30m frames; not hosted activation","orders_submitted":0,"runners_started":0,"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"events":[]}
start=time.monotonic();sock=None
try:
 sock=websocket.create_connection("wss://public-socket.india.delta.exchange",timeout=5,sslopt={"cert_reqs":ssl.CERT_REQUIRED,"ca_certs":certifi.where()})
 sock.send(json.dumps({"type":"subscribe","payload":{"channels":[{"name":"candlestick_"+r,"symbols":["PAXGUSD"]}for r in b.candle_resolutions.values()]}}))
 print("Public socket subscribed; isolated ingest only.",flush=True)
 while time.monotonic()-start<65:
  try:message=json.loads(sock.recv())
  except websocket.WebSocketTimeoutException:continue
  received=time.time();kind=message.get("type","")
  if not str(kind).startswith("candlestick_"):continue
  before={key:row["stream_exchange_at"]for key,row in b.forming_bars.items()}
  b.ingest(message,received)
  changed=any(before.get(key)!=row["stream_exchange_at"]for key,row in b.forming_bars.items())
  stamp=float(message.get("ts",0))/1e6
  report["events"].append({"channel":kind,"age_seconds":round(received-stamp,4),"changed_frame":changed})
 report["callback_timestamps_monotonic"]=all(a<=z for a,z in zip(callbacks,callbacks[1:]))
 assert report["callback_timestamps_monotonic"]
 report["retained_frames"]=[{"seconds":seconds,"opening":opening,"exchange_at":row["stream_exchange_at"]}for(_,seconds,opening),row in b.forming_bars.items()]
 report["status"]="PASS_SAMPLE"if{60,300,1800}<={x["seconds"]for x in report["retained_frames"]}else"PARTIAL_SAMPLE"
except Exception as error:report.update(status="UNVERIFIED",error_type=type(error).__name__)
finally:
 if sock:sock.close()
 report["elapsed_seconds"]=round(time.monotonic()-start,2)
 (out/"current-owner-live-sample.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps({k:v for k,v in report.items()if k!="events"}),flush=True)
