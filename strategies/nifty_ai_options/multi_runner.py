"""Instrument-scoped AI workers with durable account-wide admission.

No import, listing, or scope operation activates a worker or submits an order.
Legacy workers retain their original paths and must finish before scoped workers.
"""
import functools,hashlib,json,math,os,re,time
from contextlib import contextmanager
from pathlib import Path
import fcntl

DATA=Path('/home/trading/sector-heatmap/.private/nifty-ai-options')
REVISION='instrument-workers-v1'
LEDGERS={'delta-live.json','delta-paper.json','direct-live.json','direct-paper.json',
         'native-indian-live.json','native-indian-paper.json','live.json','paper.json'}
EXPOSURE=('position','pending','positions','closing_legs','detached_position','stop_verification_position')

def symbol(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Z0-9][A-Z0-9:_.&/-]{0,159}',value):
  raise ValueError('Exact broker instrument required')
 return value

def scope(value):return hashlib.sha256(symbol(value).encode()).hexdigest()[:24]

def binding(config):
 expected=scope(config['underlying'])
 if config.get('runner_scope') not in (None,expected):raise ValueError('Runner scope differs from captured instrument')
 return expected

def runtime_root(config,data=DATA):
 """Pure path lookup; old configurations keep their exact legacy ledger."""
 if not config.get('runner_scope'):return Path(data)/'runtime'
 binding(config)
 return Path(data)/'runtime'/'instruments'/config['account']/config['runner_scope']

def configure_executor(executor,config,data=DATA):
 """Metadata is diagnostic/admission binding; credentials never enter it."""
 executor.runner_config=dict(config);executor.runner_data=Path(data)
 native=getattr(getattr(executor,'adapter',None),'native',None) or getattr(getattr(executor,'api',None),'native',None)
 if native is not None:native._ai_instrument_context=(dict(config),Path(data))
 if config.get('runner_scope'):
  from strategies.nifty_ai_options.run import atomic
  path=runtime_root(config,data)/'binding.json'
  atomic(path,{k:config.get(k) for k in ('account','broker','underlying','runner_scope','execution_mode','execution_route')})
 return executor

def rows(owner,data=DATA):
 from strategies.nifty_ai_options.process_state import identity,fingerprint
 result=[]
 for directory in sorted((Path(data)/'runs'/owner).glob('*'),reverse=True):
  p=directory/'config.json'
  if not p.exists():continue
  c=json.loads(p.read_text())
  if c.get('account')!=owner:raise ValueError('Run owner mismatch')
  if c.get('_verification_only'):continue
  record=json.loads((directory/'process.json').read_text()) if (directory/'process.json').exists() else {}
  active=bool(record and identity(record.get('pid'),directory.resolve())==record)
  claim_path=directory/'launching.json';claim=json.loads(claim_path.read_text()) if claim_path.exists() else {}
  launching=bool(claim and time.time()-claim.get('at',0)<600 and fingerprint(claim.get('pid'))==claim.get('start_ticks'))
  result.append(dict(launching=launching,run_id=directory.name,instrument=c['underlying'],runner_scope=binding(c),
    mode=c.get('execution_mode','PAPER'),running=active,legacy_scope=not bool(c.get('runner_scope')),
    directory=directory,config=c))
 return result

def selected_symbol(owner,fields,data=DATA):
 fields=fields or {};value=fields.get('runner_symbol')
 run=fields.get('run_id')
 if run:
  if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',run):raise ValueError('Invalid run identity')
  c=json.loads((Path(data)/'runs'/owner/run/'config.json').read_text())
  if c.get('account')!=owner:raise ValueError('Run owner differs')
  if value and value!=c['underlying']:raise ValueError('Selected runner and run instrument differ')
  value=c['underlying']
 return symbol(value) if value else ('' if 'runner_symbol' in fields else None)

