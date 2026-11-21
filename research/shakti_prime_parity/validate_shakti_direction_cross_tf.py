import csv,json,numpy as np
from pathlib import Path
r=Path(__file__).parent
out=[]
for name in ["btcusd_2m_diagnostic_20261104.csv","btcusd_5m_jumpclean_on_20261104.csv"]:
 rows=list(csv.DictReader(open(r/name)))[:-1]
 c=np.array([float(x["close"]) for x in rows]);h=np.array([float(x["high"]) for x in rows]);l=np.array([float(x["low"]) for x in rows])
 target=np.array([float(x["SHAKTI Midline (clean)"]) for x in rows]);st=np.array([float(x["MAHAKAAL Renko Supertrend"]) for x in rows])
 beta=(1-np.cos(2*np.pi/123))/(2**(1/3)-1);a=-beta+np.sqrt(beta*beta+2*beta);g=c.copy()
 for n in range(3):
  for i in range(1,len(g)):g[i]=a*g[i]+(1-a)*g[i-1]
 warm=min(250,len(rows)//2);agree=np.sign(np.diff(g)[warm:])==np.sign(np.diff(target)[warm:])
 out.append(dict(sample=name,model="Gaussian3period123close",compared=len(agree),direction_matches=int(sum(agree)),direction_agreement=float(np.mean(agree)),price_rmse=float(np.sqrt(np.mean((g[warm:]-target[warm:])**2)))))
(r/"dashboard_shakti_cross_timeframe.json").write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
