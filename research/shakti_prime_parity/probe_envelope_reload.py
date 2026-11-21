import csv,json,numpy as np
from pathlib import Path
root=Path(__file__).parent
rows=list(csv.DictReader(open(root/"btcusd_5m_auto_diagnostic_reload_20261104.csv")))[:-1]
def col(k): return np.array([float(r[k]) for r in rows])
o,h,l,c=[col(k) for k in ["open","high","low","close"]]
y=col("SHAKTI Midline (clean)");u=col("SHAKTI Upper Envelope");lo=col("SHAKTI Lower Envelope");w=(u-lo)/2
print("envelope symmetry max",max(abs((u+lo)/2-y)))
tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))));tr[0]=h[0]-l[0]
sources={"tr":tr,"range":h-l,"absclose":abs(np.diff(c,prepend=c[0]))}
res=[]
for name,x in sources.items():
 for n in range(1,201):
  for typ,a in [("EMA",2/(n+1)),("RMA",1/n)]:
   z=np.empty(len(x));z[0]=x[0]
   for i in range(1,len(z)): z[i]=a*x[i]+(1-a)*z[i-1]
   for lag in range(0,4):
    xx=z[300-lag:len(z)-lag or None];ww=w[300:];m=xx@ww/(xx@xx);err=m*xx-ww
    res.append({"input":name,"length":n,"filter":typ,"lag":lag,"multiplier":float(m),"rmse":float(np.sqrt(np.mean(err**2))),"max":float(max(abs(err)))})
res.sort(key=lambda d:d["rmse"]);print(json.dumps(res[:8],indent=2))
(root/"envelope_reload_fit.json").write_text(json.dumps(res[:30],indent=2))
