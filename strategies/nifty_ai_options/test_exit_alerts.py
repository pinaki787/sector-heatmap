import unittest
from exit_alerts import notices
class ExitNoticeTests(unittest.TestCase):
 def state(self,stage='UNRESOLVED_FILL',action='SELL'):
  return dict(position=dict(symbol='EXACT-CALL',quantity=20),pending=dict(key='one',stage=stage,intent=dict(action=action,timestamp=10,position=dict(symbol='EXACT-CALL',quantity=20))))
 def test_persistent_unknown_exit_uses_recorded_qty_and_never_invents_flat(self):
  import json
  state=self.state('FILLED_AWAITING_FLAT');state['pending']['filled_quantity']=20
  first=notices(state);second=notices(json.loads(json.dumps(state)))
  self.assertEqual(first,second);self.assertEqual(first[0]['severity'],'error')
  self.assertEqual(first[0]['recorded_quantity'],20);self.assertIsNone(first[0]['remaining_quantity'])
  self.assertFalse(first[0]['automatic_resubmission'])
 def test_pending_entry_and_historic_journal_do_not_prove_failed_exit(self):
  self.assertEqual(notices(self.state(action='BUY')),[])
  self.assertEqual(notices(dict(trade_journal=dict(rows=[dict(status='OPEN',symbol='OLD')]))),[])
 def test_notice_clears_only_when_retained_exit_state_is_cleared(self):
  state=self.state();self.assertEqual(len(notices(state)),1)
  state['position']=None;self.assertEqual(len(notices(state)),1)
  state['pending']=None;self.assertEqual(notices(state),[])
 def test_separate_closing_legs_preserve_each_warning(self):
  state=self.state();state['closing_legs']={'put':dict(position=dict(symbol='EXACT-PUT',quantity=10),pending=dict(key='two',intent=dict(action='SELL',timestamp=11,position=dict(symbol='EXACT-PUT')),stage='UNCERTAIN'))}
  self.assertEqual({r['symbol'] for r in notices(state)},{'EXACT-CALL','EXACT-PUT'})
 def test_direct_long_and_short_exits_are_supported(self):
  for action in ('CLOSE_LONG','CLOSE_SHORT'):
   self.assertEqual(len(notices(self.state(action=action))),1)
