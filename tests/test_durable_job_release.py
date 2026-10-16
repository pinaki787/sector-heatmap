import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.durable_job_release import NEW_FILES,digest,install,plan


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.stage=self.root/'stage';self.target=self.root/'target'
        self.stage.mkdir();self.target.mkdir();(self.target/'heatmap_server.py').write_text('# existing dashboard')
        for relative in NEW_FILES:
            path=self.stage/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('# reviewed module\n' if path.suffix=='.py' else '// reviewed asset\n')
        (self.stage/'index.html').write_text('new dashboard')
        (self.target/'index.html').write_text('old dashboard')
        (self.stage/'baseline-sha256.json').write_text(json.dumps({'index.html':digest(b'old dashboard')}))

    def test_dry_run_is_read_only_and_install_backs_up_exact_source(self):
        changes=plan(self.stage,[self.target]);self.assertEqual((self.target/'index.html').read_text(),'old dashboard')
        backup=self.root/'backup';result=install(changes,backup)
        self.assertFalse(result['services_restarted']);self.assertEqual(result['orders_submitted'],0)
        self.assertEqual((self.target/'index.html').read_text(),'new dashboard')
        records=json.loads((backup/'manifest.json').read_text())
        old=next(row for row in records if row['path']==str(self.target/'index.html'))
        self.assertEqual((backup/old['backup']).read_text(),'old dashboard')
        self.assertEqual(plan(self.stage,[self.target]),[])

    def test_drift_in_any_destination_prevents_all_changes(self):
        other=self.root/'other';other.mkdir();(other/'heatmap_server.py').write_text('# dashboard')
        (other/'index.html').write_text('unreviewed change')
        with self.assertRaisesRegex(ValueError,'destination drift'):plan(self.stage,[self.target,other])
        self.assertEqual((self.target/'index.html').read_text(),'old dashboard')

    def test_install_write_failure_rolls_back_preceding_changes(self):
        import os
        changes=plan(self.stage,[self.target]);original=os.replace;calls=0
        def fail_second(src,dst):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('simulated disk error')
            return original(src,dst)
        with patch('scripts.durable_job_release.os.replace',side_effect=fail_second):
            with self.assertRaises(OSError):install(changes,self.root/'failed-backup')
        for dest,before,after in changes:
            self.assertEqual(dest.read_bytes() if dest.exists() else None,before)
