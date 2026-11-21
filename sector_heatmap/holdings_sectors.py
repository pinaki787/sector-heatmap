"""Exact public cash-symbol classifications. Never transmit portfolio values."""
import json,re,time
from pathlib import Path
import requests
from .investment import download,SCAN

def lookup(root,rows):
    tickers={}
    for row in rows:
        symbol=str(row.get("symbol", ""))
        if row.get("kind")=="DELIVERY_EQUITY" and re.fullmatch(r"(?:NSE|BSE):[A-Z0-9&_.-]+-EQ",symbol):
            tickers[symbol]=symbol[:-3]
    directory=Path(root)/"data"/"public-sector-metadata"
    directory.mkdir(parents=True,exist_ok=True)
    cache=directory/"classifications.json"
    try:saved=json.loads(cache.read_text())
    except (OSError,ValueError):saved={}
    now=time.time(); missing=[s for s,t in tickers.items() if not isinstance(saved.get(t),dict) or now-saved[t].get("captured",0)>86400]
    if missing:
        payload={"symbols":{"tickers":sorted({tickers[s] for s in missing}),"query":{"types":[]}},"columns":["name","sector","type","description"],"range":[0,len(missing)]}
        with requests.Session() as session:
            result=json.loads(download(session,SCAN,payload))
        found={}
        for item in result.get("data",[]):
            ticker=item.get("s");data=item.get("d") or []
            if ticker not in tickers.values() or len(data)<4:continue
            name,sector,kind,description=data[:4]
            if name!=ticker.split(":",1)[1]:continue
            category="ETF / fund" if kind=="fund" else sector if kind=="stock" and isinstance(sector,str) and sector.strip() else "Unclassified"
            found[ticker]={"sector":category,"instrument_type":kind,"captured":now}
        for symbol in missing:saved[tickers[symbol]]=found.get(tickers[symbol],{"sector":"Unclassified","instrument_type":None,"captured":now})
        import tempfile,os
        fd,temp=tempfile.mkstemp(dir=directory)
        with os.fdopen(fd,"w") as stream:json.dump(saved,stream)
        os.replace(temp,cache)
    return {"schema":"holdings-sectors/v1","classifications":{s:saved[t] for s,t in tickers.items()},"source":"TradingView public India scanner · exact cash symbols","fetched_at":now,"classified":sum(saved[t]["sector"]!="Unclassified" for t in tickers.values()),"requested":len(tickers),"order_authority":"NONE"}
