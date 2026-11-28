"""One fresh depth snapshot per entry attempt; no orders, retries or history here."""
ENTRY_POLICY_REVISION='fresh-depth-market-entry-v1'
from decimal import Decimal,InvalidOperation
from urllib.parse import quote as escape
class EntryNotReady(ValueError):pass
def decimal(value):
 try:v=Decimal(str(value))
 except (InvalidOperation,ValueError,TypeError):raise EntryNotReady('Invalid executable depth')
 if not v.is_finite():raise EntryNotReady('Invalid executable depth')
 return v
def _read_depth_once(delta,symbol,max_age=2):
 reply=delta._get('/v2/l2orderbook/'+escape(symbol,safe=''),dict(depth=20))
 if not isinstance(reply,dict) or not isinstance(reply.get('result'),dict):raise EntryNotReady('Executable depth unavailable')
 book=reply['result']
 if book.get('symbol')!=symbol:raise EntryNotReady('Depth belongs to another contract')
 now=delta.clock();stamp=float(decimal(book.get('last_updated_at'))/Decimal(1000000))
 if not -2<=now-stamp<=max_age:raise EntryNotReady('Executable depth is stale')
 sides={}
 for side in ['buy','sell']:
  rows=book.get(side)
  if not isinstance(rows,list) or not rows:raise EntryNotReady('Executable depth unavailable')
  levels=[]
  for row in rows:
   if not isinstance(row,dict):raise EntryNotReady('Invalid executable depth')
   price,size=decimal(row.get('price')),decimal(row.get('size'))
   if price<=0 or size<0 or size!=size.to_integral_value():raise EntryNotReady('Invalid contract depth')
   levels.append((price,int(size)))
  if len({p for p,n in levels})!=len(levels):raise EntryNotReady('Duplicate depth levels')
  sides[side]=levels
 bid=max(p for p,n in sides['buy']);ask=min(p for p,n in sides['sell'])
 if bid>ask:raise EntryNotReady('Crossed executable depth')
 return dict(symbol=symbol,bid=float(bid),ask=float(ask),exchange_at=stamp,received_at=now),sides
def read_depth(delta,symbol,max_age=2):
 # Refetch only stale depth, before any order intent exists. Never relax age.
 import time
 for attempt in range(3):
  try:return _read_depth_once(delta,symbol,max_age)
  except EntryNotReady as error:
   if str(error)!='Executable depth is stale' or attempt==2:raise
   time.sleep(.15)

def sufficient_depth(levels,side,quantity,limit):
 boundary=decimal(limit)
 rows=levels['sell' if side==1 else 'buy']
 available=sum(n for price,n in rows if (price<=boundary if side==1 else price>=boundary))
 if available<quantity:raise EntryNotReady('Insufficient executable quantity within original price limit')
 return available

def sufficient_market_depth(levels,side,quantity):
 available=sum(size for price,size in levels['sell' if side==1 else 'buy'])
 if available<quantity:raise EntryNotReady('Insufficient executable market depth for selected quantity')
 return available
