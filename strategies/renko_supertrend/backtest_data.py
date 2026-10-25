"""Research-only market archive access. No order or runner interfaces."""
import csv,hashlib,json,math,re,time
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from sector_heatmap.persistent_jobs import checkpoint
IST=ZoneInfo('Asia/Kolkata')

def valid_rows(rows):
    unique={}
    for raw in rows:
        if isinstance(raw,dict):r={k:raw[k] for k in ('timestamp','open','high','low','close','volume')}
        else:
            if len(raw)<6:raise ValueError('Historical candle is missing required fields.')
            r=dict(zip(('timestamp','open','high','low','close','volume'),raw[:6]))
        if not all(isinstance(r[k],(int,float)) and not isinstance(r[k],bool) and math.isfinite(r[k]) for k in r):raise ValueError('Historical candle has missing/nonfinite fields.')
        if not 0<r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high']:raise ValueError('Historical candle OHLC is invalid.')
        if r['volume']<0 or int(r['timestamp'])!=r['timestamp']:raise ValueError('Historical candle volume/timestamp is invalid.')
        if r['timestamp'] in unique and unique[r['timestamp']]!=r:raise ValueError('Conflicting historical candles; data must be reconciled.')
        unique[r['timestamp']]=r
    return [unique[k] for k in sorted(unique)]

def session(symbol):
    if symbol.startswith(('NSE:','BSE:')):return dict(open='09:15',close='15:30',cutoff='15:10',timezone='Asia/Kolkata',basis='NSE/BSE regular session; nonregular sessions excluded')
    if symbol.startswith('MCX:'):return dict(open='09:00',close='23:30',cutoff='23:30',timezone='Asia/Kolkata',basis='Conservative MCX common session subset; later seasonal close excluded')
    return dict(open='00:00',close='24:00',cutoff=None,timezone='UTC',basis='Crypto continuous session; provider coverage required')

def in_session(stamp,policy):
    clock=datetime.fromtimestamp(stamp,ZoneInfo(policy['timezone']));minute=clock.hour*60+clock.minute
    lower,upper=[int(x.split(':')[0])*60+int(x.split(':')[1]) for x in (policy['open'],policy['close'])]
    if not lower<=minute<upper:return False
    if policy['timezone']=='Asia/Kolkata':
        from sector_heatmap.market_calendar import is_trading_day
        if policy['basis'].startswith('NSE/BSE') and clock.year==2026:return is_trading_day(clock.date())
        return clock.weekday()<5
    return True

