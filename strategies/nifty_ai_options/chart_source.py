"""Durable exact close series consumed by one AI runtime; no broker requests."""
import hashlib,json,math,re,threading
from bisect import bisect_right
from collections import OrderedDict
from pathlib import Path
try:from .run import atomic,normalize_closes
except ImportError:from run import atomic,normalize_closes

def source_rows(rows,full=False):
    clean,_=normalize_closes(rows)
    if not full:return clean
    by_stamp={}
    for row in rows:
        if len(row)<5 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0 for x in row[1:5]) or not row[3]<=min(row[1],row[4])<=max(row[1],row[4])<=row[2]:raise ValueError('Candles mode requires complete real broker OHLC')
        value=list(row[:5])+[row[5] if len(row)>5 else None]
        if row[0] in by_stamp and by_stamp[row[0]][:5]!=value[:5]:raise ValueError('Conflicting owned candle OHLC')
        by_stamp[row[0]]=value
    return [by_stamp[row[0]] for row in clean]


def series_key(symbol,frame):
    return hashlib.sha256((symbol+'|'+str(frame)).encode()).hexdigest()[:24]

_cache_lock=threading.RLock()
_price_cache=OrderedDict()
_seed_cache=OrderedDict()
_band_cache=OrderedDict()
def _seed(path):
    stat=path.stat();identity=(stat.st_ino,stat.st_mtime_ns,stat.st_size)
    with _cache_lock:
        old=_seed_cache.get(path)
        if old and old[0]==identity:return old[1]
        value=json.loads(path.read_text())
        clean=source_rows(value['rows'],value.get('ohlc_available',False))
        if clean!=value['rows']:raise ValueError('AI source is not the captured close-only sequence')
        _seed_cache[path]=(identity,value);_seed_cache.move_to_end(path)
        while len(_seed_cache)>64:_seed_cache.popitem(last=False)
        return value

def _price_tail(path,symbol,seed_end,cursor,forming_config=None,epoch=None):
    with _cache_lock:
        stat=path.stat();cache_key=(path,'hybrid',epoch) if forming_config and epoch else (path,epoch) if epoch else (path,'hybrid') if forming_config else path;state=_price_cache.get(cache_key)
        if state is None or state['inode']!=stat.st_ino or stat.st_size<state['offset']:
            state=dict(inode=stat.st_ino,offset=0,rows=[],times=[],sequence=0,bytes_read=0)
            _price_cache[cache_key]=state
        if stat.st_size>state['offset']:
            with path.open('rb') as stream:
                stream.seek(state['offset']);chunk=stream.read()
            # A concurrent writer may not yet have completed its last line.
            complete=chunk.rfind(b'\n')+1
            added=[];sequence=state['sequence'];prior=state['times'][-1] if state['times'] else seed_end
            for line in chunk[:complete].splitlines():
                event=json.loads(line);stamp=event.get('available_at');close=event.get('close');seq=event.get('sequence')
                if event.get('symbol')!=symbol or event.get('source_basis')!='BROKER_LIVE_PRICE' or isinstance(seq,bool) or not isinstance(seq,int) or seq<=sequence or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (stamp,close)) or stamp<=prior or close<=0:raise ValueError('Runtime live-price ordering requires reconciliation')
                if forming_config:
                    try:from .hybrid_basis import bucket
                    except ImportError:from hybrid_basis import bucket
                    from types import SimpleNamespace
                    source_at=event.get('timestamp')
                    if isinstance(source_at,bool) or not isinstance(source_at,(int,float)) or not math.isfinite(source_at) or source_at<=0 or source_at>stamp:raise ValueError('Invalid captured hybrid provider timestamp')
                    start=bucket(SimpleNamespace(config=forming_config),source_at)
                    forming=state.get('forming')
                    if forming and start<forming[0]:raise ValueError('Captured hybrid provider time regressed')
                    if not forming or start!=forming[0]:state['forming']=[start,close,close,close,close,None]
                    else:forming[2]=max(forming[2],close);forming[3]=min(forming[3],close);forming[4]=close
                added.append([stamp,None,None,None,close,None]);sequence=seq;prior=stamp
            state['rows'].extend(added);state['times'].extend(r[0] for r in added)
            state['sequence']=sequence;state['offset']+=complete;state['bytes_read']+=len(chunk)
        _price_cache.move_to_end(cache_key)
        while len(_price_cache)>64:_price_cache.popitem(last=False)
        index=bisect_right(state['times'],cursor) if cursor is not None else 0
        result=([] if forming_config else state['rows'][index:],len(state['rows']),state['sequence'],state['times'][-1] if state['times'] else seed_end)
        return result+(list(state['forming']) if state.get('forming') else None,) if forming_config else result

