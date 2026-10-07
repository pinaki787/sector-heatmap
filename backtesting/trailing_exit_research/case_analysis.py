import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
OUT=Path(__file__).resolve().parent;IST=ZoneInfo('Asia/Kolkata')
quotes={}
for p in OUT.glob('case_history_*.json'):
 d=json.loads(p.read_text());quotes[d['symbol']]=d['response'].get('candles',[])
results=[]
for t in json.loads((OUT/'journal_cases.json').read_text()):
 e,x=t['entry_time'],t['exit_time'];p=t['entry_price'];unit=t['entry_filled']*t['quantity_multiplier'];q=quotes.get(t['symbol'],[])
 inside=[r for r in q if r[0]>=e and r[0]+60<=x];boundary=[r for r in q if r[0]<x and r[0]+60>e]
 bound=max([r[2] for r in boundary],default=p);peak=max([r[4] for r in inside],default=p)
 future=[r for r in q if x<=r[0]<=x+1800]
 results.append(dict(symbol=t['symbol'],entry_time=datetime.fromtimestamp(e,IST).isoformat(),exit_time=datetime.fromtimestamp(x,IST).isoformat(),entry_premium=p,units=unit,actual_paper_gross=t['realized_pnl'],actual_cost_available=t['costs']['available'],peak_interior_close_gross=(peak-p)*unit,overlapping_candle_high_upper_bound_gross=(bound-p)*unit,upper_bound_gain_pct=100*(bound/p-1),gain_required_20pct=p*.2*unit,highest_next30m_close=max([r[4] for r in future],default=None),exit_reason=t['exit_reasons'],trail_20pct_can_activate=bound>=p*1.2,peak_disclaimer='Interior closes are trade prices, not executable bids; boundary OHLC includes pre-fill/post-exit ticks. Upper bound is not verified exposure MFE.'))
(OUT/'case_results.json').write_text(json.dumps(results,indent=2))
for r in results:
 if 100<=r['actual_paper_gross']<=125 or 2000<=r['actual_paper_gross']<=2250:print(json.dumps(r,indent=2))
