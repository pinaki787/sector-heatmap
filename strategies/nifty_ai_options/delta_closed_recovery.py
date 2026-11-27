"""Read-only broker-evidence validation for a filled entry closed externally.
Produces idempotent journal records; never owns a client or submits an order.
Unknown, partial, ambiguous and incomplete evidence remains blocked.
"""
from decimal import Decimal
from datetime import datetime
import copy,hashlib,json,math

def value(v):
 try:r=Decimal(str(v))
 except Exception:raise ValueError('Invalid broker numeric evidence')
 if not r.is_finite():raise ValueError('Non-finite broker evidence')
 return r

def epoch(v):
 try:r=datetime.fromisoformat(str(v).replace('Z','+00:00'))
 except Exception:raise ValueError('Missing broker fill timestamp')
 if r.tzinfo is None:raise ValueError('Unzoned broker fill timestamp')
 return r.timestamp()

def complete(reply):
 if not isinstance(reply,dict) or reply.get('success') is not True or not isinstance(reply.get('result'),list):raise ValueError('Broker inventory unavailable')
 if (reply.get('meta') or {}).get('after'):raise ValueError('Broker inventory incomplete; pagination required')
 return reply['result']

def build(pending,native,evidence,account_identity,*,now):
 if not math.isfinite(now) or not 0<=now-evidence.get('checked_at',0)<=30:raise ValueError('Fresh broker evidence required')
 if not account_identity or native.get('account_identity')!=account_identity:raise ValueError('Native account identity mismatch')
 intent=copy.deepcopy(pending.get('intent') or {});action=intent.get('action');position=intent.get('position') or {}
 if action not in ('OPEN_LONG','OPEN_SHORT') or position.get('execution_route')!='DIRECT':raise ValueError('Explicit direct entry required')
 key=pending.get('native_request_id') or pending.get('key');pid=position.get('product_id');symbol=position.get('symbol')
 if native.get('request_id')!=key or native.get('symbol')!=symbol:raise ValueError('Native intent identity mismatch')
 request=native.get('request') or {};qty=value(request.get('size'));entry_side='buy' if action=='OPEN_LONG' else 'sell'
 if qty<=0 or qty!=qty.to_integral_value() or request.get('product_id')!=pid or request.get('side')!=entry_side or request.get('reduce_only') is not False:raise ValueError('Native quantity/contract/side mismatch')
 if native.get('status')!='closed' or value(native.get('filled_contracts'))!=qty:raise ValueError('Native fill is not complete')
 if request.get('order_type')!='market_order' or request.get('time_in_force')!='ioc':raise ValueError('Captured market entry terms differ')
 pos=evidence.get('positions') or {}
 if pos.get('success') is not True:raise ValueError('Broker position unavailable')
 current_quantity=value((pos.get('result') or {}).get('size'))
 if any(int(r.get('product_id',-1))==pid for r in complete(evidence['open_orders'])):raise ValueError('Active selected-contract order blocks recovery')
 orders=[r for r in complete(evidence['orders']) if r.get('product_id')==pid]
 matches=[r for r in orders if str(r.get('id'))==str(native.get('order_id'))]
 if len(matches)!=1:raise ValueError('Exact entry order unavailable or ambiguous')
 entry=matches[0]
 if not entry.get('client_order_id') or entry['client_order_id']!=native.get('client_order_id'):raise ValueError('Broker/native client-order identity mismatch')
 if entry.get('side')!=entry_side or entry.get('state')!='closed' or value(entry.get('size'))!=qty or value(entry.get('unfilled_size'))!=0 or entry.get('order_type')!='market_order' or entry.get('reduce_only') is not False:raise ValueError('Entry broker fill terms mismatch')
 # Complete selected-product history must contain precisely one subsequent fill:
 # the exact reduce-only closing order. Never infer a close from flat alone.
 later=sorted([r for r in orders if epoch(r['created_at'])>epoch(entry['created_at']) and value(r.get('size',0))-value(r.get('unfilled_size',0))>0],key=lambda r:epoch(r['created_at']))
 if len(later) not in (1,2):raise ValueError('Ambiguous subsequent broker fills')
 exit=later[0]
 if exit.get('state')!='closed' or exit.get('side')==entry_side or exit.get('reduce_only') is not True or value(exit.get('size'))!=qty or value(exit.get('unfilled_size'))!=0:raise ValueError('Exact full reduce-only close required')
 fills=[r for r in complete(evidence['fills']) if r.get('product_id')==pid]
 def fill(order,expected_qty=qty):
  rows=[r for r in fills if str(r.get('order_id'))==str(order['id'])]
  if not rows or any(not r.get('id') for r in rows) or len({str(r.get('id')) for r in rows})!=len(rows):raise ValueError('Missing or duplicate broker fill evidence')
  if any(r.get('side')!=order['side'] or value(r.get('size'))<=0 or value(r.get('price'))<=0 for r in rows):raise ValueError('Broker fill side/quantity/price invalid')
  total=sum(value(r['size']) for r in rows)
  if total!=expected_qty:raise ValueError('Partial or inconsistent broker fill quantity')
  average=sum(value(r['size'])*value(r['price']) for r in rows)/expected_qty
  if average!=value(order.get('average_fill_price')):raise ValueError('Broker fill average disagrees with order')
  return dict(order_id=str(order['id']),filled_quantity=int(expected_qty),fill_price=float(average),filled_at=max(epoch(r['created_at']) for r in rows),broker_commission=order.get('paid_commission'),costs_unavailable_reason='Full fees, funding and taxes have not been independently reconciled',dry_run=False)
 opened=fill(entry);closed=fill(exit)
 external=None
 if len(later)==2:
  extra=later[1];extra_qty=value(extra.get('size'))
  if extra.get('state')!='closed' or extra.get('reduce_only') is not False or extra.get('side') not in ('buy','sell') or extra_qty<=0 or extra_qty!=extra_qty.to_integral_value() or value(extra.get('unfilled_size'))!=0:raise ValueError('Subsequent exposure is not an independently confirmed new entry')
  extra_fill=fill(extra,extra_qty)
  expected=extra_qty*(1 if extra['side']=='buy' else -1)
  if current_quantity!=expected or value((pos.get('result') or {}).get('entry_price'))!=value(extra_fill['fill_price']) or extra_fill['filled_at']<=closed['filled_at']:raise ValueError('New external holding does not reconcile to broker position')
  external=dict(symbol=symbol,quantity=int(current_quantity),fill_price=extra_fill['fill_price'],order_id=extra_fill['order_id'],verified_at=evidence['checked_at'],managed=False)
 elif current_quantity!=0:raise ValueError('Unexplained broker exposure blocks recovery')
 if opened['fill_price']!=float(value(native.get('average_fill_price'))) or closed['filled_at']<=opened['filled_at']:raise ValueError('Native fill average or entry/exit chronology differs')
 multiplier=value(position.get('quantity_multiplier',position.get('contract_value')))
 if multiplier<=0:raise ValueError('Exact contract multiplier required')
 position['quantity_multiplier']=float(multiplier);position['quantity']=int(qty);intent['position']=position
 close_action=dict(action='CLOSE_LONG' if action=='OPEN_LONG' else 'CLOSE_SHORT',timestamp=closed['filled_at'],position=dict(position,order_id=opened['order_id'],fill_price=opened['fill_price']),reason='EXTERNAL_BROKER_REDUCE_ONLY_CLOSE')
 proof=hashlib.sha256(json.dumps([key,opened,closed],sort_keys=True).encode()).hexdigest()
 records=[dict(action=intent,result=opened),dict(action=close_action,result=closed)]
 for r in records:r.update(recorded_at=now,recovery=dict(revision='delta-closed-entry-v1',proof=proof,source='SELECTED_ACCOUNT_BROKER_ORDERS_AND_FILLS',external_exit=True))
 return dict(key=key,proof=proof,entry_order=opened['order_id'],exit_order=closed['order_id'],broker_flat=current_quantity==0,historical_pair_closed=True,external_position=external,orders_submitted=0,records=records)

