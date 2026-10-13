import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from sector_heatmap.workspaces import WorkspaceStore, WorkspaceRuntime

class SnapshotTests(unittest.TestCase):
    def test_fresh_owned_dhan_snapshot_imports_all_execution_dependencies(self):
        repo=Path(__file__).resolve().parents[1]
        if not (repo/'.git').exists():self.skipTest('Git checkout provision test')
        with tempfile.TemporaryDirectory() as temp:
            store=WorkspaceStore(Path(temp)/'registry.sqlite3')
            user=store.create_user('test-owner','test-only-private-password',bootstrap=True)
            account=store.create_account(user,'DHAN','Test Dhan','test-id')
            folder=WorkspaceRuntime(store,repo).provision(account)
            source=folder/'source'
            files=('sector_heatmap/dhan_handoff.py','sector_heatmap/dhan_account_login.py','sector_heatmap/network_policy.py',
                   'sector_heatmap/premium_exit_mapping.py','strategies/renko_supertrend/dhan_costs.py')
            for name in files:
                self.assertEqual((source/name).read_bytes(),(repo/name).read_bytes())
            env=dict(os.environ,PYTHONPATH=str(source))
            result=subprocess.run([sys.executable,'-c',
                'import socket; import sector_heatmap.dhan_handoff; import sector_heatmap.dhan_form_routes; from strategies.renko_engine.runner import DhanRunner; assert getattr(socket.getaddrinfo,"_sector_pulse_ipv4_only",False); print("owned snapshot imports pass")'],
                cwd=source,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('owned snapshot imports pass',result.stdout)
            self.assertFalse((source/'.fyers.env').exists())
