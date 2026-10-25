"""Owned selected Screener -> Handoff evidence. No order methods or authority."""
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import sqlite3,json,hashlib,re,time,fcntl,html
from .market_calendar import IST,market_session
from .persistent_jobs import checkpoint
MAX_SYMBOLS=150
MAX_SOURCES=5

def parse_time(value):
 if not isinstance(value,str):raise ValueError('Source timestamp unavailable.')
 result=datetime.fromisoformat(value.replace('Z','+00:00'))
 if result.tzinfo is None:raise ValueError('Source timestamp requires timezone.')
 return result.astimezone(IST)

def ticker(value):
 value=str(value or "").strip().upper()
 if value.startswith("NSE:") and value.endswith("-EQ"):value=value[4:-3]
 if not re.fullmatch(r"[A-Z0-9][A-Z0-9&_.-]{0,28}",value):raise ValueError("Only exact NSE cash underlyings are supported for this Screener integration.")
 return value

def source_url(value):
 p=urlparse(str(value or "").strip())
 if p.scheme not in {"http","https"} or p.hostname not in {"chartink.com","www.chartink.com"} or p.port or p.username or p.password or p.query or p.fragment or not re.fullmatch(r"/screener/[A-Za-z0-9_-]{1,180}",p.path):raise ValueError("Use an exact Chartink screener URL without query parameters.")
 return "https://chartink.com"+p.path

def owned_folder():
 import os
 aid=os.environ.get("SECTOR_PULSE_WORKSPACE_ID");broker=os.environ.get("SECTOR_PULSE_WORKSPACE_BROKER")
 if not aid:return None
 if broker!="FYERS":return None
 source=Path.cwd().resolve();folder=source.parent
 if source.name!="source" or folder.name!=aid:raise PermissionError("Screener selection must use its owned account source.")
 return folder

def check_permissions(folder):
 folder=Path(folder)
 if folder.parent.name!="accounts":return  # isolated test stores have no registry
 registry=folder.parent.parent/"registry.sqlite3"
 if not registry.exists():raise PermissionError("Owned Screener account registry unavailable.")
 with sqlite3.connect(registry.resolve().as_uri()+"?mode=ro",uri=True) as db:
  row=db.execute("SELECT u.id,u.admin,a.broker FROM accounts a JOIN users u ON a.user_id=u.id WHERE a.id=?",(folder.name,)).fetchone()
  if not row or row[2]!="FYERS":raise PermissionError("Owned FYERS Screener account required.")
  if not row[1]:
   features={r[0] for r in db.execute("SELECT feature FROM user_features WHERE user_id=?",(row[0],))}
   if not {"screener","handoff"}<=features:raise PermissionError("Both Screener and Handoff permissions are required.")

