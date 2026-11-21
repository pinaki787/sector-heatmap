"""Read-only seasonal price returns. No portfolio P&L or execution authority."""
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import math, re, json, time, hashlib
from pathlib import Path
import requests
from .persistent_jobs import checkpoint

PERIODS=('Weekly','Monthly','Yearly')

def symbol_options(payload):
    symbol=str(payload.get('symbol') or '').upper().strip()
    # Explicit exchange identity only: never guess a derivative's underlying.
    match=re.fullmatch(r'(NSE|BSE):([A-Z0-9&_.-]{1,45})',symbol)
    if not match:raise ValueError('Seasonality requires an identified NSE or BSE cash-equity symbol.')
    exchange,name=match.groups()
    name=name.removesuffix('-EQ')
    if name.endswith(('-FUT','-CE','-PE')) or re.search(r'\d{2}[A-Z]{3}\d',name):
        raise ValueError('Contract seasonality is unavailable. Select its cash-equity underlying separately.')
    return exchange+':'+name,name+('.NS' if exchange=='NSE' else '.BO')

def period_key(day,mode):
    if mode=='Weekly':
        year,week,_=day.isocalendar();return year,week
    return day.year,day.month if mode=='Monthly' else 1

def next_key(key,mode):
    y,s=key
    if mode=='Weekly':return period_key(date.fromisocalendar(y,s,1)+timedelta(days=7),mode)
    if mode=='Monthly':return (y+1,1) if s==12 else (y,s+1)
    return y+1,1

def calculate(candles,as_of,timezone='Asia/Kolkata'):
    """Group daily closes; use prior-period close and require calendar continuity.

    Forming calendar periods and the unanchored first group are excluded. Missing
    periods invalidate annual and overall compounded returns, rather than being
    silently treated as 0%. Daily session completeness remains a source limit.
    """
    today=datetime.fromtimestamp(as_of,ZoneInfo(timezone)).date()
    rows=[];previous=None
    for item in candles:
        day=date.fromisoformat(item['date']);close=float(item['close'])
        if not math.isfinite(close) or close<=0:raise ValueError('Invalid daily close.')
        if previous is not None and day<=previous:raise ValueError('Duplicate or unordered daily sessions.')
        previous=day
        if day<today:rows.append(dict(date=day,close=close))
    if len(rows)<2:raise ValueError('Not enough completed daily history for seasonal returns.')
    modes={}
    for mode in PERIODS:
        groups={}
        for row in rows:groups[period_key(row['date'],mode)]=row
        current=period_key(today,mode)
        complete=[(key,row) for key,row in groups.items() if key<current]
        periods=[]
        for (prior,base),(key,end) in zip(complete,complete[1:]):
            valid=next_key(prior,mode)==key
            periods.append(dict(year=key[0],slot=key[1],value=(end['close']/base['close']-1)*100 if valid else None,
                start_close=base['close'],end_close=end['close'],from_date=base['date'].isoformat(),to_date=end['date'].isoformat(),continuous=valid))
        years=[]
        for year in sorted({p['year'] for p in periods},reverse=True):
            items=[p for p in periods if p['year']==year]
            all_slots=53 if mode=='Weekly' else 12 if mode=='Monthly' else 1
            expected=period_key(today,mode)[1]-1 if year==current[0] else (date(year,12,28).isocalendar().week if mode=='Weekly' else all_slots)
            full=bool(items) and items[0]['slot']==1 and len(items)==expected and all(p['continuous'] for p in items)
            # Direct endpoints independently enforce the same compounded result.
            net=(items[-1]['end_close']/items[0]['start_close']-1)*100 if full else None
            years.append(dict(year=year,periods=items,net_return=net,complete=full,partial=year==current[0],samples=sum(p['value'] is not None for p in items),expected=expected))
        contiguous=bool(periods) and all(p['continuous'] for p in periods)
        net=(periods[-1]['end_close']/periods[0]['start_close']-1)*100 if contiguous else None
        span_days=(date.fromisoformat(periods[-1]['to_date'])-date.fromisoformat(periods[0]['from_date'])).days if periods else 0
        annualized=((1+net/100)**(365.2425/span_days)-1)*100 if net is not None and span_days>=365 else None
        summary=[]
        slots=53 if mode=='Weekly' else 12 if mode=='Monthly' else 0
        for slot in range(1,slots+1):
            values=[p['value'] for p in periods if p['slot']==slot and p['value'] is not None]
            summary.append(dict(slot=slot,average=sum(values)/len(values) if values else None,positive=sum(v>0 for v in values),samples=len(values),win_rate=100*sum(v>0 for v in values)/len(values) if values else None))
        modes[mode]=dict(years=years,statistics=summary,net_return=net,annualized_return=annualized,continuous=contiguous,period_count=len(periods),
            from_date=periods[0]['from_date'] if periods else None,to_date=periods[-1]['to_date'] if periods else None)
    return dict(schema='seasonality/v1',modes=modes,daily_from=rows[0]['date'].isoformat(),daily_to=rows[-1]['date'].isoformat(),daily_samples=len(rows),timezone=timezone,
        method='Period return = ending close / preceding period close − 1. Net return = ending close / starting close − 1; compounded at full precision. Calendar gaps invalidate net return.',
        limitations=['Historical price returns are not forecasts or position P&L; fees, taxes and dividends are excluded.',
        'Source corporate-action adjustment and daily session completeness are not independently certified.',
        'Current calendar week, month and year are excluded. Current-year net in weekly/monthly views includes closed periods only.',
        'An incomplete first year or missing calendar period has no annual net. Overall net uses the labelled available range, not the requested start year.',
        'Weeks use ISO week-year; weekly and monthly year boundaries can differ.'])

