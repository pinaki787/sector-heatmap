import unittest,tempfile,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from test_delta_execution import PRODUCT
import delta_live
class RuntimeTests(unittest.TestCase):
    def test_offline_direct_stream_routes_long_exit_short_with_actual_indicator(self):
        self.run_runtime()
    def test_active_timeframe_change_preserves_position_and_price_decisions(self):
        self.run_runtime(reconfigure=True)
    def test_live_direct_branch_uses_fake_executor(self):
        self.run_runtime(live=True)
    def test_manual_direct_entry_uses_normal_runtime_exit(self):
        self.run_runtime(manual=True)
    def test_quiet_price_pause_keeps_worker_alive_without_order_replay(self):
        self.run_runtime(quiet=True)
    def run_runtime(self,reconfigure=False,live=False,manual=False,hybrid=False,quiet=False):
        delta=Mock();delta.product.return_value=PRODUCT;delta.current=120;delta.price=100;delta.clock.side_effect=lambda:delta.current
        prices={120+i*60:price for i,price in enumerate([100,102,104,106,108,110,108,106,104,102,100,98,96,94,92,90])}
        delta._get.side_effect=lambda path,params:dict(result=[dict(time=params['start'],open=prices[params['start']],high=prices[params['start']]+.1,low=prices[params['start']]-.1,close=prices[params['start']])])
        instances={};monotonic=[0];quiet_injected=[False]
        class FakeQueue:
            def __init__(self,*a,**kw):self.rows=[]
            def put_nowait(self,tick):self.rows.append(tick)
            def get(self,**kw):
                if not self.rows:raise ValueError('offline fixture completed')
                if quiet and len(self.rows)==10 and not quiet_injected[0]:
                    import queue
                    quiet_injected[0]=True;monotonic[0]=40
                    raise queue.Empty

                if reconfigure and len(self.rows)==11:
                    from runtime_control import enqueue
                    enqueue(folder/'run',config,dict(account_id=config['account'],broker=config['broker'],run_id='run',runtime_session=config['runtime_session'],underlying='BTCUSD',timeframe=5))
                tick=self.rows.pop(0);delta.current=tick['exch_feed_time'];delta.price=tick['ltp']
                if manual and len(self.rows)==15:
                    from manual_entry import runtime_identity,enqueue
                    expected=runtime_identity(config,folder/'run','LIVE' if live else 'PAPER')
                    enqueue(folder/'run',expected,dict(expected,direction='LONG',request_id='c'*32),now=delta.current)
                return tick
        class FakeBroker:
            def __init__(self,d,out,on_tick):self.callback=on_tick;self.stopped=False;instances['broker']=self
            def subscribe(self,*a):pass
            def start(self):
                for i,price in enumerate([100,102,104,106,108,110,108,106,104,102,100,98,96,94,92,90]):self.callback(dict(symbol='BTCUSD',exch_feed_time=135+i*60,ltp=price))
            def stream_status(self):return dict(connected=True,generation=1)
            def source_health(self,*a):return dict(connected=True,heartbeat_fresh=True,quote_fresh=True)
            def subscribe_all(self):raise AssertionError('Healthy quiet stream must not resubscribe')
            def tick(self,*a):return dict(exch_feed_time=delta.current)
            def quote(self,*a):return dict(bid=delta.price,ask=delta.price+.5,exchange_at=delta.current,received_at=delta.current)
            def stop(self):self.stopped=True
        class FakeExecutor:
            def __init__(self,*a,**kw):self.state=dict(position=None,pending=None);self.actions=[];self.submitted_at=[];instances['executor']=self
            def submit(self,action,quote):
                self.actions.append(action);self.submitted_at.append(delta.current);self.state['position']=dict(action['position'],quantity=1) if action['action'].startswith('OPEN_') else None
                return dict(dry_run=True,simulated_fill=quote['ask'])
            def save(self):(folder/'executor-state.json').write_text(json.dumps(self.state))
            def close(self):pass
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);config=dict(runtime_session='b'*32,account='a'*32,broker='DELTA_INDIA',underlying='BTCUSD',reference_symbol='BTCUSD',market='CRYPTO',execution_route='DIRECT',timeframe=1,reference_value=46,reference_session='fixture',reference_evidence='offline test only',lots=1,accept_close_source_renko_approximation=True)
            if hybrid:config['calculation_mode']='HYBRID'
            (folder/'config.json').write_text(json.dumps(config));args=SimpleNamespace(config=str(folder/'config.json'),output=str(folder/'run'),live=live)
            import manual_entry,os
            original_dispatch=manual_entry.ManualDispatcher
            with patch('delta_live.time.monotonic',side_effect=lambda:monotonic[0]),patch('delta_live.live_readiness'),patch('delta_live.ManualDispatcher',side_effect=lambda *args,**kwargs:original_dispatch(*args,**kwargs,clock=lambda:delta.current)),patch.dict(os.environ,{'AI_RENKO_LIVE_ORDERS':'I_ACCEPT_REAL_ORDERS'}):
                with patch('delta_live.runtime_configuration',side_effect=lambda config,output:config),patch('delta_live.automatic_strategy',side_effect=lambda engine,*a,**kw:engine),patch('delta_live.bound_delta',return_value=delta),patch('delta_live.history',return_value=[[0,100,100.1,99.9,100,None],[60,100,100.1,99.9,100,None]] if hybrid else [[0,None,None,None,100,None],[60,None,None,None,100,None]]),patch('delta_live.SourceBroker',FakeBroker),patch('delta_live.DeltaExecution',FakeExecutor),patch('delta_live.queue.Queue',FakeQueue),self.assertRaisesRegex(ValueError,'offline fixture completed'):
                    delta_live.stream(args)
            if quiet:
                health=json.loads((folder/'run/source-health.json').read_text());self.assertEqual(health['state'],'WAITING_FOR_TRADED_PRICE');self.assertTrue(health['entries_blocked'])
            actions=[a['action'] for a in instances['executor'].actions]
            self.assertIn('OPEN_LONG',actions);self.assertIn('CLOSE_LONG',actions);self.assertIn('OPEN_SHORT',actions)
            exit_index=actions.index('CLOSE_LONG');reverse_index=actions.index('OPEN_SHORT')
            self.assertEqual(reverse_index,exit_index+1)
            self.assertEqual(instances['executor'].submitted_at[exit_index],instances['executor'].submitted_at[reverse_index])
            self.assertTrue(instances['broker'].stopped)
            self.assertEqual(json.loads((folder/'run/heartbeat.json').read_text())['mode'],'LIVE' if live else 'PAPER')
            if manual:self.assertTrue(instances['executor'].actions[0].get('manual_override'))
            series=[p for p in (folder/'run/chart-source').glob('*.json') if not p.name.endswith('-meta.json')]
            if reconfigure:
                self.assertEqual(json.loads((folder/'run/config.json').read_text())['timeframe'],5)
                self.assertEqual(json.loads((folder/'run/reconfigure.json').read_text())['phase'],'APPLIED')
                series=[p for p in series if json.loads(p.read_text())['frame']==5]
            self.assertEqual(len(series),1)
            source=json.loads(series[0].read_text())
            events=[json.loads(line)['event'] for line in (folder/'run/events.jsonl').read_text().splitlines() if 'event' in json.loads(line)]
            candles=[e for e in events if e['kind']!='price']
            prices=[e for e in events if e['kind']=='price']
            if not reconfigure and not hybrid:self.assertEqual(source['rows'][2:],[[event['timestamp'],None,None,None,event['close'],None] for event in candles])
            self.assertTrue(all(event['source_basis']=='PROVIDER_CONFIRMED_CLOSE' for event in candles))
            captured=[json.loads(line) for path in [series[0].with_name(series[0].stem+'-observations.jsonl')] for line in path.read_text().splitlines()]
            self.assertEqual(captured,prices)
            self.assertEqual([e['sequence'] for e in prices],list(range(1,len(prices)+1)))
            self.assertTrue(all(e['source_basis']=='BROKER_LIVE_PRICE' for e in prices))
            self.assertTrue(any(a['timestamp'] not in [e['timestamp'] for e in candles] for a in instances['executor'].actions))

            delta._private.assert_not_called()
    def test_verification_config_cannot_start_delta_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.json';path.write_text(json.dumps({'_verification_only':True}))
            with patch('delta_live.bound_delta') as client,self.assertRaisesRegex(ValueError,'Verification-only'):
                delta_live.stream(SimpleNamespace(config=str(path),live=False))
            client.assert_not_called()


