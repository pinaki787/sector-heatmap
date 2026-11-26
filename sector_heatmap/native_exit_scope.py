"""Narrow trusted exception for an independently retiring bought-option exit.

Only the owning executor supplies this in-process context. It does not permit
submission, retry, account changes, or ignoring unrelated/manual intents.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
_SCOPE=ContextVar('ai_native_closing_exits',default=None)

@contextmanager
def closing_exits(native,state):
 allowed={}
 for slot in state.get('closing_legs',{}).values():
  pending=slot.get('pending') or {};intent=pending.get('intent') or {}
  owned=slot.get('original_position') or slot.get('position') or {}
  position=intent.get('position') or {};payload=pending.get('payload') or {}
  key=pending.get('key')
  if (not isinstance(key,str) or not key or intent.get('action')!='SELL'
      or owned.get('side') not in ('CE','PE') or not owned.get('order_id')
      or position.get('symbol')!=owned.get('symbol') or payload.get('symbol')!=owned.get('symbol')
      or payload.get('side')!=-1 or payload.get('orderTag')!=key
      or not isinstance(owned.get('quantity'),int) or owned['quantity']<=0
      or payload.get('qty')!=owned['quantity']):continue
  allowed[key]=deepcopy(payload)
 token=_SCOPE.set((native,allowed))
 try:yield
 finally:_SCOPE.reset(token)

def managed_closing_exit(native,tag,order,*,dhan_ticket=False):
 scope=_SCOPE.get()
 if not scope or scope[0] is not native:return False
 expected=scope[1].get(tag)
 if not expected or not isinstance(order,dict):return False
 if dhan_ticket:
  symbol=str(order.get('exchangeSegment'))+':'+str(order.get('securityId'))
  return (order.get('correlationId')==tag and order.get('transactionType')=='SELL'
          and symbol==expected['symbol'] and order.get('quantity')==expected['qty']
          and order.get('productType')==expected['productType'])
 return (order.get('orderTag')==tag and order.get('side')==-1
         and all(order.get(k)==expected.get(k) for k in ('symbol','qty','productType','type','limitPrice','validity')))
