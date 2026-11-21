import csv,numpy as np
from pathlib import Path
root=Path(__file__).parent
r=list(csv.DictReader(open(root/"btcusd_5m_auto_diagnostic_reload_20261104.csv")))[:-1]
y=np.array([float(x["SHAKTI Midline (clean)"]) for x in r]);c=np.array([float(x["close"]) for x in r]);st=np.array([float(x["MAHAKAAL Renko Supertrend"]) for x in r]);print("rows",len(y),"st",st[-8:]);d=np.diff(y)
s=[]
for n in range(2,301):
 a=2/(n+1);x=y[1:]+d*(1/a-1);flat=np.mean(abs(np.diff(x))<1e-7);s.append((flat,n,np.std(np.diff(x)),np.sqrt(np.mean((x-c[1:])**2))))
print("single EMA inverse",sorted(s,reverse=True)[:8])
s=[]
for n in range(2,101):
 a=2/(n+1);x=y[1:]+d*(1/a-1)
 for m in range(n,101):
  b=2/(m+1);z=x[1:]+np.diff(x)*(1/b-1);flat=np.mean(abs(np.diff(z))<1e-6)
  s.append((flat,n,m,np.std(np.diff(z)),np.sqrt(np.mean((z-c[2:])**2))))
print("double EMA inverse",sorted(s,reverse=True)[:8]);print("last mid",y[-8:])
