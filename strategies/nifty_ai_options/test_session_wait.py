import unittest
from datetime import datetime
from session_wait import SessionWait,IST

class SessionWaitTests(unittest.TestCase):
    def test_closed_start_open_close_and_next_open(self):
        now=[datetime(2026,11,25,8,tzinfo=IST).timestamp()];calls=[]
        gate=SessionWait(lambda:calls.append(now[0]) or True,555,930,clock=lambda:now[0])
        self.assertFalse(gate.poll());self.assertEqual(calls,[])
        now[0]+=75*60
        self.assertTrue(gate.poll());self.assertTrue(gate.changed)
        self.assertTrue(gate.poll());self.assertFalse(gate.changed);self.assertEqual(len(calls),1)
        now[0]=datetime(2026,11,25,16,tzinfo=IST).timestamp()
        self.assertFalse(gate.poll());self.assertTrue(gate.changed)
        now[0]=datetime(2026,11,26,9,15,tzinfo=IST).timestamp()
        self.assertTrue(gate.poll());self.assertTrue(gate.changed)
    def test_broker_closed_and_unknown_never_ready(self):
        now=[datetime(2026,11,25,10,tzinfo=IST).timestamp()]
        def failed():raise ValueError("private broker detail")
        gate=SessionWait(failed,555,930,clock=lambda:now[0])
        self.assertFalse(gate.poll());self.assertEqual(gate.state,"WAITING_FOR_MARKET_STATUS")
        self.assertNotIn("private",str(gate.snapshot()))
        gate.check=lambda:False;now[0]+=16
        self.assertFalse(gate.poll());self.assertEqual(gate.state,"WAITING_FOR_MARKET")

    def test_late_open_recovers_bodies_without_replaying_prices_or_orders(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from session_wait import reconcile_bodies
        opening=datetime(2026,11,25,9,15,tzinfo=IST).timestamp()
        owned=dict(side='LONG',symbol='EXACT')
        engine=SimpleNamespace(last_time={'underlying':opening-86400},position=owned,pending_direction=('LONG',1),update=Mock())
        confirmed=Mock()
        confirmed.confirm.side_effect=lambda event,*a,**kw:dict(event,close=100,source_basis='PROVIDER_CONFIRMED_CLOSE')
        result=reconcile_bodies(engine,confirmed,[('underlying','EXACT')],5,opening+7*60,555)
        self.assertEqual(len(result),1)
        self.assertEqual(engine.last_time['underlying'],opening)
        self.assertIs(engine.position,owned);engine.update.assert_not_called()
        self.assertIsNone(engine.pending_direction)
        self.assertEqual(confirmed.confirm.call_args.kwargs['previous'],opening-86400)
    def test_missing_recovery_body_stops_before_cursor_advance(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from session_wait import reconcile_bodies
        opening=datetime(2026,11,25,9,15,tzinfo=IST).timestamp()
        engine=SimpleNamespace(last_time={'underlying':opening-86400},position={'owned':True})
        confirmed=Mock();confirmed.confirm.side_effect=ValueError('Exact completed provider close unavailable')
        with self.assertRaises(ValueError):reconcile_bodies(engine,confirmed,[('underlying','EXACT')],5,opening+7*60,555)
        self.assertEqual(engine.last_time['underlying'],opening-86400)
        self.assertEqual(engine.position,{'owned':True})

    def test_reopening_reconnect_is_once_and_uses_external_saved_auth_loader(self):
        from unittest.mock import Mock
        from session_wait import ReopenConnection
        callback=Mock();connection=ReopenConnection(callback)
        self.assertFalse(connection.observe(True));callback.assert_not_called()
        connection.observe(False);connection.observe(False)
        self.assertTrue(connection.observe(True));callback.assert_called_once_with()
        self.assertFalse(connection.observe(True));self.assertEqual(callback.call_count,1)
    def test_failed_reconnect_remains_pending_for_next_attempt(self):
        from unittest.mock import Mock
        from session_wait import ReopenConnection
        callback=Mock(side_effect=ValueError('offline failure'))
        connection=ReopenConnection(callback);connection.observe(False)
        with self.assertRaises(ValueError):connection.observe(True)
        self.assertTrue(connection.saw_closed);self.assertFalse(connection.restarting)

    def test_recovered_adverse_sma_waits_for_a_fresh_executable_price(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from session_wait import reconcile_bodies
        opening=datetime(2026,11,25,9,15,tzinfo=IST).timestamp()
        owned={'symbol':'EXACT','side':'LONG'}
        engine=SimpleNamespace(last_time={'underlying':opening-86400,'sma':opening-86400},position=owned,sma=SimpleNamespace(previous=-1),update=Mock())
        confirmed=Mock();confirmed.confirm.side_effect=lambda event,*a,**kw:dict(event,source_basis='PROVIDER_CONFIRMED_CLOSE')
        reconcile_bodies(engine,confirmed,[('underlying','EXACT')],5,opening+60,555,sma_enabled=True)
        self.assertIs(engine.position,owned);self.assertTrue(engine.session_sma_exit_pending)
        engine.update.assert_called_once()

    def test_daily_broker_bounds_refresh_precedes_clock_filter(self):
        from unittest.mock import Mock
        now=[datetime(2026,11,25,23,40,tzinfo=IST).timestamp()]
        bounds=Mock(return_value=dict(opening_minutes=540,closing_minutes=1435))
        gate=SessionWait(lambda:True,540,1410,clock=lambda:now[0],bounds=bounds)
        self.assertTrue(gate.poll());self.assertEqual(gate.closing,1435);bounds.assert_called_once()
        gate.poll();bounds.assert_called_once()
        now[0]=datetime(2026,11,26,9,0,tzinfo=IST).timestamp()
        self.assertTrue(gate.poll());self.assertEqual(bounds.call_count,2)
    def test_unknown_new_day_bounds_blocks_session_without_reusing_stale_hours(self):
        from unittest.mock import Mock
        now=[datetime(2026,11,25,10,tzinfo=IST).timestamp()]
        bounds=Mock(side_effect=ValueError('missing selected master'))
        gate=SessionWait(lambda:True,555,930,clock=lambda:now[0],bounds=bounds)
        self.assertFalse(gate.poll());self.assertEqual(gate.state,'WAITING_FOR_MARKET_STATUS')
        gate.poll();bounds.assert_called_once()
        now[0]+=16;gate.poll();self.assertEqual(bounds.call_count,2)


class SavedAccountSessionTests(unittest.TestCase):
    def test_changed_saved_session_is_reused_without_login_or_file_mutation(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import Mock
        from session_wait import SavedAccountSession
        with tempfile.TemporaryDirectory() as folder:
            token=Path(folder)/'token.json';token.write_text('old')
            old,new=Mock(),Mock();load=Mock(return_value=new);verify=Mock();apply=Mock()
            session=SavedAccountSession(old,[token],load=load,verify=verify,apply=apply)
            self.assertIs(session.refresh(),old);load.assert_not_called()
            token.write_text('new saved session')
            self.assertIs(session.refresh(),new);load.assert_called_once();verify.assert_called_once_with(new);apply.assert_called_once_with(new)
            old._sector_pulse_ipv4_session.close.assert_called_once()
            self.assertEqual(token.read_text(),'new saved session')
            session.refresh();self.assertEqual(load.call_count,1)
    def test_mismatched_new_session_never_replaces_the_owned_account(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock
        from session_wait import SavedAccountSession
        with tempfile.TemporaryDirectory() as folder:
            token=Path(folder)/'token.json';token.write_text('old')
            old,new=Mock(),Mock();apply=Mock()
            session=SavedAccountSession(old,[token],load=lambda:new,verify=Mock(side_effect=ValueError('owner mismatch')),apply=apply)
            token.write_text('changed')
            with self.assertRaises(ValueError):session.refresh()
            self.assertIs(session.current,old);apply.assert_not_called();old._sector_pulse_ipv4_session.close.assert_not_called();new._sector_pulse_ipv4_session.close.assert_called_once()
