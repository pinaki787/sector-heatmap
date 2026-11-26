import unittest
from unittest.mock import Mock
from strategies.nifty_ai_options.delta_feed_health import FeedHealth
class FeedHealthTests(unittest.TestCase):
 def test_quiet_contract_with_fresh_transport_and_quote_does_not_stop_or_refetch(self):
  broker=Mock();broker.source_health.return_value=dict(connected=True,heartbeat_fresh=True,quote_fresh=True)
  f=FeedHealth()
  for now in range(30,1000):
   state=f.check(broker,'PAXGUSD',now)
   self.assertEqual(state['state'],'WAITING_FOR_TRADED_PRICE');self.assertTrue(state['entries_blocked'])
  broker.subscribe_all.assert_not_called()
 def test_repairs_are_bounded_with_cooldown_and_no_order_calls(self):
  broker=Mock();broker.source_health.return_value=dict(connected=True,heartbeat_fresh=False,quote_fresh=False)
  f=FeedHealth()
  for now in range(30,60):f.check(broker,'PAXGUSD',now)
  self.assertEqual(broker.subscribe_all.call_count,3)
  with self.assertRaisesRegex(ValueError,'exhausted'):f.check(broker,'PAXGUSD',60)
  self.assertEqual(broker.subscribe_all.call_count,3)
  broker.place.assert_not_called()
 def test_fresh_heartbeat_alone_cannot_claim_quote_readiness(self):
  broker=Mock();broker.source_health.return_value=dict(connected=True,heartbeat_fresh=True,quote_fresh=False)
  self.assertEqual(FeedHealth().check(broker,'PAXGUSD',30)['state'],'RECOVERING_SUBSCRIPTION')
 def test_disconnect_requires_reconciliation(self):
  broker=Mock();broker.source_health.return_value=dict(connected=False)
  with self.assertRaisesRegex(ValueError,'reconciliation'):FeedHealth().check(broker,'PAXGUSD',30)
  broker.subscribe_all.assert_not_called()
 def test_fresh_tick_reset_allows_a_new_incident_without_replaying_orders(self):
  f=FeedHealth();f.attempts=3;f.next_retry=100;f.reset()
  self.assertEqual((f.attempts,f.next_retry),(0,0))

class TransportHealthTests(unittest.TestCase):
 def test_heartbeat_has_no_symbol_and_cannot_create_a_trade_tick(self):
  import tempfile
  from pathlib import Path
  from types import SimpleNamespace
  from strategies.renko_supertrend.delta_broker import Broker
  now=[1000.]
  with tempfile.TemporaryDirectory() as directory:
   broker=Broker(SimpleNamespace(clock=lambda:now[0]),Path(directory))
   broker.connected=True;broker.subscribe('PAXGUSD',60)
   broker.ingest(dict(type='heartbeat'),received=now[0])
   self.assertEqual(broker.ticks,{})
   self.assertTrue(broker.source_health('PAXGUSD')['heartbeat_fresh'])
   self.assertFalse(broker.source_health('PAXGUSD')['quote_fresh'])
   broker.ingest(dict(type='ob_l1',sy='PAXGUSD',ts=now[0]*1e6,bp=3560,ap=3561))
   self.assertTrue(broker.source_health('PAXGUSD')['quote_fresh'])
   now[0]+=36
   self.assertFalse(broker.source_health('PAXGUSD')['heartbeat_fresh'])
   self.assertFalse(broker.source_health('PAXGUSD')['quote_fresh'])
