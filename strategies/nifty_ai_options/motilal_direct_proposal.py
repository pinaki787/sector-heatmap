"""Read-only proposed direct-order pricing. Not wired to any runner or broker."""
from decimal import Decimal,ROUND_FLOOR,ROUND_CEILING
import math
from datetime import datetime
from zoneinfo import ZoneInfo
def positive(value,label):
 if isinstance(value,bool):raise ValueError(label+' unavailable')
 try:value=Decimal(str(value))
 except Exception:raise ValueError(label+' unavailable') from None
 if not value.is_finite() or value<=0:raise ValueError(label+' unavailable')
 return value
def propose(meta,quote,*,side,quantity,account,now,buffer_ticks=1):
 if not isinstance(account,str) or len(account)!=32 or any(c not in '0123456789abcdef' for c in account):raise ValueError('Exact execution account required')
 if not str(meta.get('symbol','')).startswith('MO:') or meta.get('broker')!='MOTILAL_OSWAL':raise ValueError('Exact Motilal execution contract required')
 kind=str(meta.get('instrument','')).upper()
 if not (kind in ('EQ','EQUITY','CASH') and not meta.get('expiry') or kind.startswith('FUT')) or meta.get('option_type') in ('CE','PE'):raise ValueError('Proposal supports direct equities/futures only')
 if kind.startswith('FUT'):
  try:expiry=datetime.fromisoformat(str(meta['expiry'])[:10]).replace(hour=23,minute=59,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
  except (KeyError,ValueError):raise ValueError('Verified futures expiry required') from None
  if expiry<=now:raise ValueError('Expired future')

 if meta.get('suspended') or meta.get('banned'):raise ValueError('Contract is not available')
 if side not in ('BUY','SELL'):raise ValueError('Choose BUY or SELL')
 lot=meta.get('lot_size')
 if isinstance(lot,bool) or not isinstance(lot,int) or lot<=0 or isinstance(quantity,bool) or not isinstance(quantity,int) or quantity<=0 or quantity%lot:raise ValueError('Verified whole broker lots required')
 if quote.get('broker')!='MOTILAL_OSWAL' or quote.get('symbol')!=meta['symbol'] or quote.get('account')!=account:raise ValueError('Execution depth must match the selected Motilal account and exact contract')
 stamp=quote.get('exchange_at')
 if isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or not math.isfinite(stamp) or not 0<=now-stamp<=5:raise ValueError('Fresh execution depth required')
 if isinstance(buffer_ticks,bool) or not isinstance(buffer_ticks,int) or not 1<=buffer_ticks<=5:raise ValueError('Protected buffer must be 1 to 5 ticks')
 tick=positive(meta.get('tick_size'),'Execution tick');bid=positive(quote.get('bid'),'Bid');ask=positive(quote.get('ask'),'Ask')
 if bid>ask:raise ValueError('Crossed execution depth')
 executable=ask if side=='BUY' else bid
 cap=executable+tick*buffer_ticks if side=='BUY' else executable-tick*buffer_ticks
 if cap<=0:raise ValueError('Positive protected limit unavailable')
 # Quantize inward so the limit never exceeds one tick of allowed movement.
 limit=(cap/tick).to_integral_value(rounding=ROUND_FLOOR if side=='BUY' else ROUND_CEILING)*tick
 if side=='BUY' and limit<ask or side=='SELL' and limit>bid:raise ValueError('No marketable tick inside the protected bound')
 return dict(read_only=True,enabled=False,approval_required=True,account=account,symbol=meta['symbol'],side=side,quantity=quantity,product='INTRADAY',order_type='LIMIT',validity='IOC',limit_price=float(limit),original_price_bound=float(cap),buffer_ticks=buffer_ticks,quote_time=stamp,orders_submitted=0,fill_guaranteed=False)
