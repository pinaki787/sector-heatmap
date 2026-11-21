"""Audit preserved raw data offline. No FYERS/network calls."""
import json
from pathlib import Path
from datetime import datetime
from run import IST,atomic,normalize
out=Path(__file__).resolve().parent/'evidence/timeframes';report=[]
for path in sorted(out.glob('*m-raw.json')):
    rows=json.loads(path.read_text())['candles'];unique={};conflicts=[];volume_conflicts=[]
    for r in rows:
        if r[0] in unique:
            if r[:5]!=unique[r[0]][:5]:conflicts.append(dict(ist=datetime.fromtimestamp(r[0],IST).isoformat(),a=unique[r[0]],b=r))
            elif r[5]!=unique[r[0]][5]:volume_conflicts.append(r[0])
        else:unique[r[0]]=r
    regular=[r for r in unique.values() if 555<=datetime.fromtimestamp(r[0],IST).hour*60+datetime.fromtimestamp(r[0],IST).minute<930]
    report.append(dict(file=path.name,raw_rows=len(rows),unique_rows=len(unique),regular_session_rows=len(regular),outside_regular=len(unique)-len(regular),ohlc_conflicts=conflicts,volume_conflicts=volume_conflicts))
atomic(out/'recorded-conflicts.json',report)
print(json.dumps(dict(files=len(report),ohlc_conflicting_files=[r['file'] for r in report if r['ohlc_conflicts']],outside_session_rows=sum(r['outside_regular'] for r in report)),indent=2))
