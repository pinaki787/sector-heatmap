"""Durable, administrator-only dashboard restart; never starts a strategy."""
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from .workspaces import private_write

_lock = threading.Lock()
ACTIVE = {'SCHEDULED', 'WAITING', 'UNKNOWN'}


def _path(store):
    return store.path.parent / 'dashboard-restart.json'


def _admin(user):
    if not user.get('admin'):
        raise PermissionError('Only an administrator can restart services.')


def _service():
    result = subprocess.run(['/usr/bin/systemctl','show','sector-heatmap.service',
                             '--property=MainPID','--property=ActiveState'],
                            check=True, capture_output=True, text=True, timeout=3)
    fields = dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    return int(fields.get('MainPID','0')), fields.get('ActiveState') == 'active'


def status(store, user):
    _admin(user)
    path = _path(store)
    if not path.exists():
        return {'status': 'IDLE', 'message': 'No dashboard restart requested.'}
    state = json.loads(path.read_text())
    if state['status'] in ACTIVE:
        elapsed = time.time() - state['started_at']
        pid, active = _service()
        if active and pid and pid != state['previous_pid']:
            state.update(status='READY', message='Dashboard restarted and authenticated status probe succeeded.', completed_at=time.time())
        elif elapsed > 120:
            state.update(status='UNKNOWN', message='Dashboard process change is not confirmed after two minutes. Keep checking status; no second restart was sent.', completed_at=time.time())
        else:
            state.update(status='WAITING', message='Restart accepted; waiting for the replacement dashboard.')
        private_write(path, json.dumps(state))
    return state


def runtime_states(source):
    """Canonical current state only; saved job/deployment snapshots never own runners."""
    source = Path(source)
    private = source / '.private'
    excluded = ('backup','cache','history','master','.jobs','snapshot','stage','evidence','before-','deploy','restart-',
                'fyers-reconciliation-reload-', 'momentum-proximity-')
    candidates = []
    for path in private.rglob('*.json'):
        parts = path.relative_to(private).parts
        if '.private' in parts or parts[0] == 'dashboard-login':
            continue
        if any(any(word in part.lower() for word in excluded) for part in parts[:-1]):
            continue
        if path.name == 'state.json' or path.name.endswith('-state.json') or path.name in ('live_position_state.json','delta-india-live.json','delta-india-paper.json','kama-chart.json'):
            candidates.append(path)
    # Native Dhan and Motilal strategy state is beside, not inside, source.
    for name in ('dhan-strategies','motilal-strategies'):
        for path in (source.parent / name).rglob('state.json'):
            parts = path.relative_to(source.parent / name).parts
            if not any(any(word in part.lower() for word in excluded) for part in parts[:-1]):
                candidates.append(path)
    return sorted(set(candidates))


def stopped_state_paths(source):
    found = runtime_states(source)
    for path in found:
        if path.stat().st_size > 4000000:
            raise ValueError(f'Oversized current runner state blocks restart: {path.name}.')
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            raise ValueError(f'Unreadable current runner state blocks restart: {path.name}.') from None
        if not isinstance(state, dict):
            raise ValueError(f'Invalid current runner state blocks restart: {path.name}.')
        reasons = [label for key, label in (
            ('running','runner running'),('accepting_entries','entries enabled'),
            ('position','open position'),('positions','retained positions'),
            ('pending','pending order'),('active','active strategy'),
            ('loop_running','strategy loop running')) if state.get(key)]
        if reasons:
            config = state.get('config') or {}
            label = str(config.get('underlying') or state.get('instrument') or state.get('symbol') or path.parent.name)
            mode = config.get('mode')
            if mode: label += f' ({mode})'
            raise ValueError('Restart blocked: '+label+' — '+', '.join(reasons)+'. Stop this runner and reconcile any positions or pending orders first. No restart was sent.')
    return found


def stopped_runtime(source):
    stopped_state_paths(source)


def begin(store, runtime, user, request_id):
    _admin(user)
    if not isinstance(request_id, str) or not re.fullmatch(r'[a-zA-Z0-9-]{16,64}', request_id):
        raise ValueError('A valid restart request ID is required.')
    if not sys.platform.startswith('linux'):
        raise ValueError('Dashboard restart is available on the Linux server.')
    with _lock:
        current = status(store, user)
        if current.get('request_id') == request_id or current['status'] in ACTIVE:
            return current
        # Main systemd service may own broker child processes. Never risk killing
        # an active monitor, even when a particular deployment uses KillMode=process.
        stopped_runtime(runtime.source)
        accounts = store.path.parent / 'accounts'
        for folder in accounts.iterdir() if accounts.exists() else []:
            if not folder.is_dir():continue
            stopped_runtime(folder / 'source')
            bounce = folder / 'bounce-status.json'
            if bounce.exists() and json.loads(bounce.read_text()).get('status') in {'CHECKING','RESTARTING','WAITING'}:
                raise ValueError('Wait for the broker restart to finish first.')
        pid, active = _service()
        if not active or not pid:raise ValueError('Dashboard service is not active; use the server terminal for recovery.')
        state = dict(status='SCHEDULED', request_id=request_id, previous_pid=pid,
                     started_at=time.time(), message='Dashboard restart scheduled; readiness will be probed every two seconds.')
        private_write(_path(store), json.dumps(state))
        try:
            # A transient system timer survives termination of the web service.
            # Fixed commands only: no client-controlled unit, executable or arguments.
            subprocess.run(['sudo','-n','systemd-run','--quiet','--collect',
                            '--unit=sector-pulse-restart-'+request_id,'--on-active=3s',
                            '/usr/bin/systemctl','restart','sector-heatmap.service'],
                           check=True, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            state.update(status='FAILED', message='Restart could not be scheduled. Check the server’s noninteractive service-management permission.', completed_at=time.time())
            private_write(_path(store), json.dumps(state))
        return state
