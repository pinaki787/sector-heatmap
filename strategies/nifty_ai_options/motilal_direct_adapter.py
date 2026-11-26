"""Motilal direct ownership with exclusively FYERS analytical prices."""
try:
 from .dhan_direct_adapter import DhanDirectAdapter
 from .motilal_direct import MotilalDirectAPI
 from .motilal_fyers_data import MarketData
 from .run import ROOT
except ImportError:
 from dhan_direct_adapter import DhanDirectAdapter
 from motilal_direct import MotilalDirectAPI
 from motilal_fyers_data import MarketData
 from run import ROOT
class MotilalDirectAdapter(DhanDirectAdapter):
 def __init__(self,config,native):
  self.config=dict(config);self.native=native;self.account=config['account'];self.broker='MOTILAL_OSWAL';self.product=config['product']
  self.api=MotilalDirectAPI(native,config);self.api.adapter=self
  self.market_data=MarketData(config,native,ROOT,clock=native.clock)
 def metadata(self,symbol):
  result=dict(self.api.master(symbol),product=self.product)
  if result['exchange']=='MCX':
   import json
   from datetime import datetime
   from zoneinfo import ZoneInfo
   mapped=self.market_data.symbol(symbol)
   path=self.market_data.root/'.private/nifty-ai-options/instrument-multipliers/FYERS.json'
   record=json.loads(path.read_text()).get(mapped,{}) if path.exists() else {}
   if record.get('as_of')!=datetime.fromtimestamp(self.native.clock(),ZoneInfo('Asia/Kolkata')).date().isoformat():raise ValueError('Current exact-contract economic multiplier is unavailable')
   mult=record.get('qtyMultiplier')
   if not isinstance(mult,(int,float)) or mult<=0:raise ValueError('Verified contract multiplier unavailable')
   result=dict(result,qtyMultiplier=mult/result['lot_size'],quantity_multiplier=mult/result['lot_size'],multiplier_basis='FYERS exact exchange contract per lot / Motilal exchange units per lot')
  return result
 def market_price(self,symbol):return self.market_data.price(symbol)
 def signal_quote(self,symbol):return self.market_data.quote(symbol)
 def validate(self):
  self.native.ready()
  if self.config.get('execution_mode')=='LIVE' and not self.native.live_enabled():raise PermissionError('Motilal Live capability disabled')
  meta=self.metadata(self.config['underlying']);mapped=self.market_data.symbol(self.config['underlying']);self.session()
  self.native.subscribe(self.config['underlying'],self.config['timeframe']*60)
  if self.config.get('execution_mode')=='LIVE':self.books()
  return dict(broker=self.broker,account_id=self.account,account_identity=self.native.account_identity,underlying=self.config['underlying'],execution_route='DIRECT',product=self.product,instrument=meta,order_type='PROTECTED_LIMIT_IOC',protected_limit_ticks=self.api.buffer,market_data_broker='FYERS',market_data_account=self.market_data.account,market_data_underlying=mapped,read_only=True,orders_submitted=0)
 def order_readiness(self,contract,quantity):
  sides=[]
  for side in (1,-1):
   payload=self.api.prepare_order(dict(symbol=contract['symbol'],qty=quantity,side=side,type=2,productType=self.product,limitPrice=0,stopPrice=0,validity='DAY',offlineOrder=False,orderTag='nai-read-only-preflight'))
   required=self.api.margin(payload);available=self.api.funds()['fund_limit'][0]['equityAmount']
   if required>available:raise ValueError('Conservative full-value reserve exceeds native available funds')
   sides.append(dict(side=side,required_reserve=required,available=available))
  return dict(read_only=True,orders_submitted=0,reserve_basis='Full contract value plus 1%; leveraged margin not inferred',sides=sides)
 def verify(self,position,*,flat=False):
  result=super().verify(position,flat=flat)
  return dict(result,broker=self.broker,account=self.account)
