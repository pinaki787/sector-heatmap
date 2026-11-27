"""Exact broker/account position views for AI ownership controls; reads only."""
import hashlib,math,time
try:
 from .run import ok
except ImportError:from run import ok

def whole(value):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or int(value)!=value:raise ValueError('Broker quantity unavailable')
 return int(value)

class FyersPositions:
 def __init__(self,api,config,master,account_hash):
  self.api=api;self.config=config;self.master=master;self.account_hash=account_hash
 def books(self):
  identity=(ok(self.api.get_profile()).get('data') or {}).get('fy_id')
  if not identity or hashlib.sha256(str(identity).encode()).hexdigest()!=self.account_hash:raise ValueError('Position-control account identity mismatch')
  positions=ok(self.api.positions()).get('netPositions');orders=ok(self.api.orderbook()).get('orderBook')
  if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Broker position/order inventory unavailable')
  return positions,orders
 def candidates(self):
  try:from .live import exposure_prefix
  except ImportError:from live import exposure_prefix
  positions,orders=self.books();result=[];under=self.config['underlying']
  parent=None
  if under.startswith('MCX:'):
   try:from .markets import FyersInstrumentMaster
   except ImportError:from markets import FyersInstrumentMaster
   parent=FyersInstrumentMaster(self.master.directory)(under)
  for row in positions:
   symbol=row.get('symbol','');qty=whole(row.get('netQty',0));product=row.get('productType')
   if not qty or product!=self.config['product']:continue
   if self.config['execution_route']=='DIRECT':
    if symbol!=under:continue
    meta=self.master(symbol);side='LONG' if qty>0 else 'SHORT'
   else:
    if qty<0 or not symbol.startswith(exposure_prefix(self.config)):continue
    try:meta=self.master(symbol)
    except ValueError:continue
    if parent and str(meta.get('underlying_token'))!=str(parent['instrument_token']):continue
    if not parent and meta.get('underlying_asset')!=exposure_prefix(self.config).split(':')[1]:continue
    if meta.get('option_type') not in ('CE','PE'):continue
    side=meta['option_type']
   lot=meta['lot_size']
   if abs(qty)%lot or meta.get('expiry_epoch') and float(meta['expiry_epoch'])<=time.time():continue
   average=row.get('buyAvg') if qty>0 else row.get('sellAvg')
   if isinstance(average,bool) or not isinstance(average,(int,float)) or not math.isfinite(average) or average<=0:continue
   if any(o.get('symbol')==symbol and o.get('status') in (4,6) for o in orders):continue
   result.append(dict(symbol=symbol,quantity=abs(qty),product=product,side=side,lots=abs(qty)//lot,average_price=average,expiry=str(meta.get('expiry_epoch')),meta=meta))
  return result
 def selected(self,request):
  rows=[r for r in self.candidates() if all(r[k]==request.get(k) for k in ('symbol','quantity','product'))]
  if len(rows)!=1:raise ValueError('Exact selected open position changed or is not eligible')
  return rows[0]
 def verify(self,owned,*,flat=False):
  positions,orders=self.books()
  if owned is None:return dict(flat=True)
  symbol=owned['symbol'];product=owned.get('product',self.config['product'])
  if any(o.get('symbol')==symbol and o.get('status') not in (1,2,5) for o in orders):raise ValueError('Open or unknown broker order blocks position control')
  matching=[p for p in positions if p.get('symbol')==symbol and p.get('productType')==product]
  if len(matching)>1:raise ValueError('Ambiguous broker position')
  qty=whole(matching[0].get('netQty')) if matching else 0
  expected=whole(owned['quantity'])*(-1 if owned.get('side')=='SHORT' else 1)
  if flat is True and qty!=0:raise ValueError('Broker has not confirmed square-off')
  if flat is False and qty!=expected or flat is None and qty not in (0,expected):raise ValueError('Broker quantity differs from strategy ownership')
  return dict(flat=qty==0,quantity=qty,checked_at=time.time(),broker='FYERS',account=self.config.get('account'))

class DeltaPositions:
 def __init__(self,delta,config,native):self.delta=delta;self.config=config;self.native=native
 def candidates(self):
  if self.native is None:
   from strategies.renko_supertrend.delta_execution import Execution
   self.native=Execution(self.delta)
  self.native.authenticate();rows=self.native.positions();orders=self.native.active_orders()
  from strategies.renko_supertrend.delta_contracts import contract_metadata
  parent=self.delta.product(self.config['underlying']);result=[]
  for row in rows:
   symbol=row['symbol'];qty=whole(row['netQty']);raw=self.delta.product(symbol)
   if self.config['execution_route']=='DIRECT':
    if symbol!=self.config['underlying']:continue
    side='LONG' if qty>0 else 'SHORT'
   else:
    if raw.get('underlying_asset',{}).get('symbol')!=parent.get('underlying_asset',{}).get('symbol') or raw.get('contract_type') not in ('call_options','put_options') or qty<0:continue
    side='CE' if raw['contract_type']=='call_options' else 'PE'
   meta=contract_metadata(raw,self.delta.clock())
   if any(str(o.get('product_id'))==str(meta['product_id']) for o in orders):continue
   result.append(dict(symbol=symbol,quantity=abs(qty),product='DELTA',side=side,lots=abs(qty),average_price=row['netAvg'],expiry=str(meta.get('expiry_epoch')),meta=meta))
  return result
 def selected(self,request):
  rows=[r for r in self.candidates() if all(r[k]==request.get(k) for k in ('symbol','quantity','product'))]
  if len(rows)!=1:raise ValueError('Exact selected Delta holding changed or is not eligible')
  return rows[0]
 def verify(self,owned,*,flat=False):
  if self.native is None:
   from strategies.renko_supertrend.delta_execution import Execution
   self.native=Execution(self.delta)
  self.native.authenticate()
  if owned is None:
   if self.config.get('execution_route')!='DIRECT':return dict(flat=True,source='NO_OWNED_OPTION_CONTRACT')
   product=self.delta.product(self.config['underlying']);pid=int(product['id'])
   quantity=self.delta._position(pid)
   if any(str(order.get('product_id'))==str(pid) for order in self.native.active_orders()):raise ValueError('Open Delta order blocks recovery rearm')
   if quantity!=0:raise ValueError('Selected Delta contract has unmanaged broker exposure; recovery pause retained')
   return dict(flat=True,quantity=0,product_id=pid,source='AUTHENTICATED_SELECTED_BROKER_POSITION_AND_ORDER_BOOK')
  product=self.delta.product(owned['symbol']);qty=self.delta._position(int(product['id']))
  if any(str(o.get('product_id'))==str(product['id']) for o in self.native.active_orders()):raise ValueError('Open Delta order blocks position control')
  expected=whole(owned['quantity'])*(-1 if owned.get('side')=='SHORT' else 1)
  if flat is True and qty!=0:raise ValueError('Delta has not confirmed square-off')
  if flat is False and qty!=expected or flat is None and qty not in (0,expected):raise ValueError('Delta signed ownership differs')
  return dict(flat=qty==0,quantity=qty,checked_at=self.delta.clock(),broker='DELTA_INDIA',account=self.config.get('account'))
