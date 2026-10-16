import unittest
from sector_heatmap.runner_job_audit import audit,attach

class RunnerAuditTests(unittest.TestCase):
    def test_all_fifteen_trades_survive_a_truncated_poll(self):
        rows=[dict(trade_id=str(i),run_id='owned',entry_time=101+i,entry_price=10,exit_price=11,realized_pnl=1) for i in range(15)]
        first=attach(dict(run_id='owned',started_at=100,trade_history=rows),observed_at=120)
        second=attach(dict(run_id='owned',started_at=100,trade_history=[dict(rows[-1],exit_price=12,realized_pnl=2)]),first,121)
        self.assertEqual(len(second['job_audit']['trades']),15)
        self.assertEqual(second['job_audit']['trades'][-1]['exit_price'],12)
        self.assertEqual(first['job_audit']['trades'][-1]['exit_price'],11)
    def test_foreign_undated_and_prestart_trades_are_not_attributed(self):
        state=dict(run_id='ours',started_at=100,trade_history=[dict(trade_id='foreign',run_id='other',entry_time=120),dict(trade_id='unknown'),dict(trade_id='old',entry_time=90),dict(trade_id='legacy',entry_time=110)])
        result=audit(state)
        self.assertEqual([r['trade_id'] for r in result['trades']],['legacy']);self.assertEqual(result['unassigned_rows'],3)
        self.assertEqual(audit(dict(run_id='new',started_at=150),result)['trades'],[])
    def test_order_ownership_and_events_remain_scoped(self):
        state=dict(run_id='ours',started_at=100,position_history=[dict(lifecycle_id='mixed',entry_time=120,orders=[dict(run_id='ours'),dict(run_id='other')]),dict(lifecycle_id='ours',orders=[dict(run_id='ours')])],events=[dict(at=90,message='old'),dict(at=110,message='entry'),dict(at=120,run_id='other',message='foreign')])
        result=audit(state)
        self.assertEqual([r['lifecycle_id'] for r in result['trades']],['ours']);self.assertEqual([r['message'] for r in result['events']],['entry'])
    def test_multiple_runner_outputs_do_not_mix_audits(self):
        result=attach({'runner_outputs':[dict(run_id='one',trade_history=[dict(trade_id='first',run_id='one')]),dict(run_id='two',trade_history=[dict(trade_id='second',run_id='two')])]})
        self.assertEqual([r['trades'][0]['trade_id'] for r in result['job_audits']],['first','second'])

    def test_audit_survives_durable_job_restart_with_all_trade_rows(self):
        import tempfile,time
        from pathlib import Path
        from sector_heatmap.persistent_jobs import JobStore
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'jobs.sqlite3';store=JobStore(path)
            def work(context):
                state=dict(run_id='ours',started_at=100,trade_history=[dict(trade_id=str(i),run_id='ours',entry_time=101+i,entry_reasons=['FIXTURE_COMPLETED_CANDLE'],entry_price=10,exit_price=11,realized_pnl=1) for i in range(15)])
                first=attach(state,observed_at=120);context.checkpoint('Journal saved',first)
                return attach(dict(run_id='ours',started_at=100,trade_history=[]),first,121)
            job=store.submit('user:account','RUNNER','renko-supertrend','Fixture journal',{},work,'fixture')
            deadline=time.monotonic()+2
            while not store.get('user:account',job['job_id'])['terminal'] and time.monotonic()<deadline:time.sleep(.01)
            store.close();reopened=JobStore(path)
            try:
                saved=reopened.get('user:account',job['job_id'])
                self.assertEqual(saved['status'],'COMPLETED');self.assertEqual(len(saved['output']['job_audit']['trades']),15)
                with self.assertRaises(PermissionError):reopened.get('other:account',job['job_id'])
            finally:reopened.close()
