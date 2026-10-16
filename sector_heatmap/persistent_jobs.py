"""Account-owned durable work; never replay interrupted execution on startup."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, copy_context
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time

TERMINAL={'COMPLETED','FAILED','CANCELLED','INTERRUPTED'}
CURRENT_JOB=ContextVar('sector_pulse_job',default=None)


class JobCancelled(Exception):pass
class JobInterrupted(Exception):pass
class JobStopFailed(Exception):pass


def checkpoint(message=None, output=None):
    context=CURRENT_JOB.get()
    if context:context.checkpoint(message,output)


class JobContext:
    def __init__(self,store,owner,job_id):self.store,self.owner,self.job_id=store,owner,job_id
    def cancelled(self):return self.store.get(self.owner,self.job_id)['status']=='CANCELLING'
    def checkpoint(self,message=None,output=None):
        if self.store.shutdown.is_set():raise JobInterrupted()
        if self.cancelled():raise JobCancelled()
        self.store._update(self.job_id,message=message,output=output)


class JobStore:
    def __init__(self,path,workers=3,capacity=12,clock=time.time):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.clock=clock;self.capacity=capacity;self.guard=threading.RLock()
        self.shutdown=threading.Event()
        self.pool=ThreadPoolExecutor(max_workers=workers,thread_name_prefix='durable-job')
        self.runner_pool=ThreadPoolExecutor(max_workers=16,thread_name_prefix='runner-job')
        self.futures={};self.stoppers={}
        with self.db() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,request_key TEXT NOT NULL,kind TEXT NOT NULL,feature TEXT NOT NULL,label TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL,request TEXT NOT NULL,output TEXT,error TEXT,message TEXT,UNIQUE(owner,request_key))')
            db.execute("UPDATE jobs SET status='INTERRUPTED',message='Server restarted; prior output retained. No work or trading signal was replayed.',updated=? WHERE status NOT IN ('COMPLETED','FAILED','CANCELLED','INTERRUPTED')",(clock(),))
        os.chmod(self.path,0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        try:
            with db:yield db
        finally:db.close()
    def _decode(self,row):
        value=dict(row)
        value['request']=json.loads(value['request']);value['output']=json.loads(value['output']) if value['output'] else None
        value['job_id']=value.pop('id');value['terminal']=value['status'] in TERMINAL
        age=max(0,self.clock()-value['updated'])
        delayed=not value['terminal'] and value['status']!='QUEUED' and age>180
        value['health']=dict(state='NO_RECENT_PROGRESS' if delayed else 'TERMINAL' if value['terminal'] else 'RESPONDING',
                             last_progress_at=value['updated'],age_seconds=round(age,1),
                             message='No job progress update for over three minutes. Execution state is unconfirmed; do not resubmit an order.' if delayed else '')
        return value
    def get(self,owner,job_id):
        with self.db() as db:row=db.execute('SELECT * FROM jobs WHERE id=? AND owner=?',(job_id,owner)).fetchone()
        if not row:raise PermissionError('Job not found in this user and broker account.')
        return self._decode(row)
    def list(self,owner,limit=100):
        with self.db() as db:rows=db.execute('SELECT * FROM jobs WHERE owner=? ORDER BY created DESC LIMIT ?',(owner,max(1,min(int(limit),200)))).fetchall()
        return [self._decode(row) for row in rows]
    def page(self,owner,before=None,limit=25):
        limit=max(1,min(int(limit),50))
        with self.db() as db:
            params=[owner];where='owner=?'
            if before:
                cursor=db.execute('SELECT created,id FROM jobs WHERE owner=? AND id=?',(owner,before)).fetchone()
                if not cursor:raise PermissionError('Job history cursor is unavailable in this account.')
                where+=' AND (created,id)<(?,?)';params.extend((cursor['created'],cursor['id']))
            rows=db.execute('SELECT * FROM jobs WHERE '+where+' ORDER BY created DESC,id DESC LIMIT ?',(*params,limit+1)).fetchall()
        more=len(rows)>limit;rows=rows[:limit]
        return [self._decode(row) for row in rows],rows[-1]['id'] if more else None

    def _update(self,job_id,status=None,message=None,output=None,error=None):
        fields={'updated':self.clock()}
        for key,value in dict(status=status,message=message,error=error).items():
            if value is not None:fields[key]=str(value)
        if output is not None:fields['output']=json.dumps(output,allow_nan=False)
        with self.guard,self.db() as db:
            db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),job_id))
    def submit(self,owner,kind,feature,label,request,work,request_key,stop=None):
        if not request_key or len(str(request_key))>160:raise ValueError('A bounded submission identity is required.')
        # Store application inputs only; never request headers or credentials.
        def clean(value):
            if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if not any(s in k.lower() for s in ('token','password','secret','cookie','authorization','api_key'))}
            if isinstance(value,list):return [clean(v) for v in value]
            return value
        encoded=json.dumps(clean(request),allow_nan=False,sort_keys=True)
        if len(encoded)>1_000_000:raise ValueError('Job input exceeds 1 MB.')
        with self.guard,self.db() as db:
            existing=db.execute('SELECT * FROM jobs WHERE owner=? AND request_key=?',(owner,request_key)).fetchone()
            if existing:
                if existing['kind']!=kind or existing['request']!=encoded:raise ValueError('Submission identity already belongs to different inputs.')
                return self._decode(existing)
            active_states="('QUEUED','RUNNING','CANCELLING')" if kind=='RUNNER' else "('QUEUED','RUNNING')"
            existing=db.execute('SELECT * FROM jobs WHERE owner=? AND kind=? AND request=? AND status IN '+active_states,(owner,kind,encoded)).fetchone()
            if existing:return self._decode(existing)
            active=db.execute("SELECT COUNT(*) FROM jobs WHERE owner=? AND status IN ('QUEUED','RUNNING','CANCELLING')",(owner,)).fetchone()[0]
            if active>=self.capacity:raise ValueError('This account has too many active jobs; stop one before submitting more.')
            job_id=secrets.token_hex(16);now=self.clock()
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(job_id,owner,str(request_key),kind,feature,str(label)[:200],'QUEUED',now,now,encoded,None,None,'Queued on server.'))
        if stop:self.stoppers[job_id]=stop
        captured=copy_context()
        pool=self.runner_pool if kind=='RUNNER' else self.pool
        future=pool.submit(captured.run,self._run,owner,job_id,work)
        with self.guard:self.futures[job_id]=future
        def release(completed):
            with self.guard:
                if self.futures.get(job_id) is completed:self.futures.pop(job_id,None)
        future.add_done_callback(release)
        return self.get(owner,job_id)
    def _run(self,owner,job_id,work):
        with self.guard:
            row=self.get(owner,job_id)
            if row['status'] in TERMINAL:return
            if row['status']=='CANCELLING':self._update(job_id,status='CANCELLED',message='Cancelled before execution.');return
            self._update(job_id,status='RUNNING',message='Running on server; page navigation does not stop this job.')
        context=JobContext(self,owner,job_id);token=CURRENT_JOB.set(context)
        try:
            result=work(context)
            with self.guard:
                cancelled=context.cancelled()
                self._update(job_id,status='CANCELLED' if cancelled else 'COMPLETED',output=None if cancelled else result,
                             message='Stopped; partial output retained.' if cancelled else 'Completed; output saved for later retrieval.')
        except JobCancelled:self._update(job_id,status='CANCELLED',message='Stopped; partial output retained.')
        except JobInterrupted:self._update(job_id,status='INTERRUPTED',message='Server shutdown; output retained, no work replayed.')
        except JobStopFailed:self._update(job_id,status='FAILED',error='Existing runner Stop failed; inspect Runner jobs and reconcile before retrying.',message='Stop failed; latest runner status retained. No automatic retry.')
        except Exception as error:
            cancelled=context.cancelled()
            # API and broker exception strings can contain private payloads.
            safe=str(error)[:700] if isinstance(error,(ValueError,PermissionError)) else 'Job failed ('+type(error).__name__+'); prior output retained.'
            self._update(job_id,status='CANCELLED' if cancelled else 'FAILED',error=None if cancelled else safe,
                         message='Stopped; partial output retained.' if cancelled else 'Failed; prior output retained.')
        finally:
            CURRENT_JOB.reset(token);self.stoppers.pop(job_id,None)
    def cancel(self,owner,job_id):
        with self.guard:
            row=self.get(owner,job_id)
            if row['terminal']:return row
            self._update(job_id,status='CANCELLING',message='Stop requested; waiting for bounded in-flight work to settle.')
            future=self.futures.get(job_id)
            if future and future.cancel():self._update(job_id,status='CANCELLED',message='Cancelled before execution.')
        return self.get(owner,job_id)
    def close(self,wait=True):
        self.shutdown.set()
        self.pool.shutdown(wait=wait,cancel_futures=True)
        self.runner_pool.shutdown(wait=wait,cancel_futures=True)
