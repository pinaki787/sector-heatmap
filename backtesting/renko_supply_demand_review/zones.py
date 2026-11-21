"""Use production strong-five-minute zones, with strictly causal timeline."""
from strategies.renko_supertrend import zone_target
def contexts(hosts):
 timeline=[];zone_target.zones(hosts,timeline);out={}
 for i,c in enumerate(hosts):
  out[c["timestamp"]]=dict(before=timeline[i-1] if i else dict(supply=None,demand=None),after=timeline[i],previous=hosts[i-1] if i else None)
 return out
def entry_distance(known,direction,price,atr):
 side="supply" if direction=="BULLISH" else "demand";z=known.get(side)
 if not z or z.get("broken_at") is not None:return dict(state="NO_ACTIVE_OPPOSING_ZONE",distance_atr=None,zone=None)
 if (direction=="BULLISH" and price>z["upper"]) or (direction=="BEARISH" and price<z["lower"]):
  return dict(state="ZONE_BEHIND_ENTRY",distance_atr=None,zone=z)
 gap=max(0.,z["lower"]-price if direction=="BULLISH" else price-z["upper"])
 if atr is None or atr<=0:return dict(state="ATR_UNAVAILABLE",distance_atr=None,zone=z)
 return dict(state="INSIDE" if gap==0 else "AHEAD",distance_atr=gap/atr,zone=z)
def allowed(known,direction,price,atr,minimum):
 d=entry_distance(known,direction,price,atr)
 if d["state"]=="ATR_UNAVAILABLE":return False
 if d["distance_atr"] is None:return True
 return d["distance_atr"]>=minimum
