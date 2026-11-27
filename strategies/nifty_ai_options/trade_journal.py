"""Account-scoped persistent fill journal derived incrementally from recorded evidence.
No broker clients or order submission. Unknown fills/costs/multipliers remain unknown.
"""
import hashlib,json,math,sqlite3,threading,time
from pathlib import Path
DATA=Path('/home/trading/sector-heatmap/.private/nifty-ai-options')
_LOCKS={};_JOBS={};_MULTIPLIERS={};_META_LOCK=threading.Lock()

def number(v):
 return float(v) if not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v) else None

def connect(data,owner):
 if len(owner)!=32 or any(c not in '0123456789abcdef' for c in owner):raise ValueError('Exact journal account required')
 path=Path(data)/'journals'/owner/'trades.sqlite3';path.parent.mkdir(parents=True,exist_ok=True)
 db=sqlite3.connect(path,timeout=15);db.row_factory=sqlite3.Row
 db.executescript("""
 PRAGMA journal_mode=WAL;
 CREATE TABLE IF NOT EXISTS trades(id TEXT PRIMARY KEY,account TEXT,broker TEXT,mode TEXT,run_id TEXT,managed_run TEXT,
 symbol TEXT,underlying TEXT,side TEXT,quantity REAL,multiplier REAL,multiplier_source TEXT,currency TEXT,
 entry_time REAL,entry_time_basis TEXT,entry_premium REAL,entry_order TEXT,entry_cost REAL,
 exit_time REAL,exit_time_basis TEXT,exit_premium REAL,exit_order TEXT,exit_cost REAL,exit_reason TEXT,
 status TEXT,latest_price REAL,latest_time REAL,source TEXT);
 CREATE INDEX IF NOT EXISTS scoped_trades ON trades(account,mode,managed_run,status);
 CREATE TABLE IF NOT EXISTS cursors(run_id TEXT PRIMARY KEY,inode INTEGER,offset INTEGER,updated REAL);
 CREATE TABLE IF NOT EXISTS imports(run_id TEXT PRIMARY KEY,attachment_stamp INTEGER);
 """)
 return db

def multiplier(position,config,data):
 for key in ('qtyMultiplier','contract_multiplier','contract_value','quantity_multiplier'):
  v=number(position.get(key))
  if v is not None and v>0:return v,'recorded '+key
 symbol=position.get('symbol','')
 if (config.get('broker')=='MOTILAL_OSWAL' and symbol.startswith(('MO:NSE:','MO:BSE:','MO:NSEFO:','MO:BSEFO:'))) or (config.get('broker')=='DHAN' and symbol.startswith(('NSE_FNO:','BSE_FNO:','NSE_EQ:','BSE_EQ:'))):
  return 1.0,'Native Indian filled quantity is exchange units'
 if config.get('broker')=='FYERS':
  if symbol.startswith(('NSE:','BSE:')):return 1.0,'FYERS filled quantity is exchange units'
  if symbol.startswith('MCX:'):
   path=Path(data)/'instrument-multipliers'/'FYERS.json'
   if path.exists():
    stamp=path.stat().st_mtime_ns
    cached=_MULTIPLIERS.get(str(path))
    if not cached or cached[0]!=stamp:_MULTIPLIERS[str(path)]=(stamp,json.loads(path.read_text()))
    item=_MULTIPLIERS[str(path)][1].get(symbol,{})
    v=number(item.get('qtyMultiplier'))
    if v is not None and v>0:return v,'FYERS exact-symbol qtyMultiplier · '+str(item.get('as_of',''))
 return None,'Contract multiplier unavailable'

def costs(result):
 for key in ('total_costs','costs','fees','commission'):
  value=number(result.get(key))
  if value is not None and value>=0:return value
 return None

