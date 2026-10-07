"""Public completed-candle archive, independent of execution ledgers."""
import csv,hashlib,io,json,math,os,re,sqlite3,threading,weakref
from pathlib import Path
ENV='INDIA_PRODUCTION'
class CandleArchive:
 def __init__(self,path,mirror=None):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock();self.mirror=Path(mirror) if mirror else None;self.mirror_error=None
  self.db=sqlite3.connect(self.path,check_same_thread=False);self.path.chmod(0o600);self.finalizer=weakref.finalize(self,self.db.close)
  self.db.executescript('CREATE TABLE IF NOT EXISTS contracts(symbol TEXT,resolution TEXT,product TEXT,last_refresh REAL,error TEXT,PRIMARY KEY(symbol,resolution));CREATE TABLE IF NOT EXISTS candles(symbol TEXT,resolution TEXT,time REAL,data TEXT,observed REAL,PRIMARY KEY(symbol,resolution,time));CREATE TABLE IF NOT EXISTS revisions(symbol TEXT,resolution TEXT,time REAL,previous TEXT,replacement TEXT,observed REAL);');self.db.commit()
 def watch(self,product,resolution):
  symbol=product['symbol']
  if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{0,79}',symbol) or not re.fullmatch(r'[0-9]+[mhdw]',resolution):raise ValueError('Invalid archive contract/timeframe.')
  with self.lock,self.db:
   old=self.db.execute('SELECT product FROM contracts WHERE symbol=? AND resolution=?',(symbol,resolution)).fetchone()
   if old and json.loads(old[0]).get('id')!=product.get('id'):raise ValueError('Archive product identity changed; no history merged.')
   self.db.execute('INSERT INTO contracts VALUES(?,?,?,NULL,NULL) ON CONFLICT(symbol,resolution) DO UPDATE SET product=excluded.product',(symbol,resolution,json.dumps(product,sort_keys=True)))
 def ingest(self,product,resolution,rows,interval,now):
  unique={}
  for row in rows:
   if row.get('is_forming') or row['timestamp']+interval>now:continue
   values={k:float(row[k]) for k in ('timestamp','open','high','low','close','volume')}
   if not all(math.isfinite(v) for v in values.values()) or values['timestamp']<=0 or min(values[k] for k in ('open','high','low','close'))<=0 or values['high']<max(values['open'],values['close']) or values['low']>min(values['open'],values['close']) or values['volume']<0:raise ValueError('Invalid archive candle.')
   values['is_forming']=False;t=values['timestamp']
   if t in unique and unique[t]!=values:raise ValueError('Conflicting timestamps in one broker response; archive not updated.')
   unique[t]=values
  self.watch(product,resolution);symbol=product['symbol']
  with self.lock,self.db:
   for t,values in unique.items():
    data=json.dumps(values,sort_keys=True);old=self.db.execute('SELECT data FROM candles WHERE symbol=? AND resolution=? AND time=?',(symbol,resolution,t)).fetchone()
    if old and old[0]!=data:self.db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?)',(symbol,resolution,t,old[0],data,now))
    self.db.execute('INSERT INTO candles VALUES(?,?,?,?,?) ON CONFLICT(symbol,resolution,time) DO UPDATE SET data=excluded.data,observed=excluded.observed',(symbol,resolution,t,data,now))
   self.db.execute('UPDATE contracts SET last_refresh=?,error=NULL WHERE symbol=? AND resolution=?',(now,symbol,resolution))
  if self.mirror:
   try:self.export(symbol,resolution);self.mirror_error=None
   except Exception as error:self.mirror_error=str(error)
 def fail(self,symbol,resolution,error):
  with self.lock,self.db:self.db.execute('UPDATE contracts SET error=? WHERE symbol=? AND resolution=?',(str(error),symbol,resolution))
 def read(self,symbol,resolution,limit=10000):
  with self.lock:
   contract=self.db.execute('SELECT product,last_refresh,error FROM contracts WHERE symbol=? AND resolution=?',(symbol,resolution)).fetchone()
   if not contract:raise ValueError('No saved history for this contract/timeframe.')
   rows=self.db.execute('SELECT data FROM candles WHERE symbol=? AND resolution=? ORDER BY time DESC LIMIT ?',(symbol,resolution,limit)).fetchall();candles=[json.loads(r[0]) for r in reversed(rows)]
   count=self.db.execute('SELECT COUNT(*) FROM candles WHERE symbol=? AND resolution=?',(symbol,resolution)).fetchone()[0];revisions=self.db.execute('SELECT COUNT(*) FROM revisions WHERE symbol=? AND resolution=?',(symbol,resolution)).fetchone()[0]
   return dict(environment=ENV,symbol=symbol,timeframe=resolution,product=json.loads(contract[0]),candles=candles,count=count,first_saved=candles[0]['timestamp'] if candles else None,last_saved=candles[-1]['timestamp'] if candles else None,last_refresh=contract[1],error=contract[2],revisions=revisions,source='Saved Delta India public REST completed candles',analysis_only=True,mirror_error=self.mirror_error)
 def watches(self):
  with self.lock:return [(json.loads(p),r) for p,r in self.db.execute('SELECT product,resolution FROM contracts')]
 def export(self,symbol,resolution):
  with self.lock:self._export(symbol,resolution)
 def _export(self,symbol,resolution):
  if not self.mirror:return
  data=self.read(symbol,resolution,10000000);self.mirror.mkdir(parents=True,exist_ok=True);stem='DeltaIndia_'+symbol+'_'+resolution
  stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=['timestamp','open','high','low','close','volume']);writer.writeheader();writer.writerows({k:c[k] for k in writer.fieldnames} for c in data.pop('candles'))
  payload=stream.getvalue();data['csv_sha256']=hashlib.sha256(payload.encode()).hexdigest();data['timestamp_basis']='UTC Unix seconds; candle opening time';data['completed_only']=True
  for suffix,value in [('.csv',payload),('.json',json.dumps(data,indent=2)+'\n')]:
   target=self.mirror/(stem+suffix);temporary=target.with_suffix(target.suffix+'.tmp');temporary.write_text(value);os.replace(temporary,target)
