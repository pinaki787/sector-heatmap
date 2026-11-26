"""Read-only notices from retained execution ownership, never from chart signals."""
import hashlib,json
CLOSE={'SELL','CLOSE_LONG','CLOSE_SHORT'}
FAILED={'UNCERTAIN','REJECTED_OR_UNCERTAIN','UNRESOLVED_FILL','FILLED_AWAITING_FLAT','CANCELLED_WITHOUT_FILL','PARTIAL_EXIT_REMAINS','EXIT_PRECHECK_FAILED'}

def notices(state):
 if not isinstance(state,dict):return []
 slots=[state]
 closing=state.get('closing_legs') or {}
 slots.extend(closing.values() if isinstance(closing,dict) else closing if isinstance(closing,list) else [])
 result=[]
 for slot in slots:
  if not isinstance(slot,dict):continue
  pending=slot.get('pending') or (slot.get('retained_exit_failure') if slot.get('position') else None)
  if not isinstance(pending,dict):continue
  intent=pending.get('intent') or {}
  if intent.get('action') not in CLOSE:continue
  position=slot.get('position') or slot.get('stop_verification_position') or intent.get('position') or {}
  symbol=position.get('symbol');qty=position.get('quantity')
  if not isinstance(symbol,str) or not symbol:continue
  if isinstance(qty,bool) or not isinstance(qty,int) or qty<=0:qty=None
  stage=pending.get('stage','UNCONFIRMED');filled=pending.get('filled_quantity')
  if isinstance(filled,bool) or not isinstance(filled,int) or filled<0:filled=None
  identity=hashlib.sha256(json.dumps([symbol,pending.get('key'),pending.get('order_id'),intent.get('timestamp')],sort_keys=True).encode()).hexdigest()[:24]
  result.append(dict(id=identity,symbol=symbol,recorded_quantity=qty,confirmed_filled_quantity=filled,
   remaining_quantity=None,phase='EXIT_REQUIRES_RECONCILIATION' if stage in FAILED else 'EXIT_PENDING',
   severity='error' if stage in FAILED else 'warning',order_id=pending.get('order_id'),
   message='Exit is not confirmed. Check this contract’s broker orders and remaining position before closing it manually.',
   quantity_basis='Recorded strategy ownership; current broker quantity requires reconciliation',
   automatic_resubmission=False))
 return result
