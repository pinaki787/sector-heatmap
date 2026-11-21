import csv,json
from pathlib import Path
import numpy as np
root=Path(__file__).parent
rows=list(csv.DictReader((root/"btcusd_5m_visual_paired_wide_20261104.csv").open()))[:-30]
def col(k):return np.array([float(r[k]) for r in rows])
o,h,l,c=[col(k) for k in ["open","high","low","close"]]
y=col("SHAKTI Midline (clean)")
sources={"close":c,"hl2":(h+l)/2,"hlc3":(h+l+c)/3,"ohlc4":(o+h+l+c)/4}
linear=[]
for name,x in sources.items():
 dy=np.diff(y);dx=np.diff(x)
 for p in [1,2,3,4,6,8]:
  for q in [0,1,2,4,8,16,32,64,100,200,300]:
   n=max(p,q)+1
   A=np.column_stack([dy[n-i:-i or None] for i in range(1,p+1)]+[dx[n-j:len(dx)-j or None] for j in range(q+1)])
   z=dy[n:];cut=int(len(z)*.7)
   coef=np.linalg.lstsq(A[:cut],z[:cut],rcond=None)[0]
   err=A@coef-z
   linear.append(dict(source=name,p=p,q=q,train_rmse=float(np.sqrt(np.mean(err[:cut]**2))),holdout_rmse=float(np.sqrt(np.mean(err[cut:]**2)))))
linear.sort(key=lambda m:m["holdout_rmse"])
fast,slow=np.meshgrid(np.arange(2,11),np.arange(10,201,5))
fast=fast.ravel();slow=slow.ravel()
valid=slow>fast;fast=fast[valid];slow=slow[valid]
kama=[]
for name,x in sources.items():
 for period in range(2,101):
  change=abs(x-np.roll(x,period));noise=np.convolve(abs(np.diff(x,prepend=x[0])),np.ones(period),"full")[:len(x)]
  er=np.divide(change,noise,out=np.zeros_like(change),where=noise!=0);er[:period]=0
  state=np.full(len(fast),y[0]);sums=np.zeros(len(fast));maxerr=np.zeros(len(fast))
  for i in range(1,len(x)):
   alpha=(er[i]*(2/(fast+1)-2/(slow+1))+2/(slow+1))**2
   state+=alpha*(x[i]-state)
   if i>=500:
    e=state-y[i];sums+=e*e;maxerr=np.maximum(maxerr,abs(e))
  scores=np.sqrt(sums/(len(x)-500));j=int(np.argmin(scores))
  kama.append(dict(source=name,period=period,fast=int(fast[j]),slow=int(slow[j]),rmse=float(scores[j]),max_error=float(maxerr[j])))
kama.sort(key=lambda m:m["rmse"])
result=dict(rows=len(rows),linear=linear[:12],kama=kama[:12],note="Models are hypotheses; exact parity requires residuals at numerical tolerance and independent samples.")
(root/"wide_model_results.json").write_text(json.dumps(result,indent=2))
print(json.dumps(dict(rows=len(rows),linear=linear[:3],kama=kama[:3]),indent=2))
