"""Broker boundaries for FYERS analysis and explicit Delta account workspaces."""
from pathlib import Path
import unittest
from sector_heatmap.workspaces import BROKERS
from sector_heatmap.workspace_guard import WorkspaceGuard

ROOT=Path(__file__).resolve().parents[1]


class BrokerBoundaryTests(unittest.TestCase):
    def test_only_explicitly_supported_brokers_can_be_provisioned(self):
        self.assertEqual(BROKERS,{'FYERS','DELTA_INDIA'})
        policy=' '.join((ROOT/'BROKER_POLICY.md').read_text().split())
        self.assertIn('supported trading brokers are FYERS and Delta India',policy)
        self.assertIn('no automatic substitution',policy)

    def test_workspace_actions_never_fall_back_to_another_broker(self):
        guard=WorkspaceGuard(None,'test',8100,8079)
        for broker,path in [('FYERS','/api/delta-india/submit'),('DELTA_INDIA','/api/renko-supertrend/start')]:
            with self.assertRaises(PermissionError):guard.validate_action({'broker':broker},path,{})

    def test_indian_handoff_keeps_its_fyers_execution_service(self):
        source=(ROOT/'sector_heatmap/web.py').read_text()
        self.assertIn('FyersExecutionService',source)
        self.assertIn('build_long_option_proposals',source)


if __name__=='__main__':unittest.main()