def inventory(owner,data=DATA):
 latest={}
 for row in rows(owner,data):
  old=latest.get(row['runner_scope'])
  if old is None or row['running'] and not old['running']:latest[row['runner_scope']]=row
 result=[]
 for row in latest.values():
  heartbeat=row['directory']/'heartbeat.json';h=json.loads(heartbeat.read_text()) if heartbeat.exists() else {}
  result.append({**{k:row[k] for k in ('run_id','instrument','runner_scope','mode','running','legacy_scope')},
   'heartbeat_at':h.get('at'),'state':'Running' if row['running'] else 'Preparing' if row['launching'] else 'Stopped',
   'has_position':bool(h.get('position')),'has_pending':bool(h.get('pending'))})
 return sorted(result,key=lambda r:r['instrument'])

@contextmanager
def account_lock(owner,data=DATA):
 if not re.fullmatch('[a-f0-9]{32}',owner):raise ValueError('Exact account owner required')
 path=Path(data)/'coordination'/owner/'admission.lock';path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  try:yield
  finally:fcntl.flock(lock,fcntl.LOCK_UN)

def ledgers(owner,data=DATA):
 """Include exact authenticated FYERS ledger hashes and retained legacy state."""
 roots={Path(data)/'runtime'/owner,Path(data)/'runtime'/'instruments'/owner}
 for row in rows(owner,data):
  for p in (row['directory']/'preflight/preflight.json',row['directory']/'preflight.json'):
   if p.exists():
    key=json.loads(p.read_text()).get('account_sha256')
    if isinstance(key,str) and re.fullmatch('[a-f0-9]{64}',key):roots.add(Path(data)/'runtime'/key)
 for root in roots:
  if root.exists():
   for p in root.rglob('*.json'):
    if p.name in LEDGERS:yield p,json.loads(p.read_text())

def retained(state):return any(state.get(k) for k in EXPOSURE)

def capacity():
 value=int(os.getenv('AI_RENKO_MAX_RUNNERS_PER_ACCOUNT','4'))
 if not 1<=value<=16:raise ValueError('Instrument runner capacity must be between 1 and 16')
 return value

def assert_start(config,data=DATA):
 if not config.get('runner_scope'):return
 binding(config)
 existing=rows(config['account'],data)
 if sum(bool(r['running'] or r['launching']) for r in existing)>=capacity():raise ValueError('Account instrument runner capacity reached')
 for row in existing:
  if (row['running'] or row['launching']) and row['legacy_scope']:
   raise ValueError('Existing account-wide AI worker must finish before instrument runners; it was not interrupted')
  if (row['running'] or row['launching']) and row['runner_scope']==config['runner_scope']:
   raise ValueError('This instrument already has an active runner')
 # A legacy ledger has no instrument binding: do not migrate its uncertain ownership.
 for path,state in ledgers(config['account'],data):
  if 'instruments' not in path.parts and retained(state):
   raise ValueError('Legacy account exposure or pending intent requires reconciliation before instrument runners')

def positions(state):
 """All legs, including retained Stop/Detach exposure and write-ahead orders."""
 for key in ('position','detached_position','stop_verification_position'):
  if state.get(key):yield state[key]
 for p in state.get('positions') or []:yield p
 for slot in (state.get('closing_legs') or {}).values():yield from positions(slot)
 pending=state.get('pending')
 if pending:
  intent=pending.get('intent') or {}
  p=intent.get('position') or pending.get('position') or {}
  payload=pending.get('payload') or {}
  saved=state.get('entry_reservation') or {}
  yield {**saved,**p,'quantity':p.get('quantity') or payload.get('qty') or saved.get('quantity'),
   'symbol':p.get('symbol') or payload.get('symbol') or saved.get('symbol'),
   'fill_price':p.get('fill_price') or payload.get('limitPrice') or p.get('entry_price') or saved.get('fill_price'),'_pending':True}

def contract_keys(p):
 keys=set()
 if p.get('symbol'):keys.add(('symbol',p['symbol']))
 if p.get('product_id') is not None:keys.add(('product_id',str(p['product_id'])))
 if p.get('token') is not None:keys.add(('token',str(p.get('exchange')),str(p['token'])))
 return keys

