"""Test volume-normalized Gaussian channels; no candidate code changes."""
import csv,json,numpy as np
from pathlib import Path
root=Path(__file__).parent
rows=list(csv.DictReader(open(root/"btcusd_5m_jumpclean_on_20261104.csv")))[:-1]
def col(k):return np.array([float(r[k]) for r in rows])
o,h,l,c=[col(k) for k in ["open","high","low","close"]];v=col("Volume");y=col("SHAKTI Midline (clean)")
periods=np.arange(40,251);out=[];warm=500
def filt(x,a,n):
 z=np.tile(x,(len(a),1))
 for _ in range(n):
  for i in range(1,len(x)):z[:,i]=a*z[:,i]+(1-a)*z[:,i-1]
 return z
for power in [.25,.5,1.0]:
 w=np.maximum(v,1)**power
 for poles in range(1,7):
  beta=(1-np.cos(2*np.pi/periods))/(2**(1/poles)-1);a=-beta+np.sqrt(beta*beta+2*beta)
  den=filt(w,a,poles)
  for name,x in {"close":c,"hl2":(h+l)/2,"hlc3":(h+l+c)/3,"ohlc4":(o+h+l+c)/4}.items():
   z=filt(x*w,a,poles)/den;e=z[:,warm:]-y[None,warm:];scores=np.sqrt(np.mean(e*e,axis=1))
   for j in np.argsort(scores)[:2]:
    out.append(dict(source=name,volume_power=power,poles=poles,period=int(periods[j]),rmse=float(scores[j]),max_error=float(max(abs(e[j]))),exact=int(sum(abs(e[j])<1e-8)),compared=len(e[j])))
out.sort(key=lambda r:r["rmse"]);(root/"gaussian_volume_results.json").write_text(json.dumps(out[:30],indent=2));print(json.dumps(out[:3],indent=2))
