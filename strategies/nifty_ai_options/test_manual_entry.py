import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from manual_entry import enqueue,ManualInbox,ManualDispatcher,ManualNotReady,runtime_identity
from direct import DirectStrategy
from core import Strategy
CONFIG=dict(account='a'*32,broker='DELTA_INDIA',underlying='BTCUSD',market='CRYPTO',timeframe=5,reference_value=46,execution_route='DIRECT',runtime_session='b'*32)
def payload(config,directory):
    expected=runtime_identity(config,directory,'PAPER')
    return expected,dict(expected,request_id='c'*32,direction='LONG')
class ManualEntryTests(unittest.TestCase):
    def test_command_is_bound_to_account_run_session_mode_symbol_and_direction(self):
        with tempfile.TemporaryDirectory() as directory:
            expected,request=payload(CONFIG,directory)
            for change in [dict(account_id='f'*32),dict(mode='LIVE'),dict(underlying='ETHUSD'),dict(run_id='other'),dict(runtime_session='d'*32),dict(direction='CE')]:
                with self.assertRaises(ValueError):enqueue(directory,expected,dict(request,**change),now=100)
            first=enqueue(directory,expected,request,now=100);self.assertEqual(enqueue(directory,expected,request,now=101),first)
            with self.assertRaisesRegex(ValueError,'pending'):enqueue(directory,expected,dict(request,request_id='d'*32),now=101)
    def test_claim_is_durable_once_only_and_expiry_or_new_session_cannot_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            expected,request=payload(CONFIG,directory);enqueue(directory,expected,request,now=100)
            inbox=ManualInbox(CONFIG,directory,'PAPER',clock=lambda:101);self.assertIsNotNone(inbox.claim());self.assertIsNone(inbox.claim())
            self.assertIsNone(ManualInbox(CONFIG,directory,'PAPER',clock=lambda:102).claim())
        with tempfile.TemporaryDirectory() as directory:
            expected,request=payload(CONFIG,directory);enqueue(directory,expected,request,now=100)
            self.assertIsNone(ManualInbox(CONFIG,directory,'PAPER',clock=lambda:131).claim())
            self.assertEqual(json.loads((Path(directory)/'manual-entry/latest.json').read_text())['phase'],'REJECTED')
        with tempfile.TemporaryDirectory() as directory:
            expected,request=payload(CONFIG,directory);enqueue(directory,expected,request,now=100)
            self.assertIsNone(ManualInbox(dict(CONFIG,runtime_session='d'*32),directory,'PAPER',clock=lambda:101).claim())
    def test_dispatch_waits_for_quote_then_confirms_owned_fill_once(self):
        with tempfile.TemporaryDirectory() as directory:
            expected,request=payload(CONFIG,directory);enqueue(directory,expected,request,now=100)
            engine=DirectStrategy(CONFIG);executor=SimpleNamespace(state=dict(position=None,pending=None));prepared=Mock();ready=Mock(side_effect=[ManualNotReady('waiting'),101]);orders=[]
            def submit(action):
                orders.append(action);executor.state['position']=dict(action['position'],quantity=2,fill_price=100);return dict(dry_run=True)
            dispatcher=ManualDispatcher(CONFIG,directory,'PAPER',engine,executor,prepare=prepared,quote_ready=ready,submit=submit,clock=lambda:101)
            dispatcher.poll();self.assertEqual(orders,[]);dispatcher.poll();dispatcher.poll()
            self.assertEqual(len(orders),1);prepared.assert_called_once_with('LONG')
            result=json.loads((Path(directory)/'manual-entry/latest.json').read_text());self.assertEqual(result['phase'],'FILLED');self.assertTrue(result['strategy_exits_active'])
    def test_uncertain_submission_is_never_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            expected,request=payload(CONFIG,directory);enqueue(directory,expected,request,now=100)
            engine=DirectStrategy(CONFIG);executor=SimpleNamespace(state=dict(position=None,pending=None));submit=Mock(side_effect=RuntimeError('unknown fill'))
            dispatcher=ManualDispatcher(CONFIG,directory,'PAPER',engine,executor,prepare=lambda side:None,quote_ready=lambda:101,submit=submit,clock=lambda:101)
            with self.assertRaisesRegex(RuntimeError,'unknown fill'):dispatcher.poll()
            self.assertEqual(json.loads((Path(directory)/'manual-entry/latest.json').read_text())['phase'],'FAILED_OR_PENDING')
            new=ManualDispatcher(CONFIG,directory,'PAPER',engine,executor,prepare=lambda side:None,quote_ready=lambda:101,submit=submit,clock=lambda:102);new.poll();submit.assert_called_once()
    def test_manual_direct_position_uses_normal_supertrend_exit(self):
        engine=DirectStrategy(CONFIG)
        for i,price in enumerate([100,102,104,106,108,110]):engine.update(dict(kind='underlying',timestamp=100+i*300,close=price));engine.position=None
        action=engine.manual_entry('LONG',2000);self.assertTrue(action['manual_override'])
        exits=[]
        for i,price in enumerate([108,106,104,102,100,98,96]):exits+=engine.update(dict(kind='underlying',timestamp=2100+i*300,close=price))
        self.assertTrue(any(a['action']=='CLOSE_LONG' and a['reason']=='AI_RENKO_SUPERTREND_UNDERLYING' for a in exits))
    def test_manual_option_position_uses_normal_premium_exit(self):
        engine=Strategy(dict(reference_value=12,market='NSE',timeframe=5));engine.reset_contract(dict(symbol='CALL',option_type='CE'),.2)
        for i,price in enumerate([40,41,42,43,44,45]):engine.update(dict(kind='premium',symbol='CALL',timestamp=100+i*300,close=price))
        engine.manual_entry('CE',2000);exits=[]
        for i,price in enumerate([44,43,42,41,40,39,38]):exits+=engine.update(dict(kind='premium',symbol='CALL',timestamp=2100+i*300,close=price))
        self.assertTrue(any(a['action']=='SELL' and a['reason']=='AI_RENKO_SUPERTREND_PREMIUM' for a in exits))
    def test_manual_override_never_adopts_existing_position_or_cash_short(self):
        engine=DirectStrategy(dict(CONFIG,product='CNC'))
        with self.assertRaises(ValueError):engine.manual_entry('SHORT',100)
        engine.manual_entry('LONG',100)
        with self.assertRaises(ValueError):engine.manual_entry('LONG',101)

