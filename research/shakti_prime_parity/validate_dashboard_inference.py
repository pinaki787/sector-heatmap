"""Evaluate dashboard direction proxies; original numerical engines remain unmatched."""
import csv,json,numpy as np
from pathlib import Path
root=Path(__file__).parent
def read(name):return list(csv.DictReader(open(root/name)))[:-1]
rows=read("btcusd_5m_jumpclean_on_20261104.csv")
c=np.array([float(r["close"]) for r in rows]);h=np.array([float(r["high"]) for r in rows]);l=np.array([float(r["low"]) for r in rows])
refmid=np.array([float(r["SHAKTI Midline (clean)"]) for r in rows]);refst=np.array([float(r["MAHAKAAL Renko Supertrend"]) for r in rows])
cut=int(len(rows)*.7);warm=250;out=[]
for poles in range(1,7):
 for period in range(20,201):
  beta=(1-np.cos(2*np.pi/period))/(2**(1/poles)-1);a=-beta+np.sqrt(beta*beta+2*beta);z=c.copy()
  for _ in range(poles):
   for i in range(1,len(z)):z[i]=a*z[i]+(1-a)*z[i-1]
  agree=np.sign(np.diff(z))==np.sign(np.diff(refmid))
  out.append(dict(poles=poles,period=period,train_agreement=float(np.mean(agree[warm:cut])),holdout_agreement=float(np.mean(agree[cut:])),rmse=float(np.sqrt(np.mean((z[warm:]-refmid[warm:])**2)))))
out.sort(key=lambda v:(-v["train_agreement"],v["rmse"]))
# Baseline candle Supertrend: explicitly evaluated against source direction.
tr=np.maximum(h-l,np.maximum(abs(h-np.roll(c,1)),abs(l-np.roll(c,1))));tr[0]=h[0]-l[0]
atr=np.empty(len(c));atr[:14]=np.mean(tr[:14])
for i in range(14,len(c)):atr[i]=(atr[i-1]*13+tr[i])/14
stmodels=[]
for factor in np.arange(1,6.01,.1):
 upper=(h+l)/2+factor*atr;lower=(h+l)/2-factor*atr;direction=np.ones(len(c))
 for i in range(1,len(c)):
  if upper[i]>=upper[i-1] and c[i-1]<=upper[i-1]:upper[i]=upper[i-1]
  if lower[i]<=lower[i-1] and c[i-1]>=lower[i-1]:lower[i]=lower[i-1]
  direction[i]=(-1 if c[i]>upper[i] else 1) if direction[i-1]==1 else (1 if c[i]<lower[i] else -1)
 pred=-direction;truth=np.where(c>refst,1,-1)
 stmodels.append(dict(factor=float(factor),train_agreement=float(np.mean(pred[warm:cut]==truth[warm:cut])),holdout_agreement=float(np.mean(pred[cut:]==truth[cut:]))))
stmodels.sort(key=lambda v:-v["train_agreement"])
native=read("btcusd_5m_native_probe_20261104.csv");ntruth=np.array([float(r["close"])>float(r["MAHAKAAL Renko Supertrend"]) for r in native]);npred=np.array([float(r["PROBE Native FIX10 Close"])>float(r["PROBE Native FIX10 ST"]) for r in native])
report=dict(sample="btcusd_5m_jumpclean_on_20261104.csv",rows=len(rows),warmup=warm,split=cut,shakti_candidates=out[:10],candle_st_candidates=stmodels[:10],native_fixed10_direction=dict(sample="btcusd_5m_native_probe_20261104.csv",rows=len(native),agreement=float(np.mean(ntruth==npred))),limitations=["Directional agreement is not line-value parity.","MarketRegime and Alignment vote rules are observational hypotheses, not yet replay-verified across transitions."])
(root/"dashboard_inference_validation.json").write_text(json.dumps(report,indent=2))
print(json.dumps(dict(shakti=out[:3],candleST=stmodels[:3],native=report["native_fixed10_direction"]),indent=2))
