import copy,unittest
from sector_heatmap.native_exit_scope import closing_exits,managed_closing_exit
class NativeExitScopeTests(unittest.TestCase):
 def fixture(self):
  payload=dict(symbol='BSE_FNO:123',qty=20,side=-1,orderTag='owned-close',productType='MARGIN',type=1,limitPrice=50,validity='IOC')
  owned=dict(symbol=payload['symbol'],side='CE',quantity=20,order_id='confirmed-entry')
  state=dict(closing_legs={'call':dict(original_position=owned,position=owned,pending=dict(key='owned-close',intent=dict(action='SELL',position=owned),payload=payload))})
  return object(),state,payload
 def test_only_exact_owned_exit_in_current_executor_scope_is_allowed(self):
  native,state,payload=self.fixture()
  self.assertFalse(managed_closing_exit(native,'owned-close',payload))
  with closing_exits(native,state):
   self.assertTrue(managed_closing_exit(native,'owned-close',payload))
   self.assertFalse(managed_closing_exit(object(),'owned-close',payload))
   for change in [dict(symbol='BSE_FNO:124'),dict(side=1),dict(qty=40),dict(productType='INTRADAY'),dict(orderTag='other')]:
    self.assertFalse(managed_closing_exit(native,'owned-close',dict(payload,**change)))
  self.assertFalse(managed_closing_exit(native,'owned-close',payload))
 def test_missing_ownership_entry_order_or_non_option_exit_remains_blocked(self):
  for changes in [dict(order_id=None),dict(side='LONG'),dict(quantity=0)]:
   native,state,payload=self.fixture();state['closing_legs']['call']['original_position']=dict(state['closing_legs']['call']['original_position'],**changes)
   with closing_exits(native,state):self.assertFalse(managed_closing_exit(native,'owned-close',payload))
 def test_dhan_ticket_requires_exact_tag_contract_quantity_and_sell(self):
  native,state,payload=self.fixture()
  ticket=dict(exchangeSegment='BSE_FNO',securityId='123',transactionType='SELL',quantity=20,productType='MARGIN',correlationId='owned-close')
  with closing_exits(native,state):
   self.assertTrue(managed_closing_exit(native,'owned-close',ticket,dhan_ticket=True))
   self.assertFalse(managed_closing_exit(native,'unrelated',ticket,dhan_ticket=True))
   self.assertFalse(managed_closing_exit(native,'owned-close',dict(ticket,transactionType='BUY'),dhan_ticket=True))
 def test_nested_context_restores_prior_scope_and_cannot_use_another_account(self):
  a,state,payload=self.fixture();b=object()
  with closing_exits(a,state):
   with closing_exits(b,{}):self.assertFalse(managed_closing_exit(a,'owned-close',payload))
   self.assertTrue(managed_closing_exit(a,'owned-close',payload))

class MotilalPreflightScopeTests(unittest.TestCase):
 fixture=NativeExitScopeTests.fixture
 def test_actual_motilal_preflight_allows_only_owned_retiring_leg_and_blocks_unrelated_intent(self):
  import sqlite3,json
  from contextlib import contextmanager
  from types import SimpleNamespace
  from sector_heatmap.motilal_strategy_broker import Broker
  _,state,payload=self.fixture();payload['productType']='NORMAL'
  with sqlite3.connect(':memory:') as db:
   db.execute('CREATE TABLE intents(full_tag TEXT,body TEXT,state TEXT)')
   db.execute('CREATE TABLE tickets(id TEXT,user_id TEXT,state TEXT)')
   db.execute('INSERT INTO intents VALUES(?,?,?)',('owned-close',json.dumps(payload),'ACKNOWLEDGED'))
   @contextmanager
   def database():yield db
   native=object.__new__(Broker);native.db=database
   native.validate_order=lambda order:None;native.ready=lambda:None
   native.reconcile_position=lambda symbol,qty:None;native.orders=lambda:[]
   native.contract=lambda symbol:dict(exchange='BSEFO',token=124)
   native.quote=lambda symbol:dict(ask=50,bid=49)
   native.funds=lambda exchange:100000
   native.service=SimpleNamespace(book=lambda name:dict(data=[]),tickets=SimpleNamespace(db=database))
   target=dict(symbol='MO:BSEFO:124',qty=20,side=1,productType='NORMAL',limitPrice=50)
   with self.assertRaisesRegex(ValueError,'outstanding native intent'):native.preflight(target,{})
   with closing_exits(native,state):
    native.preflight(target,{})
    db.execute('INSERT INTO intents VALUES(?,?,?)',('unrelated',json.dumps(dict(payload,orderTag='unrelated')),'UNCERTAIN'))
    with self.assertRaisesRegex(ValueError,'outstanding native intent'):native.preflight(target,{})

class DhanPreflightScopeTests(unittest.TestCase):
 fixture=NativeExitScopeTests.fixture
 def test_actual_dhan_preflight_keeps_manual_unknown_blocked_while_owned_exit_can_retire(self):
  import tempfile,json
  from pathlib import Path
  from types import SimpleNamespace
  from sector_heatmap.dhan_strategy_broker import Broker
  _,state,payload=self.fixture()
  ticket=dict(exchangeSegment='BSE_FNO',securityId='123',transactionType='SELL',quantity=20,productType='MARGIN',correlationId='owned-close')
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);journal=root/'dhan-strategy-intents';journal.mkdir()
   (journal/'owned.json').write_text(json.dumps(dict(status='UNKNOWN',ticket=ticket)))
   calls=[]
   def request(method,path,*args):
    calls.append((method,path))
    if path=='/fundlimit':return dict(dhanClientId='client',availableBalance=100000)
    if path=='/margincalculator':return dict(totalMargin=1000,availableBalance=100000)
    raise AssertionError('Unexpected endpoint')
   native=object.__new__(Broker)
   native.service=SimpleNamespace(folder=root)
   native.validate_order=lambda order:None;native.reconcile_position=lambda symbol,qty:None;native.orders=lambda:[]
   native.authenticated_client=lambda:SimpleNamespace(client_id='client',request=request)
   native.quote=lambda symbol:dict(ask=50,bid=49)
   native.contract=lambda symbol:dict(exchange_segment='BSE_FNO',security_id='124',quantity_multiplier=1)
   target=dict(symbol='BSE_FNO:124',qty=20,side=1,productType='MARGIN',limitPrice=50,validity='IOC',orderTag='new-entry')
   with self.assertRaisesRegex(ValueError,'Uncertain Dhan'):native.preflight(target,{})
   with closing_exits(native,state):
    native.preflight(target,{})
    manual=root/'dhan-orders';manual.mkdir()
    (manual/'manual.json').write_text(json.dumps(dict(status='UNKNOWN',ticket=ticket)))
    with self.assertRaisesRegex(ValueError,'Uncertain Dhan'):native.preflight(target,{})
   self.assertNotIn(('POST','/orders'),calls)
