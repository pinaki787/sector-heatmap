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
  ident=secrets.token_urlsafe(24);ticket=dict(ticket_id=ident,broker=broker,text=text,parsed=parsed,mapping=mapping,expires_at=self.clock()+120,queue_id=queue['id'] if queue else None,revision=queue['revision'] if queue else None)
  self.tickets[ident]=deepcopy(ticket);self.tickets={k:v for k,v in self.tickets.items() if v['expires_at']>=self.clock()};return ticket
 def submit(self,p,automatic=False):
  t=self.tickets.get(p.get('ticket_id'))
  if not t or t['expires_at']<self.clock():raise ValueError('Parse a fresh recommendation before submitting.')
  if t['broker']!=p.get('broker') or t['text']!=p.get('text'):raise ValueError('Broker or message changed. Parse again.')
  if t['mapping']['status']!='EXACT':raise ValueError('An exact listed contract is required.')
  if t.get('queue_id'):self.polling.snapshot(t['queue_id'],t['revision'])
  if p.get('mode')!='CONFIRMATION' and not automatic:raise ValueError('Auto submission runs only from explicitly started channel polling.')
  symbol=t['mapping']['contract']['symbol'];entry_mode=p.get('entry_mode',t['parsed']['entry_instruction'])
  terms=dict(text=t['text'],symbol=symbol,submission_id=p.get('submission_id'),lots=p.get('quantity'),entry_mode=entry_mode,trigger_price=p.get('trigger_price'),limit_price=p.get('limit_price'),protect_after_fill=False)
  def finish(result):
   result=dict(result,broker=t['broker']);t['result']=result
   if t.get('queue_id'):
    with self.polling.lock:
     row=next(r for r in self.polling.data['queue'] if r['id']==t['queue_id']);row.update(result=result,state='BROKER_RESPONSE' if not result.get('error') else 'REJECTED');self.polling.save()
   return result
  if t['broker']=='FYERS':
   if t.get('queue_id'):self.polling.reserve(t['queue_id'],t['revision'],p.get('submission_id'))
   return finish(self.fyers_submit(terms))
  if entry_mode not in ('LIMIT','STOP_LIMIT'):raise ValueError('Choose Limit or Stop-limit.')
  try:
   qty=float(p.get('quantity'));price=float(p.get('limit_price'))
  except (ValueError,TypeError):raise ValueError('Enter positive whole contracts and a tick-aligned limit price.') from None
  if not math.isfinite(qty) or qty<1 or qty!=int(qty) or not math.isfinite(price) or price<=0:raise ValueError('Enter positive whole contracts and a tick-aligned limit price.')
  # No strategy signal or RSI monitor is attached to a discretionary parser entry.
  payload=dict(mode='LIVE',symbol=symbol,contracts=int(qty),side='buy' if t['parsed']['action']=='BUY' else 'sell',order_type='limit_order',limit_price=str(p['limit_price']),time_in_force='gtc' if entry_mode=='STOP_LIMIT' else 'ioc',reduce_only=False,request_id=p.get('submission_id'),strategy='TELEGRAM_DISCRETIONARY',execution_reason='TELEGRAM_EXPLICIT_SUBMIT')
  if entry_mode=='STOP_LIMIT':payload['telegram_stop_price']=p.get('trigger_price')
  def send():
   if t.get('queue_id'):self.polling.reserve(t['queue_id'],t['revision'],p.get('submission_id'))
   return self.delta.submit_discretionary(payload)
  return finish(self.guard.submit(str(p.get('submission_id') or ''),dict(p),send))

 def auto(self,row,execution):
  if not re.search(r'\b(BUY|SELL|SHORT)\b',row['text'].upper()):raise ValueError('Auto requires an explicit BUY, SELL or SHORT recommendation.')
  ticket=self.parse(dict(text=row['text'],queue_id=row['id'],revision=row['revision'],broker=execution['broker']))
  if ticket['mapping']['status']!='EXACT':raise ValueError(ticket['mapping'].get('message','Exact contract required.'))
  parsed=ticket['parsed'];entry=parsed.get('entry');tick=float(ticket['mapping']['contract']['tick_size'])
  if parsed.get('missing') or entry is None:raise ValueError('Actionable recommendation requires entry, stop and target evidence.')
  entry_mode=parsed['entry_instruction'];limit=entry+(tick if parsed['action']=='BUY' else -tick) if entry_mode=='STOP_LIMIT' else entry
  return self.submit(dict(ticket_id=ticket['ticket_id'],broker=ticket['broker'],text=ticket['text'],mode='AUTO',quantity=execution['quantity'],entry_mode=entry_mode,trigger_price=entry,limit_price=format(limit,'.10g'),submission_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'telegram:'+row['id']))),automatic=True)

 def reconcile(self,p):
  with self.polling.lock:
   row=next((r for r in self.polling.data['queue'] if r['id']==p.get('queue_id')),None)
   if not row or not row.get('result'):raise ValueError('No attributed broker response exists for this queued message; inspect the broker orderbook.')
   result=row['result']
   if result.get('broker')=='DELTA_INDIA':fresh=self.delta.reconcile(dict(request_id=result['request_id']))
   elif result.get('broker')=='FYERS' and self.fyers_reconcile:fresh=self.fyers_reconcile(result)
   else:raise ValueError('Broker reconciliation unavailable.')
   row['result']=dict(fresh,broker=result['broker']);row['state']='RECONCILED_BROKER_SNAPSHOT';self.polling.save();return row['result']