class DeltaLiveReadinessTests(unittest.TestCase):
    def test_live_preflight_authenticates_and_refuses_external_selected_position(self):
        from delta_live import live_readiness
        from unittest.mock import Mock,patch
        delta=Mock();delta.product.return_value={'id':27};delta._position.return_value=-50
        with patch('strategies.renko_supertrend.delta_execution.Execution') as native:
            native.return_value.active_orders.return_value=[]
            with self.assertRaisesRegex(ValueError,'existing broker exposure'):
                live_readiness(delta,['BTCUSD'])
            native.return_value.authenticate.assert_called_once();delta.submit.assert_not_called()
    def test_live_preflight_checks_exact_contract_pending_orders_without_placement(self):
        from delta_live import live_readiness
        from unittest.mock import Mock,patch
        delta=Mock();delta.product.return_value={'id':27};delta._position.return_value=0
        with patch('strategies.renko_supertrend.delta_execution.Execution') as native:
            native.return_value.active_orders.return_value=[dict(product_id=27)]
            with self.assertRaisesRegex(ValueError,'active order'):live_readiness(delta,['BTCUSD'])
            delta.submit.assert_not_called()

class DeltaCompletedHybridDirectRuntimeTests(RuntimeTests):
 def test_completed_unit_hybrid_direct_execution_and_reversal_through_mock_worker(self):self.run_runtime(hybrid=True)
