"""Read-only SOLARINDS KAMA, VWAP, and completed 15-minute trend-gate test."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from fyers_apiv3 import fyersModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

SYMBOL, ER, FAST, SLOW = "NSE:SOLARINDS-EQ", 10, 2, 30

def kama(values):
    out = [None] * len(values)
    if len(values) <= ER: return out
    out[ER] = values[ER]
    fast, slow = 2 / (FAST + 1), 2 / (SLOW + 1)
    for i in range(ER + 1, len(values)):
        efficiency = abs(values[i] - values[i-ER]) / sum(abs(values[j] - values[j-1]) for j in range(i-ER+1, i+1)) if sum(abs(values[j] - values[j-1]) for j in range(i-ER+1, i+1)) else 0
        smooth = (efficiency * (fast - slow) + slow) ** 2
        out[i] = out[i-1] + smooth * (values[i] - out[i-1])
    return out

def vwap(rows):
    out=[]; day=None; pv=vol=0
    for ts,_,h,l,c,v in rows:
        d=datetime.fromtimestamp(ts).astimezone().date()
        if d != day: day,pv,vol=d,0,0
        pv += ((h+l+c)/3)*v; vol += v; out.append(pv/vol if vol else c)
    return out

def main():
    app, token = load_config()["FYERS_ACCESS_TOKEN"].split(":", 1)
    client=fyersModel.FyersModel(client_id=app, token=token); now=datetime.now().astimezone()
    def fetch(res):
        r=client.history({"symbol":SYMBOL,"resolution":res,"date_format":1,"range_from":(now-timedelta(days=7)).date().isoformat(),"range_to":now.date().isoformat(),"cont_flag":1})
        if r.get("s") != "ok": raise RuntimeError(r.get("message") or "history unavailable")
        seconds=int(res)*60
        return [x for x in r["candles"] if x[0]+seconds <= now.timestamp()]
    low, high = fetch("5"), fetch("15")
    lc, hc = [x[4] for x in low], [x[4] for x in high]
    lk, hk, vw = kama(lc), kama(hc), vwap(low)
    position=None; trades=[]
    for i in range(ER+2, len(low)-1):
        eligible=[j for j,x in enumerate(high) if x[0]+900 <= low[i][0]]
        if not eligible or lk[i] is None: continue
        j=eligible[-1]
        if hk[j] is None or j < 1 or hk[j-1] is None: continue
        t=datetime.fromtimestamp(low[i][0]).astimezone(); last=t.hour == 15 and t.minute >= 15
        enter=lc[i]>lk[i] and lc[i-1]<=lk[i-1] and lk[i]>lk[i-1] and lc[i]>vw[i] and hc[j]>hk[j] and hk[j]>hk[j-1]
        exit_now=lc[i]<lk[i] or lc[i]<vw[i] or last
        if position is None and enter and not last: position=low[i+1][1]
        elif position and exit_now:
            gross=low[i+1][1]/position-1; cost=.0006+40/position
            trades.append(gross-cost); position=None
    print(json.dumps({"completed_5m_bars":len(low),"completed_15m_bars":len(high),"closed_trades":len(trades),"wins":sum(x>0 for x in trades),"net_return_pct":round(sum(trades)*100,3),"filter":"15-minute close above rising KAMA"},indent=2))
if __name__ == "__main__": main()
