import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from process_state import fingerprint,identity,RecoveredProcess,recover,assert_stopped

class ProcessStateTests(unittest.TestCase):
    def test_exact_command_and_start_ticks_prevent_pid_reuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);proc=root/'proc';pid=proc/'123';pid.mkdir(parents=True);run=root/'run'
            fields=['S']+['0']*18+['777']
            (pid/'stat').write_text('123 (python worker) '+' '.join(fields))
            (pid/'cmdline').write_bytes(('python\0/approved/run.py\0stream\0--config\0'+str(run/'config.json')+'\0--output\0'+str(run)+'\0').encode())
            self.assertEqual(identity(123,run,proc=proc),dict(pid=123,start_ticks='777'))
            self.assertIsNone(identity(123,root/'other',proc=proc))
            fields[0]='Z';(pid/'stat').write_text('123 (python worker) '+' '.join(fields))
            self.assertIsNone(fingerprint(123,proc))

    def test_stop_never_signals_reused_pid(self):
        process=RecoveredProcess(dict(pid=123,start_ticks='777'),'/run')
        with patch('process_state.identity',return_value=dict(pid=123,start_ticks='888')),patch('process_state.os.kill') as kill:
            self.assertEqual(process.poll(),1);process.terminate();kill.assert_not_called()

    def test_restart_guard_blocks_retained_ledger_and_recovers_job_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);owner='a'*32;data=root/'.private/nifty-ai-options'
            run=data/'runs'/owner/'20261120-test';run.mkdir(parents=True)
            (run/'config.json').write_text(json.dumps(dict(account=owner,broker='DELTA_INDIA',execution_mode='PAPER')))
            ledger=data/'runtime'/owner;ledger.mkdir(parents=True)
            (ledger/'delta-paper.json').write_text(json.dumps(dict(position={'symbol':'BTCUSD'},pending=None)))
            recovered,process=recover(owner,data)
            self.assertEqual(recovered['id'],run.name);self.assertIsNone(process)
            with self.assertRaisesRegex(ValueError,'retained position'):
                assert_stopped(root/'.private/dashboard-login/accounts'/owner/'source',root)
            (ledger/'delta-paper.json').write_text(json.dumps(dict(position=None,pending=None)))
            assert_stopped(root,root)
