import unittest,tempfile,json
from pathlib import Path
from unittest.mock import Mock,patch
from ui_bridge import configuration,Service
PAYLOAD=dict(account_id='owner',broker='FYERS',underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',lots=1,ai_product='MARGIN',ai_expiry='1795428600',ai_reference_symbol='NSE:NIFTY50-INDEX',ai_reference_session='2026-11-19',ai_reference_value=400,ai_reference_evidence='fixture',mode='PAPER')
class Tests(unittest.TestCase):
    def setUp(self):
        bound=patch('ui_bridge.owner_broker',return_value='FYERS');bound.start();self.addCleanup(bound.stop)
        reference=patch('native_reference.resolve_reference',return_value=dict(native_box=400,reference_session='2026-11-19',source='unit fixture',url='fixture'));reference.start();self.addCleanup(reference.stop)

    def test_sma_only_has_no_supertrend_configuration_gate(self):
        for source in ('UNDERLYING','PREMIUM'):
            c=configuration(dict(PAYLOAD,ai_supertrend_enabled=False,ai_signal_source=source,ai_sma_band_period=10,ai_indicator_inputs={'factor':0},ai_ema_band_exit=True),'owner')
            self.assertFalse(c['supertrend_enabled'])
            self.assertEqual(c['strategy_signal_mode'],'SMA_BAND_ONLY')
            self.assertEqual(c['entry_gate'],'sma_band_only');self.assertEqual(c['exit_supertrend'],'disabled')
            self.assertTrue(c['sma_band_entry']);self.assertTrue(c['sma_band_exit'])
            self.assertFalse(c['ema_band_entry']);self.assertFalse(c['ema_band_exit'])
            self.assertEqual(c['sma_band_period'],10)
            self.assertEqual(c['band_price_basis'],source.lower())
        self.assertTrue(configuration(PAYLOAD,'owner')['supertrend_enabled'])

    def test_explicit_expiry_is_preserved_only_with_new_policy(self):
        with patch('ui_bridge.time.time',return_value=100):
            c=configuration(dict(PAYLOAD,ai_expiry_policy='explicit_listed',ai_expiry='300'),'owner')
            self.assertEqual(c['expiry'],'300')
            self.assertEqual(c['expiry_policy'],'explicit_listed')
            with self.assertRaises(ValueError):configuration(dict(PAYLOAD,ai_expiry_policy='explicit_listed',ai_expiry='99'),'owner')

    def test_band_controls_bind_periods_and_default_off_in_both_modes(self):
        for mode in ('PAPER','LIVE'):
            c=configuration(dict(PAYLOAD,mode=mode),'owner')
            for kind in ('sma','ema'):
                self.assertEqual(c[kind+'_band_period'],30)
                self.assertFalse(c[kind+'_band_entry'])
                self.assertFalse(c[kind+'_band_exit'])
            c=configuration(dict(PAYLOAD,mode=mode,ai_sma_band_period=10,ai_sma_band_entry=True,ai_ema_band_period=20,ai_ema_band_exit=True),'owner')
            self.assertEqual(c['sma_band_period'],10);self.assertTrue(c['sma_band_entry'])
            self.assertEqual(c['ema_band_period'],20);self.assertTrue(c['ema_band_exit'])
        for value in (True,0,501,'30',2.5):
            with self.assertRaises(ValueError):configuration(dict(PAYLOAD,ai_sma_band_period=value),'owner')

    def test_market_parent_policy(self):
        from sizing_policy import parent_hours,reference_window
        for market,asset,expected in [('NSE',None,6),('BSE',None,6),('CRYPTO',None,23),('MCX','GOLD',14),('MCX','SILVER',14),('NCDEX',None,14)]:self.assertEqual(parent_hours(market,asset),expected)
        with self.assertRaises(ValueError):parent_hours('CRYPTO','GOLD',tokenized_gold=True)
        self.assertEqual(parent_hours('CRYPTO','GOLD',tokenized_gold=True,explicit_category='GOLD'),22)
        with self.assertRaises(ValueError):reference_window('CRYPTO')

    def test_configuration_preserves_selected_rule(self):
        config=configuration(PAYLOAD,'owner')
        self.assertEqual(config['entry_gate'],'underlying_flip_premium_bullish')
        self.assertEqual(config['exit_supertrend'],'premium')
        self.assertEqual(config['expiry_policy'],'nearest_tradable')
        self.assertNotIn('expiry',config)
        self.assertFalse(config['sma_exit_enabled'])
        self.assertEqual(config['sma_price_basis'],'underlying')
    def test_browser_reference_cannot_override_verified_instrument_reference(self):
        config=configuration(dict(PAYLOAD,ai_reference_value=999999,ai_reference_symbol='OTHER'),'owner')
        self.assertEqual(config['reference_value'],400)
        self.assertEqual(config['reference_symbol'],PAYLOAD['underlying'])
        self.assertEqual(config['reference_source'],'verified_native_cache')

    def test_missing_native_reference_cannot_inherit_browser_nifty_value(self):
        with patch('native_reference.resolve_reference',return_value=None) as resolve:
            config=configuration(dict(PAYLOAD,underlying='NSE:RELIANCE-EQ'),'owner')
        resolve.assert_called_once_with('owner','NSE:RELIANCE-EQ','NSE',None)
        self.assertIsNone(config['reference_value'])
        self.assertEqual(config['reference_state'],'UNAVAILABLE')
        self.assertEqual(config['reference_symbol'],'NSE:RELIANCE-EQ')

    def test_account_live_capability_still_requires_explicit_start_click(self):
        legacy=Mock();legacy.snapshot.return_value={};service=Service('owner',legacy)
        with patch.dict('ui_bridge.os.environ',{'SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS':'1'},clear=True):
            with self.assertRaises(ValueError):service.start(dict(PAYLOAD,mode='LIVE',ai_accept_chart_basis=True))
    def test_live_start_maps_explicit_user_intent_without_running_thread(self):
        legacy=Mock();legacy.snapshot.return_value={};service=Service('owner',legacy)
        with tempfile.TemporaryDirectory() as directory, patch('release_state.require_ready'), patch('ui_bridge.DATA',Path(directory)), patch('ui_bridge.threading.Thread') as thread, patch.dict('ui_bridge.os.environ',{'SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS':'1'},clear=True):
            result=service.start(dict(PAYLOAD,mode='LIVE',start_requested=True,ai_accept_chart_basis=True))
            self.assertEqual(result['phase'],'PREFLIGHT');self.assertEqual(result['mode'],'LIVE');thread.return_value.start.assert_called_once()
            self.assertIsNone(service.process)
    def test_worker_sdk_failure_is_reported_before_preflight_or_process(self):
        service=Service('owner',Mock())
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);(directory/'config.json').write_text(json.dumps(dict(broker='FYERS')))
            with patch('ui_bridge.subprocess.run',return_value=Mock(returncode=1,stdout='missing SDK dependency')) as check,patch('ui_bridge.subprocess.Popen') as popen:
                service._launch(directory,False)
                self.assertIn('streaming SDK unavailable',service.error)
                popen.assert_not_called();self.assertEqual(check.call_count,1)
                self.assertEqual(check.call_args.args[0][1],'-c')

    def test_worker_exit_error_is_retained_without_order_or_restart(self):
        service=Service('owner',Mock());process=Mock();process.wait.return_value=1;service.process=process
        with tempfile.TemporaryDirectory() as folder:
            service._watch(process,Path(folder))
            report=json.loads((Path(folder)/'runtime-exit.json').read_text())
            self.assertEqual(report['exit_code'],1);self.assertIn('stopped with an error',service.error)

    def test_child_live_flags_are_derived_only_after_validated_live_start(self):
        service=Service('owner',Mock())
        with tempfile.TemporaryDirectory() as directory,patch('ui_bridge.subprocess.run',return_value=Mock(returncode=0,stdout='read-only preflight')),patch('ui_bridge.subprocess.Popen') as popen:
            service._launch(Path(directory),True)
            args,kwargs=popen.call_args
            self.assertIn('--live',args[0]);self.assertEqual(kwargs['env']['NIFTY_AI_LIVE_ORDERS'],'I_ACCEPT_REAL_ORDERS')
    def test_wrong_owner_blocked(self):
        with self.assertRaises(ValueError):configuration(PAYLOAD,'other')
    def test_prepare_no_process(self):
        legacy=Mock();service=Service('owner',legacy)
        with patch('ui_bridge.subprocess.Popen') as popen:
            self.assertEqual(service.prepare(PAYLOAD)['config']['reference_value'],400)
            popen.assert_not_called();legacy.snapshot.assert_not_called()
    def test_preview_without_quantity_or_product_is_read_only(self):
        service=Service('owner',Mock())
        with patch('ui_bridge.option_preview',return_value={'read_only':True,'orders_submitted':0}) as preview,patch('ui_bridge.subprocess.Popen') as popen:
            result=service.prepare(dict(PAYLOAD,lots=None,ai_product=None,preview_options=True))
            self.assertTrue(result['preview']['read_only']);preview.assert_called_once();popen.assert_not_called()

    def test_stopped_snapshot_reads_exact_account_ledger_after_crash(self):
        with tempfile.TemporaryDirectory() as folder,patch('ui_bridge.DATA',Path(folder)):
            root=Path(folder);run=root/'runs'/'fixture';run.mkdir(parents=True)
            (run/'config.json').write_text(json.dumps(dict(broker='FYERS',execution_route='DIRECT')))
            (run/'preflight.json').write_text(json.dumps(dict(account_sha256='a'*64)))
            ledger=root/'runtime'/('a'*64);ledger.mkdir(parents=True)
            pending=dict(intent=dict(position=dict(symbol='EXACT',underlying='EXACT')))
            (ledger/'direct-paper.json').write_text(json.dumps(dict(position=None,pending=pending)))
            service=Service('owner',Mock());service.run=dict(id='fixture',directory=run,mode='PAPER')
            result=service.snapshot()
            self.assertFalse(result['running']);self.assertEqual(result['heartbeat']['pending'],pending)
            self.assertEqual(result['ownership']['pending'],pending)

    def test_active_legacy_untouched(self):
        legacy=Mock();legacy.snapshot.return_value=dict(running=True)
        service=Service('owner',legacy)
        with patch('ui_bridge.subprocess.Popen') as popen:
            with self.assertRaises(ValueError):service.start(PAYLOAD)
            popen.assert_not_called()
    def test_live_requires_both_explicit_gates(self):
        legacy=Mock();legacy.snapshot.return_value={}
        service=Service('owner',legacy)
        with patch.dict('ui_bridge.os.environ',{},clear=True):
            with self.assertRaises(ValueError):service.start(dict(PAYLOAD,mode='LIVE'))
if __name__=='__main__':unittest.main()

class DhanDirectConfigurationTests(unittest.TestCase):
 def test_direct_route_defaults_intraday_and_has_no_option_or_premium_dependency(self):
  payload=dict(PAYLOAD,broker='DHAN',underlying='NSE_FNO:123',ai_market='NSE',ai_execution_route='DIRECT',ai_product=None,ai_calculation_mode='HYBRID',ai_display_mode='RENKO',ai_signal_source='PREMIUM')
  with patch('ui_bridge.owner_broker',return_value='DHAN'),patch('native_reference.resolve_reference',return_value=dict(native_box=400,reference_session='2026-11-19',source='fixture',url='fixture')):
   config=configuration(payload,'owner')
  self.assertEqual(config['product'],'INTRADAY');self.assertEqual(config['execution_route'],'DIRECT')
  self.assertEqual(config['signal_source'],'UNDERLYING');self.assertEqual(config['exit_supertrend'],'underlying')
  self.assertEqual(config['exit_confirmation_mode'],'RENKO_BRICKS_ONLY')
  self.assertEqual(config['entry_order_type'],'MARKET_WITH_BROKER_MPP')
