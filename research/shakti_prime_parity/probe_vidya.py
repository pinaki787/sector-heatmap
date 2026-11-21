"""Test CMO-adaptive VIDYA and post-SMA hypotheses against untouched Shakti exports."""
import csv,json,sys
from pathlib import Path
import numpy as np
root=Path(__file__).parent
sample=sys.argv[1] if len(sys.argv)>1 else "btcusd_5m_auto_diagnostic_reload_20261104.csv"
rows=list(csv.DictReader(open(root/sample)))[:-1]
def col(k):return np.array([float(r[k]) for r in rows])
o,h,l,c=[col(k) for k in ["open","high","low","close"]];y=col("SHAKTI Midline (clean)")
lengths=np.arange(2,101);momenta=np.arange(2,101)
period,mom=np.meshgrid(lengths,momenta);period=period.ravel();mom=mom.ravel()
results=[]
warm=min(500,len(y)//2)
for name,x in {"close":c,"hl2":(h+l)/2,"hlc3":(h+l+c)/3,"ohlc4":(o+h+l+c)/4}.items():
 d=np.diff(x,prepend=x[0]);up=np.r_[0,np.cumsum(np.maximum(d,0))];dn=np.r_[0,np.cumsum(np.maximum(-d,0))]
 alpha=np.empty((len(momenta),len(x)))
 for j,m in enumerate(momenta):
  end=np.arange(1,len(x)+1);start=np.maximum(0,end-m)
  u=up[end]-up[start];v=dn[end]-dn[start]
  alpha[j]=np.divide(abs(u-v),u+v,out=np.zeros(len(x)),where=u+v!=0)
 z=np.empty((len(period),len(x)));z[:,0]=x[0]
 for i in range(1,len(x)):
  a=2/(period+1)*alpha[mom-2,i]
  z[:,i]=z[:,i-1]+a*(x[i]-z[:,i-1])
 sums=np.pad(np.cumsum(z,axis=1),((0,0),(1,0)))
 for post in [1,2,3,5,8,10,14,15,20,30,40]:
  end=np.arange(1,len(x)+1);start=np.maximum(0,end-post)
  smooth=(sums[:,end]-sums[:,start])/(end-start)
  e=smooth[:,warm:]-y[None,warm:]
  score=np.sqrt(np.mean(e*e,axis=1))
  for j in np.argsort(score)[:3]:
   results.append(dict(source=name,length=int(period[j]),momentum=int(mom[j]),post_sma=post,rmse=float(score[j]),max_error=float(max(abs(e[j]))),exact=int(sum(abs(e[j])<1e-8)),compared=len(e[j])))
results.sort(key=lambda m:m["rmse"])
report=dict(sample=sample,rows=len(rows),warmup=warm,models=results[:30],accepted=False)
(root/("vidya_results_"+sample+".json")).write_text(json.dumps(report,indent=2))
print(json.dumps(dict(sample=sample,best=results[:4]),indent=2))