def reserve(p):
 q=p.get('quantity');price=p.get('fill_price') or p.get('entry_price') or p.get('entry_premium')
 multiplier=p.get('quantity_multiplier',p.get('contract_value',1))
 try:values=[float(q),float(price),float(multiplier)]
 except (ValueError,TypeError):raise ValueError('Other runner exposure has no verified funding reserve; entry remains blocked')
 if any(not math.isfinite(v) or v<=0 for v in values):raise ValueError('Other runner funding reserve is invalid')
 return values[0]*values[1]*values[2]*1.02

def other_exposure(executor,action):
 config=executor.runner_config;live=config.get('execution_mode')=='LIVE';incoming=contract_keys(action['position'])
 result=[]
 for path,state in ledgers(config['account'],executor.runner_data):
  if path.resolve()==executor.path.resolve():continue
  paper=path.name=='paper.json' or path.name.endswith('-paper.json')
  if paper==live:continue
  for p in positions(state):
   keys=contract_keys(p)
   if not keys:raise ValueError('Unidentified account exposure requires reconciliation; no new entry')
   if keys&incoming:raise ValueError('Another runner owns this traded contract or pending order')
   result.append(p)
 return result

def available(executor,p):
 """Fresh selected-account funds only, called at order admission, never per tick."""
 c=executor.runner_config
 if c['broker']=='DELTA_INDIA':
  meta=executor.delta.product(p['symbol'])
  currency=(meta.get('settling_asset') or {}).get('symbol') or p.get('settlement_currency')
  if not currency:raise ValueError('Verified settlement currency unavailable')
  rows=executor.delta._private('GET','/v2/wallet/balances')['result']
  vals=[float(r['available_balance']) for r in rows if (r.get('asset_symbol') or (r.get('asset') or {}).get('symbol'))==currency]
  if len(vals)!=1:raise ValueError('Selected settlement-currency funds unavailable')
  return vals[0],currency
 if hasattr(executor,'adapter'):
  native=executor.adapter.native;meta=executor.adapter.metadata(p['symbol'])
  if c['broker']=='MOTILAL_OSWAL':return float(native.funds(meta['exchange'])),'INR'
  client=native.authenticated_client();funds=client.request('GET','/fundlimit')
  if str(funds.get('dhanClientId'))!=str(client.client_id):raise ValueError('Funds account mismatch')
  return float(funds.get('availabelBalance',funds.get('availableBalance'))),'INR'
 api=executor.api
 if hasattr(api,'funds'):
  from strategies.nifty_ai_options.execution import available_funds
  reply=api.funds()
  return float(available_funds(reply['fund_limit'],commodity=c.get('market')=='MCX')),'INR'
 # Direct native adapters expose their existing order margin boundary; unknown
 # funds shape is not treated as unlimited account capital.
 reader=getattr(api,'runner_available_funds',None)
 if reader:return float(reader()),'INR'
 raise ValueError('Concurrent funding adapter unavailable for selected broker')

