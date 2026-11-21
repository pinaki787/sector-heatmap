import csv,json,math
from pathlib import Path
import numpy as np
root=Path(__file__).parent
base={r["time"]:r for r in csv.DictReader(open(root/"btcusd_5m_visual_paired_wide_20261104.csv"))}
fixed={r["time"]:r for r in csv.DictReader(open(root/"btcusd_5m_fix10_20261104.csv"))}
rows=[base[t] for t in sorted(base)]
target={t:float(r["MAHAKAAL Renko Supertrend"]) for t,r in fixed.items() if r["MAHAKAAL Renko Supertrend"]}
out=[]
for path in ["close","ohlc","olhc","candle"]:
 for reverse in [1,2]:
  for aggregation in ["eachbrick","eachbar"]:
   for cap in ["all","one"]:
    for offset in [0,.5,1,2,2.5,3,4,4.5,5,5.5,6,7,7.5,8,9,9.5]:
     rc=math.floor(float(rows[0]["close"])/10)*10+offset;direction=0;atr=10.;upper=lower=rc;st=rc;trend=1;lastc=rc;errors=[]
     def step(ro,cl):
      global atr,upper,lower,st,trend,lastc
      tr=max(abs(cl-ro),abs(cl-lastc),abs(ro-lastc));atr=(13*atr+tr)/14
      mid=(cl+ro)/2;bu=mid+3*atr;bl=mid-3*atr
      pu,pl=upper,lower
      upper=bu if bu<pu or lastc>pu else pu
      lower=bl if bl>pl or lastc<pl else pl
      if trend==1:trend=-1 if cl>upper else 1
      else:trend=1 if cl<lower else -1
      st=lower if trend==-1 else upper;lastc=cl
     for r in rows:
      o,h,l,c=[float(r[k]) for k in ["open","high","low","close"]]
      prices={"close":[c],"ohlc":[o,h,l,c],"olhc":[o,l,h,c],"candle":[o,l,h,c] if c>=o else [o,h,l,c]}[path]
      start=rc;formed=False
      for price in prices:
       dist=price-rc;sgn=1 if dist>0 else -1
       threshold=10*(reverse if direction and sgn!=direction else 1)
       if abs(dist)+1e-9>=threshold:
        count=int(abs(dist)//10);count=min(count,1) if cap=="one" else count
        for j in range(count):
         ro=rc;rc+=sgn*10;direction=sgn;formed=True
         if aggregation=="eachbrick":step(ro,rc)
      if aggregation=="eachbar":step(start,rc)
      if r["time"] in target:errors.append(st-target[r["time"]])
     e=np.array(errors[:-1]);out.append(dict(path=path,reverse=reverse,aggregation=aggregation,cap=cap,offset=offset,rmse=float(np.sqrt(np.mean(e*e))),mae=float(np.mean(abs(e))),exact=int(sum(abs(e)<1e-7)),count=len(e)))
out.sort(key=lambda x:x["rmse"]);(root/"custom_renko_probe_results.json").write_text(json.dumps(out[:40],indent=2));print(json.dumps(out[:5],indent=2))
