"""Offline hypotheses for native ATR box update rules. NOT a sizing provider."""
import json,math,hashlib
from pathlib import Path
from datetime import datetime,timezone,timedelta
from indicator import RMA,Traditional
ROOT=Path('/home/trading/sector-heatmap')
BASE=Path(__file__).parent
IST=timezone(timedelta(hours=5.5))

def parents(rows,step):
    days={}
    for row in rows:
        date=datetime.fromtimestamp(row[0],IST);minute=date.hour*60+date.minute
        if 555<=minute<915:
            slots=days.setdefault(date.date().isoformat(),{})
            if minute in slots and slots[minute]!=row:raise ValueError('Conflicting source row')
            slots[minute]=row
    output={}
    for date,slots in days.items():
        if set(slots)!=set(range(555,915,step)):continue
        bars=[slots[k] for k in sorted(slots)]
        output[date]=dict(time=bars[0][0],open=bars[0][1],high=max(r[2] for r in bars),low=min(r[3] for r in bars),close=bars[-1][4])
    return output

def normalize(value,rule):
    if rule=='tick':return math.floor(value/.05+.5)*.05
    quantum=.5*10**math.floor(math.log10(value))
    return math.floor(value/quantum+.5)*quantum

def replay_rebuild(bars,length,rule):
    atr=RMA(length);previous=None;engine=None;size=None;prices=[];bricks=[];resizes=[]
    for bar in bars:
        price=bar['close']
        tr=bar['high']-bar['low'] if previous is None else max(bar['high']-bar['low'],abs(bar['high']-previous),abs(bar['low']-previous))
        previous=price;prices.append(bar)
        value=atr.update(tr)
        if value is None:continue
        calculated=normalize(value,rule)
        if engine is None:
            size=calculated;engine=Traditional(size)
            for old in prices:
                for brick in engine.update(old['close']):bricks.append(dict(brick,time=old['time'],box=size,atr=value))
            continue
        emitted=engine.update(price)
        if emitted and calculated!=size:
            resizes.append(dict(time=bar['time'],previous=size,next=calculated))
            size=calculated;engine=Traditional(size);bricks=[]
            for old in prices:
                for brick in engine.update(old['close']):bricks.append(dict(brick,time=old['time'],box=size,atr=value))
        else:
            for brick in emitted:bricks.append(dict(brick,time=bar['time'],box=size,atr=value))
    return dict(last=bricks[-1] if bricks else None,previous=bricks[-2] if len(bricks)>1 else None,count=len(bricks),last_candidate=calculated,sizing_box=size,resizes=resizes)

def replay(bars,length,rule,update):
    atr=RMA(length);previous=None;size=None;anchor=None;direction=0;last=None;bricks=[]
    for bar in bars:
        price=bar['close']
        tr=bar['high']-bar['low'] if previous is None else max(bar['high']-bar['low'],abs(bar['high']-previous),abs(bar['low']-previous))
        previous=price;value=atr.update(tr)
        if value is None:continue
        calculated=normalize(value,rule)
        if anchor is None:
            size=calculated;anchor=math.floor(price/size)*size;continue
        if update=='every_parent':size=calculated
        difference=price-anchor;step=1 if difference>0 else -1
        count=math.floor(abs(difference)/size+1e-12)
        reversal=direction!=0 and step!=direction
        if count<(2 if reversal else 1):continue
        if reversal:anchor+=step*size
        for _ in range(1 if reversal else 0,count):
            op=anchor;anchor+=step*size
            last=dict(time=bar['time'],open=op,close=anchor,box=size,atr=value)
            bricks.append(last)
        direction=step
        if update.startswith('after_emission'):
            changed=size!=calculated;size=calculated
            if changed and update!='after_emission':
                ratio=anchor/size
                if update=='after_emission_snap_nearest':anchor=math.floor(ratio+.5)*size
                elif update=='after_emission_snap_direction':anchor=(math.floor(ratio) if direction>0 else math.ceil(ratio))*size
                elif update=='after_emission_price_grid':anchor=(math.floor(price/size) if direction>0 else math.ceil(price/size))*size
    return dict(last=last,previous=bricks[-2] if len(bricks)>1 else None,count=len(bricks),last_candidate=calculated,sizing_box=size)

def load_parents():
    archive=ROOT/'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_30m.json'
    recent=BASE/'evidence/20261120/history-15m.json'
    special=BASE/'evidence/native-parent-special-20261108-1m-raw.json'
    old=parents(json.loads(archive.read_text())['rows'],30)
    new=parents(json.loads(recent.read_text())['candles'],15)
    # Keep the newer source for the documented overlapping date range; do not
    # claim revisions agree or overwrite either retained source.
    merged={**old,**new}
    rows=[r for r in json.loads(special.read_text())['candles'] if 1794127800<=r[0]<1794131100]
    assert [r[0] for r in rows]==list(range(1794127800,1794131100,60))
    merged['2026-11-08']=dict(time=rows[0][0],open=rows[0][1],high=max(r[2] for r in rows),low=min(r[3] for r in rows),close=rows[-1][4])
    bars=[v for k,v in sorted(merged.items()) if k<='2026-11-19']
    return bars,(archive,recent,special)

if __name__=='__main__':
    bars,sources=load_parents()
    target=json.loads((BASE/'evidence/native-box-update-diagnostic-20261120.json').read_text())
    results=[]
    for update in ('every_parent','after_emission','after_emission_snap_nearest','after_emission_snap_direction','after_emission_price_grid','rebuild_on_emission'):
        for rule in ('tick','half_decade'):
            cases=[]
            for control in target['comparisons']:
                result=replay_rebuild(bars,control['length'],rule) if update=='rebuild_on_emission' else replay(bars,control['length'],rule,update)
                result.update(length=control['length'],observed_box=control['native_box'],observed_time=control['native_time']/1000,
                    box_matches=result['last'] is not None and abs(result['sizing_box']-control['native_box'])<1e-8,body_matches=result['last'] is not None and abs(result['last']['box']-control['native_box'])<1e-8)
                cases.append(result)
            results.append(dict(update=update,normalization=rule,matches=sum(c['box_matches'] for c in cases),body_matches=sum(c['body_matches'] for c in cases),cases=cases))
    report=dict(status='UNVERIFIED_OFFLINE_HYPOTHESES_NOT_SIZING_PROVIDER',parents=len(bars),
        archive_calendar_complete=False,source_revisions_equal=False,used_by_strategy=False,
        sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        models=results)
    (BASE/'evidence/native-sizing-replay-20261120.json').write_text(json.dumps(report,indent=2)+'\n')
    for model in results:
        print(model['update'],model['normalization'],'setting matches',model['matches'],'body matches',model['body_matches'],'of',len(model['cases']))
        print([(c['length'],round(c['sizing_box'],2) if c['last'] else None,c['observed_box']) for c in model['cases']])
