"""Persistent offline comparison fixture for exact NEW chart Renko + Pine runtime."""
import json,math,sys
from pathlib import Path
from indicator import Traditional,AIRenko
root=Path(__file__).resolve().parent
raw=json.loads((root/'evidence/20261120/history-15m.json').read_text())['candles']
unique={r[0]:r for r in raw}
bars=[dict(time=r[0],open=r[1],high=r[2],low=r[3],close=r[4],volume=r[5]) for r in sorted(unique.values())]
reference=float(sys.argv[1]) if len(sys.argv)>1 else 400
size=reference/12
renko=Traditional(size);ai=AIRenko(manual_brick=size,pine_series_precision=True);bricks=[];result=[]
for bar in bars:
    for brick in renko.update(bar['close']):
        bricks.append(dict(brick,time=len(bricks)+1,sourceTime=bar['time'],provisional=False,historyOnly=False))
        result.append(ai.update(brick))
(root/'evidence/chart-fixture.json').write_text(json.dumps(dict(bars=bars,size=size,bricks=bricks,expected=result)))
print(json.dumps(dict(source_rows=len(bars),bricks=len(bricks),baseline=reference)))
