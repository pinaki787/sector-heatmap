"""Readable Telegram HTML for private trade updates; no transport or brokers."""
from datetime import datetime
from html import escape
import math
from zoneinfo import ZoneInfo

LIMIT=3900

def units(text):return len(text.encode("utf-16-le"))//2

def numeric(value,places=2,signed=False):
    if isinstance(value,bool):return "Unavailable"
    try:number=float(value)
    except (TypeError,ValueError):return "Unavailable"
    if not math.isfinite(number):return "Unavailable"
    if places==0:return format(number,",.8f").rstrip("0").rstrip(".")
    return format(number,("+," if signed else ",")+"."+str(places)+"f")

def money(value,currency="INR",signed=False):
    text=numeric(value,signed=signed)
    if text=="Unavailable":return text
    prefix="₹" if currency=="INR" else "$" if currency=="USD" else str(currency)+" "
    if text[:1] in ("-","+"):return text[0]+prefix+text[1:]
    return prefix+text

def stamp(value):
    try:
        if isinstance(value,bool):raise ValueError()
        return datetime.fromtimestamp(float(value),ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y · %I:%M %p IST").replace(" 0"," ")
    except (ValueError,TypeError,OverflowError,OSError):return "Unavailable"

def line(label,value):return "<b>"+escape(label)+":</b> "+escape(str(value))

def text_lines(text):
    piece=""
    for char in str(text):
        if units(escape(piece+char))>1200:
            yield escape(piece);piece=""
        piece+=char
    if piece:yield escape(piece)

def parts(event):
    mode=str(event.get("mode") or "Unavailable")
    broker=str(event.get("broker") or "Broker unavailable")
    currency=str(event.get("currency") or ("INR" if broker in {"FYERS","DHAN","MOTILAL_OSWAL"} else "broker-native"))
    summary=event.get("kind")=="POSITION_SUMMARY"
    heading=("🔒 Positions" if summary else "🔔 "+str(event.get("action") or "Trade update").title()+" fill")+" · "+mode
    try:when=datetime.fromtimestamp(float(event.get("time")),ZoneInfo("Asia/Kolkata")).strftime("%d %b · %H:%M IST")
    except (ValueError,TypeError,OverflowError,OSError):when="Time unavailable"
    blocks=["<b>"+escape(heading)+"</b>",escape(broker+" · "+when)]
    if summary:
        rows=event.get("positions") or []
        if not rows:blocks.append("No open positions.")
        for row in rows:
            values="Qty "+numeric(row.get("netQty"),0)
            if row.get("price") is not None:values+=" · Avg "+money(row["price"],currency)
            blocks.append("<b>"+escape(str(row.get("symbol") or "Instrument unavailable"))+"</b>\n"+escape(values)+"\n"+line("P&L",money(row.get("pnl"),currency,True)))
        if event.get("daily_pnl") is not None:blocks.append(line("Day P&L · realized + unrealized",money(event["daily_pnl"],currency,True)))
    else:
        if event.get("strategy"):blocks.append(escape(str(event["strategy"])))
        blocks.extend((line("Instrument",event.get("symbol") or "Unavailable"),line("Side",event.get("side") or "Unavailable"),
            "\n".join((line("Filled · this update",numeric(event.get("quantity"),0)+" @ "+money(event.get("price"),currency)),
                line("Cumulative filled",numeric(event.get("cumulative_quantity"),0)),line("Cumulative average",money(event.get("cumulative_average"),currency))))))
        if event.get("action")=="EXIT":
            blocks.append(line("Exit reason",event.get("reason") or "Unavailable"))
            blocks.append(line("P&L · before fees",money(event.get("realized_pnl"),currency,True)))
        blocks.append("<i>Time: local fill confirmation.</i>")
        if mode=="PAPER":blocks.append("<i>Simulation · no broker execution.</i>")
    safe=[]
    for block in blocks:
        if units(block)<=LIMIT:safe.append(block)
        else:
            import re
            from html import unescape
            safe.extend(text_lines(unescape(re.sub("<[^>]*>","",block))))
    result=[];current=""
    for block in safe:
        candidate=current+("\n\n" if current else "")+block
        if units(candidate)>LIMIT:
            result.append(current);current=block
        else:current=candidate
    if current:result.append(current)
    if len(result)>1:
        result=["<b>Sector Pulse · "+str(i+1)+"/"+str(len(result))+"</b>\n\n"+part for i,part in enumerate(result)]
    return result
