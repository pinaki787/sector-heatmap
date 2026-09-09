"""Read-only confluence sweep; it never calls an order endpoint."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from fyers_apiv3 import fyersModel
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sector_heatmap.web import load_config

ER, FAST, SLOW = 10, 2, 30
def kama(x):
    out=[None]*len(x)
    if len(x)<=ER:return out
    out[ER]=x[ER]; f,s=2/(FAST+1),2/(SLOW+1)
    for i in range(ER+1,len(x)):
        noise=sum(abs(x[j]-x[j-1]) for j in range(i-ER+1,i+1)); e=abs(x[i]-x[i-ER])/noise if noise else 0
        out[i]=out[i-1]+(e*(f-s)+s)**2*(x[i]-out[i-1])
    return out
def vwap(rows):
    out=[]; d=None; pv=vol=0
    for ts,_,h,l,c,v in rows:
        day=datetime.fromtimestamp(ts).astimezone().date()
        if day!=d:d,pv,vol=day,0,0
        pv+=((h+l+c)/3)*v;vol+=v;out.append(pv/vol if vol else c)
    return out
def main():
    app,tok=load_config()["FYERS_ACCESS_TOKEN"].split(":",1); c=fyersModel.FyersModel(client_id=app,token=tok); now=datetime.now().astimezone()
    def fetch(res):
        r=c.history({"symbol":"NSE:SOLARINDS-EQ","resolution":res,"date_format":1,"range_from":(now-timedelta(days=7)).date().isoformat(),"range_to":now.date().isoformat(),"cont_flag":1});secs=int(res)*60
        return [x for x in r["candles"] if x[0]+secs<=now.timestamp()]
    low,high=fetch("5"),fetch("15");lc,hc=[x[4] for x in low],[x[4] for x in high];lk,hk,vw=kama(lc),kama(hc),vwap(low);results=[]
    for volume_factor in (.75,1.0,1.25):
      for breakout in (0,3,6):
        pos=None;rets=[]
        for i in range(max(ER+20,breakout+2),len(low)-1):
          js=[j for j,x in enumerate(high) if x[0]+900<=low[i][0]]
          if not js:continue
          j=js[-1]
          if j<ER+1 or lk[i] is None or hk[j] is None or hk[j-1] is None:continue
          t=datetime.fromtimestamp(low[i][0]).astimezone();last=t.hour==15 and t.minute>=15
          vol_ok=low[i][5]>=sum(x[5] for x in low[i-20:i])/20*volume_factor
          bo_ok=not breakout or lc[i]>max(x[2] for x in low[i-breakout:i])
          enter=lc[i]>lk[i] and lc[i-1]<=lk[i-1] and lk[i]>lk[i-1] and lc[i]>vw[i] and hc[j]>hk[j] and hk[j]>hk[j-1] and vol_ok and bo_ok
          exit_now=lc[i]<lk[i] or lc[i]<vw[i] or last
          if pos is None and enter and not last:pos=low[i+1][1]
          elif pos and exit_now:
            rets.append(low[i+1][1]/pos-1-.0006-40/pos);pos=None
        results.append({"volume_factor":volume_factor,"breakout_bars":breakout,"trades":len(rets),"wins":sum(x>0 for x in rets),"net_return_pct":round(sum(rets)*100,3)})
    print(json.dumps(sorted(results,key=lambda x:x["net_return_pct"],reverse=True),indent=2))
if __name__=="__main__":main()
