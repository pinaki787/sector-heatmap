from pathlib import Path
import json,sys,datetime
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(OUT));import replay
sys.path.insert(0,str(ROOT/'backtesting/nifty_atm_options'));from expiry_calendar import expected_weekly_expiry
rows,days,_=replay.load_underlying();quotes,surface,coverage=replay.load_options(days[0],days[-1]);requests=[]
for mode in ('auto','manual'):
 result=json.loads((OUT/(mode+'.json')).read_text())
 for issue in result['audit']:
  at=issue['at'];day=replay.day(at);expiry=expected_weekly_expiry(datetime.date.fromisoformat(day));side=issue['side']
  if issue['type'] in ('MISSING_EXIT_PRICE','MISSING_MARK'):strikes=[issue['strike']]
  elif issue['type']=='TARGET_OUTSIDE_AVAILABLE_SURFACE':
   candidates=surface[(at-60,side)]
   edge=min(k for k,q in candidates) if side=='PUT' else max(k for k,q in candidates)
   strikes=[edge+(-1 if side=='PUT' else 1)*50*i for i in range(1,6)]
  else:continue
  requests += [dict(day=day,expiry=expiry,side=side,strike=k) for k in strikes]
requests=list({(r['day'],r['expiry'],r['side'],r['strike']):r for r in requests}.values())
(OUT/'repair_requests.json').write_text(json.dumps(requests,indent=2));print('Exact-contract requests',len(requests),flush=True)
