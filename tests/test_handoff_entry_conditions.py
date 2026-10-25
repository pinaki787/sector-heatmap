import unittest,time,tempfile,json,sqlite3
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from sector_heatmap.handoff_entry_conditions import condition,reached,stop_limit_before_trigger,order_fields
from sector_heatmap.handoff_entry_queue import Queue
from sector_heatmap.handoff_exit_monitor import Store
class EntryConditionsTests(unittest.TestCase):
 def quote(self,p=100,now=100):return dict(symbol='NSE:T-EQ',price=p,provider_at=now,received_at=now,connected=True)
 def test_direction_and_chase_bound(self):
  for direction,yes,no in [('BULLISH',100.4,99.9),('BEARISH',99.6,100.1)]:
   c=condition('NSE:T-EQ',direction,100);self.assertTrue(reached(c,self.quote(yes),100)[0]);self.assertFalse(reached(c,self.quote(no),100)[0]);self.assertFalse(reached(c,self.quote(101 if direction=='BULLISH' else 99),100)[0])
 def test_stale_disconnected_wrong_symbol_and_ambiguous_prose(self):
  c=condition('NSE:T-EQ','BULLISH',100)
  self.assertFalse(reached(c,self.quote(),106)[0]);self.assertFalse(reached(c,dict(self.quote(),connected=False),100)[0]);self.assertFalse(reached(c,dict(self.quote(),symbol='NSE:OTHER-EQ'),100)[0]);self.assertFalse(reached({'description':'buy now'},self.quote(),100)[0])
 def test_exact_cash_stop_limit_and_option_underlying_never_copied(self):
  c=condition('NSE:T-EQ','BULLISH',100);leg=dict(symbol='NSE:T-EQ',limit_price=100,tick_size=.05,action='BUY')
  self.assertTrue(stop_limit_before_trigger(c,dict(price=99),leg['symbol'],'BUY',.05,100));self.assertFalse(stop_limit_before_trigger(c,dict(price=101),leg['symbol'],'BUY',.05,100))
  p=dict(proposal={'kind':'EQUITY'},entry_condition=c,execution_entry_order={'type':'STOP_LIMIT'})
  self.assertEqual(order_fields(p,leg),dict(type=4,stopPrice=100));self.assertEqual(order_fields({},leg),dict(type=1,stopPrice=0))
  with self.assertRaises(ValueError):order_fields(p,dict(leg,symbol='NSE:T100CE'))
  with self.assertRaises(ValueError):order_fields(p,dict(leg,limit_price=99.95))
 def test_short_sell_stop_limit_constraints(self):
  c=condition('NSE:T-EQ','BEARISH',100);self.assertTrue(stop_limit_before_trigger(c,dict(price=101),c['symbol'],'SELL',.05,100));self.assertEqual(order_fields(dict(proposal={'kind':'EQUITY'},entry_condition=c,execution_entry_order={'type':'STOP_LIMIT'}),dict(symbol=c['symbol'],limit_price=100,tick_size=.05,action='SELL'))['type'],4)
 def test_queue_preserves_recommendation_and_no_submit_on_enqueue_or_restart(self):
  with tempfile.TemporaryDirectory() as t:
   q=Queue(Path(t));p=dict(fingerprint='f'*64,symbol='NSE:T100CE',kind='LONG_OPTION',entry_condition=condition('NSE:T-EQ','BULLISH',100),ticket_payload={});old=json.dumps(p)
   r=q.enqueue(p,dict(revision='r'));self.assertEqual(r['orders_submitted'],0);self.assertEqual(json.dumps(p),old);q=Queue(Path(t))
   with q.db() as d:
    state,raw=d.execute('select state,body from waits').fetchone();self.assertEqual(state,'WAITING');self.assertEqual(json.loads(raw)['condition']['level'],100)
 def test_pending_restart_uncertain_is_never_submitted(self):
  with tempfile.TemporaryDirectory() as t:
   q=Queue(Path(t));q.enqueue(dict(fingerprint='f'*64,entry_condition=condition('NSE:T-EQ','BULLISH',100),ticket_payload={}),dict(revision='r'))
   with q.db() as d:d.execute("update waits set state='PREPARING'")
   calls=[];schedule=SimpleNamespace(account_id='A',policy=lambda:{},claims=SimpleNamespace(uncertain=lambda *x:calls.append('uncertain')))
   q.process(SimpleNamespace(),schedule);self.assertEqual(calls,['uncertain'])
   with q.db() as d:self.assertEqual(d.execute('select state from waits').fetchone()[0],'UNCERTAIN')

