from unittest import TestCase
from tempfile import TemporaryDirectory
from pathlib import Path
from copy import deepcopy
from sector_heatmap.parser_lifecycle import ParserLifecycle, protection_plan

class Broker:
 def __init__(self):self.account={'account':'A','orders':[],'positions':[],'gtt':[]};self.entries=[];self.exits=[];self.fail=False
 def snapshot(self):return deepcopy(self.account)
 def place_entry(self,o):
  self.entries.append(o);self.account['orders']=[{**o,'id':'ENTRY','status':6,'filledQty':0}];return {'s':'ok','id':'ENTRY'}
 def fresh_price(self,s):return 81
 def place_oco(self,o):
  self.exits.append(o)
  if self.fail:raise TimeoutError()
  id='G'+str(len(self.exits));self.account['gtt'].append({**o,'id':id,'ord_status':6});return {'s':'ok','id':id}

class LifecycleTests(TestCase):
 def setUp(self):
  self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'state.sqlite';self.b=Broker();self.enabled=True
  self.m=self.manager();self.order={'symbol':'NSE:DMART26OCT4000CE','qty':300,'side':1,'productType':'MARGIN','stopPrice':80,'limitPrice':80.05}
  self.parsed={'stop_loss':72,'targets':[85,90,100]};self.contract={'tick_size':.05,'lot_size':150}
  self.plan=protection_plan(self.parsed,self.contract,self.order,85)
  self.ticket={'preview_id':'P1','order':self.order,'protection':self.plan}
 def manager(self):
  m=ParserLifecycle(self.path,self.b,lambda:self.enabled);self.addCleanup(m.db.close);return m
 def fill(self,qty):
  self.b.account['orders'][0].update(filledQty=qty,status=2 if qty==300 else 6)
  self.b.account['positions']=[{'symbol':self.order['symbol'],'productType':'MARGIN','netQty':qty}]
 def test_target_allocation_not_invented(self):
  with self.assertRaisesRegex(ValueError,'Choose'):protection_plan(self.parsed,self.contract,self.order)
  self.assertEqual(self.plan['targets'],[85,90,100])
 def test_trigger_not_fill_and_idempotent_entry(self):
  self.m.submit_entry(self.ticket);self.m.submit_entry(self.ticket)
  self.assertEqual(len(self.b.entries),1);self.assertEqual(self.m.reconcile('P1')['status'],'WAITING_FOR_FILL');self.assertEqual(self.b.exits,[])
 def test_partial_fill_then_incremental_protection_restart(self):
  self.m.submit_entry(self.ticket);self.fill(150)
  self.assertEqual(self.m.reconcile('P1')['status'],'PROTECTION_PENDING')
  restarted=self.manager();self.assertEqual(restarted.reconcile('P1')['status'],'PROTECTED')
  self.assertEqual(len(self.b.exits),1);self.fill(300)
  restarted.reconcile('P1');self.assertEqual(len(self.b.exits),2)
  self.assertEqual([o['orderInfo']['leg1']['qty'] for o in self.b.exits],[150,150])
  self.assertEqual(restarted.reconcile('P1')['protected_quantity'],300)
 def test_uncertain_exit_never_retried_after_restart(self):
  self.m.submit_entry(self.ticket);self.fill(150);self.b.fail=True
  self.m.reconcile('P1');restarted=self.manager();restarted.reconcile('P1');restarted.reconcile('P1')
  self.assertEqual(len(self.b.exits),1)
 def test_foreign_position_and_account_stop_management(self):
  self.m.submit_entry(self.ticket);self.fill(150);self.b.account['positions'][0]['netQty']=300
  self.assertEqual(self.m.reconcile('P1')['status'],'RECONCILIATION_REQUIRED');self.assertEqual(self.b.exits,[])
  self.fill(150);self.b.account['account']='B';self.m.reconcile('P1');self.assertEqual(self.b.exits,[])
 def test_disabled_and_nonlot_partial_fill_fail_closed(self):
  self.enabled=False
  with self.assertRaises(ValueError):self.m.submit_entry(self.ticket)
  self.enabled=True;self.m.submit_entry(self.ticket);self.fill(10);self.m.reconcile('P1');self.assertEqual(self.b.exits,[])
 def test_closed_or_changed_oco_never_certified_protected(self):
  self.m.submit_entry(self.ticket);self.fill(150);self.m.reconcile('P1')
  self.b.account['gtt'][0]['ord_status']=2
  self.assertEqual(self.m.reconcile('P1')['status'],'RECONCILIATION_REQUIRED');self.assertEqual(len(self.b.exits),1)
 def test_entry_rejected_is_not_success(self):
  self.b.place_entry=lambda o:{'s':'error','code':-50}
  self.assertEqual(self.m.submit_entry(self.ticket)['status'],'REJECTED')
 def test_entry_timeout_recovered_by_exact_tag(self):
  original=self.b.place_entry
  def uncertain(o):original(o);raise TimeoutError()
  self.b.place_entry=uncertain
  self.assertEqual(self.m.submit_entry(self.ticket)['status'],'ENTRY_SUBMISSION_UNKNOWN')
  self.assertEqual(self.manager().reconcile('P1')['status'],'WAITING_FOR_FILL')
  self.assertEqual(len(self.b.entries),1)

 def test_lost_protection_clears_previously_verified_quantity(self):
  self.m.submit_entry(self.ticket);self.fill(150);self.m.reconcile('P1')
  self.assertEqual(self.m.reconcile('P1')['protected_quantity'],150)
  self.b.account['gtt']=[]
  result=self.m.reconcile('P1')
  self.assertEqual(result['status'],'RECONCILIATION_REQUIRED')
  self.assertEqual(result['protected_quantity'],0)
  self.assertEqual(len(self.b.exits),1)
