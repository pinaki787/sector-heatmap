"""INR entry allocation. No broker request or order on import.
Allocation is gross premium/share value/futures notional, never margin or a cap.
"""
from decimal import Decimal,ROUND_FLOOR
import math,time,json
from pathlib import Path

def positive(value,name):
 if isinstance(value,bool):raise ValueError(name+" must be positive")
 try:d=Decimal(str(value))
 except Exception:raise ValueError(name+" must be positive") from None
 if not d.is_finite() or d<=0:raise ValueError(name+" must be positive")
 return d

def policy(payload):
 mode=payload.get('entry_quantity_mode','QUANTITY')
 if mode not in ('QUANTITY','AMOUNT_INR'):raise ValueError('Choose quantity or INR amount')
 if mode=='QUANTITY':return dict(entry_quantity_mode=mode)
 amount=positive(payload.get('entry_amount_inr'),'INR amount')
 if payload.get('broker')=='DELTA_INDIA':raise ValueError('INR allocation needs a verified currency conversion; use contracts for Delta')
 if payload.get('ai_attach_position'):raise ValueError('Attach uses the actual holding quantity; select quantity mode')
 return dict(entry_quantity_mode=mode,entry_amount_inr=float(amount))

def calculate(amount,price,lot,multiplier=1,*,quote_at,now=None,currency='INR',kind='STOCK'):
 now=time.time() if now is None else now
 if currency!='INR':raise ValueError('Verified INR conversion unavailable; use quantity mode')
 if isinstance(quote_at,bool) or not isinstance(quote_at,(int,float)) or not math.isfinite(quote_at) or not 0<=now-quote_at<=5:raise ValueError('Fresh selected-broker LTP required for amount sizing')
 if isinstance(lot,bool) or not isinstance(lot,int) or lot<1:raise ValueError('Valid whole exchange lot required')
 cash=positive(amount,'INR amount');price=positive(price,'LTP');multiplier=positive(multiplier,'Contract multiplier')
 unit=price*multiplier;lots=int((cash/(unit*lot)).to_integral_value(rounding=ROUND_FLOOR))
 if lots<1:raise ValueError('Amount is insufficient for one share/lot at the current LTP')
 return dict(lots=lots,quantity=lots*lot,estimated_cost_inr=float(unit*lot*lots),ltp=float(price),quote_at=quote_at,currency='INR',basis='premium' if kind=='OPTION' else 'futures notional (not margin)' if kind=='FUTURE' else 'share value',amount_inr=float(cash),costs_included=False,budget_cap=False)

def economic_multiplier(meta,symbol,data):
 value=next((meta[k] for k in ('quantity_multiplier','qtyMultiplier','contract_multiplier') if meta.get(k) is not None),None)
 if value is not None:return positive(value,'Contract multiplier')
 if symbol.startswith(('NSE:','BSE:','NSE_EQ:','BSE_EQ:','NSE_FNO:','BSE_FNO:','MO:NSE:','MO:BSE:','MO:NSEFO:','MO:BSEFO:')):return Decimal(1)
 # Exact public FYERS MCX metadata, cached daily by the existing journal service.
 path=Path(data)/'instrument-multipliers'/'FYERS.json'
 if symbol.startswith('MCX:') and path.exists() and time.time()-path.stat().st_mtime<86400:
  row=json.loads(path.read_text()).get(symbol,{})
  if row.get('currency') not in (None,'INR',1):raise ValueError('Contract currency is not verified INR')
  return positive(row.get('qtyMultiplier'),'Exact MCX multiplier')
 raise ValueError('Exact contract multiplier unavailable; use quantity mode')

def from_quote(config,symbol,meta,quote,data,now=None):
 stamp=quote.get('timestamp',quote.get('exchange_at'))
 return calculate(config['entry_amount_inr'],quote.get('ltp',quote.get('last_price')),meta['lot_size'],
  economic_multiplier(meta,symbol,data),quote_at=stamp,now=now,
  currency=meta.get('settlement_currency',meta.get('currency','INR')),
  kind='OPTION' if meta.get('option_type') in ('CE','PE') else meta.get('product_type','STOCK'))

def apply(executor,action,args):
 config=getattr(executor,'runner_config',{})
 if config.get('entry_quantity_mode')!='AMOUNT_INR' or action.get('action') not in ('BUY','OPEN_LONG','OPEN_SHORT'):return
 if executor.state.get('pending'):raise ValueError('Uncertain intent blocks allocation recalculation')
 symbol=action['position']['symbol']
 if config.get('broker')=='DELTA_INDIA':raise ValueError('INR conversion unavailable')
 if hasattr(executor,'adapter'):
  meta=executor.adapter.metadata(symbol);quote=executor.adapter.quote(symbol)
 else:
  native_adapter=getattr(executor.api,'adapter',None) if config.get('broker')=='MOTILAL_OSWAL' else None
  meta=native_adapter.metadata(symbol) if native_adapter is not None else executor.master(symbol)
  quote=args[0] if args and isinstance(args[0],dict) else executor.api.quote()
 result=from_quote(config,symbol,meta,quote,executor.runner_data)
 executor.lots=result['lots']
 if hasattr(executor,'adapter'):executor.adapter.config['lots']=result['lots']
 executor.state['entry_allocation']=dict(result,symbol=symbol,at=time.time())
 # Persist the estimate with the subsequently prepared intent; not an order.
 executor.save()

def preview(owner,config,data):
 """Bounded read-only quote; no native sizing acquisition, history or order."""
 broker=config['broker']
 if broker in ('DHAN','MOTILAL_OSWAL'):
  from .native_indian import bound_native
  adapter=bound_native(config)
  contracts=[adapter.metadata(config['underlying'])] if config['execution_route']=='DIRECT' else [adapter.select(side) for side in ('CE','PE')]
  return [dict(from_quote(config,c['symbol'],adapter.metadata(c['symbol']),adapter.quote(c['symbol']),data),symbol=c['symbol']) for c in contracts]
 if broker!='FYERS':raise ValueError('INR conversion unavailable; use quantity mode')
 from .live import client,Master,choose,Reads
 from .markets import FyersInstrumentMaster
 raw=client(owner)
 try:
  api=Reads(raw)
  if config['execution_route']=='DIRECT':
   contracts=[FyersInstrumentMaster(Path(data)/'preview-master'/owner)(config['underlying'])]
  else:
   master=Master(Path(data)/'preview-master'/owner)
   contracts=[dict(master(c['symbol']),symbol=c['symbol']) for c in [choose(api,master,config,s,require_reference=False)[0] for s in ('CE','PE')]]
  result=[]
  for meta in contracts:
   symbol=meta['symbol'];reply=api.depth(data={'symbol':symbol,'ohlcv_flag':'1'})
   v=(reply.get('d') or {}).get(symbol) if reply.get('s')=='ok' else None
   if not isinstance(v,dict):raise ValueError('Selected FYERS depth/LTP unavailable')
   # quotes.tt is a session/date timestamp, not proof of a fresh trade.
   quote=dict(ltp=v.get('ltp'),timestamp=v.get('ltt'))
   result.append(dict(from_quote(config,symbol,meta,quote,data),symbol=symbol))
  return result
 finally:raw._sector_pulse_ipv4_session.close()
