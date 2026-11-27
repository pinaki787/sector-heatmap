"""Exact Dhan master alias to chart-ID binding; no prices/orders/provider fallback."""
import re
def identity(native,symbol):
 if re.fullmatch(r'(?:IDX_I|MCX_COMM|(?:NSE|BSE)_(?:EQ|FNO|CURRENCY)):[0-9]{1,12}',symbol):return symbol
 row=native.underlying(symbol)
 exchange=row.get('SEM_EXM_EXCH_ID');segment=row.get('SEM_SEGMENT');security=str(row.get('SEM_SMST_SECURITY_ID',''))
 if not security.isdecimal() or exchange not in ('NSE','BSE','MCX'):raise ValueError('Exact Dhan master identity unavailable')
 prefix={'I':'IDX_I','E':exchange+'_EQ','D':exchange+'_FNO','M':'MCX_COMM','C':exchange+'_CURRENCY'}.get(segment)
 if not prefix:raise ValueError('Dhan chart segment unavailable')
 return prefix+':'+security

def display_payload(payload,source,display):
 if payload.get('symbol')!=source:raise ValueError('Captured Dhan source symbol differs')
 def mapped(value):
  if isinstance(value,dict):return {k:(display if k in ('symbol','underlying') and v==source else mapped(v)) for k,v in value.items()}
  if isinstance(value,list):return [mapped(v) for v in value]
  return value
 return dict(mapped(payload),execution_symbol=source)
