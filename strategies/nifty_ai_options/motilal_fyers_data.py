"""Explicit same-user FYERS market data, with no order methods or source fallback."""
import csv,json,math,sqlite3,time,threading
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
IST=ZoneInfo('Asia/Kolkata')

def source_account(registry,target,selected=None):
 with sqlite3.connect(Path(registry).resolve().as_uri()+'?mode=ro',uri=True) as db:
  row=db.execute('SELECT user_id,broker FROM accounts WHERE id=?',(target,)).fetchone()
  if not row or row[1]!='MOTILAL_OSWAL':raise PermissionError('FYERS split data is available only for Motilal execution')
  rows=db.execute('SELECT id FROM accounts WHERE user_id=? AND broker=?',(row[0],'FYERS')).fetchall()
 ids=[r[0] for r in rows]
 if selected:
  if selected not in ids:raise PermissionError('FYERS data account must belong to the same application user')
  return selected
 if len(ids)!=1:raise ValueError('Select exactly one of your FYERS data accounts')
 return ids[0]

def exact_option(meta,rows):
 expiry=str(meta.get('expiry',''))[:10];strike=meta.get('strike',meta.get('strike_price'))
 if not expiry or strike is None or meta.get('option_type') not in ('CE','PE'):raise ValueError('Exact native option metadata required for FYERS data')
 matches=[]
 for r in rows:
  if len(r)<=16:continue
  try:
   same=(r[9].split(':')[0]=={'NSEFO':'NSE','BSEFO':'BSE'}.get(meta['exchange'],meta['exchange']) and (str(r[12])==str(meta['token']) if meta.get('token') is not None else r[13]==meta['underlying'])
    and datetime.fromtimestamp(float(r[8]),IST).date().isoformat()==expiry
    and float(r[15])==float(strike) and r[16]==meta['option_type']
    and int(float(r[3]))==meta['lot_size'])
  except (ValueError,TypeError,KeyError,OverflowError):continue
  if same:matches.append(r[9])
 if len(matches)!=1:raise ValueError('Exact FYERS option contract is missing or ambiguous; no substituted expiry or strike')
 return matches[0]


def exact_instrument(meta,rows,*,native_lots=False):
 exchange={'NSEFO':'NSE','BSEFO':'BSE'}.get(meta['exchange'],meta['exchange'])
 derivative=str(meta.get('instrument','')).startswith('FUT')
 matches=[]
 for row in rows:
  if len(row)<=16:continue
  try:
   if row[9].split(':')[0]!=exchange:continue
   if meta.get('token') is None or str(row[12])!=str(meta['token']):continue
   if int(float(row[3]))!=int(meta['lot_size']):
    if not (native_lots and exchange=='MCX' and meta.get('native_quantity_unit')=='LOTS' and meta.get('order_quantity_multiplier')==meta['lot_size'] and int(float(row[3]))==1):continue
   if derivative:
    if row[16]!='XX' or datetime.fromtimestamp(float(row[8]),IST).date().isoformat()!=str(meta['expiry'])[:10]:continue
   else:
    if not meta.get('isin') or row[5]!=meta['isin']:continue
   matches.append(row[9])
  except (ValueError,TypeError,KeyError,OverflowError):continue
 if len(matches)!=1:raise ValueError('Exact FYERS instrument mapping is missing or ambiguous; exchange token, expiry and lot must match')
 return matches[0]

