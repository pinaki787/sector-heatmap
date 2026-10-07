import unittest
from copy import deepcopy
from .runner import analysis,price_state
from .test_signals import candle
from .test_intrabar import TickBroker
from . import test_runner as fixtures


class PriceContinuityTests(unittest.TestCase):
    def setUp(self):
        self.config={'underlying':'NSE:TEST','timeframe':'1 minute'}
        self.rows=[candle(i,100+i) for i in range(30)]

    def test_volume_revision_keeps_every_indicator_and_no_repeated_event(self):
        a=analysis(self.rows,self.config,.05);changed=deepcopy(self.rows);changed[5]['volume']=66889
        b=analysis(changed,self.config,.05,a)
        self.assertEqual(price_state(a['state']),price_state(b['state']))
        self.assertEqual(a['last'],b['last']);self.assertEqual(a['rows'],b['rows'])

    def test_legacy_migration_requires_exact_full_state_reproduction(self):
        a=analysis(self.rows,self.config,.05);a.pop('price_fingerprints')
        changed=deepcopy(self.rows);changed[5]['volume']=66889
        b=analysis(changed,self.config,.05,a)
        self.assertEqual(price_state(a['state']),price_state(b['state']))
        self.assertTrue(b['price_fingerprints'])
        changed[5]['high']+=3
        with self.assertRaisesRegex(ValueError,'price history changed'):analysis(changed,self.config,.05,a)
        with self.assertRaisesRegex(ValueError,'original history'):analysis(self.rows[1:],self.config,.05,a)

    def test_price_revisions_still_fail_closed(self):
        a=analysis(self.rows,self.config,.05)
        changed=deepcopy(self.rows);changed[5]['high']+=3
        with self.assertRaisesRegex(ValueError,'changed after processing'):analysis(changed,self.config,.05,a)

class ConfirmedPreflightTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    start=fixtures.RenkoLifecycleTests.start
    def test_confirmed_entry_does_not_add_an_intrabar_signal_gate(self):
        self.b=TickBroker();self.r.adapter=self.b;self.c['intrabar_entries']=False
        self.b.forming=lambda *args: (_ for _ in ()).throw(ValueError('forming unavailable'))
        self.start();self.r.step()
        self.assertIsNotNone(self.r.state['position'])

    def test_executable_marker_comes_from_same_signal_as_actual_owned_entry(self):
        self.start();self.r.step()
        first=self.r.snapshot()['execution_signals']
        self.assertEqual(len(first),1);self.assertEqual(first[0]['status'],'FILLED')
        self.assertEqual(first[0]['event_at'],self.r.state['order_history'][0]['entry_event_at'])
        self.r.step();self.assertEqual(self.r.snapshot()['execution_signals'],first)
        self.assertEqual(len(self.r.state['order_history']),1);self.assertEqual(self.b.sent,[])

    def test_blocked_entry_keeps_signal_and_exact_preflight_reason(self):
        self.start()
        self.b.quote=lambda s:(_ for _ in ()).throw(ValueError('Executable bid unavailable'))
        with self.assertRaises(ValueError):self.r.step()
        self.r.state.update(status='BLOCKED',message='Executable bid unavailable')
        event=self.r.snapshot()['execution_signals'][0]
        self.assertEqual(event['status'],'BLOCKED');self.assertEqual(event['reason'],'Executable bid unavailable')
        self.assertIsNone(self.r.state['position']);self.assertFalse(self.r.state.get('order_history'))
