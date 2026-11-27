"""Read-only, exact-account evidence for externally closed bought options.
Flat alone never fabricates an exit fill. Unknown/partial histories remain retained.
"""
import hashlib,json,math,time
from datetime import datetime
from zoneinfo import ZoneInfo

def whole(v):
 if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or int(v)!=v:raise ValueError('Broker quantity unavailable')
 return int(v)
def stamp(row):
 try:return datetime.strptime(row['orderDateTime'],'%d-%b-%Y %H:%M:%S').replace(tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
 except (KeyError,ValueError,TypeError):raise ValueError('Broker order time unavailable') from None
def evidence(owned,product,positions,orders,*,now):
 symbol=owned['symbol'];quantity=whole(owned['quantity'])
 if quantity<=0 or owned.get('side') not in ('CE','PE'):raise ValueError('Exact bought-option ownership required')
 matching=[r for r in positions if r.get('symbol')==symbol and r.get('productType')==product]
 if len(matching)!=1:raise ValueError('Explicit unambiguous broker position row required')
 current=whole(matching[0].get('netQty'))
 selected=[r for r in orders if r.get('symbol')==symbol and r.get('productType')==product]
 if any(r.get('status') not in (1,2,5) for r in selected):raise ValueError('Open or unknown selected-contract order prevents external-close cleanup')
 if current==quantity:return None
 if current!=0:raise ValueError('Broker quantity differs; partial external exit remains retained')
 entries=[r for r in selected if str(r.get('id'))==str(owned.get('order_id'))]
 if len(entries)!=1:raise ValueError('Exact owned entry order required for external close')
 entry=entries[0];entry_at=stamp(entry)
 if entry.get('status')!=2 or entry.get('side')!=1 or whole(entry.get('filledQty'))!=quantity or whole(entry.get('qty'))!=quantity:raise ValueError('Owned entry is not completely filled')
 if not isinstance(owned.get('fill_price'),(int,float)) or abs(float(entry.get('tradedPrice',0))-owned['fill_price'])>1e-8:raise ValueError('Entry fill price differs from ownership')
 later=[]
 for row in selected:
  if str(row.get('id'))==str(entry['id']):continue
  at=stamp(row)
  if at<entry_at:continue
  if at==entry_at:raise ValueError('Ambiguous same-second orders require explicit reconciliation')
  filled=whole(row.get('filledQty',0))
  if filled:
   if row.get('status')!=2 or row.get('side')!=-1 or whole(row.get('qty'))!=filled:raise ValueError('Subsequent fill is partial, unknown or a new entry')
   price=row.get('tradedPrice')
   if isinstance(price,bool) or not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0:raise ValueError('External exit fill price unavailable')
   later.append((row,at,filled,price))
 if not later or len({str(r[0]['id']) for r in later})!=len(later) or sum(r[2] for r in later)!=quantity:raise ValueError('Complete unique external closing fills required')
 if any(at>now+5 for _,at,_,_ in later):raise ValueError('Future-dated broker fill evidence')
 sanitized=[{k:r.get(k) for k in ('id','symbol','productType','status','side','qty','filledQty','tradedPrice','orderDateTime')} for r,_,_,_ in sorted(later,key=lambda r:r[1])]
 proof=hashlib.sha256(json.dumps([owned.get('order_id'),sanitized],sort_keys=True).encode()).hexdigest()
 return dict(revision='fyers-external-exit-v1',proof=proof,symbol=symbol,product=product,quantity=quantity,
  checked_at=now,broker_flat_confirmed=True,orders_submitted=0,entry_order=str(entry['id']),
  exit_orders=sanitized,fill_price=sum(q*p for _,_,q,p in later)/quantity,broker_order_at=max(at for _,at,_,_ in later),
  exit_order=str(later[0][0]['id']) if len(later)==1 else '+'.join(r['id'] for r in sanitized))

def trades(proof,rows):
 if not isinstance(rows,list):raise ValueError('Selected broker tradebook unavailable')
 selected=[r for r in rows if r.get('symbol')==proof['symbol'] and r.get('productType')==proof['product'] and str(r.get('orderNumber')) in {r['id'] for r in proof['exit_orders']}]
 ids=[r.get('tradeNumber') for r in selected]
 if not ids or any(not x for x in ids) or len(set(ids))!=len(ids):raise ValueError('Unique external fill records required')
 stamps=[]
 for order in proof['exit_orders']:
  matches=[r for r in selected if str(r.get('orderNumber'))==order['id']]
  if not matches or any(r.get('side')!=-1 or whole(r.get('tradedQty'))<=0 for r in matches):raise ValueError('External trade side/quantity mismatch')
  total=sum(whole(r['tradedQty']) for r in matches)
  if total!=order['filledQty'] or any(not isinstance(r.get('tradePrice'),(int,float)) or isinstance(r['tradePrice'],bool) or not math.isfinite(r['tradePrice']) or r['tradePrice']<=0 for r in matches):raise ValueError('External trade fill quantity/price unavailable')
  avg=sum(r['tradePrice']*r['tradedQty'] for r in matches)/total
  if abs(avg-order['tradedPrice'])>1e-8:raise ValueError('Order/tradebook fill average disagrees')
  stamps.extend(stamp(r) for r in matches)
 return dict(proof,broker_trade_at=max(stamps),trade_ids=ids,fill_time_basis='FYERS tradebook timestamp (orderDateTime)')

def read(executor,owned):
 from strategies.nifty_ai_options.run import ok
 identity=(ok(executor.api.get_profile()).get('data') or {}).get('fy_id')
 if not identity or hashlib.sha256(str(identity).encode()).hexdigest()!=executor.path.parent.name:raise ValueError('External-close broker account identity mismatch')
 positions,orders=executor.exposure()
 proof=evidence(owned,executor.product,positions,orders,now=time.time())
 if proof is None:return None
 return trades(proof,ok(executor.api.tradebook()).get('tradeBook'))
