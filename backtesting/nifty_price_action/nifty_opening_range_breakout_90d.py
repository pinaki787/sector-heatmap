"""Read-only NIFTY 90-day price-action opening-range-breakout research."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from fyers_apiv3 import fyersModel
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config
SYMBOL, STOP, TARGET = "NSE:NIFTY50-INDEX", .005, .01
def main():
    app,tok=load_config()["FYERS_ACCESS_TOKEN"].split(":",1);c=fyersModel.FyersModel(client_id=app,token=tok);now=datetime.now().astimezone()
    r=c.history({"symbol":SYMBOL,"resolution":"5","date_format":1,"range_from":(now-timedelta(days=90)).date().isoformat(),"range_to":now.date().isoformat(),"cont_flag":1})
    if r.get("s") != "ok":raise RuntimeError(r.get("message") or "history unavailable")
    rows=[x for x in r["candles"] if x[0]+300<=now.timestamp()];days={}
    for row in rows: days.setdefault(datetime.fromtimestamp(row[0]).astimezone().date(),[]).append(row)
    returns=[];reasons=[]
    for bars in days.values():
        if len(bars)<6:continue
        opening=bars[:3];orb_high=max(x[2] for x in opening);orb_low=min(x[3] for x in opening);side=entry=None
        for i in range(3,len(bars)-1):
            ts=datetime.fromtimestamp(bars[i][0]).astimezone();next_open=bars[i+1][1]
            if side is None:
                if bars[i][4]>orb_high:side,entry="long",next_open
                elif bars[i][4]<orb_low:side,entry="short",next_open
                continue
            stop=entry*(1-STOP) if side=="long" else entry*(1+STOP);target=entry*(1+TARGET) if side=="long" else entry*(1-TARGET)
            hi,lo=bars[i][2],bars[i][3];session_end=ts.hour==15 and ts.minute>=15
            # If both levels print in a single candle, choose the conservative stop outcome.
            hit_stop=lo<=stop if side=="long" else hi>=stop;hit_target=hi>=target if side=="long" else lo<=target
            if hit_stop or hit_target or session_end:
                exit_price=stop if hit_stop else target if hit_target else next_open
                gross=exit_price/entry-1 if side=="long" else entry/exit_price-1
                returns.append(gross-.0006-40/entry);reasons.append("stop" if hit_stop else "target" if hit_target else "session")
                side=entry=None;break
    equity=peak=1.;dd=0.
    for x in returns:equity*=1+x;peak=max(peak,equity);dd=min(dd,equity/peak-1)
    print(json.dumps({"lookback_days":90,"completed_5m_bars":len(rows),"closed_trades":len(returns),"wins":sum(x>0 for x in returns),"win_rate_pct":round(sum(x>0 for x in returns)/len(returns)*100,2) if returns else None,"net_return_pct":round((equity-1)*100,3),"max_drawdown_pct":round(dd*100,3),"exits":{x:reasons.count(x) for x in set(reasons)},"definition":"first 15-minute range; one completed 5-minute close break; next-open fill; 0.5% stop, 1% target, 15:20 exit"},indent=2))
if __name__=="__main__":main()