class ManualServiceTests(unittest.TestCase):
    def service(self,folder,mode='PAPER'):
        import ui_bridge,threading
        directory=Path(folder)/'run';directory.mkdir();(directory/'config.json').write_text(json.dumps(CONFIG))
        service=ui_bridge.Service.__new__(ui_bridge.Service);service.owner=CONFIG['account'];service.lock=threading.RLock();service.run=dict(id='run',directory=directory,mode=mode);service.process=Mock();service.process.poll.return_value=None
        service.snapshot=Mock(return_value=dict(running=True,manual_entry_ready=True,native_acquisition_ready=True,heartbeat=dict(position=None,pending=None,native_sizing=dict(state='READY'))))
        expected,request=payload(CONFIG,directory);request['mode']=mode
        return service,request,directory
    def test_active_manual_request_queues_without_starting_process_or_calling_broker(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            service,request,directory=self.service(folder)
            with patch('ui_bridge.owner_broker',return_value='DELTA_INDIA'),patch('ui_bridge.subprocess.Popen') as start:
                response=service.manual_entry(request)
            self.assertEqual(response['manual_entry']['phase'],'QUEUED');start.assert_not_called();self.assertTrue((directory/'manual-entry/command.json').exists())
    def test_manual_request_refuses_stale_runtime_and_exposure(self):
        from unittest.mock import patch
        for change in [dict(manual_entry_ready=False),dict(heartbeat=dict(position={'symbol':'BTCUSD'},pending=None,native_sizing=dict(state='READY'))),dict(heartbeat=dict(position=None,pending={'id':'unknown'},native_sizing=dict(state='READY'))),dict(heartbeat=dict(position=None,pending=None,native_sizing=dict(state='WAITING_FOR_NATIVE_SIZE')))]:
            with tempfile.TemporaryDirectory() as folder:
                service,request,directory=self.service(folder);service.snapshot.return_value.update(change)
                with patch('ui_bridge.owner_broker',return_value='DELTA_INDIA'),self.assertRaises(ValueError):service.manual_entry(request)
                self.assertFalse((directory/'manual-entry/command.json').exists())
    def test_manual_request_cannot_switch_live_mode_or_symbol(self):
        from unittest.mock import patch
        for change in [dict(mode='LIVE'),dict(underlying='ETHUSD'),dict(account_id='f'*32),dict(timeframe=1)]:
            with tempfile.TemporaryDirectory() as folder:
                service,request,directory=self.service(folder)
                with patch('ui_bridge.owner_broker',return_value='DELTA_INDIA'),self.assertRaises(ValueError):service.manual_entry(dict(request,**change))
                self.assertFalse((directory/'manual-entry/command.json').exists())
    def test_revoked_live_capability_blocks_manual_entry(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            service,request,directory=self.service(folder,'LIVE')
            with patch('ui_bridge.owner_broker',return_value='DELTA_INDIA'),patch('ui_bridge.live_capability',return_value=False),self.assertRaises(ValueError):service.manual_entry(request)
            self.assertFalse((directory/'manual-entry/command.json').exists())

class LatestQuoteTests(unittest.TestCase):
    def test_selected_symbol_cache_never_rewinds_or_uses_stale_quote(self):
        from manual_entry import LatestQuote
        now=[100];cache=LatestQuote('EXACT',clock=lambda:now[0])
        self.assertFalse(cache.accept(dict(symbol='OTHER',exch_feed_time=100,ltp=10)))
        self.assertTrue(cache.accept(dict(symbol='EXACT',exch_feed_time=100,ltp=10)))
        self.assertFalse(cache.accept(dict(symbol='EXACT',exch_feed_time=99,ltp=9)))
        self.assertEqual(cache.get()['ltp'],10);now[0]=106
        with self.assertRaises(ManualNotReady):cache.get()
    def test_new_quote_arriving_during_exit_is_used_for_reverse_entry(self):
        from manual_entry import LatestQuote
        now=[100];cache=LatestQuote('EXACT',clock=lambda:now[0]);cache.accept(dict(symbol='EXACT',exch_feed_time=100,ltp=10))
        initial=cache.get();now[0]=102;cache.accept(dict(symbol='EXACT',exch_feed_time=102,ltp=12))
        self.assertEqual(initial['ltp'],10);self.assertEqual(cache.get()['ltp'],12)

class DeferredOwnershipTests(unittest.TestCase):
    def test_unsubmitted_exit_preserves_actual_fill_confirmation(self):
        from types import SimpleNamespace
        from manual_entry import restore_unsubmitted
        from hybrid_confirmation import confirm_exit
        engine=SimpleNamespace(position=None,pending_direction=('SHORT',112))
        executor=SimpleNamespace(state={'position':dict(symbol='EXACT',side='LONG',entry_timestamp=100,fill_price=101,quantity=1)})
        action=dict(action='CLOSE_LONG',position=dict(symbol='EXACT',side='LONG',entry_timestamp=100,entry_confirmed_at=110))
        restore_unsubmitted(engine,executor,action)
        self.assertEqual(engine.position['entry_confirmed_at'],110)
        self.assertEqual(engine.position['quantity'],1)
        self.assertIsNone(engine.pending_direction)
        unit=dict(kind='brick',closed=True,open=101,close=100,closed_at=105,available_at=115)
        self.assertIsNone(confirm_exit(unit,engine.position,'SHORT',102,1))
    def test_unsubmitted_entry_cannot_become_an_owned_position(self):
        from types import SimpleNamespace
        from manual_entry import restore_unsubmitted
        engine=SimpleNamespace(position={'symbol':'UNSUBMITTED'},pending_direction=('LONG',100))
        executor=SimpleNamespace(state={'position':None})
        restore_unsubmitted(engine,executor,dict(action='OPEN_LONG',position={'symbol':'UNSUBMITTED'}))
        self.assertIsNone(engine.position);self.assertIsNone(engine.pending_direction)
