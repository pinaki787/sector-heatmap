"""Durable exact close series consumed by one AI runtime; no broker requests."""
import hashlib,json,math,re
from pathlib import Path
try:from .run import atomic,normalize_closes
except ImportError:from run import atomic,normalize_closes

def series_key(symbol,frame):
    return hashlib.sha256((symbol+'|'+str(frame)).encode()).hexdigest()[:24]

class ChartSource:
    def __init__(self,directory):self.directory=Path(directory)
    def path(self,symbol,frame):return self.directory/(series_key(symbol,frame)+'.json')
    def persist(self,path,value):
        atomic(path,value)
        atomic(path.with_name(path.stem+'-meta.json'),dict({k:v for k,v in value.items() if k!='rows'},row_count=len(value['rows'])))

    def seed(self,symbol,frame,rows,brick):
        if frame not in (1,5,30) or not isinstance(brick,(int,float)) or isinstance(brick,bool) or not math.isfinite(brick) or brick<=0:raise ValueError('Exact source frame and fixed brick required')
        clean,audit=normalize_closes(rows)
        if not clean:raise ValueError('Empty AI source seed')
        digest=hashlib.sha256(json.dumps(clean,separators=(',',':')).encode()).hexdigest()
        value=dict(symbol=symbol,frame=frame,brick=brick,rows=clean,seed_rows=len(clean),seed_sha256=digest,revision=digest,source_basis='PROVIDER_CONFIRMED_CLOSE_ONLY',ohlc_available=False,confirmed_through=clean[-1][0])
        self.persist(self.path(symbol,frame),value)
        return value
    def append(self,event,frame):
        if event.get('source_basis')!='PROVIDER_CONFIRMED_CLOSE':raise ValueError('Only provider-confirmed source events may reach runtime charts')
        path=self.path(event['symbol'],frame);value=json.loads(path.read_text());stamp=event['timestamp'];close=event['close']
        if stamp<=value['confirmed_through']:
            old=next((r for r in value['rows'] if r[0]==stamp),None)
            if not old or old[4]!=close:raise ValueError('Runtime chart source revision/conflict requires reconciliation')
            return
        row=normalize_closes([[stamp,None,None,None,close,None]])[0][0]
        value['rows'].append(row);value['confirmed_through']=stamp
        value['revision']=hashlib.sha256((value['revision']+'|'+str(stamp)+'|'+str(close)).encode()).hexdigest()
        self.persist(path,value)

def read_source(data,owner,run_id,symbol,frame,*,after=None):
    if not isinstance(run_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id):raise ValueError('Invalid exact AI run id')
    if not isinstance(owner,str) or not re.fullmatch(r'[a-f0-9]{32}',owner):raise ValueError('Exact private AI account required')
    if frame not in (1,5,30):raise ValueError('AI runtime source supports only1/5/30 minutes')
    directory=Path(data)/'runs'/owner/run_id
    config=json.loads((directory/'config.json').read_text())
    if config.get('account')!=owner or config.get('timeframe')!=frame:raise ValueError('AI chart source differs from exact run account/timeframe')
    path=directory/'chart-source'/(series_key(symbol,frame)+'.json')
    if not path.exists():raise ValueError('This exact instrument has no captured AI runtime source')
    value=json.loads(path.read_text())
    if value.get('symbol')!=symbol or value.get('frame')!=frame:raise ValueError('AI source identity mismatch')
    clean,audit=normalize_closes(value['rows'])
    if clean!=value['rows']:raise ValueError('AI source is not the captured close-only sequence')
    if after is not None:
        cursor=float(after)
        if not math.isfinite(cursor):raise ValueError('Invalid AI chart cursor')
        clean=[r for r in clean if r[0]>cursor]
    return dict(value,rows=clean,provider='AI runtime confirmed source',run_id=run_id,account=owner,verification_only=config.get('_verification_only',False),older_history=False,read_only=True,orders_submitted=0)
