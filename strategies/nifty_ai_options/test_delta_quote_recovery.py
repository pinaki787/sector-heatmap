import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from . import delta_quote_recovery as recovery
from .delta_feed_health import FeedHealth

class QuoteRecoveryTests(unittest.TestCase):
 def fixture(self,owned=None):
  engine=SimpleNamespace(position=None,pending_direction=('LONG',1),entry_confirmation=SimpleNamespace(clear=Mock()),band=SimpleNamespace(consume_entry=Mock()))
  executor=SimpleNamespace(state=dict(position=owned,pending=None),save=Mock())
  return engine,executor
 def test_pre_submission_entry_is_discarded_without_order_retry(self):
  e,x=self.fixture();action=dict(action='OPEN_LONG',position=dict(symbol='BTCUSD',side='LONG'))
  result=recovery.defer_quote(e,x,action,ValueError(recovery.QUOTE_UNAVAILABLE),100)
  self.assertTrue(result['deferred']);self.assertEqual(result['orders_submitted'],0)
  self.assertIsNone(e.position);self.assertIsNone(e.pending_direction)
  self.assertFalse(x.state['quote_recovery']['retained_exit'])
  recovery.quote_recovered(x,101)
  self.assertFalse(x.state['quote_recovery']['entries_blocked'])
 def test_owned_exit_is_retained_and_retries_only_when_no_order_is_pending(self):
  owned=dict(symbol='BTCUSD',side='SHORT',quantity=100)
  e,x=self.fixture(owned);action=dict(action='CLOSE_SHORT',timestamp=1,position=dict(owned))
  recovery.defer_quote(e,x,action,ValueError(recovery.QUOTE_UNAVAILABLE),100)
  self.assertEqual(e.position,owned);self.assertEqual(x.state['quote_recovery_exit'],action)
  submit=Mock(return_value=dict(deferred=True))
  x.state['pending']={'key':'uncertain'}
  self.assertIsNone(recovery.retry_exit(e,x,submit));submit.assert_not_called()
  x.state['pending']=None;recovery.retry_exit(e,x,submit);submit.assert_called_once()
  submit.return_value=dict(filled_quantity=100)
  recovery.retry_exit(e,x,submit)
  self.assertIsNone(e.quote_exit_pending);self.assertNotIn('quote_recovery_exit',x.state)
 def test_lost_ownership_cancels_retained_exit_without_submission(self):
  e,x=self.fixture(dict(symbol='BTCUSD',side='LONG'))
  action=dict(action='CLOSE_LONG',position=dict(x.state['position']))
  recovery.defer_quote(e,x,action,ValueError(recovery.QUOTE_UNAVAILABLE),100)
  x.state['position']=None;send=Mock();recovery.retry_exit(e,x,send);send.assert_not_called()
 def test_other_errors_are_not_swallowed(self):
  e,x=self.fixture()
  with self.assertRaisesRegex(ValueError,'ownership mismatch'):
   recovery.defer_quote(e,x,{},ValueError('ownership mismatch'),100)
  x.save.assert_not_called()
 def test_quiet_feed_repair_continues_with_bounded_frequency(self):
  health=FeedHealth();broker=SimpleNamespace(source_health=lambda s:dict(connected=True,heartbeat_fresh=True,quote_fresh=False),subscribe_all=Mock())
  for at in range(0,301):
   result=health.check(broker,'BTCUSD',at,automatic=True)
   self.assertTrue(result['entries_blocked'])
  self.assertGreater(broker.subscribe_all.call_count,3);self.assertLess(broker.subscribe_all.call_count,25)
  broker.source_health=lambda s:dict(connected=False)
  self.assertEqual(health.check(broker,'BTCUSD',400,automatic=True)['state'],'RECONNECTING')
  broker.source_health=lambda s:dict(connected=True,heartbeat_fresh=True,quote_fresh=True)
  self.assertEqual(health.check(broker,'BTCUSD',401,automatic=True)['state'],'WAITING_FOR_TRADED_PRICE')

 def test_fresh_quote_resumes_without_submitting_and_stale_quote_repairs_are_throttled(self):
  e,x=self.fixture();recovery.defer_quote(e,x,dict(action='OPEN_LONG',position=dict(symbol='BTCUSD')),ValueError(recovery.QUOTE_UNAVAILABLE),100)
  broker=SimpleNamespace(quote=Mock(side_effect=ValueError(recovery.QUOTE_UNAVAILABLE)),subscribe_all=Mock())
  self.assertFalse(recovery.refresh_quote(x,broker,'BTCUSD',100));self.assertFalse(recovery.refresh_quote(x,broker,'BTCUSD',101))
  broker.subscribe_all.assert_called_once()
  broker.quote.side_effect=None;broker.quote.return_value=dict(bid=99,ask=100)
  self.assertTrue(recovery.refresh_quote(x,broker,'BTCUSD',102))
  self.assertFalse(x.state['quote_recovery']['entries_blocked'])