def recorded_fill(action,result,marker=None,recorded_at=None):
 if result.get('deferred'):return None
 price=number(result.get('fill_price',result.get('simulated_fill')))
 if price is None or price<=0:return None
 qty=number(result.get('filled_quantity',result.get('payload',{}).get('qty',action.get('position',{}).get('quantity'))))
 if qty is None or qty<=0:return None
 at=number(result.get('filled_at')) or number((marker or {}).get('confirmed_at')) or number(recorded_at)
 basis='recorded fill confirmation'
 if at is None:at=number(action.get('timestamp'));basis='recorded decision time; fill time unavailable'
 if result.get('fill_time_basis'):basis=str(result['fill_time_basis'])
 return dict(price=price,quantity=qty,time=at,time_basis=basis,order=str(result.get('order_id') or ''),cost=costs(result))

def ingest(db,owner,run,config,record,data,markers):
 action=record.get('action') or {};result=record.get('result') or {};operation=action.get('action')
 if operation=='EXTERNAL_FLAT':
  proof=record.get('broker_reconciliation') or {};position=action.get('position') or {}
  if config.get('execution_mode')!='LIVE' or proof.get('account')!=owner or proof.get('broker')!=config.get('broker') or proof.get('symbol')!=position.get('symbol') or proof.get('quantity')!=0 or result.get('broker_flat_confirmed') is not True or result.get('orders_submitted')!=0:return
  db.execute("UPDATE trades SET status='CLOSED',exit_time=?,exit_time_basis=?,exit_reason='EXTERNAL_BROKER_CLOSE',latest_price=NULL,latest_time=NULL WHERE account=? AND broker=? AND mode='LIVE' AND symbol=? AND entry_order=? AND quantity=? AND status='OPEN'",(proof['checked_at'],'broker-flat confirmation; exact fill unavailable',owner,config['broker'],position['symbol'],str(position.get('order_id') or ''),position.get('quantity')))
  return
 if operation not in ('BUY','SELL','OPEN_LONG','OPEN_SHORT','CLOSE_LONG','CLOSE_SHORT'):return
 position=action.get('position') or {};symbol=position.get('symbol')
 if not symbol:return
 key=(operation,symbol,action.get('timestamp'))
 fill=recorded_fill(action,result,markers.get(key),record.get('recorded_at'))
 if not fill:return
 mode=config.get('execution_mode','PAPER');broker=config.get('broker','')
 existing=db.execute("SELECT * FROM trades WHERE account=? AND broker=? AND mode=? AND symbol=? AND status='OPEN' ORDER BY entry_time DESC",(owner,broker,mode,symbol)).fetchall()
 opening=operation in ('BUY','OPEN_LONG','OPEN_SHORT')
 if opening:
  identity=hashlib.sha256(json.dumps([owner,broker,mode,fill['order'] or [run,symbol,action.get('timestamp'),operation]]).encode()).hexdigest()
  mult,source=multiplier(position,config,data)
  values=dict(id=identity,account=owner,broker=broker,mode=mode,run_id=run,managed_run=run,symbol=symbol,underlying=config.get('underlying'),side=position.get('side','SHORT' if operation=='OPEN_SHORT' else 'LONG'),quantity=fill['quantity'],multiplier=mult,multiplier_source=source,currency=config.get('quote_currency') or ('INR' if broker in ('FYERS','DHAN','MOTILAL_OSWAL') else 'USD'),entry_time=fill['time'],entry_time_basis=fill['time_basis'],entry_premium=fill['price'],entry_order=fill['order'],entry_cost=fill['cost'],status='OPEN',source='recorded simulated fill' if result.get('dry_run') else 'recorded broker-confirmed fill')
  columns=','.join(values);db.execute('INSERT OR IGNORE INTO trades('+columns+') VALUES('+','.join('?' for _ in values)+')',list(values.values()))
 else:
  duplicate=db.execute("SELECT id FROM trades WHERE account=? AND broker=? AND mode=? AND symbol=? AND status='CLOSED' AND exit_time IS ? AND exit_premium=? AND exit_order=?",(owner,broker,mode,symbol,fill['time'],fill['price'],fill['order'])).fetchone()
  if duplicate:return
  match=[row for row in existing if row['quantity']>=fill['quantity'] and (number(position.get('fill_price')) is None or row['entry_premium']==number(position.get('fill_price')))]
  by_order=[row for row in match if position.get('order_id') and row['entry_order']==str(position['order_id'])]
  if len(by_order)==1:match=by_order
  same_run=[row for row in match if row['managed_run']==run]
  if len(same_run)==1:match=same_run
  if len(match)==1 and match[0]['quantity']>fill['quantity']:
   parent=dict(match[0]);ratio=fill['quantity']/parent['quantity']
   identity=hashlib.sha256(json.dumps([parent['id'],'partial-exit',fill['order'] or [run,action.get('timestamp')],fill['quantity'],fill['price']]).encode()).hexdigest()
   if db.execute('SELECT 1 FROM trades WHERE id=?',(identity,)).fetchone():return
   closed=dict(parent,id=identity,managed_run=run,quantity=fill['quantity'],entry_cost=parent['entry_cost']*ratio if parent['entry_cost'] is not None else None,exit_time=fill['time'],exit_time_basis=fill['time_basis'],exit_premium=fill['price'],exit_order=fill['order'],exit_cost=fill['cost'],exit_reason=action.get('reason'),status='CLOSED',latest_price=None,latest_time=None)
   columns=','.join(closed);db.execute('INSERT INTO trades('+columns+') VALUES('+','.join('?' for _ in closed)+')',list(closed.values()))
   db.execute('UPDATE trades SET quantity=?,entry_cost=? WHERE id=?',(parent['quantity']-fill['quantity'],parent['entry_cost']*(1-ratio) if parent['entry_cost'] is not None else None,parent['id']))
  elif len(match)==1:
   db.execute("UPDATE trades SET managed_run=?,exit_time=?,exit_time_basis=?,exit_premium=?,exit_order=?,exit_cost=?,exit_reason=?,status='CLOSED' WHERE id=?",(run,fill['time'],fill['time_basis'],fill['price'],fill['order'],fill['cost'],action.get('reason'),match[0]['id']))
  elif not match:
   # A retained/attached holding may predate the captured entry ledger.
   entry=number(position.get('fill_price'))
   if entry is None:return
   mult,source=multiplier(position,config,data)
   identity=hashlib.sha256(json.dumps([owner,broker,mode,run,symbol,'retained-exit',action.get('timestamp')]).encode()).hexdigest()
   db.execute("""INSERT OR IGNORE INTO trades(id,account,broker,mode,run_id,managed_run,symbol,underlying,side,quantity,multiplier,multiplier_source,currency,entry_premium,entry_time_basis,exit_time,exit_time_basis,exit_premium,exit_order,exit_cost,exit_reason,status,source)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(identity,owner,broker,mode,run,run,symbol,config.get('underlying'),position.get('side','LONG'),fill['quantity'],mult,source,config.get('quote_currency') or ('INR' if broker in ('FYERS','DHAN','MOTILAL_OSWAL') else 'USD'),entry,'broker average; original fill time unavailable',fill['time'],fill['time_basis'],fill['price'],fill['order'],fill['cost'],action.get('reason'),'CLOSED','retained holding with recorded exit fill'))

def refresh_multipliers(data):
 # Public FYERS metadata only; never opens a broker trading session.
 path=Path(data)/'instrument-multipliers'/'FYERS.json'
 if path.exists() and time.time()-path.stat().st_mtime<86400:return
 import requests,os
 response=requests.get('https://public.fyers.in/sym_details/MCX_COM_sym_master.json',timeout=10)
 response.raise_for_status();raw=response.json()
 if not isinstance(raw,dict):raise ValueError('Invalid FYERS multiplier metadata')
 values={symbol:dict(qtyMultiplier=item['qtyMultiplier'],as_of=item.get('lastUpdate'),currency=item.get('currencyCode')) for symbol,item in raw.items() if isinstance(item,dict) and number(item.get('qtyMultiplier')) is not None and item['qtyMultiplier']>0}
 if not values:raise ValueError('Empty FYERS multiplier metadata')
 path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(values));os.replace(temporary,path)

def sync_account(owner,data=DATA):
 data=Path(data);db=connect(data,owner);counts=0
 try:
  base=data/'runs'/owner
  for directory in sorted(base.iterdir()) if base.exists() else []:
   if not directory.is_dir() or not (directory/'config.json').exists():continue
   config=json.loads((directory/'config.json').read_text())
   if config.get('account')!=owner or config.get('_verification_only'):continue
   run=directory.name;markers={}
   path=directory/'markers.json'
   if path.exists():
    for item in json.loads(path.read_text()):
     if item.get('confirmed') is True:markers[(item.get('action'),item.get('symbol'),item.get('timestamp'))]=item
   attachment=directory/'attachment.json'
   if attachment.exists():
    stamp=attachment.stat().st_mtime_ns;prior=db.execute('SELECT attachment_stamp FROM imports WHERE run_id=?',(run,)).fetchone()
    if not prior or prior[0]!=stamp:
     item=json.loads(attachment.read_text());position=item.get('position') or {}
     if item.get('phase')=='ATTACHED' and position.get('symbol'):
      matches=db.execute("SELECT id FROM trades WHERE account=? AND mode=? AND broker=? AND symbol=? AND quantity=? AND status='OPEN'",(owner,config.get('execution_mode'),config.get('broker'),position['symbol'],position.get('quantity'))).fetchall()
      if len(matches)==1:db.execute('UPDATE trades SET managed_run=? WHERE id=?',(run,matches[0]['id']))
      elif not matches:
       mult,source=multiplier(position,config,data);identity=hashlib.sha256(json.dumps([owner,run,position['symbol'],'attachment']).encode()).hexdigest()
       db.execute("""INSERT OR IGNORE INTO trades(id,account,broker,mode,run_id,managed_run,symbol,underlying,side,quantity,multiplier,multiplier_source,currency,entry_premium,entry_time_basis,status,source)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(identity,owner,config.get('broker'),config.get('execution_mode'),run,run,position['symbol'],config.get('underlying'),position.get('side'),position.get('quantity'),mult,source,config.get('quote_currency') or ('INR' if config.get('broker')=='FYERS' else 'USD'),position.get('fill_price'),'broker average; original fill time unavailable','OPEN','verified broker attachment'))
     db.execute('INSERT OR REPLACE INTO imports VALUES(?,?)',(run,stamp))
   for filename in ('confirmed-fills.jsonl','events.jsonl'):
    path=directory/filename
    cursor_key=run if filename=='events.jsonl' else run+'|confirmed-fills'
    if not path.exists():continue
    stat=path.stat();cursor=db.execute('SELECT inode,offset FROM cursors WHERE run_id=?',(cursor_key,)).fetchone()
    offset=cursor['offset'] if cursor and cursor['inode']==stat.st_ino and cursor['offset']<=stat.st_size else 0
    with path.open('rb') as stream:
     stream.seek(offset)
     while True:
      start=stream.tell();line=stream.readline()
      if not line:break
      if not line.endswith(b'\n'):stream.seek(start);break
      try:record=json.loads(line)
      except (ValueError,UnicodeError):continue
      if 'action' in record:ingest(db,owner,run,config,record,data,markers);counts+=1
      event=record.get('event') or {}
      if event.get('kind')=='price' and number(event.get('close')) is not None:
       quote_at=event.get('available_at',event.get('timestamp'))
       db.execute("UPDATE trades SET latest_price=?,latest_time=? WHERE account=? AND managed_run=? AND symbol=? AND status='OPEN' AND (latest_time IS NULL OR latest_time<=?) AND (entry_time IS NULL OR entry_time<=?)",(event['close'],quote_at,owner,run,event.get('symbol'),quote_at,quote_at))
     offset=stream.tell()
    db.execute('INSERT OR REPLACE INTO cursors VALUES(?,?,?,?)',(cursor_key,stat.st_ino,offset,time.time()));db.commit()
  return counts
 finally:db.close()

