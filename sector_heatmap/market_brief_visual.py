"""Public market-only executive brief. Strict projections; never render raw reports."""
import math,re
from datetime import datetime
from .sector_cards import parse_time
from .sectors import SECTOR_DEFINITIONS

REVISION="executive-rotation-mtf-v2"
def numeric(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def positive(v):return round(v,2) if numeric(v) and v>0 else None
def metric(v):return f"{v:,.2f}" if numeric(v) else "N/A"
def date(v):
 try:return parse_time(v).strftime("%d %b %H:%M IST")
 except (ValueError,TypeError):return "Unavailable"
def status_label(v):
 return {"REQUIRES_INVALIDATION_ACCEPTANCE":"Proposed stop needs review","REVIEW_REQUIRED":"Review required","NO_TRADE":"No trade","ANALYSIS_ONLY":"Analysis only","QUALIFIED":"Qualified for review","READY":"Ready for review","WAIT":"Wait"}.get(v,"Review required")
def symbol(v):
 v=str(v or "").upper()
 return v if re.fullmatch(r"[A-Z0-9:&_.-]{1,38}",v) else "Instrument unavailable"
def quality(rows,now):
 from .combined_reports import freshness
 stamps=[(r.get("timeframe_states") or {}).get("15m",{}).get("last_updated") for r in rows]
 stamps=[v for v in stamps if v]
 asof=min(stamps,key=parse_time) if stamps else None
 states={str(v.get("data_quality","")).upper() for r in rows for v in (r.get("timeframe_states") or {}).values()}
 status=freshness(asof,now)
 if "DELAYED" in states:status="BROKER DELAYED / "+status
 if states & {"STALE","UNAVAILABLE","INSUFFICIENT DATA"}:status="INCOMPLETE / "+status
 if "MARKET CLOSED" in states:status="MARKET CLOSED / "+status
 return status,asof


TF_ORDER=("15m","1h","daily","weekly")
ALIGNMENTS={"FULL BULLISH ALIGNMENT","FULL BEARISH ALIGNMENT","BULLISH ALIGNMENT","BEARISH ALIGNMENT","MIXED","UNAVAILABLE"}
def sector_mtf_public(value,now):
 from .analysis import mtf_alignment,STATE_LABELS
 from .market_calendar import market_session,trading_elapsed_seconds
 from .analysis_config import TIMEFRAMES
 expected=market_session(now).get("last_completed_session")
 collector_old=False
 if market_session(now)["status"]=="OPEN":
  try:collector_old=not 0<=(now-parse_time(value.get("generated_at"))).total_seconds()<=1800
  except (ValueError,TypeError):collector_old=True
 result={}
 for sector in value.get("sectors",[]):
  frames={};issues=[]
  for tf in TF_ORDER:
   f=(sector.get("timeframe_states") or {}).get(tf) or {};state=f.get("state")
   state=state if isinstance(state,int) and not isinstance(state,bool) and state in STATE_LABELS else None
   quality=f.get("data_quality");quality=quality if quality in {"DELAYED","MARKET CLOSED","STALE","UNAVAILABLE","INSUFFICIENT DATA"} else "UNAVAILABLE"
   asof=f.get("last_updated");valid_time=True
   try:
    t=parse_time(asof);valid_time=t<=now
    # Use dashboard quality and stale thresholds; closed-session intraday bars
    # must belong to the last completed session. Do not age weekly bars as 15m.
    if tf in {"15m","1h"}:
     if market_session(now)["status"]!="OPEN":valid_time=valid_time and t.date().isoformat()==expected
     else:valid_time=valid_time and t.date()==now.date() and trading_elapsed_seconds(t,now)<=TIMEFRAMES[tf]["stale_seconds"]
    else:valid_time=valid_time and (now-t).total_seconds()<=TIMEFRAMES[tf]["stale_seconds"]
   except (ValueError,TypeError):valid_time=False;asof=None
   if (not valid_time or collector_old) and state is not None:quality="STALE"
   if state is None:issues.append(tf+" missing")
   elif quality in {"STALE","UNAVAILABLE","INSUFFICIENT DATA"}:issues.append(tf+" "+quality.lower())
   frames[tf]=dict(state=state,label=STATE_LABELS.get(state,"Unavailable"),data_quality=quality,asof=asof)
  alignment=mtf_alignment(frames)
  recorded=sector.get("mtf_alignment")
  if recorded in ALIGNMENTS and recorded!=alignment:issues.append("label mismatch")
  result[sector.get("sector_id")]=dict(alignment=alignment,frames=frames,evidence="INCOMPLETE" if any(f["state"] is None for f in frames.values()) else "STALE / UNAVAILABLE" if issues else "BROKER DELAYED" if any(f["data_quality"]=="DELAYED" for f in frames.values()) else "LAST COMPLETED SESSION",issues=issues)
 return result

def sector_public(snap,history,mtf=None,now=None):
 rows=[];defs={d.sector_id:d.name for d in SECTOR_DEFINITIONS};mtf_rows=sector_mtf_public(mtf or {},now) if now else {}
 for row in snap.get("rows",[]):
  sid=row.get("sector_id")
  if sid not in defs:continue
  score=row.get("score");score=score if numeric(score) and 0<=score<=100 else None
  series=history.get("modes",{}).get("intraday",{}).get(sid,[])
  previous=None
  for old in reversed(series):
   try:
    gap=(parse_time(row.get("asof"))-parse_time(old.get("last_updated"))).total_seconds()
    if 0<gap<=2700 and parse_time(row["asof"]).date()==parse_time(old["last_updated"]).date() and numeric(old.get("overall_score")):
     previous=old;break
   except (ValueError,TypeError):continue
  rotation=row.get("rotation")
  if rotation not in {"LEADING","IMPROVING","WEAKENING","LAGGING","NEUTRAL"}:rotation="UNAVAILABLE"
  rows.append(dict(name=defs[sid],score=score,rotation=rotation,delta=round(score-previous["overall_score"],2) if score is not None and previous else None,prior_asof=previous.get("last_updated") if previous else None,mtf=mtf_rows.get(sid) or dict(alignment="UNAVAILABLE",frames={},evidence="INCOMPLETE",issues=["Timeframe detail not captured"]),recorded_alignment=(series[-1].get("mtf_alignment") if series else None)))
 rows.sort(key=lambda x:-(x["score"] if x["score"] is not None else -1))
 known=[x for x in rows if x["score"] is not None];strong=sum(x["score"]>=55 for x in known);weak=sum(x["score"]<45 for x in known)
 regime="Broad strength" if known and strong/len(known)>=.6 else "Defensive tilt" if known and weak/len(known)>=.6 else "Mixed leadership" if known else "Evidence unavailable"
 asofs={}
 for tf in TF_ORDER:
  values=sorted({m["frames"][tf]["asof"] for m in mtf_rows.values() if m["frames"][tf]["asof"]})
  asofs[tf]=values[0] if len(values)==1 else "MIXED" if values else None
 return dict(mtf_asofs=asofs,mtf_checked=(mtf or {}).get("generated_at"),rows=rows,status=snap.get("freshness","UNAVAILABLE"),asof=snap.get("asof"),regime=regime,known=len(known),total=len(defs),strong=strong,weak=weak)

def handoff_public(report,now):
 cards=report.get("cards") or [];candidates=[c.get("candidate") or {} for c in cards]
 status,asof=quality(candidates,now)
 rows=[]
 for card in cards:
  a=card.get("analysis") or {};c=card.get("candidate") or {};conv=a.get("conviction") or {};score=conv.get("score");maximum=conv.get("maximum_score")
  rating=round(score/maximum*10,2) if numeric(score) and numeric(maximum) and maximum>0 and 0<=score<=maximum else None
  direction=a.get("direction") or c.get("direction");direction=direction if direction in {"BULLISH","BEARISH"} else "UNAVAILABLE"
  levels=a.get("report_levels") or {};horizons=[]
  for horizon in ("intraday","swing"):
   h=(levels.get("horizons") or {}).get(horizon) or {};u=h.get("underlying") or {};prem=h.get("premium") or {}
   horizons.append(dict(name=horizon,underlying={k:positive(u.get(k)) for k in ("entry","stop_loss","target")},premium={k:positive(prem.get(k)) for k in ("entry","stop_loss","target")} if a.get("kind")=="LONG_OPTION" else None))
  # Legacy snapshots retain exact labels, with no invented horizon calculation.
  if not any(h["underlying"]["entry"] for h in horizons):
   active=a.get("active_invalidation") or {};proposed=a.get("proposed_sizing") or {};recommended=a.get("recommended_invalidation") or {};proposal=a.get("proposal") or {}
   horizons=[dict(name="shared plan",underlying=dict(entry=positive(active.get("entry") or proposed.get("entry") or a.get("entry")),stop_loss=positive(active.get("price") or proposed.get("price") or recommended.get("price")),target=positive(active.get("target") or proposed.get("target") or a.get("target"))),premium=dict(entry=positive(proposal.get("entry_points")),stop_loss=positive((proposal.get("premium_stop_estimate") or {}).get("stop_loss_price")),target=positive(proposal.get("target_exit_points"))) if a.get("kind")=="LONG_OPTION" else None)]
  state=a.get("status");state=state if state in {"READY","WAIT","NO_TRADE","REQUIRES_INVALIDATION_ACCEPTANCE","ANALYSIS_ONLY","QUALIFIED"} else "REVIEW_REQUIRED"
  contract=(levels.get("contract") or {}).get("symbol") or ((a.get("proposal") or {}).get("legs") or [{}])[0].get("symbol") if a.get("kind")=="LONG_OPTION" else None
  review=next((x.get("decision") for x in (report.get("ai_review") or {}).get("recommendations",[]) if x.get("symbol")==c.get("symbol")),None) if report.get("ai_provider")=="CODEX_CHATGPT" else None
  review=review if review in {"WAIT","NO_TRADE","TRADE","BUY","SELL","AVOID","REVIEW"} else None
  rows.append(dict(review_decision=review,symbol=symbol(c.get("symbol") or c.get("name")),direction=direction,conviction=rating,status=state,kind="OPTION" if a.get("kind")=="LONG_OPTION" else "EQUITY",contract=symbol(contract) if contract else None,horizons=horizons))
 rows.sort(key=lambda x:-(x["conviction"] or 0))
 return dict(status=status,asof=asof,checked=report.get("generated_at"),rows=rows[:2],total=len(rows))

def public_snapshot(snapshot):
 """Re-project persisted records: unknown/private fields never reach rendering or caption."""
 s=snapshot.get("sector_visual") or {};allowed={d.name for d in SECTOR_DEFINITIONS}
 rows=[{k:r.get(k) for k in ("name","score","rotation","delta","prior_asof","mtf","recorded_alignment")} for r in s.get("rows",[]) if r.get("name") in allowed]
 return dict(generated=snapshot.get("generated"),sector={k:s.get(k) for k in ("status","asof","regime","known","total","strong","weak","mtf_asofs","mtf_checked")},sector_rows=rows,handoff=snapshot.get("handoff_visual") or dict(status="UNAVAILABLE",rows=[]),screener=snapshot.get("screener_visual") or {})

def caption(snapshot):
 p=public_snapshot(snapshot);s=p["sector"];h=p["handoff"];rows=p["sector_rows"];known=[r for r in rows if numeric(r.get("score"))]
 out=["SECTOR PULSE | MARKET BRIEF",date(p["generated"]),"",str(s.get("regime") or "Sector evidence unavailable")+" · "+str(s.get("status") or "UNAVAILABLE"),"Sector bars: "+date(s.get("asof"))]
 if known:out += ["Highest: "+known[0]["name"]+" "+metric(known[0]["score"])+"/100", "Lowest: "+known[-1]["name"]+" "+metric(known[-1]["score"])+"/100"]
 aligns=[(r.get("mtf") or {}).get("alignment") for r in rows]
 out += ["MTF: "+str(aligns.count("FULL BULLISH ALIGNMENT"))+" full bullish / "+str(aligns.count("FULL BEARISH ALIGNMENT"))+" full bearish", "15m / 1H / Daily / Weekly; freshness + states in image."]
 out += ["","ANALYSIS HANDOFF",str(h.get("status") or "UNAVAILABLE"),"Bars: "+date(h.get("asof"))]
 for r in h.get("rows",[])[:2]:out.append(r["symbol"]+" · "+r["direction"]+" · "+status_label(r["status"]))
 if not h.get("rows"):out.append("No verified recommendation available.")
 out += ["","Levels in image: proposed report-only plans.","Premiums are model estimates; not executable quotes.","Analysis only. No order or fill confirmation."]
 # ASCII/BMP-only report; UTF-16 and Python character counts both below Telegram 1024.
 return "\n".join(out)[:1000]

def fallback_text(snapshot):
 p=public_snapshot(snapshot);out=[caption(snapshot),"","SECTOR MTF | 15m / 1H / D / W"]
 short={2:"SB+",1:"B+",0:"N",-1:"B-",-2:"SB-",None:"N/A"}
 for row in p["sector_rows"]:
  m=row.get("mtf") or {};codes="/".join(short.get(((m.get("frames") or {}).get(tf) or {}).get("state"),"N/A") for tf in TF_ORDER)
  delta=row.get("delta");change=f"{delta:+.2f}" if numeric(delta) else "N/A"
  out.append(row["name"]+" "+metric(row.get("score"))+" Δ"+change+" "+str(row.get("rotation") or "UNAVAILABLE")+": "+m.get("alignment","UNAVAILABLE")+" | "+codes+" | "+m.get("evidence","INCOMPLETE"))
 out += ["SB+/B+ Strong Bullish/Bullish; SB-/B- Strong Bearish/Bearish; N Neutral.","","COMPACT LEVELS | E entry; S stop; T target. All proposed."]
 for r in p["handoff"].get("rows",[])[:2]:
  out.append(r["symbol"]+(" | "+r["contract"] if r.get("contract") else ""))
  for h in r.get("horizons",[]):
   u=h["underlying"];out.append(h["name"].title()+" spot E "+metric(u["entry"])+" / S "+metric(u["stop_loss"])+" / T "+metric(u["target"]))
   if h.get("premium"):
    v=h["premium"];out.append("Premium est. E "+metric(v["entry"])+" / S "+metric(v["stop_loss"])+" / T "+metric(v["target"]))
 return "\n".join(out)[:3900]

def render(snapshot,target):
 from PIL import Image,ImageDraw,ImageFont
 p=public_snapshot(snapshot);s=p["sector"];rows=p["sector_rows"];h=p["handoff"]
 cards=h.get("rows",[])[:2];card_heights=[150+len(r["horizons"])*(85 if r["kind"]=="OPTION" else 50) for r in cards]
 chart_y=340;chart_bottom=chart_y+len(rows)*138;handoff_y=chart_bottom+430
 height=handoff_y+150+sum(card_heights)+200
 im=Image.new("RGB",(960,height),"#E9EFF5");d=ImageDraw.Draw(im)
 navy="#17364B";ink="#18394F";muted="#51697A";teal="#16786F";amber="#94611E";purple="#755895"
 def font(n,b=False):return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans"+("-Bold" if b else "")+".ttf",n)
 def text(x,y,t,n=27,color=ink,b=False):d.text((x,y),str(t),font=font(n,b),fill=color)
 def fit(x,y,t,width,n=27,color=ink,b=False):
  while d.textlength(str(t),font=font(n,b))>width and n>18:n-=1
  text(x,y,t,n,color,b)
 def right(x,y,t,n=27,color=ink,b=False):text(x-d.textlength(str(t),font=font(n,b)),y,t,n,color,b)
 d.rectangle((0,0,960,218),fill=navy);text(40,28,"SECTOR PULSE",25,"#BFDCD9",True);right(920,30,date(p["generated"]),23,"#FFFFFF")
 text(40,75,"The rotation brief",49,"#FFFFFF",True);text(42,143,s.get("regime") or "Sector evidence unavailable",32,"#FFFFFF",True)
 fit(42,187,str(s.get("status") or "UNAVAILABLE")+" · bars "+date(s.get("asof")),880,23,"#CEE0EA")
 text(40,245,"SECTOR STRENGTH",29,ink,True);right(920,249,str(s.get("known") or 0)+" / "+str(s.get("total") or 14)+" scored",24,muted)
 text(40,287,"Composite / 100 · not price returns or fund flows",24,muted)
 text(40,320,"SECTOR / ROTATION",19,muted,True);text(355,320,"0",19,muted);right(710,320,"100",19,muted);right(810,320,"SCORE",19,muted);right(920,320,"Δ SCORE",19,muted)
 colors={"LEADING":teal,"IMPROVING":"#377EA8","WEAKENING":amber,"LAGGING":purple,"NEUTRAL":"#73818A","UNAVAILABLE":"#73818A"}
 for i,row in enumerate(rows):
  y=chart_y+i*138
  if i%2==0:d.rectangle((26,y,934,y+137),fill="#FFFFFF")
  fit(40,y+5,row["name"],300,29,ink,True);text(40,y+39,row.get("rotation") or "UNAVAILABLE",17,colors.get(row.get("rotation"),muted),True)
  d.rounded_rectangle((355,y+20,710,y+38),radius=7,fill="#D7E1E9")
  score=row.get("score")
  if numeric(score) and 0<=score<=100:
   d.rounded_rectangle((355,y+20,355+max(2,355*score/100),y+38),radius=7,fill=colors.get(row.get("rotation"),muted));right(810,y+12,metric(score),28,ink,True)
  else:right(810,y+12,"N/A",26,muted)
  delta=row.get("delta");right(920,y+12,f"{delta:+.2f}" if numeric(delta) else "—",26,muted)
  mtf=row.get("mtf") or {};alignment=mtf.get("alignment") or "UNAVAILABLE"
  align_color="#28796F" if "BULLISH" in alignment else "#8B515F" if "BEARISH" in alignment else muted
  fit(40,y+65,alignment+" · "+mtf.get("evidence","INCOMPLETE"),875,24,align_color,True)
  short={2:"Strong Bull",1:"Bull",0:"Neutral",-1:"Bear",-2:"Strong Bear",None:"N/A"}
  parts=[]
  for tf,label in zip(TF_ORDER,("15m","1H","D","W")):
   f=(mtf.get("frames") or {}).get(tf) or {};suffix="!" if f.get("state") is None or f.get("data_quality") in {"STALE","UNAVAILABLE","INSUFFICIENT DATA"} else ""
   parts.append(label+" "+short.get(f.get("state"),"N/A")+suffix)
  fit(40,y+103,"  |  ".join(parts),875,23,muted)

 y=chart_bottom+18
 text(40,y,"Δ vs prior stored completed candle (same session, ≤45m).",22,muted)
 text(40,y+31,"— = no comparable candle. Colour = named rotation state.",22,muted)
 text(40,y+62,"Strength rank is separate from MTF directional alignment.",22,muted)
 text(40,y+93,"MTF: completed 15m / 1H / Daily / Weekly; ! stale or missing.",22,muted)
 text(40,y+124,"Bull/Bear = Bullish/Bearish; Strong uses dashboard states.",22,muted)
 text(40,y+155,"Alignment uses exact dashboard rules; no score threshold.",22,muted)
 asofs=s.get("mtf_asofs") or {}
 text(40,y+188,"MTF bars: 15m "+date(asofs.get("15m"))+" / 1H "+date(asofs.get("1h")),21,muted)
 text(40,y+218,"Daily "+date(asofs.get("daily"))+" / Weekly "+date(asofs.get("weekly")),21,muted)
 text(40,y+248,"MTF checked "+date(s.get("mtf_checked"))+"; mixed times marked unavailable.",21,muted)
 known=[r for r in rows if numeric(r.get("score"))]
 if known:
  text(40,y+280,"READOUT",20,teal,True)
  fit(40,y+310,known[0]["name"]+" leads the ranking; "+known[-1]["name"]+" is lowest.",880,28,ink,True)
  text(40,y+349,f"{s.get('strong',0)} at ≥55 / {s.get('weak',0)} below 45. Regime uses this breadth.",23,muted)
 else:text(40,y+310,"No verified sector scores. Ranking withheld.",28,muted,True)
 y=handoff_y;d.rectangle((0,y,960,y+115),fill=navy);text(40,y+18,"ANALYSIS HANDOFF",32,"#FFFFFF",True)
 fit(40,y+64,h.get("status") or "UNAVAILABLE",880,23,"#EACD95");text(40,y+92,"Bars "+date(h.get("asof"))+" · checked "+date(h.get("checked")),20,"#CEE0EA")
 y+=130
 if not cards:text(40,y+10,"No verified recommendation available.",28,muted);y+=45
 for r,ch in zip(cards,card_heights):
  d.rounded_rectangle((26,y,934,y+ch-12),radius=15,fill="#FFFFFF")
  fit(42,y+14,r["symbol"]+" · "+r["direction"],850,30,ink,True)
  fit(42,y+56,status_label(r["status"])+" · conviction "+metric(r["conviction"])+"/10",850,22,muted)
  if r.get("contract"):fit(42,y+88,r["contract"]+" · report-only option plan",850,22,muted)
  else:text(42,y+88,"Report-only equity plan",22,muted)
  ly=y+122
  for plan in r["horizons"]:
   u=plan["underlying"];text(42,ly,plan["name"].upper(),19,teal,True)
   fit(205,ly,"Spot  E "+metric(u["entry"])+"   S "+metric(u["stop_loss"])+"   T "+metric(u["target"]),685,26,ink,True)
   if plan.get("premium"):
    v=plan["premium"];fit(205,ly+34,"Premium est.  E "+metric(v["entry"])+"   S "+metric(v["stop_loss"])+"   T "+metric(v["target"]),685,24,muted);ly+=85
   else:ly+=50
  y+=ch
 y+=12
 text(40,y,"E entry · S stop · T target. N/A = evidence unavailable.",22,muted)
 text(40,y+31,"Proposed levels; option models hold time/IV unchanged.",22,muted)
 sc=p["screener"];text(40,y+67,"Screener: "+str(sc.get("coverage") or "unavailable"),22,muted)
 sc_status=str(sc.get("status") or "UNAVAILABLE")
 short="Delayed / incomplete evidence" if "DELAYED" in sc_status or "STALE" in sc_status or "UNAVAILABLE" in sc_status else sc_status
 text(40,y+96,short+" · bars "+date(sc.get("asof")),22,muted)
 fit(40,y+133,"Analysis only · no order / fill confirmation · source FYERS",880,23,ink,True)
 target.parent.mkdir(parents=True,exist_ok=True);im.save(target,optimize=True)
 if target.stat().st_size>9_000_000:raise ValueError("Image exceeds safe Telegram photo size")
 return dict(width=960,height=height,bytes=target.stat().st_size,revision=REVISION)