def coordinated_submit(method):
 @functools.wraps(method)
 def wrapped(self,action,*args,**kwargs):
  c=getattr(self,'runner_config',{})
  if c.get('entry_quantity_mode')=='AMOUNT_INR':
   from strategies.nifty_ai_options.allocation import apply
   apply(self,action,args or ((kwargs['quote'],) if 'quote' in kwargs else ()))
  if not c.get('runner_scope'):return method(self,action,*args,**kwargs)
  entry=action.get('action') in ('BUY','OPEN_LONG','OPEN_SHORT')
  # Exits never wait for a different instrument's entry acknowledgement.
  if not entry:return method(self,action,*args,**kwargs)
  # Entries share this lock through acknowledgement and durable local save.
  with account_lock(c['account'],self.runner_data):
   reservation=None
   if entry:
    others=other_exposure(self,action)
    if getattr(self,'live',False):
     p=action['position'];quote=args[0] if args and isinstance(args[0],dict) else {}
     if not quote and hasattr(self,'adapter'):quote=self.adapter.quote(p['symbol'])
     if not quote and hasattr(self,'api') and hasattr(self.api,'quote'):quote=self.api.quote()
     if not quote and hasattr(self,'delta'):
      from strategies.nifty_ai_options.delta_entry_policy import read_depth
      quote,_=read_depth(self.delta,p['symbol'])
     qty=p.get('quantity') or (getattr(self,'contracts',None) or getattr(self,'lots',None) or c.get('lots',1))*p.get('lot_size',1)
     reservation=dict(p,quantity=qty,fill_price=quote.get('ask') or quote.get('ltp') or p.get('fill_price') or p.get('entry_price'))
     needed=reserve(reservation)
     if others:
      funds,currency=available(self,p);distinct={}
      for other in others:
       if other.get('settlement_currency') not in (None,currency):raise ValueError('Cannot combine different collateral currencies')
       key=tuple(sorted(contract_keys(other)));distinct[key]=max(distinct.get(key,0),reserve(other))
      if not math.isfinite(funds) or funds<sum(distinct.values())+needed:raise ValueError('Account funds insufficient after other instrument reserves')
     self.state['entry_reservation']=reservation;self.save()
   try:return method(self,action,*args,**kwargs)
   finally:
    if reservation and not self.state.get('pending'):
     self.state.pop('entry_reservation',None);self.save()
 return wrapped

def independent_native_intent(native,tag,order,target_symbol,*,dhan_ticket=False):
 """Permit only an exact durable different-runner intent, never manual tickets.

 The caller still verifies the selected contract broker book and fresh margin.
 Unknown tags, quantities, products or owners retain the native account gate.
 """
 context=getattr(native,'_ai_instrument_context',None)
 if not context or not isinstance(order,dict) or not isinstance(tag,str):return False
 config,data=context
 if not config.get('runner_scope'):return False
 if getattr(getattr(native,'service',None),'account',{}).get('id')!=config['account']:return False
 found=[]
 def walk(state):
  if state.get('pending'):yield state['pending']
  for slot in (state.get('closing_legs') or {}).values():yield from walk(slot)
 for path,state in ledgers(config['account'],data):
  if 'instruments' not in path.parts or config['runner_scope'] in path.parts:continue
  for pending in walk(state):
   payload=pending.get('payload') or {};intent=pending.get('intent') or {};p=intent.get('position') or {}
   if pending.get('key')!=tag or payload.get('orderTag')!=tag:continue
   owned_symbol=payload.get('symbol')
   aliases={owned_symbol,p.get('symbol'),p.get('execution_symbol')}
   if not owned_symbol or target_symbol in aliases:continue
   if dhan_ticket:
    matches=(order.get('correlationId')==tag and
      str(order.get('exchangeSegment'))+':'+str(order.get('securityId'))==owned_symbol and
      order.get('quantity')==payload.get('qty') and
      order.get('transactionType')==('BUY' if payload.get('side')==1 else 'SELL') and
      order.get('productType')==payload.get('productType'))
   else:
    products={payload.get('productType')}
    if payload.get('productType')=='INTRADAY':products.add('VALUEPLUS')
    matches=(order.get('symbol') in aliases and order.get('productType') in products and
      all(order.get(k)==payload.get(k) for k in ('orderTag','qty','side','type','limitPrice','validity')))
   if matches:found.append(path)
 return len(found)==1

def worker_admission(config,directory,*,timeout=3):
 """Scoped children wait for their exact durable parent process receipt."""
 if not config.get('runner_scope'):return
 binding(config)
 from strategies.nifty_ai_options.process_state import identity
 directory=Path(directory).resolve();deadline=time.monotonic()+timeout
 while time.monotonic()<deadline:
  p=directory/'process.json'
  record=json.loads(p.read_text()) if p.exists() else None
  if record and record.get('pid')==os.getpid() and identity(os.getpid(),directory)==record:return
  time.sleep(.02)
 raise ValueError('Instrument worker has no verified launch receipt; trading was not initialized')
