"""Deterministic completed-candle structure, no orders and no future pivots."""
from datetime import datetime
from zoneinfo import ZoneInfo
IST=ZoneInfo("Asia/Kolkata")
def build_facts(rows,k=2):
 facts={};window=[];highs=[];lows=[];resistance=[];support=[];bos=0;sweep_long=-999;sweep_short=-999;session=None;n=0;previous=None
 for r in rows:
  day=datetime.fromtimestamp(r["timestamp"],IST).date()
  if day!=session or previous is not None and r["timestamp"]!=previous+300:
   window=[];highs=[];lows=[];resistance=[];support=[];bos=0;sweep_long=-999;sweep_short=-999;session=day;n=0
  previous=r["timestamp"];n+=1
  # Sweep/break only levels already confirmed before this candle.
  rh=highs[-1]["price"] if highs else None;ll=lows[-1]["price"] if lows else None
  if rh is not None:
   if r["high"]>rh and r["close"]<rh:sweep_long=n
   if r["close"]>rh:bos=1
  if ll is not None:
   if r["low"]<ll and r["close"]>ll:sweep_short=n
   if r["close"]<ll:bos=-1
  resistance=[x for x in resistance if r["close"]<=x]
  support=[x for x in support if r["close"]>=x]
  window=(window+[r])[-(2*k+1):]
  if len(window)==2*k+1:
   pivot=window[k];others=window[:k]+window[k+1:]
   if all(pivot["high"]>x["high"] for x in others):
    highs=(highs+[dict(price=pivot["high"],at=pivot["timestamp"],confirmed_at=r["timestamp"]+300)])[-2:];resistance=(resistance+[pivot["high"]])[-20:]
   if all(pivot["low"]<x["low"] for x in others):
    lows=(lows+[dict(price=pivot["low"],at=pivot["timestamp"],confirmed_at=r["timestamp"]+300)])[-2:];support=(support+[pivot["low"]])[-20:]
  structure=0
  if len(highs)==2 and len(lows)==2:
   if highs[-1]["price"]>highs[-2]["price"] and lows[-1]["price"]>lows[-2]["price"]:structure=1
   elif highs[-1]["price"]<highs[-2]["price"] and lows[-1]["price"]<lows[-2]["price"]:structure=-1
  facts[r["timestamp"]]=dict(structure=structure,bos=bos,age_long_sweep=n-sweep_long,age_short_sweep=n-sweep_short,
   resistance=resistance.copy(),support=support.copy(),bars=n,highs=highs.copy(),lows=lows.copy())
 return facts
def allows(fact,direction,price,atr,rule):
 if not rule:return True
 sign=1 if direction=="BULLISH" else -1
 if rule.get("delay") and fact["bars"]<rule["delay"]:return False
 if rule.get("structure") and fact["structure"]!=sign:return False
 if rule.get("bos") and fact["bos"]!=sign:return False
 if rule.get("sweep"):
  age=fact["age_long_sweep" if sign>0 else "age_short_sweep"]
  if age<rule["sweep"]:return False
 if rule.get("room"):
  if atr is None or atr<=0:return False
  distances=[sign*(level-price) for level in fact["resistance" if sign>0 else "support"] if sign*(level-price)>0]
  if distances and min(distances)<rule["room"]*atr:return False
 return True
