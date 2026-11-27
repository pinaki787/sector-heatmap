import copy,json,tempfile,unittest
from pathlib import Path
from strategies.nifty_ai_options.delta_closed_recovery import build
from strategies.nifty_ai_options.trade_journal import sync_account,report

def fixture():
 position=dict(symbol='PAXGUSD',product_id=123006,side='LONG',execution_route='DIRECT',underlying='PAXGUSD',quantity_multiplier=.001,entry_timestamp=10)
 pending=dict(key='owned',native_request_id='owned',intent=dict(action='OPEN_LONG',timestamp=10,position=position))
 native=dict(account_identity='owner',request_id='owned',symbol='PAXGUSD',request=dict(size=10,product_id=123006,side='buy',reduce_only=False,order_type='market_order',time_in_force='ioc'),order_id=1,client_order_id='owned-client',status='closed',filled_contracts=10,average_fill_price='3566.3')
 first=dict(id=1,product_id=123006,client_order_id='owned-client',side='buy',state='closed',size=10,unfilled_size=0,order_type='market_order',reduce_only=False,average_fill_price='3566.3',created_at='2026-11-27T00:00:00Z')
 second=dict(id=2,product_id=123006,side='sell',state='closed',size=10,unfilled_size=0,reduce_only=True,average_fill_price='3616.7',created_at='2026-11-27T01:00:00Z')
 fills=[dict(id='fill1',order_id=1,product_id=123006,side='buy',size=10,price='3566.3',created_at=first['created_at']),dict(id='fill2',order_id=2,product_id=123006,side='sell',size=10,price='3616.7',created_at=second['created_at'])]
 inventory=lambda rows:dict(success=True,result=rows,meta=dict(after=None))
 evidence=dict(checked_at=100,positions=dict(success=True,result=dict(size=0)),open_orders=inventory([]),orders=inventory([first,second]),fills=inventory(fills))
 return pending,native,evidence

class ClosedRecovery(unittest.TestCase):
 def test_exact_owned_fill_and_external_close_are_recovered(self):
  p,n,e=fixture();r=build(p,n,e,'owner',now=100)
  self.assertEqual((r['entry_order'],r['exit_order']),('1','2'))
  self.assertEqual(r['orders_submitted'],0)
  self.assertEqual(r['records'][1]['action']['reason'],'EXTERNAL_BROKER_REDUCE_ONLY_CLOSE')
  self.assertNotIn('total_costs',r['records'][0]['result'])
 def test_uncertain_partial_conflicting_or_unowned_evidence_remains_blocked(self):
  for mutation in [
   lambda p,n,e:n.update(account_identity='other'),
   lambda p,n,e:n.update(status='UNKNOWN'),
   lambda p,n,e:n.update(filled_contracts=5),
   lambda p,n,e:e['orders']['result'][0].update(client_order_id='other'),
   lambda p,n,e:e['orders']['result'][0].update(average_fill_price='3567'),
   lambda p,n,e:e['positions']['result'].update(size=10),
   lambda p,n,e:e['open_orders']['result'].append(dict(product_id=123006)),
   lambda p,n,e:e['orders']['meta'].update(after='next'),
   lambda p,n,e:e['orders']['result'].append(dict(e['orders']['result'][1],id=3)),
   lambda p,n,e:e['orders']['result'][1].update(reduce_only=False),
   lambda p,n,e:e['fills']['result'][0].update(size=5),
   lambda p,n,e:e.update(checked_at=60),
  ]:
   p,n,e=fixture();mutation(p,n,e)
   with self.assertRaises(ValueError):build(p,n,e,'owner',now=100)
 def test_replayed_recovery_creates_one_closed_trade_with_real_multiplier_and_unknown_net(self):
  p,n,e=fixture();r=build(p,n,e,'owner',now=100)
  with tempfile.TemporaryDirectory() as directory:
   data=Path(directory);owner='a'*32;run=data/'runs'/owner/'run';run.mkdir(parents=True)
   (run/'config.json').write_text(json.dumps(dict(account=owner,broker='DELTA_INDIA',execution_mode='LIVE',underlying='PAXGUSD')))
   (run/'events.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in r['records']*2))
   sync_account(owner,data);sync_account(owner,data)
   result=report(owner,'run',data)
   self.assertEqual(result['total'],1);row=result['rows'][0]
   self.assertEqual(row['status'],'CLOSED');self.assertAlmostEqual(row['gross_profit'],.504)
   self.assertIsNone(row['net_profit']);self.assertIsNone(row['costs'])
   self.assertEqual(row['entry_order'],'1');self.assertEqual(row['exit_order'],'2')
   self.assertEqual(row['quantity'],10);self.assertEqual(row['multiplier'],.001)

class ApplyRecovery(unittest.TestCase):
 def test_apply_preserves_seen_audit_and_is_idempotent(self):
  from types import SimpleNamespace
  from strategies.nifty_ai_options.delta_closed_recovery import apply
  p,n,e=fixture();receipt=build(p,n,e,'owner',now=100)
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp)/'run';directory.mkdir()
   state=dict(position=None,pending=p,seen=['owned'],reconciled_intents=[])
   executor=SimpleNamespace(live=True,management_only=True,owner='a'*32,state=state,save=lambda:None)
   config=dict(account='a'*32,broker='DELTA_INDIA',execution_mode='LIVE',runtime_session='session')
   apply(executor,directory,receipt,config);before=(directory/'events.jsonl').read_bytes()
   apply(executor,directory,receipt,config)
   self.assertEqual((directory/'events.jsonl').read_bytes(),before)
   self.assertEqual(state['seen'],['owned']);self.assertIsNone(state['pending'])
   self.assertEqual(len(state['reconciled_intents']),1)
   self.assertEqual(json.loads((directory/'reconciliation.json').read_text())['phase'],'RECOVERED_CLOSED')
 def test_changed_intent_never_clears_pending(self):
  from types import SimpleNamespace
  from strategies.nifty_ai_options.delta_closed_recovery import apply
  p,n,e=fixture();receipt=build(p,n,e,'owner',now=100)
  state=dict(position=None,pending=dict(key='another'),seen=[])
  executor=SimpleNamespace(live=True,management_only=True,owner='a'*32,state=state,save=lambda:None)
  with tempfile.TemporaryDirectory() as tmp,self.assertRaises(ValueError):
   apply(executor,tmp,receipt,dict(account='a'*32,broker='DELTA_INDIA',execution_mode='LIVE'))
  self.assertEqual(state['pending']['key'],'another')

class SubsequentExternalHolding(unittest.TestCase):
 def test_later_manual_entry_is_preserved_and_not_assumed_owned(self):
  p,n,e=fixture()
  e['orders']['result'].append(dict(id=3,product_id=123006,side='buy',state='closed',size=50,unfilled_size=0,reduce_only=False,average_fill_price='3620.7',created_at='2026-11-27T02:00:00Z'))
  e['fills']['result'].append(dict(id='new-fill',order_id=3,product_id=123006,side='buy',size=50,price='3620.7',created_at='2026-11-27T02:00:00Z'))
  e['positions']['result']=dict(size=50,entry_price='3620.7')
  r=build(p,n,e,'owner',now=100)
  self.assertFalse(r['broker_flat']);self.assertEqual(r['external_position']['quantity'],50)
  self.assertFalse(r['external_position']['managed'])
  self.assertEqual([x['result']['order_id'] for x in r['records']],['1','2'])
  e['positions']['result']['size']=49
  with self.assertRaises(ValueError):build(p,n,e,'owner',now=100)
