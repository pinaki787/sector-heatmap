import json,multiprocessing,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
import native_sizing as n
from test_native_sizing import DELTA
from native_reference import choose_reference

def at(day,hour=12):
 return datetime(2026,11,day,hour,tzinfo=timezone.utc).timestamp()

def worker(folder,queue):
 with patch.object(n,'DATA',Path(folder)),patch.object(n,'authorize',return_value='user'):
  def fetch(config,**kw):
   with (Path(folder)/'calls').open('a') as out:out.write('call\n')
   time.sleep(.05)
   return dict(native_box=100,valid_until=n.session_scope(config,now=kw['now'])['valid_until'])
  with patch.object(n,'_acquire',side_effect=fetch):
   queue.put(n.acquire(DELTA,now=at(26))['native_box'])

class SessionCacheTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.data=patch.object(n,'DATA',self.root);self.data.start()
  self.auth=patch.object(n,'authorize',return_value='user');self.auth.start()
 def tearDown(self):
  self.auth.stop();self.data.stop();self.tmp.cleanup()
 def ref(self,c,**kw):
  return dict(native_box=100,valid_until=n.session_scope(c,now=kw['now'])['valid_until'])
 def test_same_session_reuses_across_restart_and_next_session_refreshes(self):
  with patch.object(n,'_acquire',side_effect=self.ref) as call:
   n.acquire(DELTA,now=at(26,1));n.JOBS.clear()
   n.acquire(DELTA,now=at(26,22));self.assertEqual(call.call_count,1)
   n.acquire(DELTA,now=at(27,1));self.assertEqual(call.call_count,2)
 def test_cross_process_deduplication(self):
  ctx=multiprocessing.get_context('fork');q=ctx.Queue()
  ps=[ctx.Process(target=worker,args=(str(self.root),q)) for _ in range(4)]
  for p in ps:p.start()
  for p in ps:p.join(5);self.assertEqual(p.exitcode,0)
  self.assertEqual([q.get(timeout=1) for _ in ps],[100]*4)
  self.assertEqual((self.root/'calls').read_text().splitlines(),['call'])
 def test_failure_is_persisted_not_retried_by_start_or_preview(self):
  with patch.object(n,'_acquire',side_effect=ValueError('Native calculation failed')) as call:
   for _ in range(3):
    with self.assertRaisesRegex(ValueError,'failed'):n.acquire(DELTA,now=at(26))
   self.assertEqual(call.call_count,1)
   with patch.object(n.time,'time',return_value=at(26)):
    self.assertEqual(n.request(DELTA)['state'],'FAILED')
   self.assertEqual(call.call_count,1)
 def test_quota_blocks_other_symbols_on_same_connection_without_leaking_text(self):
  with patch.object(n,'_acquire',side_effect=ValueError('TradingView native sizing quota exceeded')) as call:
   for c in (DELTA,dict(DELTA,underlying='BTCUSD')):
    with self.assertRaisesRegex(ValueError,'quota'):n.acquire(c,now=at(26))
   self.assertEqual(call.call_count,1)
 def test_unknown_interrupted_attempt_does_not_send_again(self):
  path=n.session_path(DELTA)
  n.atomic(path,dict(session=n.session_scope(DELTA,now=at(26))['id'],state='RUNNING'))
  with patch.object(n,'_acquire') as call:
   with self.assertRaisesRegex(ValueError,'interrupted'):n.acquire(DELTA,now=at(26))
   call.assert_not_called()
 def test_scope_isolated_by_account_symbol_broker_category(self):
  with patch.object(n,'_acquire',side_effect=self.ref) as call:
   for c in (DELTA,dict(DELTA,account='b'*32),dict(DELTA,underlying='BTCUSD'),dict(DELTA,asset='GOLD',market='GLOBAL_COMMODITY')):
    n.acquire(c,now=at(26))
   self.assertEqual(call.call_count,4)
 def test_indian_session_lease_and_mcx_not_parent_or_hour_boundary(self):
  c=dict(DELTA,market='MCX')
  one=n.session_scope(c,now=datetime.fromisoformat('2026-11-26T08:00:00+05:30').timestamp())
  two=n.session_scope(c,now=datetime.fromisoformat('2026-11-26T23:50:00+05:30').timestamp())
  self.assertEqual(one,two)
  self.assertEqual(datetime.fromtimestamp(one['valid_until'],n.IST).isoformat(),'2026-11-27T09:00:00+05:30')
  c=dict(DELTA,market='BSE')
  one=n.session_scope(c,now=datetime.fromisoformat('2026-11-26T08:00:00+05:30').timestamp())
  two=n.session_scope(c,now=datetime.fromisoformat('2026-11-26T15:00:00+05:30').timestamp())
  self.assertEqual(one,two)
 def test_parse_quota_diagnostic_is_sanitized(self):
  with self.assertRaisesRegex(ValueError,'quota exceeded') as err:
   n.parse_result(dict(isError=True,content=[dict(text='TOOL_QUOTA_EXCEEDED secret-token')]),DELTA)
  self.assertNotIn('secret-token',str(err.exception))

 def test_frozen_indian_reference_reuses_only_its_acquisition_session(self):
  from test_native_session_provenance import SessionProvenanceTests
  now,reply,c=SessionProvenanceTests().fixture()
  ref=n.parse_result(reply,c,now=now)
  self.assertIsNotNone(choose_reference([ref],c['underlying'],'BSE',expected_session='other',now=now+60))
  self.assertIsNone(choose_reference([ref],c['underlying'],'BSE',expected_session='other',now=ref['valid_until']+1))
