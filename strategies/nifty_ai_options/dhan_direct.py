"""Dhan-only direct stock/future boundary for the durable direct executor.

Construction, master resolution and margin queries never place an order.
The transport cannot submit until bound to a persisted PREPARED executor intent.
"""
import copy,json,math,time
from datetime import datetime
from zoneinfo import ZoneInfo
IST=ZoneInfo('Asia/Kolkata')
SEGMENTS={'NSE_EQ','BSE_EQ','NSE_FNO','BSE_FNO','MCX_COMM'}
_SEARCH_CATALOG={}

def direct_metadata(native,symbol,now=None):
 now=native.clock() if now is None else now
 if symbol.split(':')[0] in SEGMENTS:
  segment,identifier=symbol.split(':',1)
  rows=[r for r in native._rows() if native._segment(r)==segment and str(r['SEM_SMST_SECURITY_ID'])==identifier]
  if len(rows)!=1:raise ValueError('Exact Dhan direct contract is missing or ambiguous')
  row=rows[0]
 else:row=native.underlying(symbol)
 return metadata_from_row(native,row,symbol,now)

def metadata_from_row(native,row,symbol,now):
 cash=row.get('SEM_SEGMENT')=='E'
 future=row.get('SEM_SEGMENT') in ('D','M') and str(row.get('SEM_INSTRUMENT_NAME','')).startswith('FUT')
 if not cash and not future:raise ValueError('Select an exact Dhan equity or futures contract; indices and options cannot use the direct route')
 meta=native._meta(row)
 result=dict(meta,symbol=symbol,execution_symbol=meta['symbol'],product_type='STOCK' if cash else 'FUTURE',underlying=symbol)
 if future:
  try:expiry=datetime.fromisoformat(str(row['SEM_EXPIRY_DATE'])[:10]).replace(hour=23,minute=59,tzinfo=IST).timestamp()
  except (KeyError,ValueError):raise ValueError('Verified futures expiry is required') from None
  if expiry<=now:raise ValueError('Expired Dhan futures contract')
  result['expiry_epoch']=expiry
 return result


def search_direct(native,query,market='ALL'):
 query=str(query or '').strip().upper();now=native.clock()
 if market=='ALL' and len(query)<2:return []
 if market.endswith('_INDEX'):return []
 rows=native._rows();owner=getattr(getattr(native,'service',None),'account',{}).get('id',id(native))
 key=(owner,market);day=datetime.fromtimestamp(now,IST).date();cached=_SEARCH_CATALOG.get(key)
 if cached and cached['rows'] is rows and cached['day']==day:result=cached['catalog']
 else:
  result=[]
  for row in rows:
   exchange=row.get('SEM_EXM_EXCH_ID');segment=native._segment(row)
   if segment not in SEGMENTS:continue
   if market!='ALL' and exchange!=market.split('_')[0]:continue
   future=str(row.get('SEM_INSTRUMENT_NAME','')).startswith('FUT') and row.get('SEM_SEGMENT') in ('D','M')
   cash=row.get('SEM_SEGMENT')=='E'
   if not cash and not future:continue
   if market.endswith(('_FUTURE','_FUTURES')) and not future:continue
   if market.endswith(('_EQUITY','_STOCK')) and not cash:continue
   symbol=segment+':'+str(row['SEM_SMST_SECURITY_ID'])
   try:meta=metadata_from_row(native,row,symbol,now)
   except ValueError:continue
   result.append(dict(symbol=symbol,description=row.get('SEM_CUSTOM_SYMBOL') or row.get('SEM_TRADING_SYMBOL'),underlying=row.get('SEM_TRADING_SYMBOL'),product_type=meta['product_type'],market=exchange,expiry=meta.get('expiry_epoch')))
  if len(_SEARCH_CATALOG)>=64:_SEARCH_CATALOG.pop(next(iter(_SEARCH_CATALOG)))
  _SEARCH_CATALOG[key]=dict(rows=rows,day=day,catalog=result)
 try:from .instrument_suggestions import ranked
 except ImportError:from instrument_suggestions import ranked
 return ranked(result,query)

