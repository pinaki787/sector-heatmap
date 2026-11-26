"""Durable same-source candle deduplication and bounded evidence-based recovery."""
import hashlib,json,fcntl,sqlite3
from contextlib import closing
from pathlib import Path
def conflicts(raw):
 groups={}
 for row in raw if isinstance(raw,list) else []:
  if isinstance(row,list) and len(row)>=6:groups.setdefault(row[0],[]).append(row)
 return {t:rs for t,rs in groups.items() if any(r[1:5]!=rs[0][1:5] for r in rs)}
def verified_fetch(*,request,verify,scope,folder,now,range_from,range_to):
 try:from .run import atomic
 except ImportError:from run import atomic
 key=hashlib.sha256(json.dumps(scope,sort_keys=True).encode()).hexdigest()
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=True,mode=0o700)
 path=folder/(key+'.json');committed_path=folder/(key+'.committed')
 with (folder/(key+'.lock')).open('a') as lock, closing(sqlite3.connect(folder/(key+'.committed.sqlite3'))) as archive_db:
  fcntl.flock(lock,fcntl.LOCK_EX)
  state=json.loads(path.read_text()) if path.exists() else None
  archive_db.execute('CREATE TABLE IF NOT EXISTS metadata(scope TEXT NOT NULL)')
  archive_db.execute('CREATE TABLE IF NOT EXISTS candles(timestamp INTEGER PRIMARY KEY, row_json TEXT NOT NULL)')
  identity=json.dumps(scope,sort_keys=True)
  stored=archive_db.execute('SELECT scope FROM metadata').fetchone()
  if stored and stored[0]!=identity or state and state.get('scope')!=scope:raise ValueError('FYERS recovery scope mismatch')
  if not stored:
   archive_db.execute('INSERT INTO metadata VALUES (?)',(identity,))
   if committed_path.exists():
    legacy=json.loads(committed_path.read_text())
    if legacy.get('scope')!=scope:raise ValueError('FYERS committed archive scope mismatch')
    archive_db.executemany('INSERT OR IGNORE INTO candles VALUES (?,?)',[(r['timestamp'],json.dumps(r)) for r in legacy['rows']])
   archive_db.commit()
  (folder/(key+'.committed.sqlite3')).chmod(0o600)
  committed={}
  have_archive=archive_db.execute('SELECT 1 FROM candles LIMIT 1').fetchone() is not None
  def save():atomic(path,state)
  def load_committed(raw):
   if not isinstance(raw,list):return
   stamps=list({r[0] for r in raw if isinstance(r,list) and len(r)>=6 and isinstance(r[0],(int,float))})
   for offset in range(0,len(stamps),900):
    part=stamps[offset:offset+900]
    for stamp,value in archive_db.execute('SELECT timestamp,row_json FROM candles WHERE timestamp IN ('+','.join('?' for _ in part)+')',part):committed[stamp]=json.loads(value)
  def commit(rows):
   # Insert new completed identities only; no rewrite of existing candles/history.
   additions=[(r['timestamp'],json.dumps(r)) for r in rows if isinstance(r,dict) and r.get('timestamp') is not None]
   archive_db.executemany('INSERT OR IGNORE INTO candles VALUES (?,?)',additions);archive_db.commit()
  def protected(raw):
   nonlocal state
   if not isinstance(raw,list):return raw
   load_committed(raw)
   working=[];quarantine=[]
   resolutions=(state or {}).get('resolutions',{})
   narrow=(state or {}).get('narrow_probe',{}).get('result',{})
   if narrow.get('resolved'):
    for row in narrow['attempts'][0]['rows']:resolutions[str(row['timestamp'])]=row
   for row in raw:
    if not isinstance(row,list) or len(row)<6:working.append(row);continue
    known=committed.get(row[0]) or resolutions.get(str(row[0]))
    if known:
     values=[known[k] for k in ('open','high','low','close')]
     if row[1:5]!=values:
      quarantine.append(dict(timestamp=row[0],incoming=row,retained=known))
      row=[row[0],*values,*row[5:]]
    working.append(row)
   if quarantine:
    if state is None:state=dict(scope=scope,state='RECOVERED',attempts=0,events=[])
    state.setdefault('quarantine',[]).extend(quarantine);state['quarantine']=state['quarantine'][-1000:]
    state['resolutions']=resolutions;save()
   return working
  # An independently verified narrow response or an existing committed candle can
  # repair a quarantined bulk response without another broad provider request.
  if state and state['state']!='RECOVERED' and state.get('events'):
   last=next((e.get('raw') for e in reversed(state['events']) if isinstance(e.get('raw'),list)),None)
   if last and (have_archive or (state.get('narrow_probe',{}).get('result',{}).get('resolved'))):
    try:
     rows=verify(protected(last),state['range_to'])
     if rows:
      commit(rows);state.update(state='RECOVERED',recovered_at=now,recovery_basis='Previously committed / independently refetched exact minute');save();return rows
    except ValueError:pass
  if state and state['state']!='RECOVERED':
   if now<state.get('next_at',0):raise ValueError('FYERS candle recovery cooling down; same-account retry pending')
   pending=state.get('narrow_pending')
   if pending:
    if pending.get('requests',0)>=2:raise ValueError('FYERS narrow recovery exhausted; contradictory minute remains quarantined')
    pending['requests']=pending.get('requests',0)+1;save() # claim before network, survives a crash
    stamp=pending['timestamp']
    raw=request(stamp,stamp+59)
    try:
     rows=verify(raw,stamp+60)
     if len(rows)!=1 or rows[0]['timestamp']!=stamp:raise ValueError('Narrow refetch did not uniquely validate the required minute')
     digest=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
     if pending.get('candidate_hash')==digest:
      state.setdefault('resolutions',{})[str(stamp)]=rows[0];state.pop('narrow_pending',None)
      raw_full=state['events'][0]['raw'];result=verify(protected(raw_full),state['range_to'])
      commit(result);state.update(state='RECOVERED',recovered_at=now,recovery_basis='Two identical independent exact-minute refetches');save();return result
     if pending.get('candidate_hash'):raise ValueError('Independent narrow refetches disagree')
     pending.update(candidate_hash=digest,candidate=rows[0]);state['next_at']=now+5;save()
     raise ValueError('FYERS exact-minute refetch is clean; waiting for independent confirmation')
    except ValueError as error:
     if pending.get('requests',0)>=2:state.update(state='BLOCKED',error=str(error))
     save();raise
   if state['state']=='BLOCKED':raise ValueError('FYERS candle recovery exhausted: '+state['error']+'; inspect source history before resetting recovery')
   beginning,end=state['range_from'],state['range_to']
  else:beginning,end=range_from,range_to
  raw=None
  try:
   raw=request(beginning,end);rows=verify(protected(raw),end)
  except (ValueError,RuntimeError,TimeoutError,ConnectionError,OSError) as error:
   prior=state if state and state['state']!='RECOVERED' else None
   state=dict(scope=scope,state='RETRY_PENDING',range_from=beginning,range_to=end,attempts=(prior or {}).get('attempts',0)+1,error=str(error) if isinstance(error,(ValueError,RuntimeError)) else type(error).__name__,first_at=(prior or {}).get('first_at',now),next_at=now+max(5,getattr(error,'retry_after',5)),events=(prior or {}).get('events',[]))
   state['events'].append(dict(at=now,error=state['error'],raw=raw))
   ambiguous=conflicts(raw)
   if len(ambiguous)==1 and not prior:
    stamp=next(iter(ambiguous))
    if isinstance(stamp,(int,float)) and stamp+60<=end:state['narrow_pending']=dict(timestamp=stamp,requests=0)
   if state['attempts']>=3 or type(error).__name__=='FyersHistoryAuthenticationRequired':state['state']='BLOCKED'
   save();raise ValueError('FYERS history validation failed; bounded same-account recovery scheduled: '+str(error)) from None
  if not state or state['state']=='RECOVERED':commit(rows);return rows
  state['attempts']+=1
  digest=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
  if state.get('candidate_hash')==digest:
   commit(rows);state.update(state='RECOVERED',recovered_at=now,validated_hash=digest);save();return rows
  state['events'].append(dict(at=now,validated_hash=digest,rows=len(rows)))
  if state.get('candidate_hash') or state['attempts']>=3:
   state.update(state='BLOCKED',error='Refetched history did not establish two identical validated closed windows');save()
   raise ValueError('FYERS candle conflict remains unverified after bounded recovery')
  if not rows:
   state.update(state='BLOCKED',error='Recovery window is empty');save();raise ValueError(state['error'])
  state.update(state='CONFIRMING',candidate_hash=digest,next_at=now+5);save()
  raise ValueError('FYERS history refetch is clean; awaiting independent consistency confirmation')
