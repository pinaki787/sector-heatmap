from copy import deepcopy
from types import SimpleNamespace
import threading
from pathlib import Path
import unittest
from sector_heatmap.holdings_trailing import HoldingTrails,interval
from sector_heatmap.file_lock import unlock_file
from tests.test_holdings_actions import ActionTests
from tests.test_holdings_analysis import NOW
import os

class TrailingTests(ActionTests):
 def setUp(self):
  super().setUp()
  self.queued=[];self.updates=[]
  self.store=SimpleNamespace(shutdown=threading.Event(),futures={},list=lambda owner,limit:[],
    _update=lambda *args,**kwargs:self.updates.append((args,kwargs)),
    submit=lambda owner,kind,feature,label,request,work,key:self.queue(work))
  self.trails=HoldingTrails(self.execution,self.service,self.store,clock=lambda:NOW)
 def queue(self,work):
  self.queued.append(work);return {'job_id':'job','status':'QUEUED'}
 def state(self):
  plan=self.service.prepare(self.report,self.row,{})
  ticket=plan['ticket'];stop=dict(order_id='order1',ticket=deepcopy(ticket),correlation_id='owned')
  self.books['/forever/orders']=[dict(ticket,orderId='order1',orderStatus='CONFIRM',orderType='SINGLE',correlationId='owned')]
  state=dict(monitor_id='TRAIL-'+'A'*16,owner='user:aid',account_id='aid',symbol=self.row['symbol'],security_id='42',exchange_segment='NSE_EQ',quantity=10,
    interval_minutes=30,status='MONITORING',running=True,stop_requested=False,pending=None,managed_stop=stop)
  self.trails.save(state)
  return state,plan
 def test_interval_choices_and_preview_do_not_create_orders(self):
  for value in (0,15,90,True,'30'):
   with self.assertRaises(ValueError):interval(value)
  for value in (30,60):
   p=self.trails.preview('user:aid',self.report,self.row,{'interval_minutes':value})
   self.assertEqual(p['interval_minutes'],value);self.assertIn('ENABLE TRAILING',p['confirmation_phrase'])
  self.assertFalse(self.posts);self.assertFalse(self.queued)
 def test_enable_requires_exact_consent_and_remains_auditable(self):
  p=self.trails.preview('user:aid',self.report,self.row,{})
  with self.assertRaises(ValueError):self.trails.enable('user:aid',p['preview_id'],p['confirmation_phrase'],False)
  with self.assertRaises(ValueError):self.trails.enable('user:aid',p['preview_id'],'wrong',True)
  with self.assertRaises(ValueError):self.trails.enable('other:aid',p['preview_id'],p['confirmation_phrase'],True)
  result=self.trails.enable('user:aid',p['preview_id'],p['confirmation_phrase'],True)
  self.assertEqual(result['status'],'QUEUED');self.assertFalse(self.posts)
  ctx=SimpleNamespace(cancelled=lambda:True,job_id='job',checkpoint=lambda *a:None)
  self.queued[0](ctx)
  saved=self.trails.load('user:aid',result['monitor_id'])
  self.assertFalse(saved['running']);self.assertEqual(saved['status'],'STOPPED')
 def test_monotonic_stop_no_change_or_weakening(self):
  state,plan=self.state();plan['ticket']['triggerPrice']=90
  self.assertFalse(self.trails.transmit(state,plan));self.assertFalse(self.posts)
  self.assertEqual(state['managed_stop']['ticket']['triggerPrice'],95)
 def test_upward_modification_exact_reconciliation(self):
  state,plan=self.state();plan['ticket'].update(triggerPrice=96,price=95.5)
  original=self.execution._client().request
  def request(method,path,payload=None):
   if method=='PUT':
    self.posts.append((method,path,payload))
    self.books['/forever/orders'][0].update(triggerPrice=payload['triggerPrice'],price=payload['price'])
    return {'orderId':'order1','orderStatus':'CONFIRM'}
   return original(method,path,payload)
  self.execution._client().request=request
  self.assertTrue(self.trails.transmit(state,plan))
  self.assertEqual(state['managed_stop']['ticket']['triggerPrice'],96);self.assertIsNone(state['pending'])
  self.assertEqual(self.posts[0][0],'PUT');self.assertEqual(self.posts[0][2]['legName'],'TARGET_LEG')
 def test_uncertain_modification_is_not_retried(self):
  state,plan=self.state();plan['ticket'].update(triggerPrice=96,price=95.5)
  original=self.execution._client().request
  def request(method,path,payload=None):
   if method=='PUT':self.posts.append((method,path,payload));raise RuntimeError('timeout')
   return original(method,path,payload)
  self.execution._client().request=request
  with self.assertRaises(RuntimeError):self.trails.transmit(state,plan)
  self.assertTrue(state['pending'])
  with self.assertRaisesRegex(ValueError,'uncertain'):self.trails.transmit(state,plan)
  self.assertEqual(len(self.posts),1)
 def test_external_stop_change_is_rejected_by_managed_plan(self):
  state,plan=self.state();self.books['/forever/orders'][0]['triggerPrice']=96
  with self.assertRaisesRegex(ValueError,'changed externally'):
   self.service._plan(self.report,self.row,{},state['managed_stop'],self.trails.path(state['monitor_id']))
 def test_duplicate_instrument_lock_and_stop_signal_survive_worker_save(self):
  state,plan=self.state();fd=self.trails.lock('42','NSE_EQ')
  try:
   with self.assertRaises(ValueError):self.trails.lock('42','NSE_EQ')
   stopped=self.trails.stop('user:aid',state['monitor_id']);self.assertTrue(stopped['stop_requested'])
   self.trails.save(state)
   self.assertTrue(self.trails.load('user:aid',state['monitor_id'])['stop_requested'])
   self.assertFalse(self.trails.transmit(state,plan));self.assertFalse(self.posts)
  finally:unlock_file(fd);os.close(fd)
 def test_orphan_is_interrupted_and_never_rearmed(self):
  state,plan=self.state();records=self.trails.list('user:aid')
  self.assertEqual(records[0]['status'],'INTERRUPTED');self.assertFalse(records[0]['running'])
  self.assertFalse(self.posts);self.assertFalse(self.queued)
  with self.assertRaises(PermissionError):self.trails.load('other:aid',state['monitor_id'])

 def test_fake_activation_creates_once_then_stops_without_cancelling_protection(self):
  p=self.trails.preview('user:aid',self.report,self.row,{'interval_minutes':60})
  original=self.execution._client().request
  def request(method,path,payload=None):
   if method=='POST':
    self.posts.append((method,path,payload))
    self.books['/forever/orders']=[dict(payload,orderId='order1',orderStatus='CONFIRM')]
    return {'orderId':'order1','orderStatus':'CONFIRM'}
   return original(method,path,payload)
  self.execution._client().request=request
  result=self.trails.enable('user:aid',p['preview_id'],p['confirmation_phrase'],True)
  count=[0];outputs=[]
  def cancelled():
   count[0]+=1
   return count[0]>1
  ctx=SimpleNamespace(cancelled=cancelled,job_id='job',checkpoint=lambda message,output:outputs.append(output))
  self.queued[0](ctx)
  saved=self.trails.load('user:aid',result['monitor_id'])
  self.assertFalse(saved['running']);self.assertEqual(saved['status'],'STOPPED')
  self.assertEqual(saved['managed_stop']['order_id'],'order1')
  self.assertEqual(outputs[0]['next_check_at'],NOW+3600)
  self.assertEqual([x[0] for x in self.posts],['POST'])
  # Explicitly reviewed re-enable adopts the exact retained stop, not another entry/stop.
  resumed=self.trails.preview('user:aid',self.report,self.row,{})
  self.assertTrue(resumed['existing_stop'])
  self.assertEqual(len(self.posts),1)

 def test_closed_exchange_retains_exact_broker_stop_without_modification(self):
  from unittest.mock import patch
  state,plan=self.state()
  self.execution._client().request=lambda *args,**kwargs: (_ for _ in ()).throw(AssertionError('Closed-session broker request'))
  with patch('sector_heatmap.holdings_trailing.window',return_value={'open':False,'next_open':NOW+3600}):
   self.trails.check(state)
  self.assertFalse(self.posts)
  self.assertIn('Exchange closed',state['message'])
  self.assertEqual(state['managed_stop']['ticket']['triggerPrice'],95)

 def test_hourly_default_and_interval_change_survives_worker_save(self):
  p=self.trails.preview('user:aid',self.report,self.row,{})
  self.assertEqual(p['interval_minutes'],60)
  state,plan=self.state()
  changed=self.trails.change_interval('user:aid',state['monitor_id'],60)
  self.assertEqual(changed['next_check_at'],NOW+3600)
  self.trails.save(state)
  saved=self.trails.load('user:aid',state['monitor_id'])
  self.assertEqual(saved['interval_minutes'],60)
  self.assertEqual(saved['next_check_at'],NOW+3600)
  with self.assertRaises(ValueError):self.trails.change_interval('user:aid',state['monitor_id'],15)
  with self.assertRaises(PermissionError):self.trails.change_interval('other:aid',state['monitor_id'],30)
  self.assertFalse(self.posts)
