import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
from sector_heatmap.telegram_subscriber import TelegramSubscriber,TelegramConnections

class SubscriberTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'subscriber.json';self.s=TelegramSubscriber(self.path,clock=lambda:1000,client_factory=lambda *a,**kw:None)
  self.s.verified=dict(channel_id=-1003660684605);self.s.receiving=True;self.s.baseline=10;self.s.watermark=10
 def message(self,id,text='ETHUSD BUY ABOVE 10 SL 9 TARGET 12'):
  return SimpleNamespace(id=id,message=text,date=datetime.fromtimestamp(999,timezone.utc),edit_date=datetime.fromtimestamp(1000,timezone.utc))
 def test_baseline_and_out_of_order_dedupe(self):
  for id in [9,10,12,11,12]:self.s.ingest_message(self.message(id))
  self.assertEqual(len(self.s.data['queue']),2);self.assertEqual(self.s.watermark,12)
 def test_never_calls_auto_or_sends_and_missed_is_review_only(self):
  self.s.auto=True;self.s.auto_submit=lambda *a: self.fail('must never submit')
  self.s.ingest_message(self.message(11),missed=True)
  row=self.s.data['queue'][0];self.assertEqual(row['state'],'REVIEW');self.assertTrue(row['missed_review']);self.assertFalse(self.s.auto)
 def test_edit_invalidates_old_revision(self):
  self.s.ingest_message(self.message(11));row=dict(self.s.data['queue'][0])
  self.s.ingest_message(self.message(11,'ETHUSD BUY ABOVE 11'),edited=True)
  with self.assertRaises(ValueError):self.s.snapshot(row['id'],row['revision'])
 def test_edit_of_prebaseline_message_not_imported(self):
  self.s.ingest_message(self.message(8),edited=True);self.assertEqual(self.s.data['queue'],[])
 def test_newer_live_post_does_not_advance_reconnect_scan_cursor(self):
  self.s.reconciled_id=10;self.s.ingest_message(self.message(15))
  self.assertEqual(self.s.reconciled_id,10)
  self.s.ingest_message(self.message(12),missed=True)
  self.assertEqual({r['id'] for r in self.s.data['queue']},{'-1003660684605:15','-1003660684605:12'})
 def test_dependency_missing_blocks_before_client_creation(self):
  self.s.stop();self.s.configure(dict(api_id='123',api_hash='c'*32,channel='-1003660684605'));self.s.dependency=lambda:'NOT_INSTALLED'
  import asyncio
  with self.assertRaisesRegex(ValueError,'dependency'):asyncio.run(self.s.connect())
  self.assertIsNone(self.s.client)
 def test_stopped_receives_nothing(self):
  self.s.stop();self.s.ingest_message(self.message(11));self.assertEqual(self.s.data['queue'],[])
 def test_credentials_private_status_redacted_restart_stopped(self):
  self.s.stop();self.s.configure(dict(api_id='1234',api_hash='a'*32,channel='-1003660684605'))
  status=self.s.status();self.assertNotIn('api_hash',status);self.assertNotIn('api_id',status);self.assertFalse(status['auto_available'])
  self.assertEqual(self.path.stat().st_mode&0o777,0o600)
  restart=TelegramSubscriber(self.path);self.assertFalse(restart.running());self.assertEqual(restart.auth,'DISCONNECTED');self.assertFalse(restart.auto)
 def test_route_survives_restart_without_reception(self):
  path=Path(self.tmp.name)/'telegram-review.json';c=TelegramConnections(path);c.select({'route':'SUBSCRIBER'})
  restart=TelegramConnections(path);self.assertEqual(restart.route,'SUBSCRIBER');self.assertFalse(restart.status()['running'])
 def test_auto_rejected_before_connect(self):
  self.s.stop()
  import asyncio
  with self.assertRaisesRegex(ValueError,'Auto'):asyncio.run(self.s.start_async({'auto':True}))

class FakeClient:
 def __init__(self,*a,**kw):self.authorized=False;self.session=SimpleNamespace(save_entities=True);self.entity=SimpleNamespace(title='Advisory',broadcast=True);self.code_calls=0
 async def connect(self):pass
 async def disconnect(self):pass
 async def is_user_authorized(self):return self.authorized
 async def send_code_request(self,phone):self.code_calls+=1;return SimpleNamespace(phone_code_hash='private-hash')
 async def sign_in(self,**kw):self.authorized=True
 async def iter_dialogs(self):yield SimpleNamespace(id=-1003660684605,entity=self.entity)
 async def get_messages(self,entity,limit):return [SimpleNamespace(id=40)]
 async def iter_messages(self,*a,**kw):
  for m in []:yield m

class AuthTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.s=TelegramSubscriber(Path(self.tmp.name)/'config.json',client_factory=FakeClient)
  self.s.configure(dict(channel='-1003660684605',api_id='123',api_hash='b'*32));self.addCleanup(self.cleanup)
 def cleanup(self):
  if self.s.loop:
   self.s.disconnect();self.s.loop.call_soon_threadsafe(self.s.loop.stop);self.s.worker.join(2);self.s.loop.close()
 def test_login_code_ephemeral_and_session_cache_disabled(self):
  s=self.s.login({'phone':'+911234567890'});self.assertEqual(s['authentication'],'CODE_REQUIRED');self.assertFalse(self.s.client.session.save_entities)
  self.s.login({'code':'12345'});self.assertIsNone(self.s.phone);self.assertIsNone(self.s.code_hash)
  saved=self.s.path.read_text();self.assertNotIn('911234567890',saved);self.assertNotIn('12345',saved)
 def test_start_baselines_old_posts_and_restart_requires_explicit_start(self):
  self.s.login({'phone':'+911234567890'});self.s.login({'code':'12345'})
  self.s.start({});self.assertEqual(self.s.baseline,40);self.assertEqual(self.s.reconciled_id,40);self.assertTrue(self.s.running());self.assertFalse(self.s.auto)
  self.s.stop();self.assertFalse(self.s.running())
 def test_unauthenticated_verify_cannot_receive(self):
  with self.assertRaisesRegex(ValueError,'Authenticate'):self.s.verify()
  self.assertFalse(self.s.running())
 def test_auth_error_never_returns_library_secret(self):
  self.s.login({'phone':'+911234567890'})
  async def fail(**kw):raise ValueError('secret-12345')
  self.s.client.sign_in=fail
  with self.assertRaises(ValueError) as e:self.s.login({'code':'12345'})
  self.assertNotIn('secret',str(e.exception));self.assertNotIn('12345',str(e.exception))

class PeerTypeTests(AuthTests):
 def test_joined_advisory_supergroup_is_valid(self):
  self.s.login({'phone':'+911234567890'});self.s.login({'code':'12345'})
  self.s.client.entity.broadcast=False;self.s.client.entity.megagroup=True
  result=self.s.verify();self.assertEqual(result['verified']['peer_type'],'SUPERGROUP');self.assertFalse(result['running'])
 def test_left_or_nonchannel_peer_is_rejected(self):
  self.s.login({'phone':'+911234567890'});self.s.login({'code':'12345'})
  self.s.client.entity.broadcast=False
  with self.assertRaisesRegex(ValueError,'joined'):self.s.verify()
  self.s.client.entity.broadcast=True;self.s.client.entity.left=True
  with self.assertRaisesRegex(ValueError,'joined'):self.s.verify()
