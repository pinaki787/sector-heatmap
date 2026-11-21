import unittest,tempfile,json
from pathlib import Path
from unittest.mock import Mock,patch
from ui_bridge import configuration,Service
PAYLOAD=dict(account_id='owner',broker='FYERS',underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',lots=1,ai_product='MARGIN',ai_expiry='1795428600',ai_reference_symbol='NSE:NIFTY50-INDEX',ai_reference_session='2026-11-19',ai_reference_value=400,ai_reference_evidence='fixture',mode='PAPER')
class Tests(unittest.TestCase):
    def setUp(self):
        bound=patch('ui_bridge.owner_broker',return_value='FYERS');bound.start();self.addCleanup(bound.stop)
        reference=patch('native_reference.resolve_reference',return_value=dict(native_box=400,reference_session='2026-11-19',source='unit fixture',url='fixture'));reference.start();self.addCleanup(reference.stop)

    def test_market_parent_policy(self):
        from sizing_policy import parent_hours,reference_window
        for market,asset,expected in [('NSE',None,6),('BSE',None,6),('CRYPTO',None,23),('MCX','GOLD',22),('MCX','SILVER',14),('NCDEX',None,14)]:self.assertEqual(parent_hours(market,asset),expected)
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

    def test_account_live_capability_still_requires_confirmation(self):
        legacy=Mock();legacy.snapshot.return_value={};service=Service('owner',legacy)
        with patch.dict('ui_bridge.os.environ',{'SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS':'1'},clear=True):
            with self.assertRaises(ValueError):service.start(dict(PAYLOAD,mode='LIVE',ai_accept_chart_basis=True))
    def test_live_start_maps_explicit_user_intent_without_running_thread(self):
        legacy=Mock();legacy.snapshot.return_value={};service=Service('owner',legacy)
        with tempfile.TemporaryDirectory() as directory, patch('ui_bridge.DATA',Path(directory)), patch('ui_bridge.threading.Thread') as thread, patch.dict('ui_bridge.os.environ',{'SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS':'1'},clear=True):
            result=service.start(dict(PAYLOAD,mode='LIVE',confirmation='START AI RENKO LIVE',ai_accept_chart_basis=True))
            self.assertEqual(result['phase'],'PREFLIGHT');self.assertEqual(result['mode'],'LIVE');thread.return_value.start.assert_called_once()
            self.assertIsNone(service.process)
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
