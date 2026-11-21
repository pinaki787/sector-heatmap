"""Research control: source true range referenced to prior constructed Renko close."""
import json,hashlib
from pathlib import Path
from indicator import RMA,Traditional
from replay_native_sizing_hypotheses import load_parents,normalize

def replay_feedback(bars,length):
    atr=RMA(length);engine=None;size=None;prices=[];last=None;timeline=[]
    seed=bars[0]['close']
    for bar in bars:
        previous=seed if engine is None else engine.level*engine.size
        tr=max(bar['high']-bar['low'],abs(bar['high']-previous),abs(bar['low']-previous))
        value=atr.update(tr);prices.append(bar)
        if value is None:continue
        calculated=normalize(value,'half_decade')
        if engine is None or calculated!=size:
            size=calculated;engine=Traditional(size);last=None
            for old in prices:
                for brick in engine.update(old['close']):last=dict(brick,time=old['time'],box=size)
        else:
            for brick in engine.update(bar['close']):last=dict(brick,time=bar['time'],box=size)
        timeline.append(dict(time=bar['time'],atr=value,size=size,previous_renko_close=previous))
    return dict(size=size,last=last,last_atr=value,timeline=timeline)

if __name__=='__main__':
    base=Path(__file__).parent
    bars,sources=load_parents()
    reference=json.loads((base/'evidence/native-box-update-diagnostic-20261120.json').read_text())
    cases=[]
    for control in reference['comparisons']:
        result=replay_feedback(bars,control['length'])
        # Verify prefix causality before treating the experiment as evidence.
        cut=len(bars)-5;prefix=replay_feedback(bars[:cut],control['length'])
        assert prefix['timeline']==[x for x in result['timeline'] if x['time']<=bars[cut-1]['time']]
        cases.append(dict(length=control['length'],computed_size=result['size'],observed_box=control['native_box'],
            match=result['size']==control['native_box'],last_atr=result['last_atr'],last_brick=result['last']))
    report=dict(status='RESEARCH_ONLY_PREVIOUS_RENKO_CLOSE_TR_CONTROL',parents=len(bars),cases=cases,
        matches=sum(c['match'] for c in cases),prefix_causality_checked=True,used_by_strategy=False,
        sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (base/'evidence/native-feedback-tr-control-20261120.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
