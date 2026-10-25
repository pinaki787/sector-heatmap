"""Stop an idle Motilal connection service only after verified account exposure."""
from contextlib import ExitStack
from decimal import Decimal,InvalidOperation
import json,os,signal,sqlite3,time
from pathlib import Path
from .workspaces import private_write
from .workspace_bounce import stopped_states
from .file_lock import lock_file
from .motilal_strategy_broker import account_lock
from .motilal_service import Service


def idle_states(source):
    paths=set(stopped_states(source))
    for path in (Path(source).parent/'motilal-strategies').rglob('state.json'):
        try:state=json.loads(path.read_text())
        except (OSError,ValueError):raise ValueError('Unreadable Motilal runner record blocks disconnect.') from None
        if not isinstance(state,dict) or any(state.get(k) for k in ('running','position','pending','positions','active')):raise ValueError('Active runner or owned exposure blocks disconnect.')
        paths.add(path)
    return sorted(paths)


def check_flat(service,folder):
    positions=service.book('positions')['data'];orders=service.book('orders')['data']
    if not isinstance(positions,list) or not isinstance(orders,list):raise ValueError('Broker exposure unavailable; disconnect blocked.')
    try:
        for row in positions:
            bought,sold=Decimal(str(row['buyquantity'])),Decimal(str(row['sellquantity']))
            if not bought.is_finite() or not sold.is_finite() or bought<0 or sold<0:raise ValueError()
            if bought!=sold:raise ValueError('Open broker position blocks disconnect.')
        if any(str(row.get('orderstatus') or '').strip().upper() not in {'CANCEL','TRADED','REJECTED','ERROR'} for row in orders):raise ValueError('Pending or unknown broker order blocks disconnect.')
    except (KeyError,TypeError,InvalidOperation):raise ValueError('Broker exposure ambiguous; disconnect blocked.') from None
    intent=folder/'motilal-strategy-intents.sqlite3'
    if intent.exists():
        with sqlite3.connect(intent) as db:
            if db.execute("SELECT 1 FROM intents WHERE state IN ('SUBMITTING','UNCERTAIN','ACKNOWLEDGED') LIMIT 1").fetchone():raise ValueError('Unresolved strategy submission blocks disconnect.')
    with service.tickets.db() as db:
        if db.execute("SELECT 1 FROM tickets WHERE state IN ('SUBMITTING','UNCERTAIN') LIMIT 1").fetchone():raise ValueError('Unresolved reviewed submission blocks disconnect.')


def stop_connection(runtime,account):
    folder=runtime.store.folder(account)
    pid=int(json.loads((folder/'dashboard-owner.lock').read_text())['pid'])
    if pid<=1 or pid==os.getpid():raise ValueError('Connection process identity unavailable; disconnect blocked.')
    process=Path('/proc')/str(pid)
    if (process/'cwd').resolve()!=(folder/'source').resolve():raise ValueError('Connection process ownership changed; disconnect blocked.')
    command=(process/'cmdline').read_bytes()
    if b'sector_heatmap.motilal_server' not in command:raise ValueError('Unexpected connection process; disconnect blocked.')
    os.kill(pid,signal.SIGTERM)
    deadline=time.monotonic()+10
    while runtime.running(account['id']):
        if time.monotonic()>=deadline:raise ValueError('Connection shutdown did not complete; no forced kill or retry was made.')
        time.sleep(.1)
    runtime.processes.pop(account['id'],None)


def stop_for_disconnect(runtime,account):
    if account['broker']!='MOTILAL_OSWAL':raise ValueError('This guarded shutdown is specific to Motilal.')
    folder=runtime.store.folder(account);source=folder/'source'
    marker=folder/'disconnected.json'
    if marker.exists() and not runtime.running(account['id']):return
    with account_lock(folder),ExitStack() as stack:
        for path in idle_states(source):
            handle=stack.enter_context(open(path.with_suffix('.lock'),'a'))
            try:lock_file(handle.fileno(),blocking=False)
            except OSError:raise ValueError('A runner owns this account; disconnect blocked.') from None
        idle_states(source)
        service=Service(folder,account)
        check_flat(service,folder)
        # Block fresh account actions while locks remain held through shutdown.
        existed=marker.exists()
        private_write(marker,json.dumps(dict(disconnected=True)))
        try:
            idle_states(source)
            if runtime.running(account['id']):stop_connection(runtime,account)
        except Exception:
            if not existed:marker.unlink(missing_ok=True)
            raise
        for name in ('motilal-session.json','motilal-login-intent.json','motilal-otp-pending.enc'):
            (folder/name).unlink(missing_ok=True)
