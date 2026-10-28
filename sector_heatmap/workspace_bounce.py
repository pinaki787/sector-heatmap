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


def reload_states(source,broker):
    """Broker-scoped reload permits only proven Paper Stop handoff; main restart stays strict."""
    from .service_restart import runtime_states
    from strategies.renko_supertrend.stop_recovery import paper_stop_identity
    source=Path(source).resolve();paths=runtime_states(source);drains={}
    for path in paths:
        if path.stat().st_size>4000000:raise ValueError('Oversized current state blocks broker reload.')
        try:state=json.loads(path.read_text())
        except (OSError,ValueError):raise ValueError('Unreadable current state blocks broker reload.') from None
        if not isinstance(state,dict):raise ValueError('Invalid current state blocks broker reload.')
        active=any(state.get(k) for k in ('running','accepting_entries','position','positions','pending','active','loop_running'))
        if not active:continue
        relative=path.resolve().relative_to(source).parts
        canonical=relative==('.private','renko-delta-state.json') or (len(relative)==4 and relative[:2]==('.private','renko-delta-instances') and relative[3]=='renko-delta-state.json')
        if broker!='DELTA_INDIA' or not canonical or state.get('active') or state.get('loop_running'):
            raise ValueError('Broker reload blocked by active runtime outside the identified Paper Stop.')
        drains[path]=paper_stop_identity(state)
    return paths,drains


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
        paths,drains=reload_states(folder/'source',account['broker'])
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
        state = dict(status='CHECKING',label=account['label'],broker=account['broker'],requested_by=user.get('username'),
                     tag='Paper Stop recovery reload' if drains else 'Broker rolling bounce',started_at=time.time(),updated_at=time.time(),
                     message='Checking retained Paper Stop identity; entries remain disabled.' if drains else 'Checking stopped runner state; no trading will be activated.',paper_stop_recovery=bool(drains))
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
        paths,drains=reload_states(source,account['broker'])
        if drains:
            audit=folder/'paper-stop-reloads'/str(time.time_ns());audit.mkdir(parents=True,mode=0o700)
            for path,identity in drains.items():
                private_write(audit/(path.parent.name+'-before.json'),path.read_text())
            private_write(audit/'handoff.json',json.dumps({str(p.relative_to(source)):v for p,v in drains.items()}))
        for path in paths:
            if path in drains:continue
            handle=open(path.with_suffix('.lock'),'a')
            lock_file(handle.fileno(),blocking=False);handles.append(handle)
        _,current_drains=reload_states(source,account['broker'])
        if current_drains!=drains:raise ValueError('Paper Stop identity changed before broker reload; no handoff.')
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
        report('RESTARTING','Reloading this broker to finish its existing Paper Stop; entries remain disabled.' if drains else 'Replacing this broker dashboard; runners remain stopped.')
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
                        report('READY','Existing Paper Stop completed: flat, no pending order, all runners stopped.' if drains else 'Broker dashboard is ready. All strategy runners remain stopped.')
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

def main():
    """Local operator entry to the same reviewed broker reload policy; no force mode."""
    import argparse
    from .workspaces import WorkspaceStore,WorkspaceRuntime
    parser=argparse.ArgumentParser(description="Reload one owned broker through the dashboard handoff policy.")
    parser.add_argument("--registry",required=True);parser.add_argument("--account",required=True);parser.add_argument("--admin",required=True);parser.add_argument("--portal-port",type=int,default=8079)
    args=parser.parse_args();store=WorkspaceStore(args.registry)
    with store.db() as db:row=db.execute("SELECT id,username,admin FROM users WHERE username=?",(args.admin,)).fetchone()
    if not row or not row["admin"]:raise PermissionError("A registered administrator is required.")
    user=dict(row);runtime=WorkspaceRuntime(store,Path(__file__).resolve().parents[1],args.portal_port)
    current=begin(store,runtime,user,args.account);last=None;deadline=time.monotonic()+80
    while True:
        if current!=last:print(json.dumps(current),flush=True);last=dict(current)
        if current["status"] not in _ACTIVE:return 0 if current["status"]=="READY" else 1
        if time.monotonic()>deadline:raise RuntimeError("Reload status did not settle; no second reload was sent.")
        time.sleep(1);current=status(store,user,args.account)

if __name__=="__main__":raise SystemExit(main())
