"""Separate broker-selected recommendation tickets; execution only on explicit submit."""
import math,re,secrets,time,uuid
from copy import deepcopy

class TelegramParser:
 def __init__(self,parse,fyers_preview,fyers_submit,delta,guard,polling,clock=time.time):
  self.parse_text=parse;self.fyers_preview=fyers_preview;self.fyers_submit=fyers_submit;self.delta=delta;self.guard=guard;self.polling=polling;self.clock=clock;self.tickets={};self.fyers_reconcile=None
 def parse(self,p):
  broker=p.get('broker')
  if broker not in ('FYERS','DELTA_INDIA'):raise ValueError('Select FYERS or Delta Exchange India.')
  text=str(p.get('text') or '').strip();queue=None
  if p.get('queue_id'):
   queue=self.polling.snapshot(p['queue_id'],p.get('revision'));text=queue['text']
  parsed=self.parse_text(text)
  if broker=='FYERS':result=self.fyers_preview(dict(text=text));mapping=result['mapping']
  else:
   rows=self.delta.catalog()['instruments'];normalized=text.upper()
   matches=[r for r in rows if re.search(r'(?<![A-Z0-9_-])'+re.escape(r['symbol'])+r'(?![A-Z0-9_-])',normalized)]
   if len(matches)==1:
    product=matches[0];mapping=dict(status='EXACT',contract=dict(symbol=product['symbol'],description=product['contract_type'],lot_size=1,tick_size=product['tick_size'],contract_value=product['contract_value'],quote_currency=product['quoting_currency']))
   else:mapping=dict(status='UNRESOLVED',message='Include one exact listed Delta symbol, such as ETHUSD. Option expiry and strike must be explicit; no automatic ATM mapping.')
  ident=secrets.token_urlsafe(24);ticket=dict(ticket_id=ident,broker=broker,text=text,parsed=parsed,mapping=mapping,expires_at=self.clock()+120,queue_id=queue['id'] if queue else None,revision=queue['revision'] if queue else None,connection_route=getattr(self.polling,'route','BOT'))
  self.tickets[ident]=deepcopy(ticket);self.tickets={k:v for k,v in self.tickets.items() if v['expires_at']>=self.clock()};return ticket
 def submit(self,p,automatic=False):
  raise ValueError('Legacy native Telegram submission is retired. Use the unified execution settings and reviewed Paper/Live entry.')
 def auto(self,row,execution):
  raise ValueError('Legacy Bot Auto is retired. Connect reception and explicitly run the unified Paper/Live executor.')

 def reconcile(self,p):
  with self.polling.lock:
   row=next((r for r in self.polling.data['queue'] if r['id']==p.get('queue_id')),None)
   if not row or not row.get('result'):raise ValueError('No attributed broker response exists for this queued message; inspect the broker orderbook.')
   result=row['result']
   if result.get('broker')=='DELTA_INDIA':fresh=self.delta.reconcile(dict(request_id=result['request_id']))
   elif result.get('broker')=='FYERS' and self.fyers_reconcile:fresh=self.fyers_reconcile(result)
   else:raise ValueError('Broker reconciliation unavailable.')
   row['result']=dict(fresh,broker=result['broker']);row['state']='RECONCILED_BROKER_SNAPSHOT';self.polling.save();return row['result']
