"""Provider-history confirmation for close-source decisions; GETs only."""
import hashlib,math,time
from pathlib import Path
try:from .run import atomic,normalize_closes,ok
except ImportError:from run import atomic,normalize_closes,ok

def fyers_reader(api):
    from sector_heatmap.fyers_history import history
    raw=getattr(api,'api',api)
    def read(symbol,frame,stamp):
        reply=ok(history(raw,dict(symbol=symbol,resolution=str(frame),date_format=0,range_from=str(int(stamp)),range_to=str(int(stamp+frame*60)),cont_flag=0)))
        return reply,reply.get('candles',[])
    return read

def delta_reader(delta,*,lookback=0):
    def read(symbol,frame,stamp):
        reply=delta._get('/v2/history/candles',dict(symbol=symbol,resolution=str(frame)+'m',start=int(stamp-lookback*frame*60),end=int(stamp+frame*60)))
        rows=reply.get('result')
        if not isinstance(rows,list):raise ValueError('Delta completed source history unavailable')
        return reply,[[r['time'],r.get('open'),r.get('high'),r.get('low'),r.get('close'),r.get('volume')] for r in rows]
    return read

class ConfirmedClose:
    def __init__(self,reader,directory):
        self.reader=reader;self.directory=Path(directory);self.cache={}
    def confirm(self,event,symbol,frame,now=None,*,previous=None,continuous=True,opening_minutes=None):
        now=time.time() if now is None else now
        stamp=event['timestamp']
        if frame not in (1,5,30):raise ValueError('Unsupported completed-source frame')
        if isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or not math.isfinite(stamp) or int(stamp)!=stamp or stamp+frame*60>now:
            raise ValueError('Source bar has not completed; no decision made')
        if previous is not None and stamp!=previous+frame*60:
            from datetime import datetime
            try:from .run import IST
            except ImportError:from run import IST
            old,current=datetime.fromtimestamp(previous,IST),datetime.fromtimestamp(stamp,IST)
            regular_open=(not continuous and opening_minutes is not None and current.date()>old.date() and current.hour*60+current.minute==opening_minutes and current.second==0)
            if stamp<=previous or not regular_open:
                raise ValueError('Source gap between warm-up/previous close and current provider bar; halt for history reconciliation')
        key=(symbol,frame,stamp)
        if key not in self.cache:
            scope=hashlib.sha256((symbol+'|'+str(frame)+'|'+str(stamp)).encode()).hexdigest()[:24]
            raw,rows=self.reader(symbol,frame,stamp)
            atomic(self.directory/(scope+'-raw.json'),raw)
            try:
                normalized,audit=normalize_closes(rows)
                exact=[r for r in normalized if r[0]==stamp]
                if len(exact)!=1:raise ValueError('Exact completed provider close unavailable; stream hint is not substituted')
                close=exact[0][4]
                originals=[r for r in rows if isinstance(r,(list,tuple)) and len(r)>=5 and r[0]==stamp]
                opens=[r[1] for r in originals]
                opening=opens[0] if opens else None
                body_available=bool(opens) and all(not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v) and v>0 and v==opening for v in opens)
                try:from .sma_band import retain_broker_ohlc
                except ImportError:from sma_band import retain_broker_ohlc
                ohlc=retain_broker_ohlc(exact,originals)[0]
                wick_available=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>0 for v in ohlc[1:4])
                body=dict(high=ohlc[2] if wick_available else None,low=ohlc[3] if wick_available else None,ohlc_available=wick_available,open=opening if body_available else None,body_available=body_available,closed=True,closed_at=stamp+frame*60,available_at=now)
                audit.update(symbol=symbol,frame=frame,timestamp=stamp,provider_close=close,provider_open=body['open'],body_available=body_available,stream_close_hint=event['close'],stream_hint_differs=close!=event['close'],confirmed_at=now)
                atomic(self.directory/(scope+'-audit.json'),audit)
            except ValueError as error:
                atomic(self.directory/(scope+'-audit.json'),dict(symbol=symbol,frame=frame,timestamp=stamp,error=str(error),decisions_made=0))
                raise
            self.cache[key]=dict(close=close,**body)
            if len(self.cache)>4096:self.cache.pop(next(iter(self.cache)))
        return dict(event,**dict(self.cache[key],symbol=symbol,source_basis='PROVIDER_CONFIRMED_CLOSE',stream_close_hint=event['close']))