class Store:
 def __init__(self,folder):
  self.folder=Path(folder);self.path=self.folder/"handoff-screener.sqlite3"
  with self.db() as db:db.executescript("""CREATE TABLE IF NOT EXISTS selection(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT);
  CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,body TEXT,updated REAL);
  CREATE TABLE IF NOT EXISTS progress(cycle TEXT PRIMARY KEY,body TEXT,updated REAL);""")
  self.path.chmod(0o600)
 def db(self):return sqlite3.connect(self.path,timeout=20)
 def get(self):
  with self.db() as db:r=db.execute("SELECT body FROM selection WHERE id=1").fetchone()
  return json.loads(r[0]) if r else dict(enabled=False,auto_enabled=False,broker="FYERS",sources=[],symbols=[],revision="NONE")
 def save(self,payload):
  if set(payload)-{"enabled","auto_enabled","sources","symbols","selection_origin"}:raise ValueError("Unsupported Screener selection field.")
  if type(payload.get("enabled")) is not bool or type(payload.get("auto_enabled")) is not bool:raise ValueError("Explicit Handoff analysis and Auto inclusion choices required.")
  symbols=list(dict.fromkeys(ticker(v) for v in payload.get("symbols",[])))
  sources=[]
  for raw in payload.get("sources",[]):
   url=source_url(raw.get("url"));ident=str(raw.get("id") or hashlib.sha256(url.encode()).hexdigest()[:20])
   if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}",ident):raise ValueError("Invalid source identity.")
   label=" ".join(str(raw.get("label") or "Chartink screener").split())[:80]
   members=list(dict.fromkeys(ticker(v) for v in raw.get("symbols",symbols)))
   if set(members)-set(symbols):raise ValueError("A source includes symbols outside the explicitly selected universe.")
   sources.append(dict(id=ident,label=label,url=url,symbols=members))
  if len(sources)>MAX_SOURCES or len({s["id"] for s in sources})!=len(sources):raise ValueError("Choose at most five unique Screener sources.")
  if len(symbols)>MAX_SYMBOLS or payload["enabled"] and (not symbols or not sources):raise ValueError("Choose one to 150 symbols and at least one source.")
  value=dict(enabled=payload["enabled"],auto_enabled=payload["auto_enabled"],broker="FYERS",symbols=symbols,sources=sources,selection_origin=str(payload.get("selection_origin") or "EXPLICIT_USER_SELECTION")[:80])
  value["revision"]=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest();value["updated_at"]=datetime.now(IST).isoformat()
  with self.db() as db:db.execute("INSERT OR REPLACE INTO selection VALUES(1,?)",(json.dumps(value),))
  return value
 def cached(self,key,max_age,clock=time.time):
  with self.db() as db:r=db.execute("SELECT body,updated FROM cache WHERE key=?",(key,)).fetchone()
  return json.loads(r[0]) if r and 0<=clock()-r[1]<=max_age else None
 def retain(self,key,value,clock=time.time):
  with self.db() as db:
   db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)",(key,json.dumps(value,allow_nan=False),clock()))
   db.execute('DELETE FROM cache WHERE updated<?',(clock()-172800,))
 def progress(self,cycle,value,clock=time.time):
  with self.db() as db:
   db.execute("INSERT OR REPLACE INTO progress VALUES(?,?,?)",(cycle,json.dumps(value,allow_nan=False),clock()))
   db.execute('DELETE FROM progress WHERE updated<?',(clock()-604800,))
 def status(self):
  value=self.get()
  with self.db() as db:r=db.execute("SELECT body,updated FROM progress ORDER BY updated DESC LIMIT 1").fetchone()
  return {**value,"latest":dict(json.loads(r[0]),updated=r[1]) if r else None,"order_authority":"EXISTING_HANDOFF_GATES_ONLY"}

def _fetch_source_once(url,session_factory=None):
 """Require executed Chartink rows, never regex symbols in a page definition."""
 import requests
 url=source_url(url);session=(session_factory or requests.Session)()
 page=session.get(url,timeout=20,allow_redirects=False)
 page.raise_for_status()
 if getattr(page,"is_redirect",False):raise ValueError("Screener redirect/access challenge; membership withheld.")
 text=page.text
 if len(text.encode())>1_500_000:raise ValueError("Screener response exceeds bound.")
 if "captcha" in text.lower() or "cloudflare" in text.lower():raise ValueError("Screener requires interactive access; no cached membership used for Live.")
 csrf=re.search(r'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)',text,re.I)
 query=re.search(r'&quot;atlas_query&quot;:&quot;(.*?)&quot;',text,re.I|re.S)
 if not csrf or not query:raise ValueError("Executable source definition unavailable; no page-text symbols accepted.")
 scan=html.unescape(query.group(1)).replace(r"\/","/")
 configured=re.search(r'&quot;column_clause&quot;:&quot;(.*?)&quot;',text,re.I|re.S)
 columns=["close","per_chg","volume","sector","market cap"]
 if configured:columns.extend(v.strip() for v in html.unescape(configured.group(1)).split(",") if v.strip())
 response=session.post("https://chartink.com/screener/process",data=dict(scan_clause=scan,column_clause=",".join(dict.fromkeys(columns))),headers={"X-CSRF-TOKEN":csrf.group(1),"X-Requested-With":"XMLHttpRequest","Referer":url},timeout=30,allow_redirects=False)
 response.raise_for_status();value=response.json();rows=value.get("data");total=value.get("recordsTotal")
 if not isinstance(rows,list) or type(total) is not int or total<0 or total!=len(rows) or total>2000:raise ValueError("Screener returned incomplete or unbounded executed membership.")
 return dict(status="READY",symbols=list(dict.fromkeys(ticker(row.get("nsecode")) for row in rows)),checked_at=datetime.now(IST).isoformat(),executed_membership=True)