def aggregate(rows,minutes,policy):
    if minutes==1:return rows
    bins={};seconds=minutes*60
    for r in rows:
        d=datetime.fromtimestamp(r['timestamp'],ZoneInfo(policy['timezone']));h,m=map(int,policy['open'].split(':'));anchor=d.replace(hour=h,minute=m,second=0,microsecond=0).timestamp()
        start=int(anchor+(r['timestamp']-anchor)//seconds*seconds);bins.setdefault(start,[]).append(r)
    result=[]
    for start,group in sorted(bins.items()):
        if len(group)!=minutes or any(r['timestamp']!=start+i*60 for i,r in enumerate(group)):continue
        result.append(dict(timestamp=start,open=group[0]['open'],high=max(r['high'] for r in group),low=min(r['low'] for r in group),close=group[-1]['close'],volume=sum(r['volume'] for r in group)))
    return result

class Archive:
    def __init__(self,root,token=None,allow_download=False):
        self.root=Path(root);self.token=token;self.allow_download=allow_download
        self.cache=self.root/'data/backtesting/fyers-contract-history';self.cache.mkdir(parents=True,exist_ok=True)
        self.calls=0;self.last_call=0;self.evidence=[]
        from .historical_lots import HistoricalLots
        self.lots=HistoricalLots(self.root)
    def get(self,path,params):
        key=hashlib.sha256(json.dumps([path,params],sort_keys=True).encode()).hexdigest();file=self.cache/(key+'.json')
        if file.exists():
            saved=json.loads(file.read_text())
            if saved.get('path')!=path or saved.get('request')!=params:raise ValueError('Historical cache identity mismatch.')
            result=saved['response']
        else:
            if not self.allow_download or not self.token:raise ValueError('Exact historical contract data is not staged; enable read-only history download with a valid FYERS session.')
            if self.calls>=400:raise ValueError('Backtest history request budget reached; cached progress retained for a rerun.')
            checkpoint('Reading historical broker data; completed responses are cached.')
            delay=1.25-(time.monotonic()-self.last_call)
            if delay>0:time.sleep(delay)
            self.calls+=1;self.last_call=time.monotonic()
            response=requests.get('https://api-t1.fyers.in'+path,params=params,headers={'Authorization':self.token},timeout=20)
            result=response.json()
            if response.status_code!=200 or result.get('s') not in ('ok','no_data'):raise ValueError('FYERS history unavailable: '+str(result.get('message') or result.get('s') or response.status_code))
            temp=file.with_name(file.name+'.'+__import__('uuid').uuid4().hex+'.tmp');temp.write_text(json.dumps(dict(path=path,request=params,response=result,downloaded_at=datetime.now(IST).isoformat())));temp.replace(file)
        self.evidence.append(dict(file=str(file.relative_to(self.root)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),path=path))
        return result
    def underlying(self,symbol,first,last,minutes):
        policy=session(symbol);archive=self.root/'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24'
        name=archive/f'nifty50_{minutes}m.csv'
        if symbol=='NSE:NIFTY50-INDEX' and (name.exists() or (archive/'nifty50_1m.csv').exists()):
            source_minutes=minutes if name.exists() else 1;name=archive/f'nifty50_{source_minutes}m.csv'
            raw=[]
            with name.open() as handle:
                for x in csv.DictReader(handle):
                    day=x['timestamp_ist'][:10]
                    if str(first)<=day<=str(last):raw.append(dict(timestamp=int(x['epoch']),**{k:float(x[k]) for k in ('open','high','low','close','volume')}))
            self.evidence.append(dict(file=str(name.relative_to(self.root)),sha256=hashlib.sha256(name.read_bytes()).hexdigest(),provider='FYERS staged underlying archive'))
            original=valid_rows(raw);inside=[r for r in original if in_session(r['timestamp'],policy)]
            result=inside if source_minutes==minutes else aggregate(inside,minutes,policy)
            return result,dict(provider='FYERS staged archive',outside_session_excluded=len(original)-len(inside),policy=policy,calendar_coverage='NSE 2026 holiday calendar; earlier years use returned broker weekdays, special sessions excluded')
        result=[];cursor=first
        while cursor<=last:
            end=min(last,cursor+timedelta(days=89));p=self.get('/data/history',dict(symbol=symbol,resolution=str(minutes),date_format=1,range_from=str(cursor),range_to=str(end),cont_flag=0));result+=p.get('candles') or [];cursor=end+timedelta(days=1)
        result=valid_rows(result);inside=[r for r in result if in_session(r['timestamp'],policy)]
        return inside,dict(provider='FYERS history, exact underlying symbol',outside_session_excluded=len(result)-len(inside),policy=policy)
    def select(self,symbol,stamp,direction,spot):
        day=datetime.fromtimestamp(stamp,IST).date();completed=datetime.now(IST).date()-timedelta(days=1)
        while completed.weekday()>4:completed-=timedelta(days=1)
        end=min(completed,day.replace(day=1)+timedelta(days=90))
        p=self.get('/data/history/fno/expired/expiry-dates',dict(symbol=symbol,range_from=str(day.replace(day=1)),range_to=str(end),date_format=1))
        expiries=sorted(date.fromisoformat(x) for x in p.get('data',{}).get('expiry_dates',{}).get('options',[]) if date.fromisoformat(x)>=day)
        if not expiries:raise ValueError('No broker-reported expiry is available for this historical entry.')
        expiry=expiries[0];p=self.get('/data/history/fno/expired/underlying-symbols',dict(symbol=symbol,expiry_date=str(expiry)))
        data=p.get('data') or {};root=data.get('symbol');side='CE' if direction=='BULLISH' else 'PE'
        if not isinstance(root,str):raise ValueError('Historical contract underlying metadata is missing.')
        month=expiry.strftime('%b').upper();weekly=str(expiry.year)[2:]+('123456789OND'[expiry.month-1])+f'{expiry.day:02}'
        pattern=re.compile(r'^[A-Z]+:'+re.escape(root)+r'(?:'+str(expiry.year)[2:]+month+'|'+weekly+r')([0-9]+(?:\.[0-9]+)?)'+side+r'$')
        contracts=[]
        for raw in data.get('contracts',{}).get('options',[]):
            ticker=raw.get('symbol') if isinstance(raw,dict) else raw
            if not isinstance(ticker,str):continue
            match=pattern.fullmatch(ticker)
            if match:
                contracts.append(dict(symbol=ticker,strike=float(match.group(1)),expiry=str(expiry),option_type=side,identity_source='FYERS expired-contract response'))
        if not contracts:raise ValueError('No exact broker-returned historical option contract could be resolved for this side/expiry.')
        selected=min(contracts,key=lambda x:(abs(x['strike']-spot),x['strike'],x['symbol']))
        selected.update(self.lots.resolve(selected,stamp))
        if selected.get('lot_size_provenance'):self.evidence.append(dict(kind='HISTORICAL_LOT_MASTER',**selected['lot_size_provenance']))
        return selected
    def premiums(self,contract,first,last,minutes):
        rows=[];cursor=first
        while cursor<=last:
            end=min(last,cursor+timedelta(days=89));p=self.get('/data/history/fno/expired/historical-data',dict(symbol=contract['symbol'],resolution=str(minutes),date_format=1,range_from=str(cursor),range_to=str(end),include_oi=1));rows+=p.get('candles') or [];cursor=end+timedelta(days=1)
        return valid_rows(rows)
