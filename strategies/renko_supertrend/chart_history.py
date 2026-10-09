"""Bounded, durable fixed-contract OHLC history for read-only chart research.

Never used to authorize orders. A changed completed candle causes a full chart
recalculation, rather than splicing incompatible path-dependent state.
"""
from sector_heatmap.fyers_history import history as bounded_history
import hashlib
import json
import math
import os
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from .runner import TIMEFRAMES, analysis
from .signals import completed

IST=ZoneInfo('Asia/Kolkata')

def selected_range(preset='45',start='',end='',now=None):
    today=datetime.fromtimestamp(time.time() if now is None else now,IST).date()
    if preset=='custom':
        first,last=date.fromisoformat(start),date.fromisoformat(end)
    else:
        if preset not in ('7','45','90'):raise ValueError('Choose 7, 45, 90 days or a custom range.')
        last=today;first=today-timedelta(days=int(preset)-1)
    if last>today or first>last or (last-first).days>90:raise ValueError('Choose a past range of at most 91 calendar days.')
    return first,last,first-timedelta(days=7)

def candle_issue(row):
    """Validate broker data without repairing or inventing prices."""
    try:
        candle=dict(timestamp=int(row[0]), **{k:float(row[i]) for i,k in enumerate(('open','high','low','close'),1)})
        completed([candle])
    except (ValueError,TypeError,IndexError,OverflowError) as exc:
        return str(exc) or 'Malformed broker candle.'
    return None