def fetch_source(url,session_factory=None):
 for attempt in range(2):
  try:return _fetch_source_once(url,session_factory)
  except ValueError as error:
   if attempt==0 and "incomplete or unbounded" in str(error):continue
   raise

def evidence_current(frames,now):
 from .analysis_config import TIMEFRAMES
 from .market_calendar import trading_elapsed_seconds
 if set(frames)!={"15m","1h","daily","weekly"}:return False
 session=market_session(now)
 for tf,f in frames.items():
  if f.get("state") not in (-2,-1,0,1,2) or isinstance(f.get("state"),bool) or f.get("data_quality") not in {"DELAYED","MARKET CLOSED","READY"}:return False
  try:t=parse_time(f.get("last_updated"))
  except (ValueError,TypeError):return False
  if t>now:return False
  if tf in {"15m","1h"}:
   if session["status"]=="OPEN":
    if t.date()!=now.date() or trading_elapsed_seconds(t,now)>min(TIMEFRAMES[tf]["stale_seconds"],2700 if tf=="15m" else 14400):return False
   else:
    if t.date().isoformat()!=session["last_completed_session"]:return False
    close=parse_time(session['last_completed_session_close'])
    if not 0<=(close-t).total_seconds()<=(2700 if tf=='15m' else 7200):return False
  elif (now-t).total_seconds()>TIMEFRAMES[tf]["stale_seconds"]:return False
 return True

def fresh_saved_evidence(folder,now):
 path=Path(folder)/"source/.private/persistent-jobs.sqlite3"
 if not path.exists():return {}
 result={}
 with sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True) as db:
  records=db.execute("SELECT request,output FROM jobs WHERE feature='screener' AND kind='ANALYSIS' AND status='COMPLETED' ORDER BY updated DESC LIMIT 12").fetchall()
 for request,output in records:
  req=json.loads(request or "{}");value=json.loads(output or "{}")
  if req.get('account_id')!=Path(folder).name or not isinstance((req.get('payload') or {}).get('symbols'),list):continue
  for row in value.get('results',[]):
   frames=row.get('timeframe_states') or {}
   if evidence_current(frames,now):
    try:x=ticker(row.get('symbol'))
    except ValueError:continue
    result.setdefault(x,frames)
 return result