def calculated(row,now):
 row=dict(row);mult=row.get('multiplier');qty=row.get('quantity');entry=row.get('entry_premium');exit=row.get('exit_premium')
 sign=-1 if row.get('side')=='SHORT' else 1
 valid=all(number(v) is not None for v in (mult,qty,entry))
 row['gross_profit']=sign*(exit-entry)*qty*mult if valid and number(exit) is not None else None
 known_costs=row.get('entry_cost') is not None and row.get('exit_cost') is not None
 row['costs']=row['entry_cost']+row['exit_cost'] if known_costs else None
 row['net_profit']=row['gross_profit']-row['costs'] if row['gross_profit'] is not None and known_costs else None
 row['unrealized_gross']=sign*(row['latest_price']-entry)*qty*mult if valid and row['status']=='OPEN' and number(row.get('latest_price')) is not None else None
 row['quote_age']=now-row['latest_time'] if row.get('latest_time') else None
 row['cost_status']='Recorded' if known_costs else 'Unavailable · gross only'
 return row

def report(owner,run_id=None,data=DATA,mode='ALL',limit=500,instrument=None):
 if mode not in ('ALL','PAPER','LIVE'):raise ValueError('Choose All, Paper or Live')
 db=connect(data,owner)
 try:
  where='account=?';args=[owner]
  if instrument is not None:where+=' AND underlying=?';args.append(instrument)
  if mode!='ALL':where+=' AND mode=?';args.append(mode)
  total=db.execute('SELECT count(*) FROM trades WHERE '+where,args).fetchone()[0]
  rows=[calculated(row,time.time()) for row in db.execute('SELECT * FROM trades WHERE '+where+' ORDER BY COALESCE(exit_time,entry_time,0) DESC LIMIT ?',args+[limit])]
  current=[calculated(row,time.time()) for row in db.execute('SELECT * FROM trades WHERE account=? AND managed_run=?',(owner,run_id))] if run_id else []
  closed=[row for row in current if row['status']=='CLOSED'];opened=[row for row in current if row['status']=='OPEN']
  gross=sum(row['gross_profit'] for row in closed) if all(row['gross_profit'] is not None for row in closed) else None
  mtm=sum(row['unrealized_gross'] for row in opened) if all(row['unrealized_gross'] is not None for row in opened) else None
  net=sum(row['net_profit'] for row in closed) if closed and all(row['net_profit'] is not None for row in closed) and not opened else None
  currencies=sorted({row['currency'] for row in current})
  pnl=dict(account_id=owner,run_id=run_id,currency=currencies[0] if len(currencies)==1 else None,underlying=current[0]['underlying'] if current else None,mode=current[0]['mode'] if current else None,realized_gross=gross if current else None,unrealized_gross=mtm if current else None,total_gross=gross+mtm if current and gross is not None and mtm is not None else None,net_profit=net,costs_available=bool(closed) and all(row['costs'] is not None for row in closed),open_trades=len(opened),closed_trades=len(closed),quote_age=max((row['quote_age'] for row in opened if row['quote_age'] is not None),default=None),updated_at=time.time())
  return dict(rows=rows,total=total,limit=limit,mode=mode,current_run=pnl,read_only=True)
 finally:db.close()

def snapshot(owner,run_id=None,instrument=None):
 if len(owner)!=32 or any(c not in '0123456789abcdef' for c in owner):raise ValueError('Exact journal account required')
 with _META_LOCK:
  lock=_LOCKS.setdefault(owner,threading.Lock())
  if not lock.locked():
   lock.acquire()
   def work():
    try:_JOBS[owner]=dict(state='RUNNING',at=time.time());refresh_multipliers(DATA);sync_account(owner);_JOBS[owner]=dict(state='READY',at=time.time())
    except Exception as error:_JOBS[owner]=dict(state='ERROR',at=time.time(),error=str(error))
    finally:lock.release()
   threading.Thread(target=work,daemon=True,name='ai-trade-journal-'+owner[:6]).start()
 try:return dict(report(owner,run_id,instrument=instrument),sync=_JOBS.get(owner,dict(state='PENDING')))
 except sqlite3.OperationalError:return dict(rows=[],total=0,sync=dict(state='RUNNING'),current_run=None)
