"""Fit the symmetric Shakti envelope to Gaussian-filtered True Range."""
import csv,json,numpy as np
from pathlib import Path
root=Path(__file__).parent
r=list(csv.DictReader(open(root/"btcusd_5m_jumpclean_on_20261104.csv")))[:-1]
def col(k):return np.array([float(x[k]) for x in r])
h,l,c=[col(k) for k in ["high","low","close"]]
w=(col("SHAKTI Upper Envelope")-col("SHAKTI Lower Envelope"))/2
tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))));tr[0]=h[0]-l[0]
periods=np.arange(3,301);out=[]
for name,s in {"tr":tr,"range":h-l}.items():
 for poles in range(1,10):
  beta=(1-np.cos(2*np.pi/periods))/(2**(1/poles)-1);a=-beta+np.sqrt(beta*beta+2*beta)
  x=np.tile(s,(len(periods),1));first=None
  for n in range(poles):
   z=np.empty_like(x);z[:,0]=x[:,0]
   for i in range(1,len(s)):z[:,i]=a*x[:,i]+(1-a)*z[:,i-1]
   x=z
   if n==0:first=z.copy()
  for fast in [False,True]:
   z=(x+first)/2 if fast else x;xx=z[:,500:];ww=w[500:]
   mul=np.sum(xx*ww[None,:],axis=1)/np.sum(xx*xx,axis=1)
   e=xx*mul[:,None]-ww[None,:];score=np.sqrt(np.mean(e*e,axis=1))
   for j in np.argsort(score)[:3]:out.append(dict(source=name,poles=poles,period=int(periods[j]),fast=fast,multiplier=float(mul[j]),rmse=float(score[j]),max_error=float(max(abs(e[j])))))
out.sort(key=lambda v:v["rmse"]);(root/"envelope_gaussian_results.json").write_text(json.dumps(out[:30],indent=2));print(json.dumps(out[:4],indent=2))
