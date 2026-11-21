"""Direct bounded FYERS HTTP GET verification, bypasses SDK response handling."""
from pathlib import Path
import json,time
from run import client,ok,atomic
from sector_heatmap.fyers_history import history
out=Path(__file__).parent/'evidence/readiness-provider';api=client('bf46fc364b610a0dfd338419e133cb41');reports=[]
try:
    for name,dates in [('direct-http-day',dict(date_format=1,range_from='2026-11-19',range_to='2026-11-19')),
                       ('exact-minute-a',dict(date_format=0,range_from='1795064520',range_to='1795064520')),
                       ('exact-minute-b',dict(date_format=0,range_from='1795064520',range_to='1795064520'))]:
        raw=ok(history(api,dict(symbol='NSE:NIFTY26NOV25850CE',resolution='1',cont_flag=0,**dates)))
        atomic(out/(name+'.json'),raw)
        groups={}
        for r in raw.get('candles',[]):groups.setdefault(r[0],[]).append(r)
        reports.append(dict(query=name,rows=len(raw.get('candles',[])),unique=len(groups),target_rows=groups.get(1795064520,[]),conflicts=[k for k,v in groups.items() if any(r[:5]!=v[0][:5] for r in v)]))
        time.sleep(.4)
    atomic(out/'direct-http-report.json',reports);print(json.dumps(reports,indent=2))
finally:api._sector_pulse_ipv4_session.close()
