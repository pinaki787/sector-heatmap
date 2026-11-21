import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sector_heatmap.workspaces import WorkspaceStore, WorkspaceRuntime

class DeleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.store=WorkspaceStore(self.root/'registry.sqlite3')
        self.owner=self.store.create_user('owner','long-owner-password',bootstrap=True)
        self.other=self.store.create_user('other','long-other-password',actor=self.owner)
        self.account=self.store.create_account(self.owner,'DHAN','Algo','WRONG-ID')
        self.runtime=WorkspaceRuntime(self.store,self.root/'shared')
    def tearDown(self):
        self.tmp.cleanup()
    def delete(self,user=None,confirmation='WRONG-ID'):
        return self.runtime.delete(user or self.owner,self.account['id'],confirmation)
    def test_owner_confirmation_and_running_guards(self):
        with self.assertRaises(PermissionError):self.delete(self.other)
        with self.assertRaises(ValueError):self.delete(confirmation='wrong')
        with patch.object(self.runtime,'running',return_value=True):
            with self.assertRaises(ValueError):self.delete()
        self.assertEqual(len(self.store.accounts(self.owner)),1)
    def test_archive_preserves_evidence_releases_reference_reserves_port(self):
        folder=self.store.folder(self.account)
        folder.mkdir(parents=True)
        evidence=folder/'journal.json';evidence.write_text('{"trade":"retained"}')
        self.assertTrue(self.delete()['records_retained'])
        self.assertEqual(evidence.read_text(),'{"trade":"retained"}')
        self.assertEqual(self.store.accounts(self.owner),[])
        with self.assertRaises(PermissionError):self.store.account(self.owner,self.account['id'])
        with self.store.db() as db:
            row=db.execute('SELECT * FROM deleted_accounts').fetchone()
            self.assertEqual(json.loads(row['registration'])['account_ref'],'WRONG-ID')
        new=self.store.create_account(self.owner,'DHAN','New Algo','WRONG-ID')
        self.assertGreater(new['port'],self.account['port'])
    def test_active_and_corrupt_shared_runner_block_deletion(self):
        state=self.runtime.source/'.private/renko/state.json'
        state.parent.mkdir(parents=True)
        for content in ('{"running":true}','invalid'):
            state.write_text(content)
            with self.assertRaises(ValueError):self.delete()
        self.assertEqual(len(self.store.accounts(self.owner)),1)
    def test_bounce_blocks_deletion(self):
        folder=self.store.folder(self.account);folder.mkdir(parents=True)
        (folder/'bounce-status.json').write_text('{"status":"WAITING"}')
        with self.assertRaises(ValueError):self.delete()
if __name__=='__main__':unittest.main()
