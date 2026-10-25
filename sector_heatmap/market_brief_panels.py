"""Ordered, phone-sized market panels. No private report fields are rendered."""
from pathlib import Path
import hashlib
from .market_brief_visual import public_snapshot,metric,numeric,date,status_label,TF_ORDER,caption,fallback_text
REVISION="phone-panels-v3"
WIDTH=720
SECTORS_PER_PANEL=3
MIN_BODY_FONT=28

def render_panels(snapshot,target):
 from PIL import Image,ImageDraw,ImageFont
 target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
 p=public_snapshot(snapshot);rows=p["sector_rows"];h=p["handoff"];s=p["sector"]
 groups=[rows[i:i+SECTORS_PER_PANEL] for i in range(0,len(rows),SECTORS_PER_PANEL)] or [[]]
 findings=h.get("rows",[])[:2];specs=[("sectors",g) for g in groups]+[("handoff",[row]) for row in findings]
 if not findings:specs.append(("handoff",[]))
 result=[];navy="#17364B";ink="#18394F";muted="#51697A";teal="#16786F"
 state_ink={2:"#166D63",1:"#166D63",0:muted,-1:"#8B515F",-2:"#8B515F",None:muted}
 rotations={"LEADING":teal,"IMPROVING":"#377EA8","WEAKENING":"#94611E","LAGGING":"#755895","NEUTRAL":"#73818A"}
 for index,(kind,items) in enumerate(specs):
  height=190+len(items)*230+120 if kind=="sectors" else 1000 if items else 480
  image=Image.new("RGB",(WIDTH,height),"#E9EFF5");d=ImageDraw.Draw(image)
  def font(size,b=False):return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans"+("-Bold" if b else "")+".ttf",size)
  def text(x,y,t,size=28,color=ink,b=False):d.text((x,y),str(t),font=font(size,b),fill=color)
  def right(x,y,t,size=28,color=ink,b=False):text(x-d.textlength(str(t),font=font(size,b)),y,t,size,color,b)
  def fit(x,y,t,width=648,size=30,color=ink,b=False,minimum=28):
   while d.textlength(str(t),font=font(size,b))>width and size>minimum:size-=1
   if d.textlength(str(t),font=font(size,b))>width:raise ValueError("Panel text exceeds readable width")
   text(x,y,t,size,color,b)
  def wrapped(x,y,t,width=648,size=28,color=muted,leading=35):
   lines=[""]
   for word in str(t).split():
    trial=(lines[-1]+" "+word).strip()
    if d.textlength(trial,font=font(size))>width:lines.append(word)
    else:lines[-1]=trial
   for j,line in enumerate(lines):text(x,y+j*leading,line,size,color)
   return y+len(lines)*leading
  d.rectangle((0,0,WIDTH,180),fill=navy)
  text(32,20,"SECTOR PULSE",25,"#BFDCD9",True);right(688,20,f"{index+1} / {len(specs)}",25,"#FFFFFF",True)
  text(32,62,"Sector alignment" if kind=="sectors" else "Analysis Handoff",39,"#FFFFFF",True)
  fit(32,115,(s.get("status") or "UNAVAILABLE") if kind=="sectors" else "Review-only market analysis",size=26,minimum=24,color="#F0D39B")
  text(32,150,"Bars "+date(s.get("asof") if kind=="sectors" else h.get("asof")),24,"#CEE0EA")
  if kind=="sectors":
   for j,row in enumerate(items):
    y=190+j*230;d.rounded_rectangle((20,y,700,y+218),radius=12,fill="#FFFFFF")
    fit(36,y+10,row["name"],510,35,ink,True);right(684,y+10,metric(row.get("score")),34,ink,True)
    rotation=row.get("rotation") or "UNAVAILABLE";text(36,y+53,rotation,24,rotations.get(rotation,muted),True)
    d.rounded_rectangle((284,y+60,512,y+74),radius=6,fill="#D7E1E9")
    score=row.get("score")
    if numeric(score) and 0<=score<=100:d.rounded_rectangle((284,y+60,284+max(2,228*score/100),y+74),radius=6,fill=rotations.get(rotation,muted))
    delta=row.get("delta");right(684,y+50,"Δ "+(f"{delta:+.2f}" if numeric(delta) else "N/A"),27,muted)
    m=row.get("mtf") or {};alignment=m.get("alignment") or "UNAVAILABLE"
    color=teal if "BULLISH" in alignment else "#8B515F" if "BEARISH" in alignment else muted
    fit(36,y+89,alignment,648,29,color,True)
    frames=m.get("frames") or {}
    for k,(tf,label) in enumerate(zip(TF_ORDER,("15m","1H","Daily","Weekly"))):
     x=36+k*166;f=frames.get(tf) or {};state=f.get("state");bad=state is None or f.get("data_quality") in {"STALE","UNAVAILABLE","INSUFFICIENT DATA"}
     text(x,y+130,label+(" !" if bad else ""),24,muted,True)
     first,second=("Strong","Bullish") if state==2 else ("Strong","Bearish") if state==-2 else ("Bullish","") if state==1 else ("Bearish","") if state==-1 else ("Neutral","") if state==0 else ("N/A","")
     text(x,y+158,first,28,state_ink.get(state,muted),True)
     if second:text(x,y+184,second,28,state_ink.get(state,muted),True)
   fy=190+len(items)*230+5
   text(32,fy,"Score /100; Δ vs prior stored candle ≤45m.",24,muted)
   text(32,fy+30,"Strength rank ≠ MTF direction. ! stale / missing.",24,muted)
   fit(32,fy+61,"MTF checked "+date(s.get("mtf_checked")),size=24,minimum=24,color=muted)
   # Direction validity is explicit; last-session/delayed applies per collector.
   evidence={((row.get("mtf") or {}).get("evidence") or "INCOMPLETE") for row in items}
   flag="Stale / incomplete timeframe evidence" if any("STALE" in x or "INCOMPLETE" in x for x in evidence) else "MTF evidence: BROKER DELAYED" if "BROKER DELAYED" in evidence else "Completed 15m / 1H / Daily / Weekly states"
   if flag!="Completed 15m / 1H / Daily / Weekly states":
    d.rectangle((28,fy+60,700,fy+90),fill="#E9EFF5");fit(32,fy+61,flag,size=24,minimum=24,color=muted)
  elif not items:
   wrapped(32,220,"No verified Handoff recommendation available.",size=32,color=ink)
   wrapped(32,320,h.get("status") or "UNAVAILABLE",size=28)
   text(32,430,"Analysis only. No orders or fills confirmed.",24,muted)
  else:
   row=items[0];fit(32,205,row["symbol"],size=35,b=True)
   fit(32,252,row["direction"]+(" · AI "+row["review_decision"] if row.get("review_decision") else " · REVIEW ONLY"),size=30,b=True)
   fit(32,294,status_label(row["status"])+" · "+metric(row.get("conviction"))+"/10",size=26,minimum=26,color=muted)
   if row.get("contract"):fit(32,336,row["contract"],size=28,color=muted)
   horizons=row.get("horizons",[])[:2]
   for j,plan in enumerate(horizons):
    y=390+j*190;d.rounded_rectangle((20,y,700,y+176),radius=12,fill="#FFFFFF")
    text(36,y+12,plan["name"].upper()+" · PROPOSED",27,teal,True)
    for col,(label,key) in enumerate((("ENTRY","entry"),("STOP","stop_loss"),("TARGET","target"))):
     x=36+col*220;text(x,y+53,label,23,muted,True)
     text(x,y+82,metric(plan["underlying"][key]),32,ink,True)
     if plan.get("premium"):text(x,y+128,metric(plan["premium"][key]),30,muted,True)
    if not plan.get("premium"):text(36,y+131,"Underlying spot levels",26,muted)
   fy=390+len(horizons)*190+8
   if row["kind"]=="OPTION":text(32,fy,"Top row: spot. Bottom: option premium estimate.",24,muted)
   text(32,fy+34,"Model holds time / IV fixed. Not executable quotes.",24,muted)
   wrapped(32,fy+72,h.get("status") or "UNAVAILABLE",size=27,leading=32)
   text(32,height-42,"Analysis only. No orders or fills confirmed.",24,ink,True)
  path=target.with_name(target.stem+f"-p{index+1}.png");image.save(path,optimize=True)
  if path.stat().st_size>9_000_000:raise ValueError("Panel exceeds photo size")
  asofs=s.get("mtf_asofs") or {}
  mtf_times="\nMTF bars: 15m "+date(asofs.get("15m"))+"; 1H "+date(asofs.get("1h"))+"; Daily "+date(asofs.get("daily"))+"; Weekly "+date(asofs.get("weekly"))
  body=caption(snapshot) if index==0 else "SECTOR PULSE | "+str(index+1)+" / "+str(len(specs))+"\n"+("Sector alignment" if kind=="sectors" else "Analysis Handoff — proposed report-only levels")+"\nBars "+date(s.get("asof") if kind=="sectors" else h.get("asof"))+"\nAnalysis only. No order or fill confirmation."
  if kind=="sectors":body+=mtf_times+"\nMTF checked "+date(s.get("mtf_checked"))
  if len(body.encode("utf-16-le"))//2>1024:raise ValueError("Panel caption limit")
  result.append(dict(index=index,kind=kind,image=str(path),image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),public_caption=body,width=WIDTH,height=height,sector_names=[x["name"] for x in items] if kind=="sectors" else [],minimum_body_font=MIN_BODY_FONT))
 return result