def merge(collection,sectors,folder=None,*,auto=False,now=None,fetcher=fetch_source,master=None):
 """Fresh complete selected universe; persistent per-bar evidence resumes safely."""
 from .analysis import calculate_timeframe_state,mtf_alignment
 from .analysis_config import TIMEFRAMES
 from .sectors import BENCHMARK_SYMBOL
 from .handoff import build_equity_opportunity,evidence_conviction,FyersCmMaster
 now=now or datetime.now(IST);folder=Path(folder) if folder else owned_folder()
 result={**collection,"scope":dict(collection.get("scope") or {})};base=[dict(x) for x in collection.get("candidates",[]) if x.get("kind")=="stock"]
 for row in base:row["provenance"]=[dict(kind="SECTOR",label=row.get("parent_sector") or "Sector rotation")]
 if folder is None:
  result["candidates"]=base;return result
 check_permissions(folder)
 store=Store(folder);selection=store.get();scope=dict(enabled=selection["enabled"],auto_enabled=selection["auto_enabled"],selected=len(selection["symbols"]),selection_revision=selection["revision"],sources=[],analyzed=0,matched=0,exclusions=[],status="DISABLED")
 result["scope"]["screener"]=scope
 if not selection["enabled"] or auto and not selection["auto_enabled"]:
  result["candidates"]=base;return result
 scope['status']='RUNNING'
 cycle=selection["revision"]+":"+now.date().isoformat()+":"+(str((now.hour*60+now.minute)//15) if market_session(now)["status"]=="OPEN" else "CLOSED:"+market_session(now)["last_completed_session"])+":"+str(result.get("mode") or "intraday")
 complete=store.cached("collection:"+cycle,900)
 if complete:
  scope.update(complete["scope"]);screened=complete["candidates"]
 else:
  lock=(folder/"handoff-screener-analysis.lock").open("a")
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:
   lock.close()
   scope.update(status="RUNNING",reason="A fresh owned Screener scan is already running; incomplete combined ranking cannot execute.");result["candidates"]=base;return result
  screened=[];membership={};failures=[]
  for source in selection["sources"]:
   key="source:"+selection["revision"]+":"+source["id"]+":"+now.date().isoformat()
   current=store.cached(key,300)
   try:
    if current is None:current=fetcher(source["url"]);store.retain(key,current)
    if current.get("status")!="READY" or current.get("executed_membership") is not True:raise ValueError("Executed source membership unavailable.")
    selected=set(source["symbols"]);members=[x for x in current["symbols"] if x in selected]
    scope["sources"].append(dict(id=source["id"],label=source["label"],checked_at=current["checked_at"],current_members=len(current["symbols"]),selected_members=len(members),status="READY"))
    for x in members:membership.setdefault(x,[]).append(dict(kind="SCREENER",source_id=source["id"],label=source["label"],url=source["url"],membership_checked_at=current["checked_at"]))
   except Exception as error:
    failures.append(dict(source_id=source["id"],label=source["label"],reason=str(error) if isinstance(error,ValueError) else "Source refresh unavailable; no stale replay."))
  scope["source_failures"]=failures
  if failures:
   scope.update(status="UNAVAILABLE");store.progress(cycle,scope);lock.close();result["candidates"]=base;return result
  scope["current_selected"]=len(membership)
  store.progress(cycle,scope)
  try:
   symbols=["NSE:"+x+"-EQ" for x in membership]
   lookup=(master or FyersCmMaster()).lookup(symbols) if symbols else {}
   imported=fresh_saved_evidence(folder,now);scope['fresh_saved_evidence_reused']=0
   benchmark=sectors._timeframe_candles(BENCHMARK_SYMBOL) if symbols and len(imported)<len(symbols) else {}
   for rank,(x,provenance) in enumerate(membership.items(),1):
    checkpoint(f"Screener evidence {rank}/{len(membership)}: {x}.")
    symbol="NSE:"+x+"-EQ";cache_key="frames:"+cycle+":"+symbol
    frames=store.cached(cache_key,900 if market_session(now)["status"]=="OPEN" else 86400)
    if frames is None and x in imported:frames=imported[x];scope['fresh_saved_evidence_reused']+=1
    if symbol not in lookup:
     scope["exclusions"].append(dict(symbol=symbol,reason="Exact NSE cash master mapping unavailable."));continue
    if frames is None or not evidence_current(frames,now):
     candles=sectors._timeframe_candles(symbol)
     frames={tf:calculate_timeframe_state(tf,candles.get(tf,[]),benchmark.get(tf,[]),sectors._quality(tf,candles.get(tf,[]))) for tf in TIMEFRAMES}
     frames={tf:{k:v for k,v in f.items() if k!="series"} for tf,f in frames.items()};store.retain(cache_key,frames)
    scope["analyzed"]+=1
    if not evidence_current(frames,now):
     scope["exclusions"].append(dict(symbol=symbol,reason="Completed broker timeframe evidence stale, missing or unavailable."));store.progress(cycle,scope);continue
    alignment=mtf_alignment(frames)
    if alignment not in {"FULL BULLISH ALIGNMENT","FULL BEARISH ALIGNMENT"}:
     scope["exclusions"].append(dict(symbol=symbol,reason="Screener stock does not have full completed four-timeframe alignment.",alignment=alignment));store.progress(cycle,scope);continue
    candidate=dict(screener_selection_revision=selection["revision"],key="stock:"+x,kind="stock",ticker=x,name=x,symbol=symbol,parent_sector="Screener selection",direction="BULLISH" if "BULLISH" in alignment else "BEARISH",mtf_alignment=alignment,data_quality="MARKET CLOSED" if market_session(now)["status"]!="OPEN" else "DELAYED",price=frames["15m"].get("close"),timeframe_states=frames,provenance=provenance,source_rank=rank)
    plan=build_equity_opportunity(candidate,{"minimum_reward_to_risk":1});candidate["screening_conviction"]=evidence_conviction(candidate,plan)
    screened.append(candidate);scope["matched"]=len(screened);store.progress(cycle,scope)
   scope.update(status="COMPLETED",matched=len(screened));store.retain("collection:"+cycle,dict(scope=scope,candidates=screened));store.progress(cycle,scope)
  except Exception:
   scope.update(status="INCOMPLETE");store.progress(cycle,scope);raise
  finally:lock.close()
 merged={row["symbol"]:row for row in base};duplicates=0
 for row in screened:
  if row["symbol"] in merged:
   old=merged[row["symbol"]]
   if old["direction"]!=row["direction"]:
    scope["exclusions"].append(dict(symbol=row["symbol"],reason="Sector and Screener directions conflict; withheld."));merged.pop(row["symbol"]);continue
   old["provenance"]+=row["provenance"];old["source_rank"]=row.get("source_rank");old["screener_selection_revision"]=selection["revision"];duplicates+=1
  else:merged[row["symbol"]]=row
 for row in merged.values():row["source_summary"]=" + ".join(dict.fromkeys(x["label"] for x in row["provenance"]))
 scope["duplicates_merged"]=duplicates;store.progress(cycle,scope);result["candidates"]=list(merged.values());result["scope"]["merged_underlyings"]=len(merged)
 return result


def guard_entry_source(candidate,folder,now=None):
 """Final Auto preflight rechecks only explicitly selected source memberships."""
 now=now or datetime.now(IST)
 provenance=[x for x in candidate.get("provenance",[]) if x.get("kind")=="SCREENER"]
 if not provenance:return
 check_permissions(folder)
 store=Store(folder);selection=store.get()
 if not selection["enabled"] or not selection["auto_enabled"] or candidate.get("screener_selection_revision")!=selection["revision"]:raise ValueError("Screener selection changed or Auto inclusion was removed; fresh analysis required.")
 x=ticker(candidate.get("symbol"))
 if x not in selection["symbols"]:raise ValueError("Underlying is no longer explicitly selected for Screener Handoff.")
 if market_session(now)["status"]!="OPEN":raise ValueError("Screener Auto entries require the live NSE session.")
 accepted=False
 for source in selection["sources"]:
  if source["id"] not in {p.get("source_id") for p in provenance}:continue
  key="source:"+selection["revision"]+":"+source["id"]+":"+now.date().isoformat();current=store.cached(key,300)
  if current is None:current=fetch_source(source["url"]);store.retain(key,current)
  if current.get("status")!="READY" or current.get("executed_membership") is not True:raise ValueError("Fresh Screener membership unavailable before entry.")
  accepted=accepted or x in current["symbols"] and x in source["symbols"]
 if not accepted:raise ValueError("Underlying left the selected Screener source; entry withheld.")

def guard_separate_submission(underlyings):
 """One execution owner: selected Auto names cannot also use manual batch flow."""
 folder=owned_folder()
 if folder is None:return
 selection=Store(folder).get()
 if not selection["enabled"] or not selection["auto_enabled"]:return
 path=folder/"handoff-schedule.sqlite3"
 if not path.exists():return
 with sqlite3.connect(path) as db:r=db.execute("SELECT body FROM policy WHERE id=1").fetchone()
 policy=json.loads(r[0]) if r else {}
 if policy.get("enabled") is not True or policy.get("mode")!="AUTO" or policy.get("live_authorized") is not True:return
 overlap={ticker(x) for x in underlyings}&set(selection["symbols"])
 if overlap:raise ValueError("These selected Screener underlyings are owned by Handoff Auto: "+", ".join(sorted(overlap))+". Remove them from Auto selection or switch Handoff to Manual before a separate submission.")
