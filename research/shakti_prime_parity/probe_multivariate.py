import csv,json,numpy as np
from pathlib import Path
root=Path(__file__).parent
r=list(csv.DictReader(open(root/"btcusd_5m_auto_diagnostic_reload_20261104.csv")))[:-1]
cols=lambda k:np.array([float(x[k]) for x in r])
y=cols("SHAKTI Midline (clean)")
X=np.column_stack([cols(k) for k in ["open","high","low","close"]])
dy=np.diff(y);dx=np.diff(X,axis=0);out=[]
for p in [1,2,3,4,6,8]:
 for q in [0,1,2,4,8,16,30]:
  n=max(p,q)+1
  A=np.column_stack([dy[n-i:-i or None] for i in range(1,p+1)]+[dx[n-j:len(dx)-j or None,:] for j in range(q+1)])
  z=dy[n:];cut=int(len(z)*.7);coef=np.linalg.lstsq(A[:cut],z[:cut],rcond=None)[0];err=A@coef-z
  out.append(dict(p=p,q=q,train=float(np.sqrt(np.mean(err[:cut]**2))),holdout=float(np.sqrt(np.mean(err[cut:]**2))),coef=coef.tolist()))
out.sort(key=lambda x:x["holdout"]);(root/"midline_multivariate_fit.json").write_text(json.dumps(out,indent=2))
print(json.dumps(out[:2],indent=2))