class ChartHistory:
    def __init__(self,path,min_interval=.35):
        self.path=Path(path);self.lock=threading.RLock();self.memory={}
        self.min_interval=min_interval;self.next_request_at=0

    def load(self,client,symbol,timeframe,preset='45',start='',end='',config=None,tick=.05,now=None):
        now=time.time() if now is None else now
        first,last,anchor=selected_range(preset,start,end,now)
        seconds=TIMEFRAMES.get(timeframe)
        if not seconds:raise ValueError('Choose a supported host timeframe.')
        identity=json.dumps([symbol,timeframe,str(anchor),str(last)])
        key=hashlib.sha256(identity.encode()).hexdigest()
        with self.lock:
            entry=self.memory.get(key)
            if entry is None:
                p=self.path/(key+'.json')
                try:entry=json.loads(p.read_text()) if p.exists() else {}
                except (ValueError,OSError):entry={}
                entry.update(analysis_key=None,analysis=None,next_retry=0)
                self.memory[key]=entry
                # The disk cache remains reusable; bound in-process copies.
                for old in list(self.memory)[:-6]:del self.memory[old]
            current_bar=int(now)//seconds
            if entry.get('forming_retry_bar')!=current_bar:
                entry.update(forming_retry_bar=current_bar,forming_retry_count=0)
            has_forming=any(len(r)>=5 and int(r[0])==current_bar*seconds and not candle_issue(r) for r in entry.get('rows',[]))
            retry_forming=(last==datetime.fromtimestamp(now,IST).date() and entry.get('complete')
                           and not has_forming and entry.get('refresh_bar')==current_bar
                           and entry.get('forming_retry_count',0)<3
                           and now-entry.get('refreshed_at',0)>=10)
            refresh=not entry.get('complete') or (last==datetime.fromtimestamp(now,IST).date() and entry.get('refresh_bar')!=current_bar) or retry_forming
            error=None
            if refresh and now>=entry.get('next_retry',0):
                if retry_forming:entry['forming_retry_count']=entry.get('forming_retry_count',0)+1
                merged={int(r[0]):r for r in entry.get('rows',[])}
                cursor=last if entry.get('complete') else date.fromisoformat(entry['covered_to'])+timedelta(days=1) if entry.get('covered_to') else anchor
                try:
                    while cursor<=last:
                        stop=min(last,cursor+timedelta(days=2))
                        time.sleep(max(0,self.next_request_at-time.monotonic()))
                        self.next_request_at=time.monotonic()+self.min_interval
                        response=bounded_history(client,dict(symbol=symbol,resolution=str(seconds//60),date_format=1,range_from=str(cursor),range_to=str(stop),cont_flag=0,oi_flag=1))
                        if isinstance(response,dict) and response.get('s')=='no_data':response={'s':'ok','candles':[]}
                        if not isinstance(response,dict) or response.get('s')!='ok' or not isinstance(response.get('candles'),list):
                            raise RuntimeError('FYERS chart history unavailable: '+str(response.get('message','invalid response') if isinstance(response,dict) else 'invalid response'))
                        for r in response['candles']:
                            # Keep malformed OHLC as evidence; never erase a known
                            # valid candle with a malformed revision.
                            if len(r)>=5:
                                stamp=int(r[0]);old=merged.get(stamp)
                                if old is None or candle_issue(old) or not candle_issue(r):merged[stamp]=r
                        entry.update(covered_to=str(stop),refreshed_at=now)
                        cursor=stop+timedelta(days=1)
                    if len(merged)>150000:raise ValueError('History exceeds the chart resource limit; choose a shorter range.')
                    entry.update(rows=[merged[k] for k in sorted(merged)],complete=True,refresh_bar=int(now)//seconds,refreshed_at=now,error=None)
                except (RuntimeError,ValueError,OSError) as exc:
                    entry.update(rows=[merged[k] for k in sorted(merged)],error=str(exc),next_retry=now+30)
                # Retain successful chunks even when a later request fails.
                if entry.get('rows'):
                    self.path.mkdir(parents=True,exist_ok=True)
                    p=self.path/(key+'.json');tmp=p.with_suffix('.tmp')
                    with tmp.open('w') as f:
                        os.chmod(tmp,0o600);json.dump({k:entry.get(k) for k in ('rows','complete','covered_to','refresh_bar','refreshed_at','error')},f);f.flush();os.fsync(f.fileno())
                    os.replace(tmp,p)
            # Retry affected historical dates, not just today's chunk. A broker
            # may alternate between valid and malformed revisions. Rate limit
            # repair and accept only validated replacements.
            invalid=[r for r in entry.get('rows',[]) if candle_issue(r)]
            if invalid and now>=entry.get('repair_after',0):
                entry['repair_after']=now+60
                repairs={}
                for day in sorted({str(datetime.fromtimestamp(int(r[0]),IST).date()) for r in invalid})[:3]:
                    try:
                        time.sleep(max(0,self.next_request_at-time.monotonic()))
                        self.next_request_at=time.monotonic()+self.min_interval
                        response=bounded_history(client,dict(symbol=symbol,resolution=str(seconds//60),date_format=1,range_from=day,range_to=day,cont_flag=0,oi_flag=1))
                        if isinstance(response,dict) and response.get('s')=='ok':
                            repairs.update({int(r[0]):r for r in response.get('candles',[]) if not candle_issue(r)})
                    except (RuntimeError,ValueError,OSError):
                        pass  # Show quarantined gaps even if the repair is unavailable.
                entry['rows']=[repairs.get(int(r[0]),r) if candle_issue(r) else r for r in entry.get('rows',[])]
                if repairs and entry.get('rows'):
                    p=self.path/(key+'.json');tmp=p.with_suffix('.tmp')
                    with tmp.open('w') as f:
                        os.chmod(tmp,0o600);json.dump({k:entry.get(k) for k in ('rows','complete','covered_to','refresh_bar','refreshed_at','error')},f);f.flush();os.fsync(f.fileno())
                    os.replace(tmp,p)
            error=entry.get('error')
            invalid=[dict(timestamp=int(r[0]),reason=candle_issue(r)) for r in entry.get('rows',[]) if candle_issue(r)]
            candles=[dict(timestamp=int(r[0]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4]),volume=float(r[5]) if len(r)>5 and r[5] is not None else None,is_forming=int(r[0])+seconds>now) for r in entry.get('rows',[]) if not candle_issue(r)]
            if not candles:raise RuntimeError(error or 'No broker candles available for this contract and date range.')
            # Key all completed values and settings. Any revision/anchor change
            # replays sequentially from the explicitly displayed oldest candle.
            digest=hashlib.sha256(json.dumps([config,tick,invalid,[r for r in candles if not r['is_forming']]],sort_keys=True).encode()).hexdigest()
            if invalid:
                a=dict(anchor=candles[0]['timestamp'],last=None,state={'count':None},rows=[r for r in candles if not r['is_forming']])
            elif entry.get('analysis_key')!=digest:
                entry.update(analysis=analysis(candles,config,tick,retain=None),analysis_key=digest)
            if not invalid:a=entry['analysis']
            begin=datetime.combine(first,datetime.min.time(),IST).timestamp()
            finish=datetime.combine(last+timedelta(days=1),datetime.min.time(),IST).timestamp()
            visible=[r for r in a['rows'] if begin<=r['timestamp']<finish]
            if not visible:raise RuntimeError(error or 'No broker candles in the selected review range; select dates when this contract traded.')
            meta=dict(analysis_revision=digest,requested_from=str(first),requested_to=str(last),warmup_requested_from=str(anchor),available_oldest=a['anchor'],display_oldest=visible[0]['timestamp'],display_latest=visible[-1]['timestamp'],display_count=len(visible),initialization_bars=sum(r['timestamp']<begin for r in a['rows']),source='FYERS fixed-contract OHLC · cont_flag=0 · 3-day request chunks · durable local cache',refreshed_at=entry.get('refreshed_at'),history_error=error,anchor_policy='Full sequential replay on older range or completed-data revision; signals can change with initialization anchor.',intrabar_history='Historical OHLC cannot reconstruct actual intrabar tick events or broker fills.')
            meta['data_quality']=dict(analysis_available=not bool(invalid),invalid_count=len(invalid),gaps=[r for r in invalid if begin<=r['timestamp']<finish],invalid_candles=invalid,message=('Historical OHLC validation failed; invalid candles are gaps. Renko, EMA, RSI and historical signals are unavailable for this history. Runner uses its own independently validated window.' if invalid else None))
            return a,visible,[c for c in candles if c['is_forming'] and begin<=c['timestamp']<finish],meta
