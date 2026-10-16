import tempfile
import unittest
from pathlib import Path
from sector_heatmap.workspaces import WorkspaceStore

class VisibilityTests(unittest.TestCase):
    def test_default_hidden_and_global_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'registry.sqlite3'
            store=WorkspaceStore(path)
            self.assertEqual(store.renko_visibility(),dict(entry_rules=False,exit_rules=False,settings=False))
            selected=dict(entry_rules=True,exit_rules=False,settings=True)
            self.assertEqual(store.set_renko_visibility({'admin':True},selected),selected)
            self.assertEqual(WorkspaceStore(path).renko_visibility(),selected)

    def test_user_cannot_change_policy_and_values_are_strict_booleans(self):
        with tempfile.TemporaryDirectory() as folder:
            store=WorkspaceStore(Path(folder)/'registry.sqlite3')
            with self.assertRaises(PermissionError):
                store.set_renko_visibility({'admin':False},dict(entry_rules=True,exit_rules=True,settings=True))
            for value in ({'entry_rules':True},dict(entry_rules=1,exit_rules=False,settings=False)):
                with self.assertRaises(ValueError):store.set_renko_visibility({'admin':True},value)
