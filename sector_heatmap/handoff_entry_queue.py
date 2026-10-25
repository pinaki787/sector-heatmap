"""Persistent waiting entries. Only an authenticated owned bridge may submit."""
from copy import deepcopy
import json,sqlite3,time
from .handoff_entry_conditions import reached
from .handoff_errors import PreflightRejected
class Queue:
    def __init__(self,folder):
        self.folder=folder;self.path=folder/'handoff-entry-waits.sqlite3'
        with self.db() as d:d.execute('CREATE TABLE IF NOT EXISTS waits(id TEXT PRIMARY KEY,state TEXT,body TEXT)')
        self.path.chmod(0o600)
    def db(self):return sqlite3.connect(self.path,timeout=10)
    def enqueue(self,plan,policy):
        c=plan.get('entry_condition')
        if not c or c.get('schema')!='handoff-entry-condition/v1':raise PreflightRejected('Explicit recommended entry condition unavailable; no immediate entry inferred.')
        p=deepcopy(plan);p['ticket_payload']['handoff_auto']=True;p['ticket_payload']['entry_condition']=deepcopy(c)
        body=dict(plan=p,policy_revision=policy.get('revision'),expires_at=(int(time.time())//900+1)*900,created_at=time.time(),condition=c,reason='Waiting for streamed recommended entry condition.')
        with self.db() as d:
            d.execute('INSERT OR IGNORE INTO waits VALUES(?,?,?)',(plan['fingerprint'],'WAITING',json.dumps(body)))
            state=d.execute('SELECT state FROM waits WHERE id=?',(plan['fingerprint'],)).fetchone()[0]
        if state!='WAITING':raise PreflightRejected('Recommendation entry already processed; no replay.')
        return dict(status='WAITING_ENTRY_TRIGGER',entry_requested=False,orders_submitted=0,reason=body['reason'])
    def release(self,schedule,key,reason):
        schedule.claims.not_submitted(schedule.account_id,key)
        with schedule.db() as d:
            row=d.execute('SELECT body FROM receipts WHERE fingerprint=?',(key,)).fetchone()
            if row:
                body=json.loads(row[0]);body['result']=dict(status='NOT_SUBMITTED',reason=reason,orders_submitted=0)
                d.execute("UPDATE receipts SET state='NOT_SUBMITTED',body=?,updated=? WHERE fingerprint=?",(json.dumps(body),time.time(),key))
    def process(self,bridge,schedule):
        from .handoff_exit_monitor import Store
        store=Store(self.folder)
        with self.db() as d:rows=d.execute("SELECT id,state,body FROM waits WHERE state IN ('WAITING','PREPARING')").fetchall()
        for key,state,raw in rows:
            body=json.loads(raw);p=schedule.policy()
            if state=='PREPARING':
                # A process may have died at the submit boundary. Never replay.
                with self.db() as d:d.execute("UPDATE waits SET state='UNCERTAIN' WHERE id=?",(key,))
                schedule.claims.uncertain(schedule.account_id,key);continue
            reason=None
            if not p.get('enabled') or p.get('mode')!='AUTO' or not p.get('live_authorized') or p.get('revision')!=body['policy_revision']:reason='Schedule authorization/settings changed before trigger.'
            elif time.time()>=body['expires_at']:reason='Recommendation entry window expired at the next analysis slot; no stale entry.'
            if reason:
                self.release(schedule,key,reason)
                with self.db() as d:d.execute("UPDATE waits SET state='EXPIRED' WHERE id=?",(key,))
                continue
            if p.get('entries_halted'):continue
            bridge.identity()
            with store.db() as d:q=d.execute('SELECT body FROM quotes WHERE symbol=?',(body['condition']['symbol'],)).fetchone()
            met,reason=reached(body['condition'],json.loads(q[0]) if q else None,time.time())
            body['reason']=reason;body['last_checked']=time.time()
            with self.db() as d:d.execute('UPDATE waits SET body=? WHERE id=?',(json.dumps(body),key))
            if not met:
                from .handoff_entry_conditions import stop_limit_before_trigger
                qv=json.loads(q[0]) if q else None
                fresh_quote=qv and qv.get('connected') and 0<=time.time()-qv.get('provider_at',0)<=5 and 0<=time.time()-qv.get('received_at',0)<=5
                plan=body['plan'];action='BUY' if plan['direction']=='BULLISH' else 'SELL'
                if not (fresh_quote and plan['kind']=='EQUITY' and stop_limit_before_trigger(body['condition'],qv,plan['symbol'],action,plan.get('tick_size'),plan['entry'])):continue
                body['plan']['ticket_payload']['execution_entry_order']={'type':'STOP_LIMIT'}
            else:body['plan']['ticket_payload']['execution_entry_order']={'type':'LIMIT'}

            body['plan']['ticket_payload']['entry_valid_until']=body['expires_at']
            if not store.policy().get('enabled'):continue
            boundary=False
            try:
                store.guard_new_entry()
                fresh=bridge.exposure(p)
                if fresh.get('positions_verified') is not True or fresh.get('orders_verified') is not True:raise PreflightRejected('Fresh broker evidence unavailable at entry trigger.')
                if schedule.loss_halted(fresh,bridge.now() if hasattr(bridge,'now') else __import__('datetime').datetime.now(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')),10000):raise PreflightRejected('Daily loss cutoff reached before entry trigger.')
                if body['plan']['underlying'] in fresh['exposed_underlyings']:raise PreflightRejected('Underlying became exposed before entry trigger.')
                with self.db() as d:
                    d.execute('BEGIN IMMEDIATE');changed=d.execute("UPDATE waits SET state='PREPARING' WHERE id=? AND state='WAITING'",(key,)).rowcount
                if not changed:continue
                boundary=True
                result=bridge._execute_now(body['plan'],p)
                with schedule.db() as d:
                    receipt=json.loads(d.execute('SELECT body FROM receipts WHERE fingerprint=?',(key,)).fetchone()[0]);receipt['result']=result
                    d.execute('UPDATE receipts SET state=?,body=?,updated=? WHERE fingerprint=?',(str(result.get('status') or 'UNKNOWN'),json.dumps(receipt),time.time(),key))
                if result.get('protection_confirmed'):
                    from .handoff_schedule import confirmed_notional
                    schedule.claims.confirmed(schedule.account_id,key,confirmed_notional(result))
                else:schedule.claims.uncertain(schedule.account_id,key)
                with self.db() as d:d.execute("UPDATE waits SET state='SUBMITTED' WHERE id=?",(key,))
            except PreflightRejected as e:
                self.release(schedule,key,str(e))
                with self.db() as d:d.execute("UPDATE waits SET state='NOT_SUBMITTED' WHERE id=?",(key,))
            except Exception:
                if not boundary:continue  # No broker submission was attempted; keep waiting within the same expiry.
                schedule.claims.uncertain(schedule.account_id,key)
                with self.db() as d:d.execute("UPDATE waits SET state='UNCERTAIN' WHERE id=?",(key,))