class DhanDirectAPI:
 def __init__(self,native,config):
  if config.get('broker')!='DHAN' or native.service.account.get('id')!=config.get('account') or native.service.account.get('broker')!='DHAN':raise PermissionError('Exact selected Dhan account is required')
  if config.get('execution_route')!='DIRECT' or config.get('product') not in ('INTRADAY','MARGIN'):raise ValueError('Dhan direct execution requires an explicit supported product')
  self.native=native;self.config=dict(config);self.meta=direct_metadata(native,config['underlying']);self.executor=None;self._margin=None;self._quote_cache=None
  if self.meta['product_type']=='STOCK' and config['product']!='INTRADAY' or self.meta['product_type']=='FUTURE' and config['product'] not in ('INTRADAY','MARGIN'):raise ValueError('Dhan product is incompatible with the selected direct instrument')
 def bind(self,executor):
  if executor.api is not self or executor.broker!='DHAN' or executor.path.parent.name!=self.config['account']:raise PermissionError('Dhan executor belongs to a different account boundary')
  if executor.product!=self.config['product'] or executor.lots!=self.config['lots']:raise PermissionError('Dhan executor quantity/product binding differs')
  self.executor=executor
 def master(self,symbol):
  if symbol!=self.config['underlying']:raise ValueError('Direct contract differs from selected instrument')
  fresh=direct_metadata(self.native,symbol)
  if any(fresh.get(k)!=self.meta.get(k) for k in ('execution_symbol','lot_size','tick_size','product_type','expiry_epoch')):raise ValueError('Dhan direct master changed; no submission')
  return fresh
 def _symbol(self,symbol):return self.config['underlying'] if symbol==self.meta['execution_symbol'] else symbol
 def positions(self):
  return dict(s='ok',netPositions=[dict(r,symbol=self._symbol(r['symbol'])) for r in self.native.positions()])
 def orderbook(self):
  return dict(s='ok',orderBook=[dict(r,symbol=self._symbol(r['symbol'])) for r in self.native.orders()])
 def get_profile(self):
  client=self.native.authenticated_client()
  return dict(s='ok',data=dict(fy_id='DHAN:'+str(client.client_id)))
 def session(self):
  try:from .native_indian import NativeIndianAdapter
  except ImportError:from native_indian import NativeIndianAdapter
  return NativeIndianAdapter.session(self)
 def quote(self):
  self.master(self.config['underlying'])
  cached=self._quote_cache;now=self.native.clock()
  if cached and 0<=now-cached['cached_at']<1:return dict(cached['quote'])
  quote=self.native._market(self.meta)
  stamp=quote.get('exchange_at')
  if not isinstance(stamp,(int,float)) or isinstance(stamp,bool) or not 0<=self.native.clock()-stamp<=5:raise ValueError('Fresh Dhan execution quote required')
  last=quote.get('last_price')
  if isinstance(last,bool) or not isinstance(last,(int,float)) or not math.isfinite(last) or last<=0:raise ValueError('Actual Dhan last trade price is unavailable')
  result=dict(quote,timestamp=stamp,ltp=last)
  self._quote_cache=dict(cached_at=now,quote=result);return dict(result)
 def payload(self,order):
  self.master(order.get('symbol'))
  qty=order.get('qty')
  if (isinstance(qty,bool) or not isinstance(qty,int) or qty<=0 or qty%self.meta['lot_size']
      or order.get('type')!=2 or order.get('side') not in (1,-1)
      or order.get('productType')!=self.config['product'] or order.get('limitPrice')!=0
      or order.get('stopPrice')!=0 or order.get('validity')!='DAY'
      or order.get('offlineOrder') is not False):raise ValueError('Exact whole-lot Dhan intraday market order required')
  tag=order.get('orderTag')
  if not isinstance(tag,str) or not 1<=len(tag)<=30:raise ValueError('Durable Dhan correlation ID required')
  client=self.native.authenticated_client()
  return dict(dhanClientId=str(client.client_id),correlationId=tag,transactionType='BUY' if order['side']==1 else 'SELL',
   exchangeSegment=self.meta['exchange_segment'],securityId=str(self.meta['security_id']),quantity=qty,
   productType=self.config['product'],orderType='MARKET',price=0,triggerPrice=0,disclosedQuantity=0,afterMarketOrder=False,validity='DAY')
 def funds(self):
  client=self.native.authenticated_client();row=client.request('GET','/fundlimit')
  if str(row.get('dhanClientId'))!=str(client.client_id):raise PermissionError('Dhan fund owner mismatch')
  available=row.get('availableBalance',row.get('availabelBalance'))
  if isinstance(available,bool) or not isinstance(available,(int,float)) or not math.isfinite(available) or available<0:raise ValueError('Dhan available balance is unknown')
  return dict(s='ok',fund_limit=[dict(id=10,equityAmount=available)])
 def margin(self,order):
  body=self.payload(order);client=self.native.authenticated_client()
  request={k:v for k,v in body.items() if k in ('dhanClientId','exchangeSegment','transactionType','quantity','productType','securityId','price','triggerPrice')}
  quote=self.quote();request['price']=quote['ask' if order['side']==1 else 'bid']
  row=client.request('POST','/margincalculator',request);required=row.get('totalMargin')
  if isinstance(required,bool) or not isinstance(required,(int,float)) or not math.isfinite(required) or required<0:raise ValueError('Dhan margin requirement unavailable')
  return required
 def place_order(self,*,data):
  executor=self.executor
  if executor is None or not executor.live:raise PermissionError('Only a user-started Live executor may submit')
  pending=executor.state.get('pending') or {}
  if pending.get('stage')!='PREPARED' or pending.get('payload')!=data:raise PermissionError('Exact durable prepared intent is required before Dhan submission')
  disk=json.loads(executor.path.read_text()).get('pending') or {}
  if disk!=pending:raise PermissionError('Durable Dhan intent differs from memory')
  if not self.native.live_enabled():raise PermissionError('Dhan Live capability is disabled')
  if not self.session()['open']:raise ValueError('Selected Dhan venue is closed')
  if pending['intent'].get('action')=='OPEN_SHORT' and self.config['product']=='CNC':raise ValueError('Delivery shares cannot open a short')
  body=self.payload(data);client=self.native.authenticated_client()
  ips=client.request('GET','/ip/getIP')
  if self.native.service.egress() not in (ips.get('primaryIP'),ips.get('secondaryIP')):raise PermissionError('Server IP is not registered for this Dhan account')
  self.quote()
  rows=self.positions()['netPositions'];orders=self.orderbook()['orderBook']
  symbol=data['symbol'];entry=pending['intent']['action'].startswith('OPEN_')
  owned=executor.state.get('position')
  if not entry and (not owned or owned.get('symbol')!=symbol):raise ValueError('Exact owned Dhan direct holding required')
  expected=0 if entry else owned['quantity']*(1 if owned['side']=='LONG' else -1)
  held=[r for r in rows if r['symbol']==symbol and r.get('netQty')]
  if any(r.get('productType')!=self.config['product'] for r in held) or sum(int(r['netQty']) for r in held)!=expected:raise ValueError('Dhan signed quantity changed before submission')
  if any(r.get('symbol')==symbol and r.get('status') in (4,6) for r in orders):raise ValueError('An open Dhan order blocks this direct contract')
  pending['stage']='SUBMITTING';executor.save()
  result=client.request('POST','/orders',body)
  identifier=result.get('orderId') if isinstance(result,dict) else None
  if not identifier:raise RuntimeError('Dhan acknowledgement is unknown; no automatic retry')
  return dict(s='ok',id=str(identifier))
