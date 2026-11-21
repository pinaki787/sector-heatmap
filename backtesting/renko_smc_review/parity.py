import sys,json,time,os
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'backtesting/renko_regime_risk'))
import run as risk
from model import simulate,EXITS
if __name__=='__main__':
 risk.initialize();EXITS['Fixed3_1_5']=dict(hard=3.,target=1.5)
 out={}
 for profile,entry,exit_name,old in [('existing','Baseline','SelectedExits','Baseline_SelectedExits'),('calibrated','overlap_130','Fixed3_1_5','overlap_130_HighWin_stop3.0_target1.5')]:
  started=time.time();r=simulate(risk.HOSTS,risk.MINUTES,risk.CONFIG,entry,exit_name,risk.START)
  prior=json.loads((ROOT/'backtesting/renko_regime_risk/trials'/f'{old}.json').read_text())
  keys=('entry_at','exit_at','entry_price','exit_price','direction','gross_points')
  identical=[{k:t[k] for k in keys}for t in r['trades']]==[{k:t[k]for k in keys}for t in prior['trades']]
  out[profile]=dict(exact_trade_match=identical,seconds=time.time()-started,summary=r['splits']['all']['2'])
  (HERE/f'{profile}-control.json').write_text(json.dumps(r))
  (HERE/'parity.json').write_text(json.dumps(out,indent=2));print(profile,out[profile],flush=True)
