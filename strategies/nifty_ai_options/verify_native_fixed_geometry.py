"""Verify local fixed-box geometry against retained native research data."""
import json
from pathlib import Path
from indicator import Traditional
from replay_native_sizing_hypotheses import load_parents

def verify():
    base=Path(__file__).parent
    reference=json.loads((base/'evidence/native-brick-history-diagnostic-20261120.json').read_text())
    sizes={r['box'] for r in reference['bricks']}
    if len(sizes)!=1:raise ValueError('This control requires a single observed fixed box')
    size=sizes.pop()
    engine=Traditional(size);calculated=[]
    bars,_=load_parents()
    for bar in bars:
        for brick in engine.update(bar['close']):
            calculated.append(dict(time=bar['time'],open=brick['open'],close=brick['close']))
    comparisons=[]
    for brick in reference['bricks']:
        source_time=int(brick['time']/1000)
        matches=[i for i,b in enumerate(calculated) if b['time']==source_time and b['open']==brick['open'] and b['close']==brick['close']]
        comparisons.append(dict(reference=brick,matched_indices=matches,match=bool(matches)))
    return dict(status='FIXED_BOX_GEOMETRY_CONTROL_NOT_SIZING_PROOF',
        fixed_diagnostic_size=size,reference_bricks=len(comparisons),
        matches=sum(c['match'] for c in comparisons),latest_local=calculated[-3:],
        timestamp_comparison='Native millisecond duplicate-brick ordinals normalized to source-candle seconds',
        comparisons=comparisons,used_by_strategy=False)

if __name__=='__main__':
    report=verify()
    (Path(__file__).parent/'evidence/native-fixed-geometry-control-20261120.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('comparisons','latest_local')},indent=2))
    if report['matches']!=report['reference_bricks']:raise SystemExit('Native fixed geometry mismatch')
