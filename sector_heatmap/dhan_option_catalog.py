"""Current Dhan option underlyings, filtered before display with no fixed page cap."""
from datetime import date
from threading import RLock
from .dhan_execution import contract_underlying
_CACHE=None
_LOCK=RLock()
MARKETS={'NSE_STOCK':('NSE','E'),'BSE_STOCK':('BSE','E'),'NSE_INDEX':('NSE','I'),'BSE_INDEX':('BSE','I'),'NSE':('NSE',None),'BSE':('BSE',None)}

def build(rows,today):
 pairs={}
 for row in rows:
  if row.get('SEM_EXM_EXCH_ID') not in ('NSE','BSE') or row.get('SEM_SEGMENT')!='D' or row.get('SEM_OPTION_TYPE') not in ('CE','PE') or row.get('SEM_INSTRUMENT_NAME') not in ('OPTSTK','OPTIDX'):continue
  expiry=str(row.get('SEM_EXPIRY_DATE',''))[:10]
  try:date.fromisoformat(expiry)
  except ValueError:continue
  if expiry<today:continue
  try:under=contract_underlying(row)
  except ValueError:continue
  key=(row['SEM_EXM_EXCH_ID'],under,expiry,str(row.get('SEM_STRIKE_PRICE')),row['SEM_INSTRUMENT_NAME'])
  pairs.setdefault(key,set()).add(row['SEM_OPTION_TYPE'])
 eligible={}
 for (exchange,under,expiry,strike,kind),sides in pairs.items():
  if sides=={'CE','PE'}:eligible.setdefault((exchange,under,kind),set()).add(expiry)
 result={}
 for row in rows:
  exchange=row.get('SEM_EXM_EXCH_ID');segment=row.get('SEM_SEGMENT');ticker=row.get('SEM_TRADING_SYMBOL')
  if exchange not in ('NSE','BSE') or segment not in ('I','E') or not ticker:continue
  if segment=='E' and exchange=='NSE' and row.get('SEM_SERIES') not in (None,'','EQ'):continue
  kind='OPTIDX' if segment=='I' else 'OPTSTK'
  expiries=eligible.get((exchange,ticker,kind))
  if not expiries:continue
  security=str(row.get('SEM_SMST_SECURITY_ID',''))
  if not security.isdecimal():continue
  key=exchange+':'+ticker
  item=dict(symbol=key,underlying=ticker,description=row.get('SEM_CUSTOM_SYMBOL') or row.get('SM_SYMBOL_NAME') or ticker,
    product_type='INDEX' if segment=='I' else 'STOCK',exchange=exchange,segment=segment,
    chart_symbol=('IDX_I' if segment=='I' else exchange+'_EQ')+':'+security,
    option_expiries=sorted(expiries))
  if key in result and result[key]['chart_symbol']!=item['chart_symbol']:raise ValueError('Ambiguous Dhan option-underlying identity: '+key)
  result[key]=item
 return tuple(result.values())

def search(rows,today,text,market=None):
 global _CACHE
 with _LOCK:
  if _CACHE is None or _CACHE[0] is not rows or _CACHE[1]!=today:_CACHE=(rows,today,build(rows,today))
  catalogue=_CACHE[2]
 exchange,segment=MARKETS.get(market,(None,None))
 query=str(text or '').strip().upper()
 if ':' in query and query.split(':',1)[0] in ('NSE','BSE'):
  venue,query=query.split(':',1)
  if exchange and venue!=exchange:return []
  exchange=venue
 terms=query.split()
 matches=[dict(r,option_expiries=list(r['option_expiries'])) for r in catalogue if (not exchange or r['exchange']==exchange) and (not segment or r['segment']==segment) and all(t in (r['underlying']+' '+r['description']).upper() for t in terms)]
 matches.sort(key=lambda r:(r['underlying']!=query,not r['underlying'].startswith(query),r['segment']!='I',r['underlying'],r['exchange']))
 return matches
