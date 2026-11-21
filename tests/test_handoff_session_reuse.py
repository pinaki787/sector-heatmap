import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from sector_heatmap.handoff_fyers_analysis import Provider

class SessionReuse(unittest.TestCase):
    def test_saved_token_change_rebinds_quotes_and_history_without_execution(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch('sector_heatmap.config.load_config') as config, \
             patch('sector_heatmap.handoff_fyers_analysis._current_client') as client, \
             patch('sector_heatmap.handoff_fyers_analysis.SectorAnalysisService') as sectors:
            config.return_value={'FYERS_ACCESS_TOKEN':'synthetic:first'}
            client.side_effect=[Mock(name='first'),Mock(name='second')]
            provider=Provider({'id':'owned'},Path(folder))
            old_client=provider.client;old_sectors=provider.sectors
            provider.refreshed=100
            self.assertFalse(provider.refresh_session())
            self.assertEqual(client.call_count,1)
            config.return_value={'FYERS_ACCESS_TOKEN':'synthetic:renewed'}
            self.assertTrue(provider.refresh_session())
            self.assertIsNot(provider.client,old_client)
            self.assertEqual(sectors.call_count,2)
            self.assertEqual(sectors.call_args.args[0],'synthetic:renewed')
            self.assertEqual(provider.refreshed,0)
            self.assertFalse(provider.refresh_session())
            self.assertEqual(client.call_count,2)

    def test_failed_rebind_never_marks_old_client_as_the_new_session(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch('sector_heatmap.config.load_config') as config, \
             patch('sector_heatmap.handoff_fyers_analysis._current_client') as client, \
             patch('sector_heatmap.handoff_fyers_analysis.SectorAnalysisService'):
            config.return_value={'FYERS_ACCESS_TOKEN':'synthetic:first'}
            provider=Provider({'id':'owned'},Path(folder));old_revision=provider._session_digest
            config.return_value={'FYERS_ACCESS_TOKEN':'synthetic:renewed'}
            client.side_effect=PermissionError('Unavailable saved authorization')
            for _ in range(2):
                with self.assertRaises(PermissionError):provider.refresh_session()
                self.assertEqual(provider._session_digest,old_revision)
