"""Dhan direct-instrument data/ownership adapter; no option contract inference."""
import hashlib,math
try:
 from .native_indian import NativeIndianAdapter
 from .dhan_direct import DhanDirectAPI
except ImportError:
 from native_indian import NativeIndianAdapter
 from dhan_direct import DhanDirectAPI

class DhanDirectAdapter(NativeIndianAdapter):
 def __init__(self,config,native):
  self.config=dict(config);self.native=native;self.account=config['account'];self.broker='DHAN';self.product=config['product'];self.market_data=None
  self.api=DhanDirectAPI(native,config)
 def market_price(self,symbol):
  if symbol!=self.config["underlying"]:raise ValueError("Selected Dhan direct source differs")
  quote=self.api.quote();return quote["ltp"],quote["timestamp"]
 def metadata(self,symbol):return self.api.master(symbol)
 def quote(self,symbol):
  if symbol!=self.config['underlying']:raise ValueError('Selected Dhan direct quote differs')
  return dict(self.api.quote(),symbol=symbol)
 def validate(self):
  client=self.native.authenticated_client()
  if self.config.get('execution_mode')=='LIVE' and not self.native.live_enabled():raise PermissionError('Dhan Live capability is disabled')
  meta=self.metadata(self.config['underlying']);self.session()
  self.native.subscribe(self.config['underlying'],self.config['timeframe']*60)
  if self.config.get('execution_mode')=='LIVE':self.books()
  return dict(broker='DHAN',account_id=self.account,account_identity=self.native.account_identity,
   underlying=self.config['underlying'],product=self.product,execution_route='DIRECT',instrument=meta,
   order_type='MARKET_WITH_BROKER_MPP',read_only=True,orders_submitted=0)
 def books(self):return self.api.positions()['netPositions'],self.api.orderbook()['orderBook']
 def order_readiness(self,contract,quantity):
  if contract.get('symbol')!=self.config['underlying']:raise ValueError('Direct preflight contract differs')
  proofs=[]
  for side in ((1,) if self.product=='CNC' else (1,-1)):
   payload=dict(symbol=contract['symbol'],qty=quantity,side=side,type=2,productType=self.product,limitPrice=0,stopPrice=0,validity='DAY',offlineOrder=False,orderTag='nai-read-only-preflight')
   required=self.api.margin(payload);available=self.api.funds()['fund_limit'][0]['equityAmount']
   if required>available:raise ValueError('Dhan margin exceeds available funds')
   proofs.append(dict(side=side,required_margin=required,available=available))
  return dict(read_only=True,orders_submitted=0,sides=proofs)
 def candidates(self):
  meta=self.metadata(self.config['underlying']);positions,orders=self.books();result=[]
  for p in positions:
   quantity=p.get('netQty')
   if p.get('symbol')!=self.config['underlying'] or p.get('productType')!=self.product or isinstance(quantity,bool) or not isinstance(quantity,int) or not quantity:continue
   if abs(quantity)%meta['lot_size'] or any(o.get('symbol')==p['symbol'] and o.get('status') in (4,6) for o in orders):continue
   average=p.get('netAvg')
   if not isinstance(average,(int,float)) or not math.isfinite(average) or average<=0:continue
   result.append(dict(symbol=p['symbol'],quantity=abs(quantity),side='LONG' if quantity>0 else 'SHORT',product=self.product,average_price=average,meta=meta,account=self.account,underlying=self.config['underlying']))
  return result
 def verify(self,position,*,flat=False):
  if position is None:return dict(flat=True)
  positions,orders=self.books();symbol=position['symbol']
  if symbol!=self.config['underlying']:raise ValueError('Owned direct instrument differs')
  if any(o.get('symbol')==symbol and o.get('status') in (4,6) for o in orders):raise ValueError('Open Dhan order prevents confirming ownership')
  rows=[p for p in positions if p.get('symbol')==symbol and p.get('netQty')]
  expected=position['quantity']*(-1 if position['side']=='SHORT' else 1)
  quantity=sum(int(p['netQty']) for p in rows)
  if any(p.get('productType')!=self.product for p in rows):raise ValueError('Dhan product differs from direct ownership')
  if flat is True and quantity!=0 or flat is False and quantity!=expected or flat is None and quantity not in (0,expected):raise ValueError('Signed Dhan quantity differs from ownership')
  return dict(flat=quantity==0,quantity=quantity,broker='DHAN',account=self.account)
