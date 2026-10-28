import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from . import workspace_bounce as bounce

class BounceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name);self.source=self.folder/'source';self.private=self.source/'.private';self.private.mkdir(parents=True)
        self.state=self.private/'renko/state.json';self.state.parent.mkdir();self.state.write_text(json.dumps(dict(running=False,position=None,pending=None)))
        self.account=dict(id='account',label='Test broker',broker='FYERS',live_enabled=False,port=8102)
        self.store=Mock();self.store.folder.return_value=self.folder;self.store.account.return_value=self.account;self.store.path=self.folder/'registry'
        self.user=dict(admin=True);self.runtime=Mock(portal_port=8080,processes={})
        platform=patch.object(bounce.sys,"platform","linux");platform.start();self.addCleanup(platform.stop)
        bounce._active_account=None
    def test_active_running_position_and_pending_block(self):
        for key,value in [('running',True),('position',{'quantity':65}),('pending',{'id':'order'})]:
            self.state.write_text(json.dumps({key:value}))
            with self.assertRaises(ValueError):bounce.stopped_states(self.source)
    def test_corrupt_state_blocks(self):
        self.state.write_text('{')
        with self.assertRaises(ValueError):bounce.stopped_states(self.source)
    def test_history_is_not_live_ownership(self):
        p=self.private/'history';p.mkdir();(p/'old.json').write_text('{"running":true}')
        self.assertEqual(bounce.stopped_states(self.source),[self.state])
    def test_nonadmin_cannot_start_or_read_job(self):
        for fn in [lambda:bounce.begin(self.store,self.runtime,{'admin':False},'account'),lambda:bounce.status(self.store,{'admin':False},'account')]:
            with self.assertRaises(PermissionError):fn()
        self.store.account.assert_not_called()
    def test_second_broker_must_wait(self):
        bounce._active_account='other'
        with self.assertRaisesRegex(ValueError,'Another broker'):bounce.begin(self.store,self.runtime,self.user,'account')
    def test_stopped_dashboard_not_restarted(self):
        self.runtime.running.return_value=False
        with self.assertRaisesRegex(ValueError,'Dashboard is stopped'):bounce.begin(self.store,self.runtime,self.user,'account')
    def test_handoff_ready_no_provision_or_runner_activation(self):
        proc=Mock(pid=12345);proc.poll.return_value=None
        def launched(*args,**kwargs):
            (self.folder/'dashboard-owner.lock').write_text(json.dumps({'pid':proc.pid}));return proc
        initial=dict(status='CHECKING',label='Test broker')
        with patch.object(Path,'resolve',return_value=self.source),patch.object(bounce.subprocess,'Popen',side_effect=launched) as popen,patch.object(bounce.os,'kill') as kill,patch.object(bounce.time,'sleep'),patch.object(bounce,'urlopen') as opening:
            opening.return_value.__enter__.return_value.status=200
            bounce._bounce(self.store,self.runtime,self.account,54321,initial)
        self.assertEqual(bounce.status(self.store,self.user,'account')['status'],'READY')
        self.assertEqual(json.loads(self.state.read_text()),dict(running=False,position=None,pending=None))
        kill.assert_called_once();popen.assert_called_once();self.runtime.provision.assert_not_called();self.runtime.start.assert_not_called()
    def test_failed_replacement_does_not_kill_original(self):
        proc=Mock();proc.poll.return_value=1
        with patch.object(Path,'resolve',return_value=self.source),patch.object(bounce.subprocess,'Popen',return_value=proc),patch.object(bounce.os,'kill') as kill,patch.object(bounce.time,'sleep'):
            bounce._bounce(self.store,self.runtime,self.account,54321,dict(status='CHECKING'))
        kill.assert_not_called();self.assertEqual(bounce.status(self.store,self.user,'account')['status'],'FAILED')

    def test_paper_stop_handoff_preserves_audit_and_ready_requires_normal_flat_result(self):
        from .test_paper_stop_reload import state
        self.state.unlink();self.state=self.private/'renko-delta-instances/test/renko-delta-state.json';self.state.parent.mkdir(parents=True);saved=state();self.state.write_text(json.dumps(saved))
        self.account['broker']='DELTA_INDIA'
        proc=Mock(pid=12345);proc.poll.return_value=None
        def launched(*args,**kwargs):
            self.assertEqual(json.loads(self.state.read_text()),saved)
            (self.folder/'dashboard-owner.lock').write_text(json.dumps({'pid':proc.pid}));return proc
        def normal_replacement_worker(*args):
            completed={**saved,'running':False,'position':None,'status':'STOPPED'};self.state.write_text(json.dumps(completed))
        original_resolve=Path.resolve
        def resolve(path,*args,**kwargs):
            if str(path).startswith('/proc/'):return self.source
            return original_resolve(path,*args,**kwargs)
        with patch.object(Path,'resolve',resolve),patch.object(bounce.subprocess,'Popen',side_effect=launched),patch.object(bounce.os,'kill',side_effect=normal_replacement_worker),patch.object(bounce.time,'sleep'),patch.object(bounce,'urlopen') as opening:
            opening.return_value.__enter__.return_value.status=200
            bounce._bounce(self.store,self.runtime,self.account,54321,dict(status='CHECKING'))
        result=bounce.status(self.store,self.user,'account');self.assertEqual(result['status'],'READY');self.assertIn('Paper Stop completed',result['message'])
        captures=list((self.folder/'paper-stop-reloads').glob('*/test-before.json'));self.assertEqual(len(captures),1);self.assertEqual(json.loads(captures[0].read_text()),saved)
        self.runtime.start.assert_not_called();self.runtime.provision.assert_not_called()
