"""Explicit FYERS long-option adoption. Broker reads only; never submits an entry."""
import math,time
try:from .run import ok
except ImportError:from run import ok

def candidate_rows(api,config,master):
    if config.get('broker')!='FYERS' or config.get('execution_route')!='OPTIONS':
        raise ValueError('Attachment currently supports FYERS bought options')
    try:from .live import exposure_prefix
    except ImportError:from live import exposure_prefix
    positions=ok(api.positions()).get('netPositions')
    if not isinstance(positions,list):raise ValueError('Unrecognized broker positions')
    result=[]
    for row in positions:
        symbol=row.get('symbol','');qty=row.get('netQty',0)
        if not symbol.startswith(exposure_prefix(config)) or not isinstance(qty,(int,float)) or isinstance(qty,bool) or qty<=0:continue
        meta=master(symbol);lot=meta['lot_size'];product=row.get('productType')
        if meta.get('option_type') not in ('CE','PE') or product not in ('MARGIN','INTRADAY') or qty%lot or float(meta['expiry_epoch'])<=time.time():continue
        result.append(dict(symbol=symbol,quantity=int(qty),product=product,lots=int(qty/lot),expiry=str(meta['expiry_epoch']),side=meta['option_type'],average_price=row.get('buyAvg')))
    return result

def verify_position(api,config,request,master):
    if config.get('execution_mode')!='LIVE':raise ValueError('Broker positions can attach only to Live mode')
    if not isinstance(request,dict) or set(request)!={'symbol','quantity','product'}:raise ValueError('Exact attachment contract, quantity and product required')
    matches=[r for r in candidate_rows(api,config,master) if r['symbol']==request.get('symbol') and r['product']==request.get('product')]
    if len(matches)!=1:raise ValueError('Exactly one matching open broker position is required')
    row=matches[0]
    if isinstance(request.get('quantity'),bool) or request.get('quantity')!=row['quantity'] or row['lots']!=config.get('lots') or row['product']!=config.get('product'):raise ValueError('Attachment quantity, lots or product changed')
    orders=ok(api.orderbook()).get('orderBook')
    if not isinstance(orders,list):raise ValueError('Unrecognized broker orders')
    if any(r.get('symbol')==row['symbol'] and r.get('status') in (1,4,6) for r in orders):raise ValueError('Attachment contract has an open broker order')
    price=row['average_price']
    if isinstance(price,bool) or not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0:raise ValueError('Broker entry average unavailable')
    return dict(row,verified_at=time.time())
