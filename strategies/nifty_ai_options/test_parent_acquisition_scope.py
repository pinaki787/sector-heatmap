import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import native_sizing as n
from test_native_session_cache import at
CONFIG=dict(account='a'*32,broker='FYERS',underlying='NSE:NIFTY50-INDEX',market='NSE',execution_route='OPTIONS',option_moneyness='OTM')
class ParentAcquisitionScope(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.data=patch.object(n,'DATA',self.root);self.data.start();self.auth=patch.object(n,'authorize',return_value='fixture-user');self.auth.start();self.now=at(26,5)
 def tearDown(self):self.auth.stop();self.data.stop();self.temp.cleanup()
 def ref(self,c,**kwargs):
  return dict(n.context(c),native_box=400,symbol=c['underlying'],verified_native_size=True,status='VERIFIED_OFFICIAL_NATIVE',chart_session='Regular trading hours',reference_measure='NATIVE_RENKO_ATR_BOX',valid_until=n.session_scope(c,now=self.now)['valid_until'],sizing_session=n.session_scope(c,now=self.now)['id'],reference_session='2026-11-25',completed_parent_at=self.now-86400,source='fixture official observation',tv_symbol='NSE:NIFTY',observed_at='2026-11-26T10:30:00+05:30')
 def legacy(self,c,state,**fields):
  p=self.root/'native-session-cache'/c['account']/(n.key(c)+'.json');n.atomic(p,dict(session=n.session_scope(c,now=self.now)['id'],symbol=c['underlying'],state=state,updated_at=self.now,**fields));return p
 def test_option_classification_and_direct_route_share_parent_but_keep_conversion(self):
  atm=dict(CONFIG,option_moneyness='ATM');direct=dict(CONFIG,execution_route='DIRECT')
  self.assertEqual(n.parent_key(CONFIG),n.parent_key(atm));self.assertEqual(n.parent_key(CONFIG),n.parent_key(direct))
  with patch.object(n,'_acquire',side_effect=self.ref) as fetch:
   first=n.acquire(CONFIG,now=self.now);second=n.acquire(atm,now=self.now+1);n.acquire(direct,now=self.now+2)
   self.assertEqual(fetch.call_count,1);self.assertEqual(second['native_box'],400)
   projected=n.apply_reference(atm,second)
   self.assertEqual(projected['reference_context']['option_multiplier'],.5)
   self.assertEqual(first['option_multiplier'],.25);self.assertEqual(projected['reference_context']['observed_at'],first['observed_at'])
 def test_concurrent_variants_send_one_mocked_provider_request(self):
  def slow(c,**kwargs):time.sleep(.02);return self.ref(c,**kwargs)
  configs=[CONFIG,dict(CONFIG,option_moneyness='ATM'),dict(CONFIG,execution_route='DIRECT')]*2
  with patch.object(n,'_acquire',side_effect=slow) as fetch,ThreadPoolExecutor(max_workers=6) as pool:
   refs=list(pool.map(lambda c:n.acquire(c,now=self.now),configs))
  self.assertEqual(fetch.call_count,1);self.assertEqual([r['native_box'] for r in refs],[400]*6)
 def test_prior_failure_cannot_be_bypassed_by_switching_classification(self):
  self.legacy(CONFIG,'FAILED',error='Fixture quota cooldown')
  with patch.object(n,'_acquire') as fetch:
   with self.assertRaisesRegex(ValueError,'quota cooldown'):n.acquire(dict(CONFIG,option_moneyness='ATM'),now=self.now)
   fetch.assert_not_called()
 def test_interrupted_or_conflicting_legacy_attempts_block_reacquisition(self):
  for interrupted in (True,False):
   with self.subTest(interrupted=interrupted):
    n.session_path(CONFIG).unlink(missing_ok=True)
    self.legacy(CONFIG,'RUNNING' if interrupted else 'READY',reference=self.ref(CONFIG))
    self.legacy(dict(CONFIG,option_moneyness='ATM'),'READY',reference=dict(self.ref(CONFIG),native_box=500))
    with patch.object(n,'_acquire') as fetch:
     with self.assertRaisesRegex(ValueError,'unresolved|reconciliation'):n.acquire(dict(CONFIG,execution_route='DIRECT'),now=self.now)
     fetch.assert_not_called()
 def test_verified_legacy_success_is_reused_without_editing_observation(self):
  p=self.legacy(CONFIG,'READY',reference=self.ref(CONFIG));before=p.read_bytes()
  with patch.object(n,'_acquire') as fetch:
   ref=n.acquire(dict(CONFIG,option_moneyness='ATM'),now=self.now)
  self.assertEqual(ref['native_box'],400);self.assertEqual(p.read_bytes(),before);fetch.assert_not_called()
 def test_parent_scope_still_isolates_account_symbol_and_native_category(self):
  for c in [dict(CONFIG,account='b'*32),dict(CONFIG,underlying='NSE:RELIANCE-EQ'),dict(CONFIG,market='CRYPTO',broker='DELTA_INDIA',underlying='ETHUSD')]:
   self.assertNotEqual(n.parent_key(CONFIG),n.parent_key(c))
 def test_manual_parent_fallback_crosses_classification_without_renewing_its_session(self):
  c=dict(CONFIG,sizing_mode='MANUAL_PARENT',manual_parent_value=300,manual_parent_entered_at=self.now)
  lease=n.session_scope(c,now=self.now)
  c.update(manual_parent_scope={k:c.get(k) for k in ('account','broker','underlying','market','asset')},manual_parent_session=lease['id'],manual_parent_valid_until=lease['valid_until'])
  with patch.object(n.time,'time',return_value=self.now):
   n.remember_manual(c)
   shared=self.root/'manual-session-fallback'/c['account']/(n.parent_key(c)+'.json')
   legacy=shared.with_name(n.key(c)+'.json');shared.rename(legacy)
   result=n.manual_fallback(dict(CONFIG,option_moneyness='ATM'))
   self.assertEqual(result['reference_value'],300);self.assertEqual(result['reference_context']['option_multiplier'],.5)
   self.assertEqual(result['manual_parent_entered_at'],self.now);self.assertEqual(result['reference_valid_until'],lease['valid_until'])
   stale=n.read_state(legacy);stale['manual_parent_valid_until']=self.now-1;n.atomic(shared,stale)
   self.assertIsNone(n.manual_fallback(dict(CONFIG,option_moneyness='ATM')))