def fetch_public(root,payload,now=None):
    symbol,provider_symbol=symbol_options(payload);now=time.time() if now is None else now
    cache=Path(root)/'data/seasonality';cache.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(provider_symbol.encode()).hexdigest();path=cache/(key+'.json')
    checkpoint('Reading ten-year daily price history for '+symbol+'.')
    raw=None
    if path.exists():
        stored=json.loads(path.read_text())
        if 0<=now-stored.get('fetched_at',0)<21600:raw=stored['raw'];captured=stored['fetched_at']
    if raw is None:
        response=requests.get('https://query1.finance.yahoo.com/v8/finance/chart/'+requests.utils.quote(provider_symbol,safe=''),params={'range':'10y','interval':'1d'},headers={'User-Agent':'Mozilla/5.0'},timeout=(5,20))
        response.raise_for_status();raw=response.json();captured=now
        import uuid
        temporary=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');temporary.write_text(json.dumps(dict(fetched_at=captured,raw=raw)));temporary.replace(path)
    results=raw.get('chart',{}).get('result') or []
    if len(results)!=1:raise ValueError('Public daily history unavailable; no substitute symbol was used.')
    data=results[0];meta=data.get('meta',{})
    if meta.get('symbol','').upper()!=provider_symbol.upper() or meta.get('instrumentType') not in ('EQUITY','ETF'):
        raise ValueError('History identity or cash-equity instrument type did not match.')
    zone=meta.get('exchangeTimezoneName','Asia/Kolkata');closes=data['indicators']['quote'][0]['close']
    by_day={}
    for stamp,close in zip(data.get('timestamp',[]),closes):
        if close is None:continue
        day=datetime.fromtimestamp(stamp,ZoneInfo(zone)).date().isoformat()
        by_day[day]=dict(date=day,close=close)
    checkpoint('Calculating closed-period returns and checking calendar continuity.')
    report=calculate([by_day[k] for k in sorted(by_day)],now,zone)
    report.update(symbol=symbol,source='Yahoo Finance daily closes',source_url='https://finance.yahoo.com/quote/'+provider_symbol+'/history/',provider_symbol=provider_symbol,fetched_at=datetime.fromtimestamp(captured,ZoneInfo('UTC')).isoformat(),price_basis='Provider close; dividends excluded; corporate-action adjustment unverified',order_authority='NONE')
    # The same public evidence supplies a bounded, completed-session chart.
    # Invalid OHLC never becomes fabricated candles or zero values.
    from .holdings_chart import chart_evidence
    quote=data['indicators']['quote'][0];chart_rows=[]
    today=datetime.fromtimestamp(now,ZoneInfo(zone)).date()
    for i,stamp in enumerate(data.get('timestamp',[])):
        if datetime.fromtimestamp(stamp,ZoneInfo(zone)).date()>=today:continue
        values={k:quote.get(k,[])[i] if i<len(quote.get(k,[])) else None for k in ('open','high','low','close')}
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in values.values()):continue
        if values['high']<max(values['open'],values['close'],values['low']) or values['low']>min(values['open'],values['close']):continue
        chart_rows.append(dict(timestamp=stamp,**values))
    checkpoint('Preparing the candlestick chart and moving-average evidence.')
    if chart_rows:
        report['chart']=chart_evidence(chart_rows[-500:])
        report['chart']['basis']='Yahoo Finance public daily candles; latest 500 completed sessions. Provider corporate-action adjustment is not independently certified.'
    else:
        report['chart']=None
        report['chart_unavailable_reason']='The source did not provide valid completed OHLC candles. Seasonal close returns are retained separately.'
    return report
