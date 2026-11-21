"""Invert Gaussian recurrences to test piecewise-constant synthetic-price input."""
import csv,json,math,numpy as np
from pathlib import Path
root=Path(__file__).parent
r=list(csv.DictReader(open(root/"btcusd_5m_jumpclean_on_20261104.csv")))[:-1]
y=np.array([float(x["SHAKTI Midline (clean)"]) for x in r])
c=np.array([float(x["close"]) for x in r])
out=[]
for poles in range(1,7):
 for period in range(5,501):
  for norm in [2**(1/poles),1.414**(2/poles)]:
   beta=(1-np.cos(2*np.pi/period))/(norm-1);a=-beta+np.sqrt(beta*beta+2*beta);b=1-a
   weights=np.array([(-1)**k*math.comb(poles,k)*b**k for k in range(poles+1)])
   x=np.convolve(y,weights,"valid")/a**poles
   dx=abs(np.diff(x));warm=200
   dx=dx[warm:]
   tolerance=max(1e-6,1e-9/a**poles)
   out.append(dict(poles=poles,period=period,norm=float(norm),alpha=float(a),flat_fraction=float(np.mean(dx<tolerance)),flat_tolerance=tolerance,small_delta=float(np.quantile(dx,.1)),median_delta=float(np.median(dx)),input_close_rmse=float(np.sqrt(np.mean((x[warm:]-c[poles+warm:])**2)))))
out.sort(key=lambda v:(-v["flat_fraction"],v["small_delta"]))
(root/"gaussian_inverse_step_results.json").write_text(json.dumps(out[:40],indent=2));print(json.dumps(out[:5],indent=2))