class EntryQueueLifecycleTests(unittest.TestCase):
 def make(self,folder):
  q=Queue(folder);store=Store(folder);store.authorize('A','U');store.beat(state='IDLE',healthy=True)
  self.calls=[];self.policy=dict(enabled=True,mode='AUTO',live_authorized=True,revision='r')
  claim=SimpleNamespace(not_submitted=lambda *x:self.calls.append('release'),confirmed=lambda *x:self.calls.append('confirmed'),uncertain=lambda *x:self.calls.append('uncertain'))
  path=folder/'handoff-schedule.sqlite3'
  with sqlite3.connect(path) as d:d.execute('create table receipts(fingerprint text,state text,body text,updated real)')
  sch=SimpleNamespace(account_id='A',policy=lambda:self.policy,claims=claim,db=lambda:sqlite3.connect(path),loss_halted=lambda *a:False)
  self.plan=dict(fingerprint='f'*64,underlying='NSE:T-EQ',symbol='NSE:T100CE',kind='LONG_OPTION',direction='BULLISH',entry=10,quantity=50,tick_size=.05,entry_condition=condition('NSE:T-EQ','BULLISH',100),ticket_payload={})
  with sch.db() as d:d.execute('insert into receipts values(?,?,?,?)',(self.plan['fingerprint'],'SUBMITTING',json.dumps({'plan':self.plan}),time.time()))
  def submit(plan,policy):self.calls.append('submit');return dict(status='OPEN',protection_confirmed=True,entry_fill_price=10,protected_quantity=50)
  bridge=SimpleNamespace(identity=lambda:None,exposure=lambda p:dict(positions_verified=True,orders_verified=True,exposed_underlyings=[]),_execute_now=submit)
  return q,store,sch,bridge
 def quote(self,store,price):
  now=time.time()
  with store.db() as d:d.execute('insert or replace into quotes values(?,?)',('NSE:T-EQ',json.dumps(dict(symbol='NSE:T-EQ',price=price,provider_at=now,received_at=now,connected=True))))
 def test_option_wait_crossing_submit_once_and_no_replay_after_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   q,store,sch,b=self.make(Path(tmp));q.enqueue(self.plan,self.policy);self.quote(store,99);q.process(b,sch);self.assertEqual(self.calls,[])
   self.quote(store,100.1);q.process(b,sch);self.assertEqual(self.calls,['submit','confirmed']);Queue(Path(tmp)).process(b,sch);self.assertEqual(self.calls,['submit','confirmed'])
 def test_replacement_settings_expire_old_wait_without_submission(self):
  with tempfile.TemporaryDirectory() as tmp:
   q,store,sch,b=self.make(Path(tmp));q.enqueue(self.plan,self.policy);self.policy['revision']='new';self.quote(store,100);q.process(b,sch);self.assertEqual(self.calls,['release'])
 def test_late_entry_expires_without_submitting(self):
  with tempfile.TemporaryDirectory() as tmp:
   q,store,sch,b=self.make(Path(tmp));q.enqueue(self.plan,self.policy)
   with q.db() as d:
    key,state,raw=d.execute('select * from waits').fetchone();body=json.loads(raw);body['expires_at']=time.time()-1;d.execute('update waits set body=?',(json.dumps(body),))
   self.quote(store,100);q.process(b,sch);self.assertEqual(self.calls,['release'])
