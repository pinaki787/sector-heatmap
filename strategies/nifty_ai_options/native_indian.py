"""AI-specific boundary for selected Dhan/Motilal native adapters.

Construction is inert. No FYERS fallback and no shared runner lifecycle methods.
Runtime/UI dispatch is deliberately separate from this order/ownership boundary.
"""
import fcntl,hashlib,json,math,time,os,threading
from pathlib import Path
try:from .run import atomic
except ImportError:from run import atomic

BROKERS={'DHAN':'MARGIN','MOTILAL_OSWAL':'NORMAL'}
OPEN={4,6}

_DHAN_MASTERS={}
_DHAN_MASTERS_LOCK=threading.Lock()
def dhan_master(account_id):
 from sector_heatmap.dhan_execution import DhanMaster
 with _DHAN_MASTERS_LOCK:
  if account_id not in _DHAN_MASTERS:_DHAN_MASTERS[account_id]=DhanMaster()
  return _DHAN_MASTERS[account_id]

from contextlib import contextmanager
@contextmanager
def native_entry_admission(adapter,entry,live):
 if not live or not entry:
  yield;return
 from sector_heatmap.chart_trade_admission import entry_lock
 from sector_heatmap.chart_trade_ownership import assert_no_chart_entry_conflict
 folder=adapter.native.service.folder
 with entry_lock(adapter.broker,folder=folder):
  assert_no_chart_entry_conflict(folder/'chart-trading.sqlite3',adapter.account,adapter.broker)
  yield

class NativeQuoteNotReady(ValueError):pass

