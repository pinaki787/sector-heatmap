"""Offline exact-parent input comparison; never writes a usable sizing reference."""
import json,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

def compare(source,tv):
    unique={};duplicates=0
    for row in source:
        stamp=row[0]
        if stamp in unique:
            if unique[stamp]!=row:raise ValueError('Conflicting parent-source timestamp')
            duplicates+=1
        else:unique[stamp]=row
    names={x['title']:x['id'] for x in tv['metainfo']['plots']}
    parents={}
    for row in tv['values']:
        values=row['plots'];t=values.get(names['Parent open timestamp'])
        if t is None:continue
        parents[int(t/1000)]={k:values.get(names[k]) for k in
            ('Parent open','Parent high','Parent low','Parent close','Ordinary parent ATR5','Standard parent close timestamp')}
    result=[]
    for start,reference in sorted(parents.items()):
        end=int(reference['Standard parent close timestamp']/1000)
        rows=sorted([r for t,r in unique.items() if start<=t<end],key=lambda r:r[0])
        if not rows:continue
        expected=list(range(start,end,900))
        complete=[r[0] for r in rows]==expected
        actual=dict(open=rows[0][1],high=max(r[2] for r in rows),low=min(r[3] for r in rows),close=rows[-1][4])
        difference={k:actual[k]-reference['Parent '+k] for k in actual}
        result.append(dict(start=datetime.fromtimestamp(start,ZoneInfo('Asia/Kolkata')).isoformat(),
            end=datetime.fromtimestamp(end,ZoneInfo('Asia/Kolkata')).isoformat(),
            source_rows=len(rows),complete=complete,missing_timestamps=sorted(set(expected)-set(r[0] for r in rows)),
            unexpected_timestamps=sorted(set(r[0] for r in rows)-set(expected)),
            fyers=actual,tradingview={k:reference['Parent '+k] for k in actual},difference=difference))
    return dict(status='READ_ONLY_PARENT_INPUT_COMPARISON',duplicate_identical_rows=duplicates,
        unique_source_rows=len(unique),parents=result,
        exact_ohlc_matches=sum(all(value==0 for value in row['difference'].values()) for row in result),
        complete_compared=sum(row['complete'] for row in result),uses_reference_cache=False)

if __name__=='__main__':
    base=Path(__file__).parent
    path=base/'evidence/20261120/history-15m.json';raw=path.read_bytes()
    tv=json.loads(Path('/home/trading/sector-heatmap/.private/nifty-ai-options/tradingview/native-parent-diagnostic-response-20261120.json').read_text())['structuredContent']
    out=compare(json.loads(raw)['candles'],tv)
    out.update(source=str(path),source_sha256=hashlib.sha256(raw).hexdigest())
    (base/'evidence/native-parent-input-comparison-20261120.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='parents'},indent=2))