def apply(executor,run_directory,receipt,config):
 """Requires the stopped executor's exclusive lock and freshly validated evidence."""
 import os
 from pathlib import Path
 from .run import atomic
 if not executor.live or not executor.management_only:raise ValueError('Stopped reconciliation executor required')
 if config.get('account')!=executor.owner or config.get('broker')!='DELTA_INDIA' or config.get('execution_mode')!='LIVE':raise ValueError('Recovery account/mode mismatch')
 state=executor.state
 prior=next((r for r in state.get('reconciled_intents',[]) if r.get('proof')==receipt['proof']),None)
 if state.get('position') or state.get('detached_position') or state.get('positions') or any(x.get('position') or x.get('pending') for x in state.get('closing_legs',{}).values()):raise ValueError('Other retained exposure blocks closed-entry recovery')
 pending=state.get('pending')
 if not pending and prior:
  path=Path(run_directory)/'reconciliation.json'
  current=json.loads(path.read_text()) if path.exists() else {}
  if current.get('phase')!='RECOVERED_CLOSED':atomic(path,dict(prior,phase='RECOVERED_CLOSED'))
  return prior
 if not pending or (pending.get('native_request_id') or pending.get('key'))!=receipt['key']:raise ValueError('Pending intent changed; recovery refused')
 if receipt.get('historical_pair_closed') is not True or receipt.get('orders_submitted')!=0 or (receipt.get('broker_flat') is not True and not receipt.get('external_position')):raise ValueError('Verified historical closure and current exposure required')
 directory=Path(run_directory)
 proof=dict(receipt,completed_at=receipt['records'][0]['recorded_at'],phase='PREPARED',account_id=executor.owner,run_id=directory.name,runtime_session=config.get('runtime_session'))
 atomic(directory/'reconciliation.json',proof)
 with (directory/'events.jsonl').open('a') as stream:
  for record in receipt['records']:stream.write(json.dumps(record,sort_keys=True)+'\n')
  stream.flush();os.fsync(stream.fileno())
 markers_path=directory/'markers.json'
 markers=json.loads(markers_path.read_text()) if markers_path.exists() else []
 for record in receipt['records']:
  action=record['action'];fill=record['result']
  if not any(str(m.get('order_id'))==fill['order_id'] and m.get('action')==action['action'] for m in markers):
   markers.append(dict(timestamp=action['timestamp'],source_timestamp=action['timestamp'],confirmed_at=fill['filled_at'],symbol=action['position']['symbol'],action=action['action'],price=fill['fill_price'],mode='LIVE',confirmed=True,order_id=fill['order_id'],recovered=True))
 atomic(markers_path,markers)
 state.setdefault('reconciled_intents',[]).append(dict(proof,phase='RECOVERED_CLOSED'))
 state['pending']=None
 executor.save()
 proof['phase']='RECOVERED_CLOSED'
 atomic(directory/'reconciliation.json',proof)
 return proof
