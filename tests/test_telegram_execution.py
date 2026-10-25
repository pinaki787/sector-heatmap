import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from sector_heatmap.telegram_execution import ExecutionPipeline,action_routes

class UnifiedExecutionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'execution.json';self.now=1000
  self.poll=Mock();self.poll.route='SUBSCRIBER';self.poll.running.return_value=True;self.poll.verified={'channel_id':-100123456};self.poll.lock=threading.RLock();self.poll.data={'queue':[]}
  self.t=Mock();self.t.preview.side_effect=self.ticket
  self.t.submit.side_effect=lambda p:dict(status='RENKO_CONFIRMED_POSITION',mode=p['mode'],position={'symbol':'C-ETH-100','quantity':p['quantity'],'entry_price':2},management_owner='RENKO_SUPERTREND')
  self.gate=Mock()
  self.p=self.make()
 def make(self,broker='DELTA_INDIA',path=None):
  with patch.dict('os.environ',{'SECTOR_PULSE_WORKSPACE_BROKER':broker}):return ExecutionPipeline(self.t,self.poll,path or self.path,lambda:self.now,guard=self.gate)
 def ticket(self,p):
  if not any(x in p['text'] for x in ('BUY','SELL')):raise ValueError('No recommendation.')
  return dict(ticket_id='ticket-'+str(self.t.preview.call_count),text=p['text'],expires_at=self.now+120,revision=p.get('revision'),contract={'symbol':'C-ETH-100','quantity_multiplier':.01},quote={'ask':2,'bid':1.9})
 def start(self,**kw):
  p={**dict(mode='PAPER',quantity=7,config_revision=self.p.revision),**kw}
  with patch('sector_heatmap.telegram_execution.threading.Thread'):return self.p.start(p)
 def row(self,id='1',text='ETHUSD BUY ABOVE 100',**kw):
  row={**dict(id=id,revision=id,text=text,timestamp=self.now,state='REVIEW'),**kw};self.poll.data['queue'].append(row);return row
 def preview(self,text='ETHUSD BUY ABOVE 100',**kw):return self.p.preview(dict(text=text,config_revision=self.p.revision,**kw))
 def manual(self,ticket,**kw):return self.p.submit_manual(dict(ticket_id=ticket['ticket_id'],text=ticket['text'],config_revision=self.p.revision,entry_confirmed=True,**kw))
 def test_paper_automatic_mode_and_quantity_are_exact_and_no_legacy_broker_calls(self):
  self.start();self.row();self.p.step()
  sent=self.t.submit.call_args.args[0];self.assertEqual((sent['mode'],sent['quantity']),('PAPER',7));self.t.delta.submit_discretionary.assert_not_called()
 def test_live_automatic_requires_consent_then_dispatches_only_live_under_mock(self):
  with self.assertRaisesRegex(ValueError,'authorize Live'):self.start(mode='LIVE')
  self.t.submit.assert_not_called();self.poll.start.assert_not_called()
  self.start(mode='LIVE',live_confirmed=True);self.row();self.p.step()
  self.assertEqual(self.t.submit.call_args.args[0]['mode'],'LIVE');self.assertTrue(self.p.status()['live_auto'])
 def test_paper_paste_uses_same_saved_quantity_and_cannot_override_live(self):
  self.p.configure(dict(quantity=13,config_revision=self.p.revision))
  t=self.preview()
  with self.assertRaisesRegex(ValueError,'overrides'):self.manual(t,mode='LIVE')
  with self.assertRaisesRegex(ValueError,'overrides'):self.manual(t,quantity=1)
  self.manual(t,live_confirmed=True)
  self.assertEqual((self.t.submit.call_args.args[0]['mode'],self.t.submit.call_args.args[0]['quantity']),('PAPER',13))
 def test_live_paste_uses_single_mode_and_requires_its_confirmation(self):
  self.p.configure(dict(mode='LIVE',quantity=3,config_revision=self.p.revision));t=self.preview()
  with self.assertRaisesRegex(ValueError,'Live confirmation'):self.manual(t)
  self.t.submit.assert_not_called();self.manual(t,live_confirmed=True)
  self.assertEqual((self.t.submit.call_args.args[0]['mode'],self.t.submit.call_args.args[0]['quantity']),('LIVE',3))
 def test_saved_live_mode_does_not_arm_connect_or_submit(self):
  self.p.configure(dict(mode='LIVE',config_revision=self.p.revision));self.assertFalse(self.p.running)
  self.t.submit.assert_not_called();self.poll.start.assert_not_called()
 def test_mode_change_during_run_is_rejected_without_stopping_paper(self):
  self.start()
  with self.assertRaises(ValueError):self.p.configure(dict(mode='LIVE',config_revision=self.p.revision))
  with self.assertRaises(ValueError):self.p.start(dict(mode='LIVE',live_confirmed=True,config_revision=self.p.revision))
  self.assertTrue(self.p.running);self.row();self.p.step();self.assertEqual(self.t.submit.call_args.args[0]['mode'],'PAPER')
 def test_changed_configuration_invalidates_preview_and_old_revision(self):
  t=self.preview();rev=self.p.revision
  self.p.configure(dict(quantity=9,config_revision=rev))
  with self.assertRaises(ValueError):self.manual(t)
  with self.assertRaises(ValueError):self.p.configure(dict(mode='LIVE',config_revision=rev))
  self.t.submit.assert_not_called()
 def test_new_post_only_backlog_edited_missed_and_old_rows_do_not_dispatch(self):
  self.row('baseline');self.start()
  self.row('old',timestamp=999);self.row('edited',edited_at=1000);self.row('missed',missed_review=True);self.row('claimed',submission_id='existing')
  self.p.step();self.t.submit.assert_not_called()
  self.row('new',text='ETHUSD SELL BELOW 99');self.p.step();self.t.submit.assert_called_once()
 def test_duplicate_text_and_repeated_step_do_not_dispatch_twice(self):
  self.start();self.row('one');self.row('two');self.p.step();self.p.step();self.t.submit.assert_called_once()
 def test_manual_and_automatic_same_post_share_one_durable_claim(self):
  self.start();row=self.row();t=self.preview(queue_id=row['id'],revision=row['revision'])
  self.p.step()
  with self.assertRaises(ValueError):self.manual(t)
  self.t.submit.assert_called_once()
 def test_manual_first_prevents_automatic_second_entry(self):
  self.start();row=self.row();t=self.preview(queue_id=row['id'],revision=row['revision']);self.manual(t)
  self.p.step();self.t.submit.assert_called_once()
 def test_uncertain_submission_is_never_replayed_after_step_or_restart(self):
  self.t.submit.side_effect=ConnectionError('synthetic')
  self.start();self.row();self.p.step();self.p.step();self.t.submit.assert_called_once()
  self.assertEqual(self.p.records['1']['status'],'BLOCKED_OR_UNCERTAIN')
  restored=self.make();self.assertFalse(restored.running)
  with patch('sector_heatmap.telegram_execution.threading.Thread'):restored.start(dict(mode='PAPER',quantity=7,config_revision=restored.revision))
  restored.step();self.t.submit.assert_called_once()
 def test_restart_preserves_choices_and_audit_without_activation(self):
  self.start(mode='LIVE',quantity=19,live_confirmed=True);self.row();self.p.step()
  restored=self.make();self.assertFalse(restored.running);self.assertEqual((restored.settings['mode'],restored.settings['quantity']),('LIVE',19));self.assertIn('1',restored.records)
  self.assertEqual(restored.lifecycle.status()['reason'],'PROCESS_RESTART')
 def test_stop_preserves_reader_and_owned_exit_management(self):
  self.start();self.p.stop();self.poll.stop.assert_not_called();self.t.stop.assert_not_called();self.assertFalse(self.p.running)
  self.row();self.p.step();self.t.submit.assert_not_called()
 def test_unsupported_product_and_invalid_quantity_fail_without_dispatch(self):
  for p in ({'product':'EXACT'},{'quantity':True},{'quantity':0},{'quantity':'1000'}):
   with self.assertRaises(ValueError):self.p.configure(dict(p,config_revision=self.p.revision))
  self.t.submit.assert_not_called()
 def test_wrong_broker_or_missing_workspace_blocks_auto_and_manual(self):
  for broker in ('FYERS','DHAN',''):
   p=self.make(broker,Path(self.tmp.name)/(broker or 'none')/'state.json')
   with self.assertRaises(ValueError):p.start(dict(mode='PAPER',quantity=1,config_revision=p.revision))
   with self.assertRaises(ValueError):p.preview(dict(text='ETHUSD BUY ABOVE 100',config_revision=p.revision))
  self.t.submit.assert_not_called()
 def test_ticket_from_another_controller_cannot_be_submitted(self):
  t=self.preview();other=self.make(path=Path(self.tmp.name)/'other.json')
  with self.assertRaises(ValueError):other.submit_manual(dict(ticket_id=t['ticket_id'],text=t['text'],config_revision=other.revision,entry_confirmed=True))
  self.t.submit.assert_not_called()
 def test_missed_queued_manual_preview_and_changed_or_expired_text_fail(self):
  row=self.row(missed_review=True)
  with self.assertRaises(ValueError):self.preview(queue_id=row['id'],revision=row['revision'])
  t=self.preview()
  with self.assertRaises(ValueError):self.p.submit_manual(dict(ticket_id=t['ticket_id'],text='changed',config_revision=self.p.revision,entry_confirmed=True))
  self.now+=121
  with self.assertRaises(ValueError):self.manual(t)
  self.t.submit.assert_not_called()
 def test_existing_pending_order_guard_prevents_new_start_without_changing_order(self):
  self.gate.side_effect=ValueError('Existing order pending.')
  with self.assertRaisesRegex(ValueError,'pending'):self.start()
  self.assertFalse(self.p.running);self.t.submit.assert_not_called();self.poll.stop.assert_not_called()
 def test_guard_rejection_is_durable_for_new_recommendation(self):
  self.start();self.gate.side_effect=ValueError('Existing order pending.');self.row();self.p.step()
  self.assertEqual(self.p.records['1']['status'],'BLOCKED_OR_UNCERTAIN');self.t.submit.assert_not_called()
 def test_bot_receiver_uses_same_paper_executor_without_legacy_auto(self):
  self.poll.route='BOT';self.poll.running.return_value=False
  self.poll.start.side_effect=lambda p:self.poll.running.configure_mock(return_value=True)
  self.start();self.assertEqual(self.poll.start.call_args.args[0],{'auto':False});self.row();self.p.step()
  self.assertEqual(self.t.submit.call_args.args[0]['mode'],'PAPER')
 def test_failed_worker_start_never_leaves_execution_armed(self):
  with patch('sector_heatmap.telegram_execution.threading.Thread') as thread:
   thread.return_value.start.side_effect=RuntimeError('synthetic')
   with self.assertRaises(ValueError):self.p.start(dict(mode='PAPER',quantity=1,config_revision=self.p.revision))
  self.assertFalse(self.p.running);self.assertFalse(self.p.live_authorized);self.t.submit.assert_not_called()
 def test_default_migration_preserves_old_paper_exits_and_quantity_without_arming(self):
  old=Path(self.tmp.name)/'legacy.json';old.write_text(json.dumps({'options':{'gold_proxy':True,'ema_exit_length':21},'recommendations':{'old':{'status':'COMPLETE','timestamp':1}}}))
  p=self.make(path=old);self.assertEqual((p.settings['mode'],p.settings['quantity'],p.settings['ema_exit_length']),('PAPER',1000,21));self.assertTrue(p.settings['gold_proxy']);self.assertFalse(p.running);self.assertIn('old',p.records)

 def test_partial_fill_keeps_requested_quantity_separate_from_confirmed_fill(self):
  self.t.submit.side_effect=lambda p:dict(mode=p['mode'],status='RENKO_CONFIRMED_POSITION',position={'symbol':'C-ETH-100','quantity':2,'entry_price':2},management_owner='RENKO_SUPERTREND')
  self.start();self.row();self.p.step()
  r=self.p.records['1']['result'];self.assertEqual(r['quantity'],7);self.assertEqual(r['position']['quantity'],2);self.assertEqual(r['execution_mode'],'PAPER')

 def test_all_http_submit_aliases_enforce_the_same_paper_mode_and_quantity(self):
  for n,alias in enumerate(('submit','option-submit','execution-submit')):
   p=self.make(path=Path(self.tmp.name)/('alias-'+alias+'.json'))
   routes=action_routes(p,Mock(),self.poll,Mock(),Mock(),Mock(),Mock())
   preview=routes['parse'](dict(text='ETHUSD BUY ABOVE '+str(100+n),config_revision=p.revision))
   terms=dict(ticket_id=preview['ticket_id'],text=preview['text'],config_revision=p.revision,entry_confirmed=True)
   with self.assertRaises(ValueError):routes[alias](dict(terms,mode='LIVE'))
   routes[alias](terms)
   self.assertEqual((self.t.submit.call_args.args[0]['mode'],self.t.submit.call_args.args[0]['quantity']),('PAPER',1000))
 def test_legacy_start_alias_is_retired_and_reconcile_stays_read_only(self):
  retired=Mock(side_effect=ValueError('retired'));parser=Mock()
  routes=action_routes(self.p,parser,self.poll,Mock(),Mock(),retired,Mock())
  with self.assertRaises(ValueError):routes['paper-start']({'mode':'LIVE'})
  routes['reconcile']({'queue_id':'historical'})
  parser.reconcile.assert_called_once();self.t.submit.assert_not_called();self.poll.start.assert_not_called()
