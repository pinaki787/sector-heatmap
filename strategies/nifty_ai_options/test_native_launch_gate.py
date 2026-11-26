import copy,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from contextlib import ExitStack
import automatic_sizing,delta_live,direct_live,live
class NativeLaunchGateTests(unittest.TestCase):
    def test_no_manual_or_stale_configuration_can_bypass_runtime_wrapper(self):
        with patch('automatic_sizing.ReferenceMonitor') as monitor,self.assertRaisesRegex(ValueError,'Automatic native sizing'):
            automatic_sizing.automatic_strategy(Mock(),dict(reference_value=400),exposure=lambda:False,chart_source=None,config_path=None)
        monitor.assert_not_called()
    def test_validated_native_value_is_persisted_without_changing_user_choices(self):
        config=dict(reference_value=68.6,lots=10,sma_exit_enabled=True,execution_mode='PAPER',timeframe=5)
        before=copy.deepcopy(config)
        verified=dict(config,reference_value=100,reference_native_provider='TRADINGVIEW',reference_context=dict(verified_native_size=True,completed_parent=True,valid_until=time.time()+300))
        with tempfile.TemporaryDirectory() as folder,patch('automatic_sizing.ensure',return_value=verified) as acquire:
            result=automatic_sizing.runtime_configuration(config,folder)
            self.assertEqual(result['reference_value'],100);self.assertEqual(config,before)
            saved=json.loads((Path(folder)/'config.json').read_text())
            for key in ['lots','sma_exit_enabled','execution_mode','timeframe']:self.assertEqual(saved[key],before[key])
            acquire.assert_called_once_with(config)
    def test_unavailable_or_expired_native_value_never_persists_runtime_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            for ref in [{},dict(verified_native_size=True,completed_parent=True,valid_until=time.time()-1)]:
                with patch('automatic_sizing.ensure',return_value=dict(reference_native_provider='TRADINGVIEW',reference_context=ref)),self.assertRaisesRegex(ValueError,'Fresh verified'):
                    automatic_sizing.runtime_configuration({},folder)
                self.assertFalse((Path(folder)/'config.json').exists())
    def test_all_paper_and_live_adapters_validate_native_sizing_before_broker_setup(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.json';path.write_text(json.dumps(dict(accept_close_source_renko_approximation=True)))
            for module,client_name,executor in [(delta_live,'bound_delta','DeltaExecution'),(direct_live,'client','DirectExecution'),(live,'client','Execution')]:
                for is_live in [False,True]:
                    with ExitStack() as stack:
                        stack.enter_context(patch.dict('os.environ',{'AI_RENKO_LIVE_ORDERS':'I_ACCEPT_REAL_ORDERS'}))
                        stack.enter_context(patch('sector_heatmap.market_calendar.market_session',return_value={'status':'OPEN'}))
                        gate=stack.enter_context(patch.object(module,'runtime_configuration',side_effect=ValueError('native unavailable')))
                        client=stack.enter_context(patch.object(module,client_name));execution=stack.enter_context(patch.object(module,executor))
                        with self.assertRaisesRegex(ValueError,'native unavailable'):module.stream(SimpleNamespace(config=str(path),output=str(Path(folder)/'run'),live=is_live))
                        gate.assert_called_once();client.assert_not_called();execution.assert_not_called()
    def test_verification_artifacts_cannot_trigger_acquisition_or_any_adapter(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input.json';path.write_text(json.dumps(dict(_verification_only=True)))
            for module in [delta_live,direct_live,live]:
                with patch.object(module,'runtime_configuration') as gate,self.assertRaisesRegex(ValueError,'Verification-only'):
                    module.stream(SimpleNamespace(config=str(path),live=False))
                gate.assert_not_called()

    def test_legacy_reference_is_reacquired_instead_of_relabelled_as_native_provider(self):
        import native_sizing
        config=dict(account='a'*32,broker='DELTA_INDIA',underlying='ETHUSD',market='CRYPTO')
        legacy=dict(native_box=999)
        official=dict(native_provider='TRADINGVIEW',native_box=100)
        with patch('native_sizing.authorize'),patch('native_reference.resolve_reference',return_value=legacy),patch('native_sizing.acquire',return_value=official) as acquire,patch('native_sizing.apply_reference',side_effect=lambda config,reference:reference):
            self.assertEqual(native_sizing.ensure(config),official);acquire.assert_called_once_with(config)
    def test_dashboard_exposes_only_current_official_native_references(self):
        import ui_bridge
        owner='a'*32;now=time.time()
        common=dict(account=owner,broker='DELTA_INDIA',verified_native_size=True,completed_parent=True,status='VERIFIED_NATIVE',native_box=100)
        records=[dict(common),dict(common,native_provider='TRADINGVIEW',valid_until=now+300),dict(common,native_provider='TRADINGVIEW',valid_until=now-1)]
        with tempfile.TemporaryDirectory() as folder,patch('ui_bridge.DATA',Path(folder)),patch('ui_bridge.owner_broker',return_value='DELTA_INDIA'),patch('ui_bridge.live_capability',return_value=True),patch('native_sizing.authorize'),patch('native_sizing.jobs',return_value=[]):
            directory=Path(folder)/'references'/owner;directory.mkdir(parents=True)
            for i,record in enumerate(records):(directory/(str(i)+'.json')).write_text(json.dumps(record))
            result=ui_bridge.Service(owner,Mock()).snapshot()
            self.assertEqual(len(result['native_references']),1);self.assertEqual(result['native_references'][0]['native_provider'],'TRADINGVIEW')
