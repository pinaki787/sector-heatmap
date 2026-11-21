"""Fit observable recurrences; no trading actions. In-sample fits are not parity proof."""
import csv,json,sys
from pathlib import Path
import numpy as np
root=Path(__file__).parent
sample=sys.argv[1] if len(sys.argv)>1 else "btcusd_5m_diagnostic_20261104.csv"
rows=list(csv.DictReader((root/sample).open()))[:-1]
def col(k):return np.array([float(r[k]) if r[k] else np.nan for r in rows])
o,h,l,c=[col(k) for k in ["open","high","low","close"]]
y=col("SHAKTI Midline (clean)")
sources={"close":c,"hl2":(h+l)/2,"hlc3":(h+l+c)/3,"ohlc4":(o+h+l+c)/4}
models=[]
# Difference series avoids ill-conditioned price-level regression.
for name,x in sources.items():
 for p in range(1,9):
  for q in range(0,5):
   n=max(p,q)+1
   A=np.column_stack([np.diff(y)[n-i:-i or None] for i in range(1,p+1)]+[np.diff(x)[n-j:len(x)-1-j or None] for j in range(q+1)])
   z=np.diff(y)[n:]
   cut=int(len(z)*.7)
   coef=np.linalg.lstsq(A[:cut],z[:cut],rcond=None)[0]
   err=A@coef-z
   models.append(dict(source=name,p=p,q=q,train_rmse=float(np.sqrt(np.mean(err[:cut]**2))),holdout_rmse=float(np.sqrt(np.mean(err[cut:]**2))),coef=coef.tolist()))
models.sort(key=lambda m:m["holdout_rmse"])
tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))));tr[0]=h[0]-l[0]
w=(col("SHAKTI Upper Envelope")-col("SHAKTI Lower Envelope"))/2
atr=[]
for length in range(1,101):
 rma=np.empty(len(c));rma[:]=np.nan;rma[length-1]=tr[:length].mean()
 for i in range(length,len(c)):rma[i]=(rma[i-1]*(length-1)+tr[i])/length
 a=rma[200:];b=w[200:];mul=float(a@b/(a@a));error=float(np.sqrt(np.mean((a*mul-b)**2)))
 atr.append(dict(length=length,multiplier=mul,rmse=error))
atr.sort(key=lambda m:m["rmse"])
result={"rows":len(rows),"recurrence_models":models[:15],"envelope_atr_models":atr[:10]}
(root/("shakti_fit_"+sample+".json")).write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
