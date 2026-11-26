"""Exact Motilal direct execution; FYERS remains the sole analytical data source."""
import copy,json,math,re,secrets
from datetime import datetime
from zoneinfo import ZoneInfo
try:from .motilal_direct_proposal import propose
except ImportError:from motilal_direct_proposal import propose
IST=ZoneInfo('Asia/Kolkata')
PRODUCTS={'INTRADAY':'VALUEPLUS','MARGIN':'NORMAL'}
def direct_metadata(native,symbol):
 row=native.underlying(symbol);kind=str(row.get('instrument','')).upper()
 from sector_heatmap.motilal_strategy_broker import cash_row
 cash=cash_row(row) and kind!='INDEX';future=kind.startswith('FUT')
 if not cash and not future:raise ValueError('Choose an exact Motilal equity or futures contract')
 if row.get('suspended') or row.get('banned'):raise ValueError('Contract unavailable')
 result=dict(row,broker='MOTILAL_OSWAL',symbol=symbol,execution_symbol=row['symbol'],product_type='STOCK' if cash else 'FUTURE',quantity_multiplier=None if row['exchange']=='MCX' else 1,underlying=symbol)
 if future:
  try:result['expiry_epoch']=datetime.fromisoformat(str(row['expiry'])[:10]).replace(hour=23,minute=59,tzinfo=IST).timestamp()
  except (KeyError,ValueError):raise ValueError('Verified futures expiry required') from None
  if result['expiry_epoch']<=native.clock():raise ValueError('Expired Motilal future')
 return result
def search_direct(native,query,market='ALL'):
 native.service.ready();rows=[]
 if market.endswith('_INDEX'):return []
 for exchange in ('NSE','BSE','NSEFO','BSEFO','MCX'):
  if market!='ALL' and exchange.replace('FO','')!=market.split('_')[0]:continue
  for row in native.service.master.rows(exchange):
   from sector_heatmap.motilal_strategy_broker import cash_row
   cash=cash_row(row) and row.get('instrument')!='INDEX';future=str(row.get('instrument','')).startswith('FUT')
   if not cash and not future or row.get('suspended') or row.get('banned'):continue
   if market.endswith(('_FUTURE','_FUTURES')) and not future or market.endswith(('_EQUITY','_STOCK')) and not cash:continue
   if future and (not row.get('expiry') or row['expiry']<datetime.fromtimestamp(native.clock(),IST).date().isoformat()):continue
   rows.append(dict(symbol=row['symbol'],description=row['name'],underlying=row['underlying'],product_type='STOCK' if cash else 'FUTURE',market=exchange.replace('FO',''),expiry=row.get('expiry')))
 try:from .instrument_suggestions import ranked
 except ImportError:from instrument_suggestions import ranked
 return ranked(rows,str(query or '').strip().upper())
