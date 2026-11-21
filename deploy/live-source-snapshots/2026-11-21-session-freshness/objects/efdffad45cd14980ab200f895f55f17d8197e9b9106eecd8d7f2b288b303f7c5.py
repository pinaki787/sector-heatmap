import tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import Mock
from sector_heatmap.telegram_parser import TelegramParser
from sector_heatmap.telegram_polling import TelegramPolling
from sector_heatmap.parser_submission import ParserSubmissionGuard
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.now=1000
  self.poll=TelegramPolling(Path(self.tmp.name)/'config.json',clock=lambda:self.now)
  self.delta=Mock();self.delta.catalog.return_value={'instruments':[dict(symbol='ETHUSD',contract_type='perpetual_futures',tick_size='.05',contract_value='.01',quoting_currency='USD')]};self.delta.submit_discretionary.return_value={'status':'pending','order_id':1,'filled_contracts':0}
  self.fyers=Mock(return_value={'status':'SUBMITTED','order_id':'test'});self.guard=ParserSubmissionGuard(Path(self.tmp.name)/'guard.sqlite');self.addCleanup(self.guard.db.close)
  self.parsed=dict(action='BUY',entry=2680,entry_instruction='STOP_LIMIT',stop_loss=2666,targets=[2700],missing=[])
  self.router=TelegramParser(lambda t:dict(self.parsed),lambda p:dict(mapping={'status':'EXACT','contract':dict(symbol='NSE:TEST',tick_size='.05')},parsed=self.parsed),self.fyers,self.delta,self.guard,self.poll,clock=lambda:self.now)
 def terms(self,broker='DELTA_INDIA'):
  ticket=self.router.parse(dict(broker=broker,text='ETHUSD BUY ABOVE 2680 SL 2666 TARGET 2700'))
  return dict(ticket_id=ticket['ticket_id'],broker=broker,text=ticket['text'],mode='CONFIRMATION',quantity='1',entry_mode='STOP_LIMIT',trigger_price='2680',limit_price='2680.05',submission_id=str(uuid.uuid4()))
 def test_parse_never_executes_and_selected_broker_routes_only_once(self):
  p=self.terms();self.delta.submit_discretionary.assert_not_called();self.fyers.assert_not_called()
  self.router.submit(p);self.router.submit(p);self.assertEqual(self.delta.submit_discretionary.call_count,1);self.fyers.assert_not_called()
  native=self.delta.submit_discretionary.call_args.args[0];self.assertEqual(native['telegram_stop_price'],'2680');self.assertNotIn('resolution',native)
  self.router.submit(self.terms('FYERS'));self.assertEqual(self.fyers.call_count,1)
 def test_changed_broker_expired_ticket_and_unresolved_fail_closed(self):
  p=self.terms()
  with self.assertRaises(ValueError):self.router.submit(p|dict(broker='FYERS'))
  self.now+=121
  with self.assertRaises(ValueError):self.router.submit(p)
  t=self.router.parse(dict(broker='DELTA_INDIA',text='BUY UNKNOWN AT 10'))
  with self.assertRaises(ValueError):self.router.submit(p|dict(ticket_id=t['ticket_id'],text=t['text']))
  self.delta.submit_discretionary.assert_not_called()
 def test_no_http_auto_activation(self):
  with self.assertRaises(ValueError):self.router.submit(self.terms()|dict(mode='AUTO'))
 def update(self,n,text='ETHUSD BUY ABOVE 2680 SL 2666 TARGET 2700',stamp=1000):return dict(update_id=n,channel_post=dict(chat={'id':-10012345},message_id=n,date=stamp,text=text))
 def test_queue_dedupe_edits_expiry_and_secret_not_in_status(self):
  self.poll.data.update(token='123:'+('x'*30),channel='-10012345');self.poll.verified=dict(channel_id=-10012345)
  self.poll.ingest([self.update(1),self.update(1)]);self.assertEqual(len(self.poll.status()['queue']),1);self.assertNotIn('token',self.poll.status())
  row=self.poll.status()['queue'][0];p=self.terms();ticket=self.router.parse(dict(broker='DELTA_INDIA',queue_id=row['id'],revision=row['revision']))
  self.poll.ingest([self.update(1,text='ETHUSD BUY ABOVE 2690')])
  with self.assertRaises(ValueError):self.router.submit(p|dict(ticket_id=ticket['ticket_id']))
  self.now+=301;self.assertTrue(self.poll.status()['queue'][0]['expired'])
 def test_auto_ignores_backlog_duplicates_edits_and_wrong_channel(self):
  self.poll.verified=dict(channel_id=-10012345);self.poll.auto=True;self.poll.armed_at=1000;self.poll.execution=dict(broker='DELTA_INDIA',quantity=1);send=Mock(return_value={'status':'pending','order_id':1,'filled_contracts':0});self.poll.auto_submit=send
  self.poll.ingest([self.update(1,stamp=999)],baseline=True);send.assert_not_called()
  self.poll.ingest([self.update(2),self.update(2)]);self.assertEqual(send.call_count,1)
  self.poll.ingest([self.update(2,text='ETHUSD BUY ABOVE 2700')]);self.assertEqual(send.call_count,1)
  u=self.update(3);u['channel_post']['chat']['id']=-10099999;self.poll.ingest([u]);self.assertEqual(send.call_count,1)
 def test_actual_auto_adapter_routes_without_confirmation(self):
  self.poll.verified=dict(channel_id=-10012345);self.poll.auto=True;self.poll.armed_at=1000;self.poll.execution=dict(broker='DELTA_INDIA',quantity=1);self.poll.auto_submit=self.router.auto
  self.poll.ingest([self.update(4)]);self.assertEqual(self.delta.submit_discretionary.call_count,1);self.assertEqual(self.poll.status()['queue'][0]['state'],'BROKER_RESPONSE')
 def test_restart_stopped_and_credentials_private(self):
  self.poll.configure(dict(token='123:'+('x'*30),channel='-10012345',interval=30));self.assertEqual(self.poll.path.stat().st_mode&0o777,0o600)
  restart=TelegramPolling(self.poll.path);self.assertFalse(restart.running());self.assertFalse(restart.auto);self.assertIsNone(restart.verified)
 def test_default_channel_label_and_saved_label_preservation(self):
  self.assertEqual(self.poll.status()['channel_label'],'Doctor Devendra’s Crypto Advisory')
  self.poll.configure(dict(token='123:'+('x'*30),channel='-10012345',channel_label='Existing configured channel',interval=30))
  restart=TelegramPolling(self.poll.path)
  self.assertEqual(restart.status()['channel_label'],'Existing configured channel')
  self.assertEqual(restart.status()['channel'],'-10012345')
 def test_verify_requires_authenticated_bot_channel_membership_and_no_webhook(self):
  self.poll.data.update(token='123:'+('x'*30),channel='-10012345')
  replies={'getMe':{'id':1,'is_bot':True,'username':'testbot'},'getChat':{'id':-10012345,'type':'channel','title':'Test'},'getChatMember':{'status':'administrator'},'getWebhookInfo':{'url':''}}
  self.poll.api=lambda method,body=None:replies[method]
  self.assertEqual(self.poll.verify()['connection'],'VERIFIED')
  replies['getWebhookInfo']={'url':'https://example.org/webhook'}
  with self.assertRaisesRegex(ValueError,'webhook'):self.poll.verify()
  self.assertIsNone(self.poll.verified)
 def test_queue_reconciliation_keeps_broker_attribution_and_no_resubmission(self):
  self.poll.verified=dict(channel_id=-10012345);self.poll.ingest([self.update(7)])
  row=self.poll.status()['queue'][0];ticket=self.router.parse(dict(broker='DELTA_INDIA',queue_id=row['id'],revision=row['revision']))
  self.delta.submit_discretionary.return_value={'request_id':'test-request','status':'pending','filled_contracts':0}
  self.router.submit(self.terms()|dict(ticket_id=ticket['ticket_id']))
  self.delta.reconcile.return_value={'status':'closed','filled_contracts':1,'request_id':'test-request'}
  result=self.router.reconcile(dict(queue_id=row['id']))
  self.assertEqual(result['filled_contracts'],1);self.assertEqual(result['broker'],'DELTA_INDIA');self.assertEqual(self.delta.submit_discretionary.call_count,1)
