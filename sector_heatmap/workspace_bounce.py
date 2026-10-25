"""Admin-only account dashboard bounce, without provisioning or arming runners."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
from .workspaces import isolated_environment, private_write

_ACTIVE = {'CHECKING', 'RESTARTING', 'WAITING'}
_lock = threading.Lock()
_active_account = None


def stopped_states(source):
    """Use the same current-state guard for dashboard and selected broker restarts."""
    from .service_restart import stopped_state_paths
    return stopped_state_paths(source)


def _account(store, user, aid):
    if not user.get('admin'):
        raise PermissionError('Only an administrator can bounce a broker dashboard.')
    return store.account(user, aid)


def status(store, user, aid):
    account = _account(store, user, aid)
    path = store.folder(account)/'bounce-status.json'
    if not path.exists():
        return dict(status='IDLE', label=account['label'])
    return json.loads(path.read_text())


def begin(store, runtime, user, aid):
    global _active_account
    account = _account(store, user, aid)
    if not sys.platform.startswith('linux'):
        raise ValueError('Managed dashboard bounce is available on the Linux host.')
    folder = store.folder(account)
    with _lock:
        current = status(store, user, aid)
        if current['status'] in _ACTIVE and time.time()-current.get('updated_at',0) < 90:
            return current
        if _active_account is not None:
            raise ValueError('Another broker bounce is in progress; wait for readiness before bouncing the next broker.')
        stopped_states(folder/'source')
        if account['broker']=='MOTILAL_OSWAL':
            from .motilal_service import Service
            from decimal import Decimal
            service=Service(folder,account)
            positions=service.book('positions')['data'];orders=service.book('orders')['data']
            if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Motilal exposure is unavailable; bounce blocked.')
            try:
                flat=all(Decimal(str(row['buyquantity']))==Decimal(str(row['sellquantity'])) for row in positions)
                pending=any(str(row.get('orderstatus','')).upper() not in {'CANCEL','TRADED','REJECTED','ERROR'} for row in orders)
            except Exception:raise ValueError('Motilal quantities are ambiguous; bounce blocked.') from None
            if not flat or pending:raise ValueError('Motilal has an open position or pending order; bounce blocked.')
            intent_path=folder/'motilal-strategy-intents.sqlite3'
            if intent_path.exists():
                import sqlite3
                with sqlite3.connect(intent_path) as intents:
                    if intents.execute("SELECT 1 FROM intents WHERE state IN ('SUBMITTING','UNCERTAIN','ACKNOWLEDGED') LIMIT 1").fetchone():raise ValueError('Motilal has an unresolved strategy order; bounce blocked.')
            with service.tickets.db() as db:
                if db.execute("SELECT 1 FROM tickets WHERE state IN ('SUBMITTING','UNCERTAIN') LIMIT 1").fetchone():raise ValueError('Reconcile uncertain Motilal tickets before bouncing.')
        if not runtime.running(aid):
            raise ValueError('Dashboard is stopped; use Open dashboard to launch it.')
        pid = int(json.loads((folder/'dashboard-owner.lock').read_text())['pid'])
        if (Path('/proc')/str(pid)/'cwd').resolve() != (folder/'source').resolve():
            raise ValueError('Dashboard owner identity could not be verified.')
        state = dict(status='CHECKING',label=account['label'],broker=account['broker'],
                     tag='Broker rolling bounce',started_at=time.time(),updated_at=time.time(),
                     message='Checking stopped runner state; no trading will be activated.')
        private_write(folder/'bounce-status.json',json.dumps(state))
        thread = threading.Thread(target=_bounce,args=(store,runtime,account,pid,state),daemon=True,name='broker-dashboard-bounce')
        _active_account = aid
        try:
            thread.start()
        except Exception:
            _active_account = None
            raise
        return state


def _bounce(store, runtime, account, pid, initial):
    global _active_account
    folder = store.folder(account);source=folder/'source'
    state=dict(initial)
    def report(phase,message):
        state.update(status=phase,message=message,updated_at=time.time())
        private_write(folder/'bounce-status.json',json.dumps(state))
    replacement=None
    handles=[]
    try:
        from .file_lock import lock_file
        # Hold the existing durable runner locks throughout handoff. An old page
        # cannot race a Start between the stopped-state check and termination.
        for path in stopped_states(source):
            handle=open(path.with_suffix('.lock'),'a')
            lock_file(handle.fileno(),blocking=False);handles.append(handle)
        stopped_states(source)
        if (Path('/proc')/str(pid)/'cwd').resolve()!=source.resolve():
            raise ValueError('Owner changed before handoff.')
        env=isolated_environment(account,folder,store.path,runtime.portal_port)
        wrapper='''
import runpy
import sector_heatmap.workspace_guard as module
from sector_heatmap.workspace_guard import WorkspaceGuard
original_lock=module.lock_file
module.lock_file=lambda fd,blocking=False: original_lock(fd,blocking=True)
guard=WorkspaceGuard.from_environment()
module.lock_file=original_lock
factory=WorkspaceGuard.from_environment
def existing(cls):
 WorkspaceGuard.from_environment=factory
 return guard
WorkspaceGuard.from_environment=classmethod(existing)
if __import__('os').environ.get('SECTOR_PULSE_WORKSPACE_BROKER')=='MOTILAL_OSWAL':
 runpy.run_module('sector_heatmap.motilal_server',run_name='__main__')
else:runpy.run_path('heatmap_server.py',run_name='__main__')
'''
        report('RESTARTING','Replacing this broker dashboard; runners remain stopped.')
        with open(folder/'dashboard.log','a') as output:
            replacement=subprocess.Popen([sys.executable,'-c',wrapper],cwd=source,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        time.sleep(.2)
        if replacement.poll() is not None:
            raise ValueError('Replacement failed before handoff; original dashboard unchanged.')
        os.kill(pid,signal.SIGTERM)
        runtime.processes[account['id']]=replacement
        report('WAITING','Probing this broker dashboard until it is ready.')
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if replacement.poll() is not None:
                raise ValueError('Replacement exited; inspect dashboard logs before retrying.')
            try:
                owner=json.loads((folder/'dashboard-owner.lock').read_text())['pid']
                if owner==replacement.pid:
                    # A completed HTTP response verifies serving, not merely a bound port.
                    from urllib.error import HTTPError
                    try:
                        with urlopen(f"http://127.0.0.1:{account['port']}/",timeout=1) as response:
                            serving=response.status==200
                    except HTTPError as response:
                        serving=response.code in (401,403)
                    if serving:
                        stopped_states(source)
                        report('READY','Broker dashboard is ready. All strategy runners remain stopped.')
                        return
            except (OSError,ValueError,KeyError):
                pass
            time.sleep(1)
        raise ValueError('Readiness timeout; no second restart was attempted.')
    except Exception as error:
        if replacement is not None and replacement.poll() is None:
            try:
                owner=json.loads((folder/'dashboard-owner.lock').read_text())['pid']
                if owner!=replacement.pid:replacement.terminate()
            except (OSError,ValueError,KeyError):pass
        # Report controlled operator text; never include process environment.
        report('FAILED',str(error) if isinstance(error,ValueError) else 'Bounce failed; inspect the account dashboard log. No automatic retry was made.')
    finally:
        for handle in handles:handle.close()
        with _lock:_active_account = None