def _band_tail(path,cursor,epoch=None):
    if not path.exists():return []
    with _cache_lock:
        stat=path.stat();cache_key=(path,epoch) if epoch else path;state=_band_cache.get(cache_key)
        if not state or state['inode']!=stat.st_ino or stat.st_size<state['offset']:state=dict(inode=stat.st_ino,offset=0,rows=[])
        if stat.st_size>state['offset']:
            with path.open('rb') as stream:stream.seek(state['offset']);chunk=stream.read()
            complete=chunk.rfind(b'\n')+1
            added=[json.loads(line) for line in chunk[:complete].splitlines()]
            state['rows'].extend(added)
            state['offset']+=complete
        _band_cache[cache_key]=state;_band_cache.move_to_end(cache_key)
        while len(_band_cache)>64:_band_cache.popitem(last=False)
        return [r for r in state['rows'] if cursor is None or r['available_at']>cursor]

class ChartSource:
    def __init__(self,directory,calculation_mode='RENKO'):
        self.directory=Path(directory);self.calculation_mode=calculation_mode
        if calculation_mode not in ('RENKO','CANDLES','HYBRID'):raise ValueError('Invalid chart calculation mode')
    def path(self,symbol,frame):return self.directory/(series_key(symbol,frame)+'.json')
    def persist(self,path,value):
        atomic(path,value)
        atomic(path.with_name(path.stem+'-meta.json'),dict({k:v for k,v in value.items() if k!='rows'},row_count=len(value['rows'])))

    def seed(self,symbol,frame,rows,brick,*,preserve_observations=False):
        if frame not in (1,5,30) or not isinstance(brick,(int,float)) or isinstance(brick,bool) or not math.isfinite(brick) or brick<=0:raise ValueError('Exact source frame and fixed brick required')
        full=self.calculation_mode in ('CANDLES','HYBRID')
        clean=source_rows(rows,full)
        if not clean:raise ValueError('Empty AI source seed')
        digest=hashlib.sha256(json.dumps(clean,separators=(',',':')).encode()).hexdigest()
        value=dict(symbol=symbol,frame=frame,brick=brick,rows=clean,seed_rows=len(clean),seed_sha256=digest,revision=digest,source_basis='PROVIDER_CONFIRMED_OHLC' if full else 'PROVIDER_CONFIRMED_CLOSE_ONLY',calculation_mode=self.calculation_mode,ohlc_available=full,confirmed_through=clean[-1][0])
        self.persist(self.path(symbol,frame),value)
        if not preserve_observations:
            self.path(symbol,frame).with_name(self.path(symbol,frame).stem+'-observations.jsonl').unlink(missing_ok=True)
            self.path(symbol,frame).with_name(self.path(symbol,frame).stem+'-signals.jsonl').unlink(missing_ok=True)
        return value
    def flush_signals(self,engine):
        queue=getattr(engine,'completed_signal_queue',[])
        if not queue:return
        for point in queue:
            path=self.path(point['symbol'],engine.config['timeframe'])
            target=path.with_name(path.stem+'-signals.jsonl')
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('a') as stream:stream.write(json.dumps(point,separators=(',',':'))+'\n')
        queue.clear()
    def decide(self,engine,event):
        actions=engine.update_hybrid(event)
        self.flush_signals(engine)
        return actions
    def seed_bands(self,engine):
        self.flush_signals(engine)
        snapshot=engine.band.snapshot(engine.config,include_history=True)
        if not snapshot['bands']:return
        if not snapshot.get('underlying'):return
        path=self.path(snapshot['underlying'],engine.config['timeframe'])
        atomic(path.with_name(path.stem+'-band-seed.json'),snapshot)
        path.with_name(path.stem+'-bands.jsonl').unlink(missing_ok=True)
    def append_bands(self,engine,event):
        if event['kind']!=engine.config.get('band_price_basis','underlying'):return
        snapshot=engine.band.snapshot(engine.config)
        if not snapshot['bands']:return
        if not snapshot.get('underlying'):return
        path=self.path(snapshot['underlying'],engine.config['timeframe'])
        with path.with_name(path.stem+'-bands.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(snapshot,available_at=event.get('available_at',event['timestamp'])),separators=(',',':'))+'\n')

    def roll_timeframe(self,symbols,old,new):
        for symbol in symbols:
            path=self.path(symbol,old)
            if not path.exists():continue
            value=json.loads(path.read_text());value=dict(value,frame=new,initialization_frame=value.get('initialization_frame',old))
            self.persist(self.path(symbol,new),value)
            observations=path.with_name(path.stem+'-observations.jsonl')
            target=self.path(symbol,new).with_name(self.path(symbol,new).stem+'-observations.jsonl')
            if observations.exists() and observations!=target:
                temporary=target.with_suffix('.tmp');temporary.write_bytes(observations.read_bytes());temporary.replace(target)

    def append_observation(self,event,frame):
        """Append exact decision input once; timestamps are observed, never synthesized."""
        if event.get('kind')!='price' or event.get('source_basis')!='BROKER_LIVE_PRICE':raise ValueError('Exact broker live price observation required')
        symbol=event.get('symbol')
        if not isinstance(symbol,str) or not symbol:raise ValueError('Exact observation symbol required')
        for field in ('timestamp','available_at','close'):
            value=event.get(field)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Invalid live observation '+field)
        sequence=event.get('sequence')
        if isinstance(sequence,bool) or not isinstance(sequence,int) or sequence<1:raise ValueError('Ordered observation sequence required')
        path=self.directory/(series_key(symbol,frame)+'-observations.jsonl')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a') as out:out.write(json.dumps(event,separators=(',',':'))+'\n')

    def append(self,event,frame):
        if event.get('source_basis')!='PROVIDER_CONFIRMED_CLOSE':raise ValueError('Only provider-confirmed source events may reach runtime charts')
        path=self.path(event['symbol'],frame);value=json.loads(path.read_text());stamp=event['timestamp'];close=event['close']
        if stamp<=value['confirmed_through']:
            old=next((r for r in value['rows'] if r[0]==stamp),None)
            if not old or old[4]!=close or (value.get('ohlc_available') and old[1:5]!=[event.get('open'),event.get('high'),event.get('low'),close]):raise ValueError('Runtime chart source revision/conflict requires reconciliation')
            return
        row=source_rows([[stamp,event.get('open'),event.get('high'),event.get('low'),close,event.get('volume')]],value.get('ohlc_available',False))[0]
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
    value=_seed(path)
    if value.get('symbol')!=symbol or value.get('frame')!=frame:raise ValueError('AI source identity mismatch')
    cursor=None
    if after is not None:
        cursor=float(after)
        if not math.isfinite(cursor):raise ValueError('Invalid AI chart cursor')
    observations=path.with_name(path.stem+'-observations.jsonl')
    if observations.exists() and value.get('calculation_mode')=='HYBRID':
        _,count,sequence,through,forming=_price_tail(observations,symbol,value['rows'][value['seed_rows']-1][0],None,forming_config=config,epoch=config.get('runtime_session'))
        clean=value['rows'] if cursor is None else [r for r in value['rows'] if r[0]>cursor]
        if forming and forming[0]>value['confirmed_through']:
            clean=list(clean)+[forming]
            value=dict(value,source_basis='BROKER_CONFIRMED_AND_OBSERVED_FORMING',provisional_at=forming[0],forming_at=through,hybrid_source_state='READY' if forming[0]<=value['confirmed_through']+frame*60 else 'WAITING_FOR_PREVIOUS_CANDLE')
        value=dict(value,observation_count=count,last_observation_sequence=sequence)
    elif observations.exists() and not value.get('ohlc_available'):
        seed=value['rows'][:value['seed_rows']]
        prices,count,sequence,through=_price_tail(observations,symbol,seed[-1][0],cursor,epoch=config.get('runtime_session'))
        clean=([r for r in seed if cursor is None or r[0]>cursor])+prices
        value=dict(value,source_basis='BROKER_SEED_AND_LIVE_PRICE',observation_count=count,last_observation_sequence=sequence,confirmed_through=through)
    else:
        clean=value['rows'] if cursor is None else [r for r in value['rows'] if r[0]>cursor]
    signal_points=[]
    if config.get('supertrend_basis')=='COMPLETED_RENKO':
        signal_points=_band_tail(path.with_name(path.stem+'-signals.jsonl'),cursor,epoch=config.get('runtime_session'))
    moving_bands=[]
    band_seed=path.with_name(path.stem+'-band-seed.json')
    if cursor is None and band_seed.exists():moving_bands.append(json.loads(band_seed.read_text()))
    moving_bands.extend(_band_tail(path.with_name(path.stem+'-bands.jsonl'),cursor,epoch=config.get('runtime_session')))
    return dict(value,supertrend_basis=config.get('supertrend_basis'),signal_points=signal_points,moving_bands=moving_bands,rows=clean,provider='AI runtime confirmed source',run_id=run_id,account=owner,verification_only=config.get('_verification_only',False),older_history=False,read_only=True,orders_submitted=0)
