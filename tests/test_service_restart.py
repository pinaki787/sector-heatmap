import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from sector_heatmap import service_restart as restart


class RestartTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'.private').mkdir()
        self.account=self.root/'accounts/a';(self.account/'source/.private').mkdir(parents=True)
        self.store=SimpleNamespace(path=self.root/'registry.sqlite3',accounts=lambda user:[{'id':'a'}],folder=lambda account:self.account)
        self.runtime=SimpleNamespace(source=self.root)
        self.user={'admin':True};self.rid='12345678-1234-1234-1234-123456789abc'

    @patch.object(restart,'_service',return_value=(123,True))
    @patch.object(restart.subprocess,'run')
    def test_restart_is_durable_deduplicated_and_requires_new_active_pid(self,run,service):
        with patch.object(restart.sys,'platform','linux'):
            job=restart.begin(self.store,self.runtime,self.user,self.rid)
            self.assertEqual(job['status'],'SCHEDULED')
            restart.begin(self.store,self.runtime,self.user,self.rid)
        self.assertEqual(run.call_count,1)
        self.assertIn('/usr/bin/systemctl',run.call_args.args[0])
        self.assertEqual(restart.status(self.store,self.user)['status'],'WAITING')
        service.return_value=(999,False)
        self.assertEqual(restart.status(self.store,self.user)['status'],'WAITING')
        service.return_value=(999,True)
        self.assertEqual(restart.status(self.store,self.user)['status'],'READY')
        self.assertEqual(json.loads(restart._path(self.store).read_text())['status'],'READY')

    @patch.object(restart.subprocess,'run')
    def test_active_account_blocks_before_any_command(self,run):
        (self.account/'source/.private/runner-state.json').write_text(json.dumps({'running':True}))
        with patch.object(restart.sys,'platform','linux'),self.assertRaises(ValueError):
            restart.begin(self.store,self.runtime,self.user,self.rid)
        run.assert_not_called()

    def test_permission_and_id_validation(self):
        with self.assertRaises(PermissionError):restart.status(self.store,{'admin':False})
        with self.assertRaises(PermissionError):restart.begin(self.store,self.runtime,{},self.rid)
        with self.assertRaises(ValueError):restart.begin(self.store,self.runtime,self.user,'; reboot')

    @patch.object(restart,'_service',return_value=(123,True))
    @patch.object(restart.subprocess,'run',side_effect=PermissionError('secret detail'))
    def test_schedule_failure_is_persisted_without_raw_output(self,run,service):
        with patch.object(restart.sys,'platform','linux'):
            job=restart.begin(self.store,self.runtime,self.user,self.rid)
        self.assertEqual(job['status'],'FAILED');self.assertNotIn('secret',job['message'])

    @patch.object(restart,'_service',return_value=(123,True))
    def test_timeout_does_not_retry(self,service):
        restart.private_write(restart._path(self.store),json.dumps(dict(status='WAITING',previous_pid=123,started_at=0)))
        with patch.object(restart.time,'time',return_value=200):
            self.assertEqual(restart.status(self.store,self.user)['status'],'UNKNOWN')

    def test_archived_state_does_not_block_but_invalid_current_state_does(self):
        archive=self.root/'.private/deploy-20261001/.private/runner-state.json';archive.parent.mkdir(parents=True);archive.write_text('{"running":true}')
        restart.stopped_runtime(self.root)
        (self.root/'.private/runner-state.json').write_text('broken')
        with self.assertRaises(ValueError):restart.stopped_runtime(self.root)

    @patch.object(restart.subprocess,'run')
    def test_main_restart_checks_other_users_workers_too(self,run):
        other=self.root/'accounts/other-user/source/.private';other.mkdir(parents=True)
        (other/'runner-state.json').write_text('{"running":true}')
        with patch.object(restart.sys,'platform','linux'),self.assertRaises(ValueError):
            restart.begin(self.store,self.runtime,self.user,self.rid)
        run.assert_not_called()
