import csv,json,numpy as np,sys
from pathlib import Path
root=Path(__file__).parent
r=list(csv.DictReader(open(root/(sys.argv[1] if len(sys.argv)>1 else "btcusd_5m_auto_diagnostic_reload_20261104.csv"))))[:-1]
def col(k):return np.array([float(x[k]) for x in r])
o,h,l,c=[col(k) for k in ["open","high","low","close"]];y=col("SHAKTI Midline (clean)")
res=[];periods=np.arange(80,161)
sources={}
for name,v in {"close":c,"hl2":(h+l)/2,"hlc3":(h+l+c)/3,"ohlc4":(o+h+l+c)/4}.items():
 for length in [3,5,7,9]:
  sources[name+"_median"+str(length)]=np.array([np.median(v[max(0,i-length+1):i+1]) for i in range(len(v))])
for name,s in sources.items():
 for poles in range(2,5):
  beta=(1-np.cos(2*np.pi/periods))/(2**(1/poles)-1);a=-beta+np.sqrt(beta*beta+2*beta)
  lags=((periods-1)/(2*poles)).astype(int)
  for reduced in [False,True]:
   x=np.tile(s,(len(periods),1))
   if reduced:
    idx=np.maximum(np.arange(len(s))[None,:]-lags[:,None],0)
    x=2*x-s[idx]
   first=None
   for n in range(poles):
    z=np.empty_like(x);z[:,0]=x[:,0]
    for i in range(1,len(s)):z[:,i]=a*x[:,i]+(1-a)*z[:,i-1]
    x=z
    if n==0:first=z.copy()
   for fast in [False,True]:
    z=(x+first)/2 if fast else x;e=z[:,200:]-y[None,200:]
    scores=np.sqrt(np.mean(e*e,axis=1))
    for j in np.argsort(scores)[:3]:
     res.append(dict(source=name,poles=poles,period=int(periods[j]),reduced_lag=reduced,fast=fast,rmse=float(scores[j]),max=float(max(abs(e[j])))))
res.sort(key=lambda v:v["rmse"]);(root/("gaussian_median_results_"+(sys.argv[1] if len(sys.argv)>1 else "5m")+".json")).write_text(json.dumps(res[:40],indent=2));print(json.dumps(res[:5],indent=2))
