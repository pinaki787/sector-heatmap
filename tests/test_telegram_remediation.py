import asyncio,json,sqlite3,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from sector_heatmap.telegram_paper import PaperPipeline
from sector_heatmap.telegram_lifecycle import Lifecycle
from sector_heatmap.telegram_subscriber import TelegramSubscriber,TelegramConnections
from sector_heatmap.workspace_guard import WorkspaceGuard
from sector_heatmap.telegram_migration import migration_plan,restore

class PipelineRemediationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'paper.json';self.now=1000
  self.poll=Mock();self.poll.route='SUBSCRIBER';self.poll.running.return_value=True;self.poll.verified={'channel_id':-100123456};self.poll.lock=threading.RLock();self.poll.data={'queue':[]}
  self.tickets=Mock();self.tickets.parse.return_value=dict(action='BUY',entry=100,entry_instruction='STOP_LIMIT',stop_loss=90,targets=[110])
  self.tickets.preview.return_value=dict(ticket_id='test',text='synthetic',contract={},renko_settings={})
  self.tickets.submit.return_value=dict(status='PAPER_CONFIRMED')
  self.feed=Mock();self.feed.stream_status.return_value={'connected':True}
  with patch.dict('os.environ',{'SECTOR_PULSE_WORKSPACE_BROKER':'DELTA_INDIA'}):self.p=PaperPipeline(self.tickets,self.poll,self.path,lambda:self.now,self.feed)
 def start(self,**kw):
  with patch('sector_heatmap.telegram_paper.threading.Thread'):return self.p.start(dict(mode='PAPER',quantity=1000,**kw))
 def row(self,id,text):
  self.poll.data['queue'].append(dict(id=id,revision=id,text=text,timestamp=self.now,state='REVIEW'))
 def test_bot_rejection_is_actionable_persisted_and_never_starts_feed(self):
  self.poll.route='BOT'
  with self.assertRaisesRegex(ValueError,'Subscriber account'):self.start()
  self.feed.start.assert_not_called();self.tickets.submit.assert_not_called()
  self.assertEqual(json.loads(self.path.with_suffix('.lifecycle.json').read_text())['reason'],'START_REJECTED')
  self.assertFalse(self.p.running)
 def test_wrong_workspace_rejected_before_reception_or_feed(self):
  self.p.workspace_broker='FYERS'
  with self.assertRaisesRegex(ValueError,'Delta India account'):self.start()
  self.poll.start.assert_not_called();self.feed.start.assert_not_called();self.tickets.submit.assert_not_called()
 def test_proxy_off_blocks_gold_and_never_calls_ticket_or_order(self):
  self.start(gold_proxy=False);self.row('gold','XAUUSD BUY ABOVE 100');self.p.step()
  self.assertEqual(self.p.records['gold']['status'],'BLOCKED');self.assertIn('proxy disabled',self.p.records['gold']['message'])
  self.tickets.preview.assert_not_called();self.tickets.submit.assert_not_called()
 def test_explicit_proxy_and_saved_exit_choices_reach_ticket_only_once(self):
  self.start(gold_proxy=True,timeframe='3 minutes',ema_exit_enabled=False,supertrend_exit_enabled=True,ema_exit_length=21)
  self.row('gold','XAUUSD BUY ABOVE 100');self.p.step();self.p.step()
  self.assertTrue(self.tickets.preview.call_args.args[0]['gold_proxy'])
  terms=self.tickets.submit.call_args.args[0];self.assertEqual(terms['mode'],'PAPER');self.assertEqual(terms['timeframe'],'3 minutes');self.assertFalse(terms['ema_exit_enabled'])
  self.tickets.submit.assert_called_once()
  self.p.stop()
  restored=PaperPipeline(self.tickets,self.poll,self.path,lambda:self.now,self.feed)
  self.assertFalse(restored.running);self.assertTrue(restored.options['gold_proxy']);self.assertEqual(restored.options['ema_exit_length'],21)
 def test_reception_stop_reason_and_heartbeat_persist(self):
  self.start();self.now+=4;self.p.step();self.assertEqual(self.p.status()['lifecycle']['heartbeat'],1004)
  self.poll.running.return_value=False;self.p.step()
  self.assertFalse(self.p.running);self.assertEqual(self.p.status()['lifecycle']['reason'],'RECEPTION_STOPPED')
  restored=PaperPipeline(self.tickets,self.poll,self.path,lambda:self.now,self.feed)
  self.assertEqual(restored.status()['lifecycle']['reason'],'RECEPTION_STOPPED')
 def test_restart_records_reason_and_never_rearms(self):
  self.start();restored=PaperPipeline(self.tickets,self.poll,self.path,lambda:self.now,self.feed)
  self.assertFalse(restored.running);self.assertEqual(restored.status()['lifecycle']['reason'],'PROCESS_RESTART')
 def test_failed_feed_start_rolls_back_only_reception_started_by_attempt(self):
  self.poll.running.return_value=False
  self.poll.start.side_effect=lambda p:self.poll.running.configure_mock(return_value=True)
  self.feed.start.side_effect=RuntimeError('synthetic unavailable')
  with self.assertRaisesRegex(ValueError,'market feed'):self.start()
  self.poll.stop.assert_called_once();self.assertFalse(self.p.running);self.tickets.submit.assert_not_called()
 def test_option_save_does_not_start_anything_and_rejects_invalid_choices(self):
  self.p.configure(dict(gold_proxy=True,ema_exit_length=14))
  self.poll.start.assert_not_called();self.feed.start.assert_not_called()
  for p in ({'gold_proxy':'true'},{'ema_exit_length':True},{'ema_exit_enabled':False,'supertrend_exit_enabled':False}):
   with self.assertRaises(ValueError):self.p.configure(p)
 def test_route_change_stop_is_distinct(self):
  self.start();self.poll.route='BOT';self.p.step()
  self.assertEqual(self.p.status()['lifecycle']['reason'],'CONNECTION_ROUTE_CHANGED')
 def test_lifecycle_file_permissions_and_no_post_content(self):
  self.start();self.assertEqual(self.path.with_suffix('.lifecycle.json').stat().st_mode&0o777,0o600)
  self.assertNotIn('token',self.path.with_suffix('.lifecycle.json').read_text())

class WorkspaceBindingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);store=Mock();store.folder.return_value=Path(self.tmp.name);self.guard=WorkspaceGuard(store,'account',8101,8080)
 def test_delta_telegram_allowed_but_cross_broker_rejected(self):
  self.guard.validate_action({'id':'account','broker':'DELTA_INDIA'},'/api/telegram/paper-start',{'mode':'PAPER'})
  with self.assertRaises(PermissionError):self.guard.validate_action({'id':'account','broker':'DELTA_INDIA'},'/api/telegram/start',{'broker':'FYERS'})
 def test_fyers_reception_allowed_but_delta_option_routes_denied(self):
  self.guard.validate_action({'id':'account','broker':'FYERS'},'/api/telegram/start',{'broker':'FYERS','auto':False})
  for action in ('paper-start','paper-stop','paper-settings','option-preview','option-submit'):
   with self.assertRaises(PermissionError):self.guard.validate_action({'id':'account','broker':'FYERS'},'/api/telegram/'+action,{})
 def test_dhan_telegram_mutation_stays_blocked(self):
  with self.assertRaises(PermissionError):self.guard.validate_action({'id':'account','broker':'DHAN'},'/api/telegram/config',{})
 def test_migrated_subscriber_session_cannot_connect_from_other_account(self):
  with tempfile.TemporaryDirectory() as td:
   s=TelegramSubscriber(Path(td)/'subscriber.json',client_factory=Mock())
   s.data['owner_binding']={'account_id':'owned'}
   with patch.dict('os.environ',{'SECTOR_PULSE_WORKSPACE_ID':'other'}),self.assertRaisesRegex(ValueError,'different account'):asyncio.run(s.connect())
   s.client_factory.assert_not_called()

class ReaderMigrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  private=self.root/'.private';(private/'dashboard-login').mkdir(parents=True);(private/'notifications').mkdir()
  with sqlite3.connect(private/'dashboard-login/registry.sqlite3') as d:
   d.executescript("CREATE TABLE users(id TEXT,username TEXT,admin INTEGER);CREATE TABLE accounts(id TEXT,broker TEXT,user_id TEXT);INSERT INTO users VALUES('owner-id','owner',1);INSERT INTO users VALUES('other-id','other',0);INSERT INTO accounts VALUES('owned','DELTA_INDIA','owner-id');INSERT INTO accounts VALUES('foreign','DELTA_INDIA','other-id');INSERT INTO accounts VALUES('fyers','FYERS','owner-id');")
  (private/'notifications/config.json').write_text(json.dumps({'owner_username':'owner','telegram':{'chat_id':123}}))
  (private/'telegram-subscriber.json').write_text(json.dumps({'api_id':1,'api_hash':'synthetic','channel':'-100123456','queue':[{'text':'do not copy'}]}))
  (private/'telegram-session').mkdir()
  with sqlite3.connect(private/'telegram-session/subscriber.session') as d:d.execute('CREATE TABLE synthetic(x INTEGER)')
 def client(self,identity=123):
  class Fake:
   def __init__(self,*a,**kw):self.session=SimpleNamespace(save_entities=True)
   async def connect(self):pass
   async def disconnect(self):pass
   async def is_user_authorized(self):return True
   async def get_me(self):return SimpleNamespace(id=identity)
   async def iter_dialogs(self):yield SimpleNamespace(id=-100123456,entity=SimpleNamespace(broadcast=True,left=False))
  return Fake
 def test_verified_owner_restore_is_single_account_stopped_and_excludes_queue(self):
  plan=migration_plan(self.root,'owner','owned');r=asyncio.run(restore(plan,True,self.client()))
  self.assertTrue(r['owner_verified']);self.assertFalse(r['reader_started']);self.assertFalse(r['paper_started'])
  data=json.loads((plan['target']/'telegram-subscriber.json').read_text())
  self.assertEqual(data['queue'],[]);self.assertEqual(data['owner_binding']['account_id'],'owned')
  self.assertEqual((plan['target']/'telegram-session/subscriber.session').stat().st_mode&0o777,0o600)
  with self.assertRaises(ValueError):migration_plan(self.root,'owner','owned')
 def test_wrong_owner_or_broker_never_gets_credentials(self):
  for owner,account in (('owner','foreign'),('other','owned'),('owner','fyers')):
   with self.assertRaises(ValueError):migration_plan(self.root,owner,account)
 def test_identity_mismatch_writes_no_destination_configuration(self):
  plan=migration_plan(self.root,'owner','owned')
  with self.assertRaisesRegex(ValueError,'identity'):asyncio.run(restore(plan,True,self.client(999)))
  self.assertFalse((plan['target']/'telegram-subscriber.json').exists())
 def test_legacy_running_or_unchecked_cannot_restore(self):
  plan=migration_plan(self.root,'owner','owned')
  with self.assertRaisesRegex(ValueError,'stopped'):asyncio.run(restore(plan,False,self.client()))
  self.assertFalse((plan['target']/'telegram-subscriber.json').exists())
