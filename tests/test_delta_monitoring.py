import unittest
from copy import deepcopy
from unittest.mock import patch,Mock
from sector_heatmap.delta_india import DeltaIndia,DeltaReadUnavailable
from sector_heatmap.delta_monitoring import health,saved_paper_config
from sector_heatmap.auth_refresh import refresh_fyers_session
from tests import test_delta_atm_runner as fixture
class Tests(unittest.TestCase):
 setUp=fixture.AtmOptionRunner.setUp
 signal=fixture.AtmOptionRunner.signal
 config=fixture.AtmOptionRunner.config
 def enter(self):
  self.b.start_runner(self.config());self.req.now+=300;self.signal('BEARISH');self.b.runner_tick();return self.b.paper['position']
 def restart(self):return DeltaIndia(self.b.path,requester=self.b.requester,clock=self.b.clock)
 def test_restart_recovers_exit_only_with_position_settings_and_no_entry_when_flat(self):
  pos=self.enter();restarted=self.restart();self.assertFalse(restarted.runner['running']);self.assertTrue(restarted.paper['position']['monitoring']['enabled'])
  restarted.product=self.b.product;restarted.ticker=self.b.ticker;restarted.chart=self.b.chart
  restarted.restore_exit_monitor(dict(mode='PAPER',_startup=True));self.assertTrue(restarted.runner['exit_only']);self.assertEqual(restarted.runner['config']['symbol'],'BTCUSD');self.assertEqual(restarted.runner['config']['resolution'],'5m')
  restarted.paper['position']=None;self.req.now+=300
  restarted.runner_tick();self.assertFalse(restarted.runner['running']);self.assertEqual(len(restarted.paper['trades']),1)
 def test_startup_supervisor_restores_only_recorded_active_monitoring(self):
  self.enter();restarted=self.restart();restarted.product=self.b.product;restarted.ticker=self.b.ticker;restarted.chart=self.b.chart
  class Event:
   stopped=False
   def is_set(self):return self.stopped
   def wait(self,n):self.stopped=True
  restarted.monitoring_stop=Event()
  with patch('threading.Thread') as thread:
   restarted.start_monitoring_supervisor();target=thread.call_args.kwargs['target'];target()
  self.assertTrue(restarted.runner['running']);self.assertTrue(restarted.runner['exit_only'])
  restarted.stop_runner();again=self.restart();again.monitoring_stop=Event()
  with patch('threading.Thread') as thread:
   again.start_monitoring_supervisor();thread.call_args.kwargs['target']()
  self.assertFalse(again.runner['running']);self.assertTrue(again.monitoring_alerts['PAPER']['alert'])
 def test_intentional_stop_survives_restart_and_blocks_auto_recovery(self):
  self.enter();self.b.stop_runner();restarted=self.restart()
  self.assertFalse(restarted.paper['position']['monitoring']['enabled'])
  with self.assertRaisesRegex(ValueError,'Intentional stop'):restarted.restore_exit_monitor(dict(mode='PAPER',_startup=True))
 def test_explicit_restore_reconciles_lifecycle_and_preserves_trailing_stop(self):
  pos=self.enter();pos['trailing']={'stop':'100','mode':'ATR'};self.b._save();self.b.stop_runner();old=deepcopy(pos['trailing'])
  self.b.restore_exit_monitor(dict(mode='PAPER',lifecycle_id=pos['lifecycle_id']));self.assertEqual(pos['trailing'],old)
  self.b.stop_runner();self.b.paper['trades'][-1]['remaining_contracts']=999
  with self.assertRaisesRegex(ValueError,'reconcile'):self.b.restore_exit_monitor(dict(mode='PAPER'))
 def test_missing_entry_settings_are_not_inferred_from_current_chart(self):
  with self.assertRaisesRegex(ValueError,'not recorded'):saved_paper_config(dict(contracts=10,symbol='TEST'))
 def test_disconnect_and_reconnect_keep_exit_intent_and_one_latched_exit(self):
  pos=self.enter();self.b.runner['exit_only']=True;self.req.now+=300;self.signal('BULLISH')
  with patch.object(self.b,'close_runner',side_effect=DeltaReadUnavailable('offline')):
   with self.assertRaises(DeltaReadUnavailable):self.b.runner_tick()
  self.assertIn('runner_exit_signal',pos);self.assertTrue(pos['monitoring']['enabled'])
  self.b.runner_tick();self.b.runner_tick();self.assertIsNone(self.b.paper['position']);self.assertFalse(self.b.runner['running']);self.assertEqual(len(self.b.paper['trades'][-1]['exit_fills']),1)
 def test_watchdog_alerts_for_inactive_stale_and_retrying_position(self):
  p=self.enter();self.b.stop_runner();self.assertTrue(self.b.status()['monitoring']['PAPER']['alert'])
  self.b.runner.update(running=True,exit_only=True);p['monitoring']['last_checked']=self.req.now-16
  self.assertEqual(health(p,self.b.runner,self.req.now)['state'],'STALE')
  self.b.runner['recovery']={'error':'offline'};self.assertEqual(health(p,self.b.runner,self.req.now)['state'],'RETRYING')
 def test_fyers_auth_refresh_replaces_only_fyers_resources_without_stopping_delta(self):
  p=self.enter();before=deepcopy(p);state={'renewing':True,'oauth_state':'test'};exchange=Mock();replace=Mock()
  refresh_fyers_session('test-code',exchange,lambda:{'FYERS_ACCESS_TOKEN':'test-token'},replace,state)
  exchange.assert_called_once_with('test-code');replace.assert_called_once_with('test-token');self.assertFalse(state['renewing']);self.assertTrue(self.b.runner['running']);self.assertEqual(p,before)
  with self.assertRaises(ValueError):refresh_fyers_session('bad',Mock(side_effect=ValueError('rejected')),lambda:{},replace,state)
  self.assertTrue(self.b.runner['running']);self.assertFalse(state['renewing'])