class MarketData:
 def __init__(self,config,native,root,*,client=None,clock=time.time):
  if config.get('broker')!='MOTILAL_OSWAL' or config.get('market_data_broker')!='FYERS':raise PermissionError('Explicit Motilal/FYERS data selection required')
  self.config=config;self.native=native;self.root=Path(root);self.clock=clock;self.client=client
  self.account=source_account(self.root/'.private/dashboard-login/registry.sqlite3',config['account'],config.get('market_data_account'))
  if self.account!=config.get('market_data_account'):raise PermissionError('Captured FYERS data account required')
  self.folder=self.root/'.private/dashboard-login/accounts'/self.account
  self.symbols={};self.cache={};self.last_quote={};self.minutes={};self.masters={};self.history_lock=threading.RLock()
 def api(self):
  if self.client is None:
   try:from .run import client
   except ImportError:from run import client
   self.client=client(self.account) # Existing credential/registry identity checks; no login or refresh.

  return self.client
 def symbol(self,symbol):
  if symbol in self.symbols:return self.symbols[symbol]
  meta=self.native.underlying(symbol)
  if meta.get('instrument')=='INDEX':
   from sector_heatmap.motilal_strategy_broker import INDEX_NAMES
   if symbol not in INDEX_NAMES:raise ValueError('Exact canonical index required for FYERS data')
   result=symbol
  else:
   exchange={'NSEFO':'NSE','BSEFO':'BSE'}.get(meta['exchange'],meta['exchange'])
   segment='MCX_COM' if exchange=='MCX' else exchange+'_FO' if meta.get('option_type') in ('CE','PE') or str(meta.get('instrument','')).startswith('FUT') else exchange+'_CM'
   path=self.folder/'source/.private/ema-band-masters'/(segment+'.csv')
   if not path.exists() or not 0<=self.clock()-path.stat().st_mtime<86400:raise ValueError('Refresh the selected FYERS instrument master')
   stat=path.stat();identity=(stat.st_ino,stat.st_mtime_ns,stat.st_size)
   masters=self.__dict__.setdefault('masters',{})
   cached=masters.get(segment)
   if not cached or cached['identity']!=identity:
    with path.open() as f:rows=list(csv.reader(f))
    tokens={}
    for row in rows:
     if len(row)>16:tokens.setdefault(str(row[12]),[]).append(row)
    cached=dict(identity=identity,rows=rows,tokens=tokens);masters[segment]=cached
   rows=cached['tokens'].get(str(meta['token']),[]) if meta.get('token') is not None else cached['rows']
   if meta.get('option_type') in ('CE','PE'):result=exact_option(meta,rows)
   else:result=exact_instrument(meta,rows,native_lots=True)
  self.symbols[symbol]=result;return result
 def candles(self,symbol,frame):
  cached=self.cache.get((symbol,frame))
  if cached and cached[0]==int(self.clock())//(frame*60):return cached[1]
  with self.history_lock:return self._candles(symbol,frame)
 def _candles(self,symbol,frame):
  now=self.clock();key=(symbol,frame);cached=self.cache.get(key)
  boundary=int(now)//(frame*60)
  if cached and cached[0]==boundary:return cached[1]
  mapped=self.symbol(symbol);prior=self.minutes.get(symbol,[])
  beginning=prior[-1]['timestamp']+60 if prior else int(now-10*86400)
  from sector_heatmap.fyers_history import history
  from sector_heatmap.motilal_history_seed import verified_minutes,aggregate
  try:from .fyers_history_recovery import verified_fetch
  except ImportError:from fyers_history_recovery import verified_fetch
  def fetch(start,end):
   result=history(self.api(),dict(symbol=mapped,resolution='1',date_format='0',range_from=str(int(start)),range_to=str(int(end)),cont_flag='0'))
   if result.get('s')!='ok':raise ValueError('Selected FYERS candle source unavailable; no alternate source used')
   return result.get('candles') or []
  def verify(raw,end):
   rows=verified_minutes(raw,end)
   prior_by_time={r['timestamp']:r for r in prior}
   for row in rows:
    previous=prior_by_time.get(row['timestamp'])
    if previous and any(previous[k]!=row[k] for k in ('open','high','low','close')):raise ValueError('FYERS refetch conflicts with an already committed completed candle')
   try:from .native_indian import NativeIndianAdapter
   except ImportError:from native_indian import NativeIndianAdapter
   from types import SimpleNamespace
   validator=SimpleNamespace(config=dict(self.config,underlying=self.config.get('underlying',symbol),market=self.config.get('market',mapped.split(':')[0])),native=self.native)
   previous=None
   for row in rows:
    stamp=datetime.fromtimestamp(row['timestamp'],IST)
    session=NativeIndianAdapter.session(validator,at=row['timestamp'])
    if not session['opening_minutes']<=stamp.hour*60+stamp.minute<session['closing_minutes']:continue
    if previous and previous[0]==stamp.date() and row['timestamp']-previous[1]!=60:raise ValueError('FYERS regular-session minute history contains a gap')
    previous=(stamp.date(),row['timestamp'])
   return rows
  incoming=verified_fetch(request=fetch,verify=verify,scope=dict(data_account=self.account,execution_account=self.config['account'],broker='FYERS',symbol=mapped,session=datetime.fromtimestamp(now,IST).date().isoformat()),folder=self.root/'.private/nifty-ai-options/history-recovery',now=now,range_from=beginning,range_to=int(now)//60*60)
  merged={r['timestamp']:r for r in prior};merged.update({r['timestamp']:r for r in incoming})
  minutes=sorted(merged.values(),key=lambda r:r['timestamp'])[-20000:];self.minutes[symbol]=minutes
  opening=self.native.session_policy(dict(self.config,underlying=symbol))['session_open']
  rows=aggregate(minutes,frame*60,opening,now)
  rows=[dict(r,symbol=symbol,broker='FYERS',account=self.account,source_symbol=mapped,execution_broker='MOTILAL_OSWAL',execution_account=self.config['account']) for r in rows]
  self.cache[key]=(boundary,rows);return rows

 def premium_quotes(self,contracts):
  # One bounded broker quote batch per 50 exact contracts, never a request per strike.
  mapped={}
  for row in contracts:
   try:mapped[self.symbol(row['symbol'])]=row['symbol']
   except ValueError:continue
  names=list(mapped);quotes={}
  for start in range(0,len(names),50):
   result=self.api().quotes(data={'symbols':','.join(names[start:start+50])});now=self.clock()
   if result.get('s')!='ok':raise ValueError('FYERS option quote batch unavailable')
   for row in result.get('d',[]):
    symbol=mapped.get(row.get('n'));v=row.get('v') or {};stamp=v.get('tt')
    if not symbol or row.get('s')!='ok' or isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or not 0<=now-stamp<=5:continue
    bid,ask=v.get('bid'),v.get('ask')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (bid,ask)) or not 0<bid<=ask:continue
    quotes[symbol]=dict(symbol=symbol,bid=bid,ask=ask,last_price=v.get('lp'),exchange_at=stamp,received_at=now,broker='FYERS',account=self.account)
  return quotes
 def quote(self,symbol):
  now=self.clock();cached=self.last_quote.get(symbol)
  if cached and now-cached[0]<1:return cached[1]
  mapped=self.symbol(symbol);result=self.api().quotes(data={'symbols':mapped})
  rows=[r for r in result.get('d',[]) if r.get('n')==mapped and r.get('s')=='ok']
  if result.get('s')!='ok' or len(rows)!=1:raise ValueError('Exact FYERS live quote unavailable')
  v=rows[0]['v'];price=v.get('lp');stamp=v.get('tt')
  if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in (price,stamp)) or price<=0 or not 0<=now-stamp<=5:raise ValueError('Fresh exchange-timestamped FYERS quote required')
  bid,ask=v.get('bid'),v.get('ask')
  value=dict(symbol=symbol,last_price=price,bid=bid,ask=ask,exchange_at=stamp,received_at=now,broker='FYERS',account=self.account)
  self.last_quote[symbol]=(now,value);return value
 def price(self,symbol):
  q=self.quote(symbol);return q['last_price'],q['exchange_at']
