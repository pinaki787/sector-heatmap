import csv,json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
base=Path(__file__).parent;rows=list(csv.DictReader((base/'hcl_tradingview_5m.csv').open()));out=[];atr=None;trs=[]
for i,r in enumerate(rows):
 t=int(float(r['time'])); o,h,l,c=[float(r[k]) for k in ['open','high','low','close']]
 tr=max(h-l,abs(h-float(rows[i-1]['close'])),abs(l-float(rows[i-1]['close']))) if i else h-l
 trs.append(tr);prevAtr=atr
 atr=sum(trs[:14])/14 if i==13 else (atr*13+tr)/14 if atr is not None else None
 if i<8 or prevAtr is None:continue
 prev=rows[i-3:i]; hi=max(float(z['high']) for z in prev);lo=min(float(z['low']) for z in prev)
 date=lambda z:datetime.fromtimestamp(int(float(z['time'])),ZoneInfo('Asia/Kolkata')).date()
 ready=date(prev[0])==date(r) and hi>lo and hi-lo<=prevAtr*1.6 and max(abs(float(z['close'])-float(z['open'])) for z in prev)<=prevAtr*.8 and abs(float(prev[-1]['close'])-float(prev[0]['open']))<=prevAtr*.8
 if not ready:continue
 down=c<lo and c<o and (lo-c>=prevAtr*.4 or o-c>=prevAtr*.4)
 up=c>hi and c>o and (c-hi>=prevAtr*.4 or c-o>=prevAtr*.4)
 incoming=float(rows[i-4]['close'])-float(rows[i-7]['close'])
 candidate=lo<=c<=hi and abs(incoming)>prevAtr*.8
 if down or up or candidate:
  out.append(dict(time=datetime.fromtimestamp(t,ZoneInfo('Asia/Kolkata')).isoformat(),lo=lo,hi=hi,kind='supply' if down else 'demand' if up else 'demand candidate' if incoming<0 else 'supply candidate'))
(base/'base_zone_audit.json').write_text(json.dumps(out,indent=2))
for z in out:
 if z['time'].startswith(('2026-11-04','2026-11-09')):print(z)
