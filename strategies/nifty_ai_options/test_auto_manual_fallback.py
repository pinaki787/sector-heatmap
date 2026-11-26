import unittest,tempfile,time
from pathlib import Path
from unittest.mock import patch
import native_sizing as n
import automatic_sizing as a
from test_native_sizing import DELTA
class FallbackTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=patch.object(n,'DATA',Path(self.tmp.name));self.data.start()
  c=dict(DELTA,sizing_mode='MANUAL_PARENT',manual_parent_value=300)
  lease=n.session_scope(c);c.update(manual_parent_scope={k:c.get(k) for k in ('account','broker','underlying','market','asset')},manual_parent_session=lease['id'],manual_parent_valid_until=lease['valid_until'],manual_parent_entered_at=time.time())
  self.manual=c;n.remember_manual(c);self.auto=dict(DELTA,sizing_mode='AUTO')
 def tearDown(self):self.data.stop();self.tmp.cleanup()
 def test_failure_uses_exact_session_manual_value_without_claiming_verified(self):
  with patch.object(n,'acquire',side_effect=ValueError('quota cooldown')):
   c=n.ensure(self.auto)
   self.assertEqual(c['reference_value'],300);self.assertTrue(c['sizing_fallback'])
   self.assertEqual(c['requested_sizing_mode'],'AUTO')
   self.assertEqual(c['reference_native_provider'],'USER');self.assertFalse(c['reference_context']['verified_native_size'])
   with patch.object(n,'acquire',side_effect=AssertionError('No repeat provider call')):
    self.assertEqual(n.ensure(c)['reference_value'],300)
 def test_success_precedes_manual_fallback(self):
  with patch.object(n,'acquire',return_value={}) as call,patch.object(n,'apply_reference',return_value={'native':'ok'}):
   self.assertEqual(n.ensure(self.auto),{'native':'ok'});call.assert_called_once()
 def test_different_instrument_account_and_expiry_never_reuse(self):
  for c in (dict(self.auto,underlying='BTCUSD'),dict(self.auto,account='b'*32)):
   with patch.object(n,'acquire',side_effect=ValueError('quota')):
    with self.assertRaisesRegex(ValueError,'quota'):n.ensure(c)
  path=n.DATA/'manual-session-fallback'/self.auto['account']/(n.parent_key(self.auto)+'.json')
  saved=n.read_state(path);saved['manual_parent_valid_until']=time.time()-1;n.atomic(path,saved)
  self.assertIsNone(n.manual_fallback(self.auto))
 def test_next_session_fetches_instead_of_reusing_expired_fallback(self):
  with patch.object(n,'acquire',side_effect=ValueError('quota')):c=n.ensure(self.auto)
  c['manual_parent_valid_until']=time.time()-1
  with patch.object(n,'acquire',return_value={}) as call,patch.object(n,'apply_reference',return_value={'native':'new'}):
   self.assertEqual(n.ensure(c),{'native':'new'});call.assert_called_once()
 def test_preview_uses_fallback_only_after_session_failure(self):
  self.assertIsNone(n.failed_session_fallback(self.auto))
  lease=n.session_scope(self.auto);n.atomic(n.session_path(self.auto),dict(session=lease['id'],state='FAILED',error='quota'))
  self.assertEqual(n.failed_session_fallback(self.auto)['reference_value'],300)
if __name__=='__main__':unittest.main()
