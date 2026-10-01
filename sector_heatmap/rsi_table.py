"""Read-only multi-timeframe RSI. Does not import any order/runner service."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import math
import threading
import time
from strategies.ema_crossover.signals import rsi_sma_series

IST = ZoneInfo('Asia/Kolkata')
NY = ZoneInfo('America/New_York')
TIMEFRAMES = [('5 minutes','5'),('15 minutes','15'),('30 minutes','30'),('6 hours','6H'),('1 day','D'),('1 week','1W'),('1 month','1M')]


def session_bounds(symbol, day):
    start = datetime(day.year,day.month,day.day,9,15,tzinfo=IST)
    end = start.replace(hour=15,minute=30)
    if symbol.startswith('MCX:'):
        if not any(symbol.startswith('MCX:'+p) for p in ('CRUDEOIL','NATURALGAS','GOLD','SILVER','COPPER','ALUMINIUM','ZINC','LEAD','NICKEL')):
            raise ValueError('6h session schedule not verified for this commodity')
        start = start.replace(minute=0)
        summer = bool(start.astimezone(NY).dst())
        end = start.replace(hour=23,minute=30 if summer else 55)
    elif not symbol.startswith(('NSE:','BSE:')):
        raise ValueError('Exchange session not supported')
    return start,end


def period_end(symbol, stamp, resolution):
    dt = datetime.fromtimestamp(stamp,IST)
    if resolution in ('D','1D'):
        return session_bounds(symbol,dt.date())[1].timestamp()
    if resolution == '1W':
        monday = dt.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=dt.weekday())
        return (monday+timedelta(days=7)).timestamp()
    if resolution == '1M':
        return dt.replace(year=dt.year+(dt.month==12),month=dt.month%12+1,day=1,hour=0,minute=0,second=0,microsecond=0).timestamp()
    _,end = session_bounds(symbol,dt.date())
    return min(stamp+int(resolution)*60,end.timestamp())


def normalize(raw):
    rows={}
    for r in raw:
        if len(r)<6 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in r[:6]):
            raise ValueError('Invalid provider candle')
        c=dict(zip(('timestamp','open','high','low','close','volume'),r[:6]))
        if c['timestamp'] in rows and rows[c['timestamp']] != c:
            raise ValueError('Conflicting provider candles')
        rows[c['timestamp']]=c
    return sorted(rows.values(),key=lambda c:c['timestamp'])


def aggregate_6h(raw,symbol,now):
    groups={}
    for c in normalize(raw):
        dt=datetime.fromtimestamp(c['timestamp'],IST);start,end=session_bounds(symbol,dt.date())
        if not start.timestamp() <= c['timestamp'] < end.timestamp():continue
        opening=start.timestamp()+int((c['timestamp']-start.timestamp())//21600)*21600
        close=min(opening+21600,end.timestamp())
        if close>now:continue
        groups.setdefault((opening,close),[]).append(c)
    result=[]
    for (opening,close),bars in sorted(groups.items()):
        expected=list(range(int(opening),int(close),1800))
        if [c['timestamp'] for c in bars] != expected:
            raise ValueError('Incomplete 30m source coverage for a completed 6h bucket')
        result.append({'timestamp':opening,'open':bars[0]['open'],'high':max(c['high'] for c in bars),'low':min(c['low'] for c in bars),'close':bars[-1]['close'],'volume':sum(c['volume'] for c in bars),'closed_at':close})
    return result


class RsiTable:
    def __init__(self):
        self.cache={};self.lock=threading.RLock()

    def history(self,client,symbol,resolution,target,now):
        source='30' if resolution=='6H' else resolution
        key=(symbol,resolution,target)
        seconds=300 if resolution in ('5','15','30','6H') else 3600 if resolution=='D' else 21600
        bucket=int(now)//seconds
        with self.lock:
            cached=self.cache.get(key)
            if cached and ((not cached.get('error') and cached['bucket']==bucket) or cached.get('retry_at',0)>time.monotonic()):
                if cached.get('error'):raise ValueError(cached['error'])
                return cached['raw'],cached['at']
            day=datetime.fromtimestamp(now,IST).date()
            days=math.ceil(target*31) if resolution=='1M' else math.ceil(target*10) if resolution=='1W' else target*2+10 if resolution=='D' else math.ceil(target*4) if resolution=='6H' else math.ceil(target*int(source)/375*1.6)+10
            # Exact selected expiry, never silently splice a continuous future.
            chunks=[];to=day;remaining=days
            if cached and cached.get('raw') and not cached.get('error'):
                chunks=cached['raw'][:];remaining=2
            cap=365 if source in ('D','1W','1M') else 99
            try:
                while remaining>0:
                    span=min(cap,remaining);start=to-timedelta(days=span-1)
                    response=client.history({'symbol':symbol,'resolution':source,'date_format':1,'range_from':start.isoformat(),'range_to':to.isoformat(),'cont_flag':0})
                    if not isinstance(response,dict) or response.get('s')!='ok':
                        if chunks:break  # Older exact-contract history unavailable; retain validated recent data.
                        raise ValueError('Provider history unavailable; retry is cached for 60s')
                    rows=response.get('candles',[])
                    if not rows:break
                    normalize(rows)
                    chunks.extend(rows);remaining-=span;to=start-timedelta(days=1)
                    if len({r[0] for r in chunks}) >= target*(12 if resolution=='6H' else 1):break
                # Upsert boundary revisions before strict normalization/validation.
                raw=list({r[0]:r for r in chunks}.values());normalize(raw)
                self.cache[key]={'raw':raw,'bucket':bucket,'at':now}
                return raw,now
            except Exception as e:
                self.cache[key]={'raw':[],'bucket':bucket,'at':now,'error':str(e),'retry_at':time.monotonic()+60}
                raise

    def snapshot(self,client,symbol,rsi_length,ma_length,ma_type,now=None):
        now=time.time() if now is None else now
        rsi_sma_series([],rsi_length,ma_length,ma_type)
        target=max(rsi_length*5+ma_length,rsi_length+ma_length)
        result=[]
        for label,resolution in TIMEFRAMES:
            row={'timeframe':label,'rsi':None,'rsi_ma':None,'status':'Unavailable','closed_at':None,'source':'30m → session-anchored 6h' if resolution=='6H' else 'FYERS '+resolution}
            try:
                raw,at=self.history(client,symbol,resolution,target,now)
                candles=aggregate_6h(raw,symbol,now) if resolution=='6H' else [{**c,'closed_at':period_end(symbol,c['timestamp'],resolution)} for c in normalize(raw) if c['timestamp'] < period_end(symbol,c['timestamp'],resolution)<=now]
                values=rsi_sma_series(candles,rsi_length,ma_length,ma_type)
                row.update(completed_bars=len(values),history_fetched_at=at)
                if len(values)<target or not values or values[-1]['rsi_ma'] is None:
                    row['detail']=f'Insufficient exact-symbol history: {len(values)}/{target} completed bars for warmup'
                else:
                    last=values[-1];row.update(rsi=last['rsi'],rsi_ma=last['rsi_ma'],status='Completed',closed_at=last['closed_at'],opened_at=last['timestamp'],detail=row['source'])
            except Exception as e:row['detail']=str(e)
            result.append(row)
        return {'symbol':symbol,'rsi_length':rsi_length,'ma_length':ma_length,'ma_type':ma_type,'rows':result,'as_of':now,'note':'Completed candles only · exact selected symbol · cached history; current week/month excluded until next calendar period. 6h starts at exchange session open and includes a shortened closing bucket.'}
