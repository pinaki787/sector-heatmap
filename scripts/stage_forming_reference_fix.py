"""Stage a guarded forming-reference patch and rebase pending frontend candidates."""
from pathlib import Path
import json,hashlib,subprocess
base=Path("chart-workspace.js").read_text()
candidate=Path("/tmp/chart-workspace-forming-reference-candidate.js").read_text()
needle="  async function refreshAlternateStudyBars(request, hostInterval, scope) {"
helpers=candidate[candidate.index("  function alternateStudyCandleEnd("):candidate.index(needle)]
a="""}) : requestChartHistory('/api/chart-workspace/' + endpoint + '?' + query, scope).then(data =>
      data.rows.map(([time, open, high, low, close, volume]) => ({time, open, high, low, close, volume})));"""
b="""}) : requestChartHistory('/api/chart-workspace/' + endpoint + '?' + query, scope).then(data => {
      state.calendarPrefix = data.prefix ?? null;
      state.intradayPrefix = data.native_seconds ? data : null;
      state.fyersSeed = data.fyers_forming_seed ?? null;
      state.regularSession = data.regular_session;
      return data.rows.map(([time, open, high, low, close, volume]) => ({time, open, high, low, close, volume}));
    });"""
old_start=base.index("        const now = Date.now() / 1000;",base.index(needle))
old_end=base.index("        state.live = candle;",old_start)
old_live=base[old_start:old_end]
changes=[(needle,helpers+needle),(a,b),
("const confirmed = candles.filter(bar => candleEnd(bar.time, sourceInterval) <= Date.now() / 1000);","const confirmed = candles.filter(bar => alternateStudyCandleEnd(bar.time, sourceInterval, state) <= Date.now() / 1000);"),
(old_live,"        const candle = alternateStudyLiveCandle(interval, frame, state, Date.now() / 1000);\n        if (state.live === candle || (state.live && candle && sameCandle(state.live, candle))) return;\n")]
def transform(text):
 for old,new in changes:
  assert text.count(old)==1,old[:100]
  text=text.replace(old,new)
 return text
assert transform(base)==candidate
r=Path(".private/chart-order-rollouts/forming-reference-live-20261119");r.mkdir(exist_ok=True)
paths=[p for p in [Path("chart-workspace.js"),*Path(".private/dashboard-login/accounts").glob("*/source/chart-workspace.js")] if "const pineTableExpanded" in p.read_text()]
entries=[]
for i,p in enumerate(paths):
 old=p.read_bytes();new=transform(old.decode()).encode();dest=r/f"active-{i}.js";dest.write_bytes(new);(r/f"original-{i}.js").write_bytes(old)
 entries.append(dict(path=str(p),original_sha256=hashlib.sha256(old).hexdigest(),candidate=str(dest),candidate_sha256=hashlib.sha256(new).hexdigest()))
originals=[Path(".private/chart-order-rollouts/chart-catalog-route-3byfgtsu/manifest.json"),Path(".private/chart-order-rollouts/yahoo-calendar-snapshot-u14i2s78/manifest.json")]
manifests=[Path(json.loads(p.read_text()).get("newer_frontend_rebase_manifest",str(p))) for p in originals]
sha_map={e["original_sha256"]:e["candidate_sha256"] for e in entries};candidate_map={}
for mf in manifests:
 def collect(v):
  if isinstance(v,dict):
   if "candidate" in v and "candidate_sha256" in v:
    p=Path(v["candidate"]);data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==v["candidate_sha256"]
    new=transform(data.decode()).encode();sha=hashlib.sha256(new).hexdigest();dest=r/("pending-"+sha+".js");dest.write_bytes(new);candidate_map[str(p)]=(str(dest),sha);sha_map[v["candidate_sha256"]]=sha
   for child in v.values():collect(child)
  elif isinstance(v,list):
   for child in v:collect(child)
 collect(json.loads(mf.read_text()))
for i,mf in enumerate(manifests):
 m=json.loads(mf.read_text())
 def rewrite(v):
  if isinstance(v,dict):
   if "candidate" in v and "candidate_sha256" in v:v["candidate"],v["candidate_sha256"]=candidate_map[v["candidate"]]
   if "original_sha256" in v and v.get("path") in [e["path"] for e in entries]:v["original_sha256"]=sha_map.get(v["original_sha256"],v["original_sha256"])
   if "base_sha256" in v:v["base_sha256"]=sha_map.get(v["base_sha256"],v["base_sha256"])
   for child in v.values():rewrite(child)
  elif isinstance(v,list):
   for child in v:rewrite(child)
 rewrite(m);m["frontend_version"]=1944+i;m["rebase_reason"]="Preserve forming reference OHLC and freshness guards"
 out=r/("catalog-rebased.json" if i==0 else "yahoo-rebased.json");m.pop("newer_frontend_rebase_manifest",None);out.write_text(json.dumps(m,indent=2)+"\n")
 for target in {mf,originals[i]}:
  old=json.loads(target.read_text());old["newer_frontend_rebase_manifest"]=str(out);target.write_text(json.dumps(old,indent=2)+"\n")
for path in {e["candidate"] for e in entries}|{p for p,sha in candidate_map.values()}:subprocess.run(["node","--check",path],check=True)
(r/"manifest.json").write_text(json.dumps(dict(status="STAGED",frontend_version=1943,frontend=entries,pending_rebase_manifests=[str(r/"catalog-rebased.json"),str(r/"yahoo-rebased.json")]),indent=2)+"\n")
print("Staged",len(entries),"active assets and",len(candidate_map),"pending variants")