class NativeIndianAdapter:
 def __init__(self,config,native):
  self.config=dict(config);self.native=native
  account=native.service.account
  if config.get('broker') not in BROKERS or account.get('broker')!=config['broker'] or account.get('id')!=config.get('account'):
   raise PermissionError('Exact selected native broker/account required')
  if config.get('execution_route')!='OPTIONS':raise ValueError('Native AI direct route is not certified')
  if config.get('product')!=BROKERS[config['broker']]:raise ValueError('Native broker product mapping differs from selected product')
  if not str(config.get('underlying','')).startswith(('NSE:','BSE:','MCX:')):raise ValueError('Explicit selected native underlying required')
  if config.get('fyers_history_enabled') or config.get('fyers_history_account_id'):raise ValueError('AI native source does not permit alternate-broker history')
  self.account=config['account'];self.broker=config['broker'];self.product=config['product']
  self.market_data=None
  if config.get('market_data_broker'):
   if self.broker!='MOTILAL_OSWAL' or config['market_data_broker']!='FYERS':raise ValueError('Split market data is supported only for Motilal with explicit FYERS selection')
   try:
    from .motilal_fyers_data import MarketData
    from .run import ROOT
   except ImportError:
    from motilal_fyers_data import MarketData
    from run import ROOT
   self.market_data=MarketData(config,native,ROOT,clock=native.clock)
 def signal_quote(self,symbol):
  return self.market_data.quote(symbol) if self.market_data else self.quote(symbol)
 def market_price(self,symbol):
  return self.market_data.price(symbol) if self.market_data else self.native.live_price(dict(self.config,underlying=symbol),self.native.clock())

 def validate(self):
  settings=dict(self.config,spread_filter_enabled=self.config.get('spread_filter_enabled',False),mode=self.config['execution_mode'],timeframe={1:'1 minute',5:'5 minutes',30:'30 minutes'}[self.config['timeframe']])
  result=self.native.validate_config(settings)
  if result.get('broker')!=self.broker or result.get('account_id')!=self.account:raise PermissionError('Native preflight provenance mismatch')
  if self.market_data:result=dict(result,source='FYERS market data; Motilal execution',market_data_broker='FYERS',market_data_account=self.market_data.account)
  return result
 def option_rows(self):
  """Resolve metadata using only this selected adapter's verified daily master."""
  native=self.native;host=native.underlying(self.config['underlying']);now=native.clock()
  if self.broker=='MOTILAL_OSWAL':
   return [dict(native.contract(r['symbol']),strike=float(r['strike'])) for r in native.option_rows(self.config['underlying'])]
  from datetime import datetime
  from sector_heatmap.dhan_execution import IST,contract_underlying
  from sector_heatmap import dhan_mcx
  if host['SEM_SEGMENT']=='M':
   rows=dhan_mcx.option_series(native._rows(),host,now);pairs=dhan_mcx.paired_options(rows)
   rows=[r for r in rows if (r['SEM_EXPIRY_DATE'],__import__('decimal').Decimal(r['SEM_STRIKE_PRICE'])) in pairs and now<dhan_mcx.entry_cutoff(r)]
  else:
   today=datetime.fromtimestamp(now,IST).date().isoformat()
   rows=[r for r in native._rows() if r['SEM_EXM_EXCH_ID']==host['SEM_EXM_EXCH_ID'] and r['SEM_SEGMENT']=='D' and contract_underlying(r)==host['SEM_TRADING_SYMBOL'] and r['SEM_OPTION_TYPE'] in ('CE','PE') and r['SEM_EXPIRY_DATE'][:10]>=today]
   if host['SEM_SEGMENT']=='E':
    from sector_heatmap.stock_expiry_policy import require_options_allowed
    require_options_allowed([r['SEM_EXPIRY_DATE'][:10] for r in rows],datetime.fromtimestamp(now,IST))
  result=[]
  for row in rows:
   meta=dict(native._meta(row),strike=float(row['SEM_STRIKE_PRICE']))
   native.contracts[meta['symbol']]=meta;result.append(meta)
  return result
 def select(self,side):
  if side not in ('CE','PE'):raise ValueError('Explicit bought Call/Put side required')
  rows=self.option_rows();pairs={}
  for r in rows:pairs.setdefault((r['expiry'],r['strike']),set()).add(r['option_type'])
  rows=[r for r in rows if pairs[(r['expiry'],r['strike'])]=={'CE','PE'}]
  expiries=sorted({r['expiry'] for r in rows})
  if not expiries:raise ValueError('No current paired native Call/Put expiry')
  expiry=self.config.get('expiry') if self.config.get('expiry_policy')=='explicit_listed' else expiries[0]
  if expiry not in expiries:raise ValueError('Selected native expiry is not currently listed for this underlying')
  rows=[r for r in rows if r['expiry']==expiry and r['option_type']==side]
  spot,_=self.market_price(self.config['underlying'])
  if isinstance(spot,bool) or not isinstance(spot,(int,float)) or not math.isfinite(spot) or spot<=0:raise ValueError('Native underlying price unavailable')
  classification=self.config.get('option_moneyness')
  if classification=='ATM':
   chosen=min(rows,key=lambda r:(abs(r['strike']-spot),r['strike'],r['symbol']))
  elif classification=='OTM':
   rows=[r for r in rows if r['strike']>spot] if side=='CE' else [r for r in rows if r['strike']<spot]
   from strategies.renko_supertrend.option_premium import choose_native
   chooser=self.native
   if self.market_data:
    from types import SimpleNamespace
    chooser=SimpleNamespace(clock=self.native.clock,quote=self.signal_quote,premium_quotes=self.market_data.premium_quotes,contract=self.native.contract)
   chosen=choose_native(chooser,dict(self.config,target_option_premium=self.config['target_premium']),rows,spot)
  else:raise ValueError('Explicit ATM or OTM selection required')
  return dict(chosen,underlying=self.config['underlying'],underlying_asset=self.config.get('asset'),execution_route='OPTIONS',verified_native_selection=dict(broker=self.broker,account=self.account,underlying=self.config['underlying'],symbol=chosen['symbol']),option_moneyness=classification)
 def candles(self,symbol=None,frame=None):
  """Completed native OHLC; no alternate broker history or invented seed."""
  symbol=symbol or self.config['underlying']
  minutes=frame or self.config['timeframe']
  frame={1:'1 minute',5:'5 minutes',30:'30 minutes'}[minutes]
  config=dict(self.config,underlying=symbol,timeframe=frame,fyers_history_enabled=False)
  rows=self.market_data.candles(symbol,minutes) if self.market_data else self.native.candles(config)
  try:from .core import chart_candle
  except ImportError:from core import chart_candle
  clean=[];prior=-1
  for row in rows:
   stamp=row.get('timestamp')
   if not isinstance(stamp,(int,float)) or stamp<=prior:raise ValueError('Native candles are not ordered and unique')
   prior=stamp
   if row.get('is_forming') or stamp+minutes*60>self.native.clock():continue
   policy=self.session(at=stamp)
   from datetime import datetime
   from zoneinfo import ZoneInfo
   minute=datetime.fromtimestamp(stamp,ZoneInfo('Asia/Kolkata'))
   if not policy['opening_minutes']<=minute.hour*60+minute.minute<policy['closing_minutes']:continue
   if clean:
    previous=clean[-1]['timestamp'];older=datetime.fromtimestamp(previous,ZoneInfo('Asia/Kolkata'))
    if older.date()==minute.date() and stamp-previous!=minutes*60:raise ValueError('Native completed candle gap requires source recovery; no invented bars')
   clean.append(dict(chart_candle(row),timestamp=stamp,volume=row.get('volume') if row.get('volume_available',True) else None,symbol=symbol,broker='FYERS' if self.market_data else self.broker,account=self.market_data.account if self.market_data else self.account,execution_broker=self.broker,execution_account=self.account))
  if len(clean)<max(30,self.config.get('indicator_length',5)):raise ValueError('Native completed OHLC warm-up is insufficient; no source fallback')
  session=self.session()
  if session['open']:
   from datetime import datetime
   from zoneinfo import ZoneInfo
   moment=datetime.fromtimestamp(self.native.clock(),ZoneInfo('Asia/Kolkata'))
   since_open=(moment.hour*60+moment.minute-session['opening_minutes'])*60+moment.second
   if since_open>=minutes*60 and self.native.clock()-(clean[-1]['timestamp']+minutes*60)>minutes*60+15:raise ValueError('Native completed candle source is stale; no entry or exit signal inferred')
  return clean
 def session(self,at=None):
  from datetime import datetime
  from zoneinfo import ZoneInfo
  now=self.native.clock() if at is None else at;dt=datetime.fromtimestamp(now,ZoneInfo('Asia/Kolkata'))
  market=self.config.get('market') or self.config['underlying'].split(':')[0]
  if dt.year!=2026:raise ValueError('Selected venue calendar requires a verified update')
  if market=='MCX':
   host=getattr(self,'_session_host',None) or self.native.underlying(self.config['underlying']);self._session_host=host
   family=str(host.get('SM_SYMBOL_NAME') or host.get('underlying') or '').upper()
   supported={'GOLD','GOLDM','GOLDPETAL','GOLDGUINEA','SILVER','SILVERM','SILVERMIC','CRUDEOIL','CRUDEOILM','NATURALGAS','NATGASMINI','NATURALGASMINI','COPPER','ALUMINIUM','ALUMINI','ZINC','ZINCMINI','LEAD','LEADMINI','NICKEL'}
   if family not in supported:raise ValueError('Selected MCX contract session category is not verified; no generic evening-hours fallback')
   from sector_heatmap.motilal_calendar import trading_bounds
   opening,closing=trading_bounds(now)
   return dict(open=opening<=dt.hour*60+dt.minute<closing,opening_minutes=opening,closing_minutes=closing,venue='MCX',source='MCX_2026_NON_AGRICULTURAL_CALENDAR')
  if market not in ('NSE','BSE'):raise ValueError('Unsupported native Indian session')
  from sector_heatmap.market_calendar import market_session
  session=market_session(dt)
  return dict(open=session['status']=='OPEN',opening_minutes=555,closing_minutes=930,venue=market,source='INDIAN_EQUITY_DERIVATIVES_2026_CALENDAR')
 def candidates(self):
  allowed={r['symbol']:r for r in self.option_rows()};positions,orders=self.books();result=[]
  for row in positions:
   symbol=row.get('symbol');meta=allowed.get(symbol);qty=row.get('netQty',0)
   if not meta or row.get('productType')!=self.product or not isinstance(qty,int) or qty<=0 or qty%meta['lot_size']:continue
   if self.pending_external(symbol) or any(o.get('symbol')==symbol and o.get('status') in OPEN for o in orders):continue
   average=row.get('netAvg')
   if not isinstance(average,(int,float)) or average<=0:average=None
   result.append(dict(symbol=symbol,quantity=qty,lots=qty//meta['lot_size'],product=self.product,side=meta['option_type'],option_type=meta['option_type'],expiry=meta['expiry'],average_price=average,entry_cost_available=average is not None,account=self.account,underlying=self.config['underlying'],meta=meta))
  return result
 def selected(self,request):
  rows=[r for r in self.candidates() if all(r.get(k)==request.get(k) for k in ('symbol','quantity','product'))]
  if len(rows)!=1:raise ValueError('Selected native holding changed or is no longer eligible')
  return rows[0]
 def order_readiness(self,contract,quantity):
  quote=self.quote(contract['symbol'])
  order=self.native.order(contract['symbol'],quantity,1,quote)
  self.native.preflight(order,self.config)
  if self.broker=='DHAN':
   client=self.native.authenticated_client();ips=client.request('GET','/ip/getIP')
   if self.native.service.egress() not in (ips.get('primaryIP'),ips.get('secondaryIP')):raise PermissionError('Selected Dhan account does not authorize the server IP')
  else:
   self.native.ready();profile=self.native.service.client.profile();meta=self.metadata(contract['symbol'])
   if meta['exchange'] not in profile.get('exchanges',[]) or self.product not in {str(p).upper() for p in profile.get('products',[])}:raise PermissionError('Selected native segment/product unavailable')
  return dict(read_only=True,orders_submitted=0)

 def quote(self,symbol):
  try:quote=self.native.quote(symbol)
  except ValueError as error:raise NativeQuoteNotReady(str(error)) from error
  now=self.native.clock()
  if quote.get('symbol',symbol)!=symbol:raise ValueError('Quote belongs to another native contract')
  for field in ('exchange_at','received_at'):
   value=quote.get(field)
   if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=now-value<=5:raise NativeQuoteNotReady('Fresh exact native quote required')
  bid,ask=quote.get('bid'),quote.get('ask')
  if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in (bid,ask)) or bid>ask:raise NativeQuoteNotReady('Executable native bid/ask unavailable')
  return dict(quote,symbol=symbol)
 def metadata(self,symbol):
  meta=self.native.contract(symbol)
  if meta.get('broker')!=self.broker or meta.get('symbol')!=symbol:raise PermissionError('Native contract provenance mismatch')
  lot,tick=meta.get('lot_size'),meta.get('tick_size')
  if isinstance(lot,bool) or not isinstance(lot,int) or lot<=0 or isinstance(tick,bool) or not isinstance(tick,(int,float)) or not math.isfinite(tick) or tick<=0:raise ValueError('Current native lot/tick unavailable')
  if meta.get('option_type') not in ('CE','PE') or not meta.get('expiry'):raise ValueError('Verified bought option metadata required')
  return meta
 def books(self):
  positions=self.native.positions();orders=self.native.orders()
  if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Native broker books unavailable')
  return positions,orders
 def pending_external(self,symbol):
  if self.broker!='MOTILAL_OSWAL':return False
  meta=self.metadata(symbol)
  rows=self.native.service.book('orders').get('data')
  if not isinstance(rows,list):raise ValueError('Native complete order book unavailable')
  for row in rows:
   if row.get('exchange')==meta.get('exchange') and str(row.get('symboltoken'))==str(meta.get('token')):
    status=str(row.get('orderstatus') or '').strip().upper()
    if status not in {'CANCEL','TRADED','REJECTED','ERROR'}:return True
  return False
 def verify(self,position,*,flat=False):
  if position is None:return dict(flat=True,no_owned_position=True)
  symbol=position['symbol'];self.metadata(symbol)
  positions,orders=self.books()
  if self.pending_external(symbol) or any(r.get('symbol')==symbol and r.get('status') in OPEN for r in orders):raise ValueError('Native contract has unresolved order')
  qty=sum(int(r['netQty']) for r in positions if r.get('symbol')==symbol and r.get('productType')==self.product)
  expected=position['quantity']
  if flat is True and qty!=0 or flat is False and qty!=expected or flat is None and qty not in (0,expected):raise ValueError('Native broker quantity differs from exact strategy ownership')
  return dict(flat=qty==0,quantity=qty,broker=self.broker,account=self.account)

class NativeIndianExecution:
 def __init__(self,adapter,state_dir,*,live=False,management_only=False):
  self.adapter=adapter;self.native=adapter.native;self.live=live;self.management_only=management_only
  root=Path(state_dir)/adapter.account;root.mkdir(parents=True,exist_ok=True)
  self.lock=(root/'execution.lock').open('a');fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  self.path=root/('native-indian-live.json' if live else 'native-indian-paper.json')
  self.state=json.loads(self.path.read_text()) if self.path.exists() else dict(position=None,pending=None,seen=[])
  direct=root/('direct-live.json' if live else 'direct-paper.json')
  if direct.exists():
   retained=json.loads(direct.read_text())
   if any(retained.get(k) for k in ('position','pending','detached_position','stop_verification_position')):
    self.close();raise ValueError('Retained native direct ownership must reconcile before options')
  if not management_only and (any(self.state.get(k) for k in ('position','pending','detached_position','stop_verification_position')) or any(slot.get('position') or slot.get('pending') for slot in self.state.get('closing_legs',{}).values())):
   self.close();raise ValueError('Retained native ownership requires explicit reconciliation or management')
 def save(self):atomic(self.path,self.state)
 def close(self):self.lock.close()
 def reconcile_pending(self):
  pending=self.state.get('pending')
  if not pending:return
  order=pending['payload'];symbol=order['symbol'];quantity=order['qty'];entry=order['side']==1
  rows=[r for r in self.native.orders() if r.get('orderTag')==order['orderTag']]
  if len(rows)!=1:raise ValueError('Retained native acknowledgement is not uniquely verified; no resend')
  row=rows[0]
  if pending.get('order_id') and str(row.get('id'))!=str(pending['order_id']):raise ValueError('Native order id changed')
  for key in ('symbol','qty','side','productType'):
   if row.get(key)!=order.get(key):raise ValueError('Retained native fill identity mismatch')
  filled=row.get('filledQty',0);status=row.get('status');intent=pending['intent'];p=intent['position']
  if isinstance(filled,bool) or not isinstance(filled,int) or not 0<=filled<=quantity or status in OPEN:raise ValueError('Native order remains open or fill quantity is unknown')
  if filled==quantity and status==2:
   self.adapter.verify(dict(p,quantity=quantity),flat=not entry)
   self.state['position']=dict(p,quantity=quantity,order_id=str(row['id']),fill_price=row.get('tradedPrice')) if entry else None
  elif status in (1,5,7) and filled<quantity:
   remaining=filled if entry else quantity-filled
   meta=self.adapter.metadata(symbol)
   if remaining%meta['lot_size']:raise ValueError('Native residual is not a whole lot; retained for recovery')
   self.adapter.verify(dict(p,quantity=remaining),flat=remaining==0)
   self.state['position']=dict(p,quantity=remaining,order_id=str(row['id']),fill_price=row.get('tradedPrice') if entry else (self.state.get('position') or {}).get('fill_price')) if remaining else None
  else:raise ValueError('Native partial or unknown state remains unreconciled')
  self.state.setdefault('reconciliations',[]).append(dict(kind='NATIVE_ORDER_VERIFIED',order_id=str(row['id']),filled_quantity=filled,checked_at=self.native.clock(),orders_submitted=0))
  receipt=dict(action=intent,order_id=str(row['id']),filled_quantity=filled,fill_price=row.get('tradedPrice') if filled else None,broker_flat=self.state.get('position') is None,checked_at=self.native.clock(),orders_submitted=0)
  if filled:
   try:from .option_legs import capture_fill
   except ImportError:from option_legs import capture_fill
   capture_fill(self.state,intent,dict(order_id=str(row['id']),filled_quantity=filled,fill_price=row.get('tradedPrice')),receipt['checked_at'],pending.get('key'))
  if not entry and self.state.get('position'):self.state['retained_exit_failure']=dict(pending,stage='CANCELLED_WITHOUT_FILL' if not filled else 'PARTIAL_EXIT_REMAINS',filled_quantity=filled)
  self.state['pending']=None;self.save();return receipt
 def submit(self,action,quote=None):
  from sector_heatmap.native_exit_scope import closing_exits
  with closing_exits(self.native,self.state),native_entry_admission(self.adapter,action.get('action')=='BUY',self.live):
   return self._submit(action,quote)
 def _submit(self,action,quote=None):
  name=action.get('action')
  if name not in ('BUY','SELL'):raise ValueError('Native AI options are bought-only')
  entry=name=='BUY'
  if self.management_only and entry:raise ValueError('Management-only runtime cannot create an entry')
  if self.state.get('pending'):raise ValueError('Retained native order prohibits duplicate submission')
  p=action['position'];symbol=p['symbol'];meta=self.adapter.metadata(symbol)
  if p.get('option_type')!=meta['option_type'] or p.get('expiry')!=meta['expiry']:raise ValueError('Captured/native option metadata mismatch')
  if entry:
   if self.state.get('position'):raise ValueError('Native strategy already owns exposure')
   lots=self.adapter.config['lots']
   if isinstance(lots,bool) or not isinstance(lots,int) or lots<=0:raise ValueError('Explicit positive lots required')
   quantity=lots*meta['lot_size']
  else:
   own=self.state.get('position')
   if not own or own['symbol']!=symbol or own.get('side')!=p.get('side'):raise ValueError('No exact native strategy-owned holding')
   quantity=own['quantity']
  if quantity<=0 or quantity%meta['lot_size']:raise ValueError('Native quantity is not whole lots')
  if self.live and not self.adapter.session()['open']:raise ValueError('Selected native venue is closed; no order submitted')
  quote=self.adapter.quote(symbol) # Never trust a UI preview as executable.
  order=self.native.order(symbol,quantity,1 if entry else -1,quote)
  if order.get('productType')!=self.adapter.product:raise ValueError('Native order product changed')
  self.native.validate_order(order)
  tag='nai'+hashlib.sha256(json.dumps([self.adapter.account,action['timestamp'],symbol,name,p['entry_timestamp']],sort_keys=True).encode()).hexdigest()[:24]
  if tag in self.state['seen']:raise ValueError('Duplicate native intent blocked')
  order['orderTag']=tag
  if self.live:
   self.adapter.verify(dict(p,quantity=quantity),flat=True if entry else False)
   if entry:self.native.preflight(order,self.adapter.config)
  self.state['pending']=dict(key=tag,intent=action,payload=order,stage='PREPARED');self.state['seen'].append(tag);self.save()
  if not self.live:
   self.state['position']=dict(p,quantity=quantity,fill_price=quote['ask'],simulated=True) if entry else None
   result=dict(dry_run=True,filled_quantity=quantity,simulated_fill=quote['ask' if entry else 'bid'])
   try:from .option_legs import capture_fill
   except ImportError:from option_legs import capture_fill
   capture_fill(self.state,action,result,self.native.clock(),tag)
   self.state['pending']=None;self.save();return result
  try:reply=self.native.place(order)
  except Exception:
   self.state['pending']['stage']='UNCERTAIN';self.save();raise RuntimeError('Native acknowledgement unknown; no resend')
  if not isinstance(reply,dict) or reply.get('s')!='ok' or not reply.get('id'):
   self.state['pending']['stage']='REJECTED_OR_UNCERTAIN';self.save();raise RuntimeError('Native submission not confirmed; retained without retry')
  identifier=str(reply['id']);self.state['pending'].update(order_id=identifier,stage='SUBMITTED');self.save()
  deadline=time.monotonic()+getattr(self,'confirmation_timeout',30)
  while time.monotonic()<deadline:
   rows=[r for r in self.native.orders() if str(r.get('id'))==identifier and r.get('orderTag')==tag]
   if len(rows)>1:raise RuntimeError('Multiple native matches require reconciliation')
   if rows:
    row=rows[0]
    if row.get('symbol')!=symbol or row.get('qty')!=quantity or row.get('side')!=order['side'] or row.get('productType')!=self.adapter.product:raise RuntimeError('Native fill identity mismatch')
    if row.get('status')==2 and row.get('filledQty')==quantity:
     self.state['pending']['stage']='FILLED_AWAITING_POSITION';self.save()
     self.adapter.verify(dict(p,quantity=quantity),flat=not entry)
     self.state['position']=dict(p,quantity=quantity,order_id=identifier,fill_price=row.get('tradedPrice')) if entry else None
     result=dict(order_id=identifier,filled_quantity=quantity,fill_price=row.get('tradedPrice'))
     try:from .option_legs import capture_fill
     except ImportError:from option_legs import capture_fill
     capture_fill(self.state,action,result,self.native.clock(),tag)
     self.state['pending']=None;self.save();return result
    if row.get('status') in (1,5,7) or row.get('filledQty',0)>0:break
   time.sleep(.5)
  self.state['pending']['stage']='UNRESOLVED_FILL';self.save();raise RuntimeError('Partial/unknown native fill retained without retry or opposite entry')

def bound_native(config):
 """Bind the registered selected account without touching shared runners."""
 import sqlite3
 try:from .run import ROOT
 except ImportError:from run import ROOT
 from sector_heatmap.automation import AutomationPolicyService
 account_id=config.get('account')
 if not isinstance(account_id,str) or len(account_id)!=32 or any(c not in '0123456789abcdef' for c in account_id):raise ValueError('Exact registered native account required')
 registry=ROOT/'.private/dashboard-login/registry.sqlite3'
 with sqlite3.connect(registry.as_uri()+'?mode=ro',uri=True) as db:
  db.row_factory=sqlite3.Row;row=db.execute('select * from accounts where id=?',(account_id,)).fetchone()
  account=dict(row) if row else None
 if not account or account['broker']!=config.get('broker') or account['broker'] not in BROKERS:raise PermissionError('Selected native registry owner mismatch')
 folder=ROOT/'.private/dashboard-login/accounts'/account_id
 if account['broker']=='MOTILAL_OSWAL':account['live_enabled']=bool(account['live_enabled']) and os.getenv('MOTILAL_ENABLE_LIVE_ORDERS')=='1'
 policy=AutomationPolicyService()
 def permitted():
  with sqlite3.connect(registry.as_uri()+'?mode=ro',uri=True) as db:
   current=db.execute('select live_enabled,broker from accounts where id=?',(account_id,)).fetchone()
  return bool((account['broker']!='MOTILAL_OSWAL' or os.getenv('MOTILAL_ENABLE_LIVE_ORDERS')=='1') and current and current[0] and current[1]==account['broker'] and not (policy.current().get('profile') or {}).get('kill_switch_engaged',False))
 if account['broker']=='DHAN':
  from sector_heatmap.dhan_execution import DhanExecutionService
  from sector_heatmap.dhan_strategy_broker import Broker
  class SelectedBroker(Broker):
   def underlying(self,symbol):
    if symbol.startswith(('NSE_FNO:','BSE_FNO:','MCX_COMM:','NSE_EQ:','BSE_EQ:')):
     segment,identifier=symbol.split(':',1)
     rows=[r for r in self._rows() if self._segment(r)==segment and r['SEM_SMST_SECURITY_ID']==identifier]
     if len(rows)!=1:raise ValueError('Exact native Dhan history contract missing or ambiguous')
     return rows[0]
    return super().underlying(symbol)
  native=SelectedBroker(DhanExecutionService(account,folder,execution_allowed=permitted,master=dhan_master(account_id)))
 else:
  from sector_heatmap.motilal_service import Service
  from sector_heatmap.motilal_strategy_broker import Broker
  class SelectedBroker(Broker):
   def underlying(self,symbol):
    if symbol.startswith('MO:'):return self.contract(symbol)
    return super().underlying(symbol)
  native=SelectedBroker(Service(folder,account,execution_allowed=permitted))
 native.entry_spread_filter_enabled=config.get('spread_filter_enabled',False)
 if config.get('execution_route')=='DIRECT' and config.get('broker')=='DHAN':
  try:from .dhan_direct_adapter import DhanDirectAdapter
  except ImportError:from dhan_direct_adapter import DhanDirectAdapter
  return DhanDirectAdapter(config,native)
 if config.get('execution_route')=='DIRECT' and config.get('broker')=='MOTILAL_OSWAL':
  try:from .motilal_direct_adapter import MotilalDirectAdapter
  except ImportError:from motilal_direct_adapter import MotilalDirectAdapter
  return MotilalDirectAdapter(config,native)
 return NativeIndianAdapter(config,native)

def map_native_host(config,host):
 from datetime import datetime
 import re
 try:from .native_sizing import INDEX_ALIASES,MONTHS
 except ImportError:from native_sizing import INDEX_ALIASES,MONTHS
 symbol=config['underlying'];exchange=symbol.split(':')[0]
 motilal_id=config.get('broker')=='MOTILAL_OSWAL' and symbol.startswith('MO:')
 if motilal_id:
  if symbol!=host.get('symbol'):raise ValueError('Exact Motilal sizing contract differs')
  exchange=host.get('exchange','').replace('FO','')
 native_id=config.get('broker')=='DHAN' and exchange in ('NSE_EQ','BSE_EQ','NSE_FNO','BSE_FNO','MCX_COMM')
 if native_id:
  if str(host.get('SEM_SMST_SECURITY_ID'))!=symbol.split(':',1)[1]:raise ValueError('Native sizing contract token differs')
  exchange=exchange.split('_')[0]
 actual=host.get('SEM_EXM_EXCH_ID') or host.get('exchange')
 if actual not in (exchange,exchange+'FO'):raise ValueError('Native sizing host exchange differs from selected instrument')
 if symbol in INDEX_ALIASES:return INDEX_ALIASES[symbol]
 kind=host.get('SEM_INSTRUMENT_NAME') or host.get('instrument')
 if exchange=='MCX':
  if kind not in ('FUTCOM','FUTIDX'):raise ValueError('Native MCX sizing requires the exact selected futures host')
  if config['broker']=='DHAN' and not native_id and ('MCX:'+str(host.get('SEM_TRADING_SYMBOL',''))).upper()!=symbol.upper():raise ValueError('Native futures host identity mismatch')
  if config['broker']=='MOTILAL_OSWAL' and not motilal_id and symbol.removeprefix('MCX:')!=str(host.get('token')):raise ValueError('Native futures token mismatch')
  asset=host.get('SM_SYMBOL_NAME') or host.get('underlying')
  expiry=host.get('SEM_EXPIRY_DATE') or host.get('expiry')
  if not isinstance(asset,str) or not re.fullmatch('[A-Z0-9_]+',asset):raise ValueError('Native futures asset metadata unavailable')
  day=datetime.fromisoformat(str(expiry)[:10])
  return 'MCX:'+asset+MONTHS[day.strftime('%b').upper()]+str(day.year)
 if motilal_id and str(kind).startswith('FUT'):
  asset=host.get('underlying');day=datetime.fromisoformat(str(host.get('expiry'))[:10])
  if not isinstance(asset,str) or not re.fullmatch('[A-Z0-9_]+',asset):raise ValueError('Native futures asset unavailable')
  return exchange+':'+asset+MONTHS[day.strftime('%b').upper()]+str(day.year)
 if motilal_id:
  from sector_heatmap.motilal_strategy_broker import cash_row
  if cash_row(host):return exchange+':'+host['underlying']
 if native_id and str(kind).startswith('FUT'):
  asset=host.get('SM_SYMBOL_NAME');expiry=host.get('SEM_EXPIRY_DATE')
  if not isinstance(asset,str) or not re.fullmatch('[A-Z0-9_]+',asset):raise ValueError('Explicit native futures underlying metadata unavailable')
  day=datetime.fromisoformat(str(expiry)[:10])
  return exchange+':'+asset+MONTHS[day.strftime('%b').upper()]+str(day.year)
 if kind in ('EQUITY','INDEX') or host.get('SEM_SEGMENT') in ('E','I'):
  ticker=str(host.get('SEM_TRADING_SYMBOL')) if native_id else symbol.split(':',1)[1].removesuffix('-EQ').removesuffix('-INDEX')
  if not re.fullmatch('[A-Z0-9_&.-]+',ticker):raise ValueError('Native cash/index reference mapping unavailable')
  return exchange+':'+ticker
 raise ValueError('No verified native sizing mapping for selected host')
