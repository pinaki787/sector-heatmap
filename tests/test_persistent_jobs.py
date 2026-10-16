import tempfile
import threading
import time
from pathlib import Path
import unittest
from sector_heatmap.persistent_jobs import JobStore,JobCancelled


class DurableJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'jobs.sqlite3';self.store=JobStore(self.path,workers=1)
        self.addCleanup(self.store.close)
    def submit(self,work,key='one',owner='user:account'):
        return self.store.submit(owner,'ANALYSIS','handoff','Analysis',{'symbol':'NIFTY'},work,key)
    def await_status(self,job_id,states):
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            value=self.store.get('user:account',job_id)
            if value['status'] in states:return value
            time.sleep(.01)
        self.fail('Job did not reach '+str(states))
    def test_output_persists_after_reopen_and_cross_account_access_fails(self):
        job=self.submit(lambda ctx:{'recommendation':'WAIT','entry':100})
        value=self.await_status(job['job_id'],{'COMPLETED'})
        reopened=JobStore(self.path);self.addCleanup(reopened.close)
        self.assertEqual(reopened.get('user:account',job['job_id'])['output'],value['output'])
        self.assertEqual(len(reopened.list('other:account')),0)
        with self.assertRaises(PermissionError):reopened.get('other:account',job['job_id'])
    def test_same_request_does_not_execute_again_and_changed_inputs_rejected(self):
        calls=[];job=self.submit(lambda ctx:calls.append(1) or {'done':True})
        self.await_status(job['job_id'],{'COMPLETED'})
        again=self.submit(lambda ctx:calls.append(2))
        self.assertEqual(again['job_id'],job['job_id']);self.assertEqual(calls,[1])
        with self.assertRaises(ValueError):self.store.submit('user:account','ANALYSIS','handoff','Analysis',{'symbol':'OTHER'},lambda ctx:None,'one')
    def test_running_cancel_retains_checkpoint_and_rejects_late_complete_output(self):
        entered=threading.Event();release=threading.Event()
        def work(ctx):
            ctx.checkpoint('One symbol complete',{'partial':[1]});entered.set();release.wait(2)
            return {'must_not_publish':[2]}
        job=self.submit(work);self.assertTrue(entered.wait(1))
        value=self.store.cancel('user:account',job['job_id']);self.assertEqual(value['status'],'CANCELLING')
        release.set();value=self.await_status(job['job_id'],{'CANCELLED'})
        self.assertEqual(value['output'],{'partial':[1]})
    def test_queued_cancel_never_runs_callback(self):
        entered=threading.Event();release=threading.Event();calls=[]
        first=self.submit(lambda ctx:entered.set() or release.wait(2),key='first');self.assertTrue(entered.wait(1))
        second=self.store.submit('user:account','ANALYSIS','handoff','Different queued analysis',{'symbol':'BANKNIFTY'},lambda ctx:calls.append(1),'second')
        self.assertNotEqual(first['job_id'],second['job_id'])
        self.store.cancel('user:account',second['job_id']);release.set()
        self.await_status(second['job_id'],{'CANCELLED'});self.assertEqual(calls,[])
    def test_restart_marks_interrupted_and_preserves_partial_output_without_replay(self):
        now=self.store.clock()
        with self.store.db() as db:db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',('dead','user:account','dead','RUNNER','renko-supertrend','Runner','RUNNING',now,now,'{}','{"journal":[1]}',None,'old'))
        restarted=JobStore(self.path);self.addCleanup(restarted.close)
        value=restarted.get('user:account','dead');self.assertEqual(value['status'],'INTERRUPTED');self.assertEqual(value['output'],{'journal':[1]})
    def test_duplicate_active_analysis_keys_share_one_execution(self):
        entered=threading.Event();release=threading.Event();calls=[]
        def work(ctx):calls.append(1);entered.set();release.wait(2);return {'done':True}
        first=self.submit(work,key='first');self.assertTrue(entered.wait(1))
        second=self.submit(lambda ctx:calls.append(2),key='different-click')
        self.assertEqual(first['job_id'],second['job_id'])
        release.set();self.await_status(first['job_id'],{'COMPLETED'});self.assertEqual(calls,[1])

    def test_new_analysis_can_follow_a_cancelling_identical_analysis(self):
        entered=threading.Event();release=threading.Event()
        first=self.submit(lambda ctx:entered.set() or release.wait(2),key='first');self.assertTrue(entered.wait(1))
        self.store.cancel('user:account',first['job_id'])
        second=self.submit(lambda ctx:{'fresh':True},key='replacement')
        self.assertNotEqual(first['job_id'],second['job_id'])
        release.set();self.assertEqual(self.await_status(second['job_id'],{'COMPLETED'})['output'],{'fresh':True})
        self.await_status(first['job_id'],{'CANCELLED'})

    def test_history_paginates_beyond_one_hundred_without_cross_owner_cursor_access(self):
        with self.store.db() as db:
            for i in range(105):
                db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(format(i,'032x'),'user:account','archive-'+str(i),'ANALYSIS','handoff','Saved','COMPLETED',i,i,'{}','{"saved":true}',None,'Saved'))
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',('other','other:account','other','ANALYSIS','handoff','Private','COMPLETED',200,200,'{}','{}',None,'Saved'))
        all_ids=[];cursor=None
        while True:
            jobs,cursor=self.store.page('user:account',cursor)
            all_ids.extend(job['job_id'] for job in jobs)
            if not cursor:break
        self.assertEqual(len(all_ids),105);self.assertEqual(len(set(all_ids)),105)
        with self.assertRaises(PermissionError):self.store.page('user:account','other')

    def test_secret_request_fields_not_persisted_and_capacity_is_bounded(self):
        self.store.capacity=1;entered=threading.Event();release=threading.Event()
        job=self.store.submit('user:account','ANALYSIS','handoff','Analysis',{'api_key':'secret','nested':{'access_token':'secret'},'symbol':'NIFTY'},lambda ctx:entered.set() or release.wait(2),'secret')
        self.assertTrue(entered.wait(1));self.assertNotIn('secret',str(self.store.get('user:account',job['job_id'])['request']))
        with self.assertRaises(ValueError):self.submit(lambda ctx:None,key='excess')
        release.set()