class MotilalDirectAPI:
 def __init__(self,native,config):
  account=native.service.account
  if account.get('broker')!='MOTILAL_OSWAL' or config.get('broker')!='MOTILAL_OSWAL' or account.get('id')!=config.get('account'):raise PermissionError('Exact Motilal account required')
  if config.get('execution_route')!='DIRECT' or config.get('product') not in PRODUCTS:raise ValueError('Explicit supported Motilal direct product required')
  self.native=native;self.config=dict(config);self.meta=direct_metadata(native,config['underlying']);self.executor=None
  if self.meta['product_type']=='STOCK' and config['product']!='INTRADAY':raise ValueError('Cash direct route requires Intraday')
  self.buffer=config.get('protected_limit_ticks',1)
  if isinstance(self.buffer,bool) or not isinstance(self.buffer,int) or not 1<=self.buffer<=5:raise ValueError('Protected buffer must be 1 to 5 ticks')
 def bind(self,executor):
  if executor.api is not self or executor.broker!='MOTILAL_OSWAL' or executor.path.parent.name!=self.config['account'] or executor.product!=self.config['product'] or executor.lots!=self.config['lots']:raise PermissionError('Exact direct executor binding required')
  self.executor=executor
 def master(self,symbol):
  if symbol!=self.config['underlying']:raise ValueError('Selected direct contract differs')
  fresh=direct_metadata(self.native,symbol)
  if any(fresh.get(k)!=self.meta.get(k) for k in ('execution_symbol','lot_size','tick_size','product_type','expiry_epoch')):raise ValueError('Motilal master changed')
  return fresh
 def _symbol(self,symbol):return self.config['underlying'] if symbol==self.meta['execution_symbol'] else symbol
 def _product(self,value):
  value=str(value).upper().replace(' ','')
  return 'INTRADAY' if value in ('VALUEPLUS','INTRADAY') else 'MARGIN' if value=='NORMAL' else value
 def positions(self):return dict(s='ok',netPositions=[dict(r,symbol=self._symbol(r['symbol']),productType=self._product(r['productType'])) for r in self.native.positions()])
 def orderbook(self):return dict(s='ok',orderBook=[dict(r,symbol=self._symbol(r['symbol']),productType=self._product(r['productType'])) for r in self.native.orders()])
 def get_profile(self):self.native.ready();return dict(s='ok',data=dict(fy_id='MOTILAL_OSWAL:'+self.config['account']))
 def quote(self):
  self.master(self.config['underlying']);q=self.native.quote(self.meta['execution_symbol'])
  last=q.get('last_price',q.get('ltp'))
  if isinstance(last,bool) or not isinstance(last,(int,float)) or not math.isfinite(last) or last<=0:raise ValueError('Actual Motilal execution LTP unavailable')
  if not 0<=self.native.clock()-q.get('ltp_exchange_at',q.get('exchange_at',0))<=5:raise ValueError('Actual execution trade price is stale')
  if not 0<=self.native.clock()-q.get('exchange_at',0)<=5:raise ValueError('Fresh Motilal execution quote required')
  return dict(q,broker='MOTILAL_OSWAL',symbol=self.meta['execution_symbol'],account=self.config['account'],ltp=last,timestamp=q['exchange_at'])
 def prepare_order(self,order):
  self.master(order['symbol'])
  plan=propose(dict(self.meta,symbol=self.meta['execution_symbol']),self.quote(),side='BUY' if order['side']==1 else 'SELL',quantity=order['qty'],account=self.config['account'],now=self.native.clock(),buffer_ticks=self.buffer)
  return dict(order,type=1,limitPrice=plan['limit_price'],validity='IOC',protection=dict(buffer_ticks=self.buffer,original_price_bound=plan['original_price_bound'],quote_time=plan['quote_time']))
 def payload(self,order):
  self.master(order['symbol']);protection=order.get('protection') or {}
  if order.get('type')!=1 or order.get('productType')!=self.config['product'] or order.get('validity')!='IOC' or order.get('side') not in (1,-1) or order.get('stopPrice')!=0 or order.get('offlineOrder') is not False:raise ValueError('Saved protected LIMIT IOC required')
  quantity=order.get('qty');lot=self.meta['lot_size']
  if isinstance(quantity,bool) or not isinstance(quantity,int) or quantity<=0 or quantity%lot:raise ValueError('Whole native lots required')
  cap=protection.get('original_price_bound');price=order.get('limitPrice')
  from decimal import Decimal
  if isinstance(price,bool) or not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0 or Decimal(str(price))%Decimal(str(self.meta['tick_size'])):raise ValueError('Exact positive tick-aligned limit required')
  if not isinstance(cap,(int,float)) or not math.isfinite(cap) or (order['side']==1 and price>cap or order['side']==-1 and price<cap):raise ValueError('Original protective bound exceeded')
  if protection.get('buffer_ticks')!=self.buffer or not 0<=self.native.clock()-protection.get('quote_time',0)<=5:raise ValueError('Prepared depth expired; no order sent')
  if self.meta.get('max_quantity') and quantity//lot>self.meta['max_quantity']:raise ValueError('Broker maximum quantity exceeded')
  if not isinstance(order.get('orderTag'),str) or not re.fullmatch('[A-Za-z0-9_-]{1,30}',order['orderTag']):raise ValueError('Durable correlation required')
  return dict(exchange=self.meta['exchange'],symboltoken=self.meta['token'],buyorsell='BUY' if order['side']==1 else 'SELL',ordertype='LIMIT',producttype=PRODUCTS[self.config['product']],orderduration='IOC',price=price,triggerprice=0,quantityinlot=quantity//lot,disclosedquantity=0,amoorder='N',algoid='',participantcode='')
 def funds(self):return dict(s='ok',fund_limit=[dict(id=10,equityAmount=self.native.funds(self.meta['exchange']))])
 def margin(self,order):
  # Conservative full contract value reserve; never invent leveraged margin.
  self.payload(order)
  multiplier=self.adapter.metadata(self.config['underlying']).get('quantity_multiplier') if self.meta['exchange']=='MCX' else 1
  if not isinstance(multiplier,(int,float)) or not math.isfinite(multiplier) or multiplier<=0:raise ValueError('Economic contract multiplier unavailable')
  return order['limitPrice']*order['qty']*multiplier*1.01
 def place_order(self,*,data):
  e=self.executor
  if e is None or not e.live:raise PermissionError('User-started Live executor required')
  pending=e.state.get('pending') or {}
  if pending.get('stage')!='PREPARED' or pending.get('payload')!=data or json.loads(e.path.read_text()).get('pending')!=pending:raise PermissionError('Exact durable prepared intent required')
  from sector_heatmap.motilal_strategy_broker import account_lock
  with account_lock(self.native.service.folder):
   if not self.native.live_enabled():raise PermissionError('Motilal Live capability disabled')
   if not self.adapter.session()['open']:raise ValueError('Selected venue closed')
   body=self.payload(data);profile=self.native.service.client.profile()
   if str(profile.get('usertype','')).strip().casefold() not in ('investorclient','investor client') or body['exchange'] not in profile.get('exchanges',[]) or body['producttype'] not in {str(p).upper().replace(' ','') for p in profile.get('products',[])}:raise PermissionError('Native profile/segment/product unavailable')
   q=self.quote()
   if data['side']==1 and q['ask']>data['limitPrice'] or data['side']==-1 and q['bid']<data['limitPrice']:raise ValueError('Depth moved outside original cap; no chasing')
   rows=self.positions()['netPositions'];self.orderbook()
   own=e.state.get('position');entry=pending['intent']['action'].startswith('OPEN_')
   expected=0 if entry else own['quantity']*(1 if own['side']=='LONG' else -1)
   selected=[r for r in rows if r['symbol']==data['symbol'] and r['netQty']]
   if any(r['productType']!=self.config['product'] for r in selected) or sum(int(r['netQty']) for r in selected)!=expected:raise ValueError('Exact signed ownership changed')
   for row in self.native.service.book('orders')['data']:
    if row['exchange']==self.meta['exchange'] and str(row['symboltoken'])==str(self.meta['token']) and str(row.get('orderstatus','')).strip().upper() not in ('CANCEL','TRADED','REJECTED','ERROR'):raise ValueError('Native contract has an unresolved order')
   with self.native.db() as db:
    if db.execute("SELECT 1 FROM intents WHERE state IN ('SUBMITTING','UNCERTAIN','ACKNOWLEDGED') LIMIT 1").fetchone():raise ValueError('Native intent requires reconciliation')
    if db.execute('SELECT 1 FROM intents WHERE full_tag=?',(data['orderTag'],)).fetchone():raise ValueError('Intent already attempted')
   with self.native.service.tickets.db() as db:
    if db.execute("SELECT 1 FROM tickets WHERE state IN ('SUBMITTING','UNCERTAIN','ACCEPTED','BROKER_CONFIRM','BROKER_PARTIAL','BROKER_SENT') LIMIT 1").fetchone():raise ValueError('Manual ticket requires reconciliation')
   if not self.native.live_enabled():raise PermissionError('Live capability changed')
   tag='MD'+secrets.token_hex(4);body['tag']=tag
   native_order=dict(data,symbol=self.meta['execution_symbol'],productType=body['producttype'])
   pending['stage']='SUBMITTING';e.save()
   with self.native.db() as db:db.execute('INSERT INTO intents VALUES (?,?,?,?,?,?)',(data['orderTag'],tag,json.dumps(native_order),'SUBMITTING',None,self.native.clock()))
   try:
    reply=self.native.service.client.request('place',body);identifier=str(reply.get('uniqueorderid') or '')
    if not re.fullmatch('[A-Za-z0-9_-]{1,50}',identifier):raise RuntimeError('Unknown Motilal acknowledgement')
    with self.native.db() as db:db.execute("UPDATE intents SET state='ACKNOWLEDGED',order_id=? WHERE full_tag=?",(identifier,data['orderTag']))
   except Exception:
    with self.native.db() as db:db.execute("UPDATE intents SET state='UNCERTAIN' WHERE full_tag=?",(data['orderTag'],))
    raise
   return dict(s='ok',id=identifier)
