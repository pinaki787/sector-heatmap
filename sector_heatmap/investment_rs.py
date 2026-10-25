"""Transparent sector peer-group and stock strength versus Nifty 500."""
from collections import defaultdict
from datetime import datetime,timezone
from .investment import number,download,SCAN
import json
BENCHMARK='NSE:CNX500'
HORIZONS={'6m':'Perf.6M','12m':'Perf.Y'}
MIN_MEMBERS=5
def classify(values):
    if any(v is None for v in values):return 'UNAVAILABLE'
    if all(v>0 for v in values):return 'LEADING'
    if all(v<0 for v in values):return 'LAGGING'
    return 'MIXED'
def calculate(rows,benchmark,now):
    """Each window uses same-session finite data; never turn missing data into zero."""
    metrics=benchmark.get('metrics',{})
    stamp=number(benchmark.get('bar_time'))
    fresh=stamp is not None and -86400<=now-stamp<=5*86400
    groups=defaultdict(list)
    for row in rows:
        if row.get('sector'):groups[row['sector']].append(row)
    summary={}
    for name,members in groups.items():
        item=dict(sector=name,method='Equal-weight current NSE EQ peer group',total_members=len(members),benchmark='Nifty 500',benchmark_symbol=BENCHMARK,bar_at=datetime.fromtimestamp(stamp,timezone.utc).isoformat() if stamp else None,windows={},status='UNAVAILABLE')
        for period,key in HORIZONS.items():
            usable=[r['metrics'][key] for r in members if number(r.get('metrics',{}).get(key)) is not None and number(r.get('metrics',{}).get('time'))==stamp]
            base=number(metrics.get(key));valid=fresh and base is not None and len(usable)>=MIN_MEMBERS
            ret=sum(usable)/len(usable) if valid else None
            item['windows'][period]=dict(sector_return_pct=ret,benchmark_return_pct=base if fresh else None,excess_pp=ret-base if valid else None,members=len(usable),minimum_members=MIN_MEMBERS)
        item['status']=classify([item['windows'][p]['excess_pp'] for p in HORIZONS])
        summary[name]=item
    for row in rows:
        same_session=number(row.get('metrics',{}).get('time'))==stamp
        stock={}
        for period,key in HORIZONS.items():
            ret=number(row.get('metrics',{}).get(key));base=number(metrics.get(key))
            stock[period]=ret-base if fresh and same_session and ret is not None and base is not None else None
        row['relative_strength']=dict(benchmark='Nifty 500',benchmark_symbol=BENCHMARK,method='Return difference in percentage points',windows=stock,status=classify(list(stock.values())))
        row['sector_strength']=summary.get(row.get('sector'),dict(status='UNAVAILABLE',windows={},reason='Sector classification unavailable.'))
        row['missing']=[v for v in row.get('missing',[]) if v!='Benchmark-relative strength']
        if row['relative_strength']['status']=='UNAVAILABLE':row['missing'].append('Same-session benchmark-relative strength')
    return dict(benchmark='Nifty 500',benchmark_symbol=BENCHMARK,benchmark_bar_at=datetime.fromtimestamp(stamp,timezone.utc).isoformat() if stamp else None,method='Sector RS = equal-weight sector peer return minus Nifty 500 return (percentage points); not an official sector-index return or 0–100 rating.',minimum_members=MIN_MEMBERS,sectors=list(summary.values()),status='AVAILABLE' if fresh and all(number(metrics.get(k)) is not None for k in HORIZONS.values()) else 'UNAVAILABLE')
def collect(session,rows,now):
    try:
        data=json.loads(download(session,SCAN,{'symbols':{'tickers':[BENCHMARK]},'columns':['name','Perf.6M','Perf.Y','time']}))
        records=data.get('data',[])
        if len(records)!=1 or records[0].get('s')!=BENCHMARK or len(records[0].get('d',[]))!=4:raise ValueError('Nifty 500 benchmark unavailable.')
        d=records[0]['d'];benchmark=dict(metrics={'Perf.6M':d[1],'Perf.Y':d[2]},bar_time=d[3])
        return calculate(rows,benchmark,now)
    except Exception as error:
        # Cancellation must propagate, rather than be reported as missing data.
        from .persistent_jobs import JobCancelled,JobInterrupted
        if isinstance(error,(JobCancelled,JobInterrupted)):raise
        context=calculate(rows,{},now)
        context['reason']='Nifty 500 benchmark unavailable; no substitute benchmark was used.'
        return context

