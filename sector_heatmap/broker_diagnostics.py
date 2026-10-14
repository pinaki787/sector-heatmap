"""Process-local, administrator-controlled broker diagnostics; never records arguments."""
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import inspect
import threading
import time
import uuid
from urllib.parse import urlsplit

BROKERS = ('FYERS', 'DELTA_INDIA')
_current = ContextVar('broker_diagnostic_span', default=None)


def source_location(depth=1):
    frame = inspect.currentframe()
    try:
        for _ in range(depth):
            frame = frame.f_back
        return {'script_path': str(Path(frame.f_code.co_filename).resolve()),
                'line': frame.f_lineno, 'function': frame.f_code.co_name}
    finally:
        del frame


def utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec='milliseconds')


def require_admin(user):
    if not user or not user.get('admin'):
        raise PermissionError('Broker diagnostics require an authenticated administrator.')


class BrokerDiagnostics:
    def __init__(self):
        self.lock = threading.RLock()
        self.states = {broker: {'enabled_until': 0, 'capture_id': None, 'events': deque(maxlen=1000), 'previous': {}, 'origin': None, 'last_start': None}
                       for broker in BROKERS}

    def active(self, broker):
        with self.lock:
            return broker in self.states and self.states[broker]['enabled_until'] > time.monotonic()

    def configure(self, broker, enabled, minutes=15):
        if broker not in BROKERS or type(enabled) is not bool or type(minutes) is not int or not 1 <= minutes <= 60:
            raise ValueError('Choose FYERS or DELTA_INDIA, a boolean enabled flag, and 1–60 minutes.')
        with self.lock:
            state = self.states[broker]
            if enabled:
                state.update(capture_id=uuid.uuid4().hex[:12], enabled_until=time.monotonic() + minutes * 60)
                state['events'].clear(); state['previous'].clear()
                state['origin'] = time.perf_counter(); state['last_start'] = None
            else:
                state['enabled_until'] = 0
        return self.report(broker)

    def begin(self, broker, operation, source=None, request_id=None):
        if not self.active(broker):
            return None
        with self.lock:
            state = self.states[broker]
            now = time.perf_counter()
            previous_key = (threading.get_ident(), request_id or _current.get())
            previous = state['previous'].get(previous_key)
            event = {'capture_id': state['capture_id'], 'span_id': uuid.uuid4().hex[:12],
                     'parent_span_id': _current.get(), 'request_id': request_id,
                     'broker': broker, 'operation': operation, 'command_invocation': operation, **(source or source_location(2)),
                     'thread': threading.current_thread().name, 'start_utc': utc(time.time() * 1000),
                     'end_utc': None, 'elapsed_ms': None,
                     'gap_from_preceding_step_ms': round((now - previous) * 1000, 3) if previous is not None else None,
                     'outcome': 'running',
                     'elapsed_since_capture_ms': round((now - state['origin']) * 1000, 3),
                     'time_from_preceding_step_start_ms': round((now - state['last_start']) * 1000, 3) if state['last_start'] is not None else None,
                     '_start': now, '_previous_key': previous_key}
            state['last_start'] = now
            state['events'].append(event)
            return event

    def end(self, event, outcome='ok'):
        if event is None:
            return
        with self.lock:
            now = time.perf_counter()
            event.update(end_utc=utc(time.time() * 1000), elapsed_ms=round((now - event['_start']) * 1000, 3), outcome=outcome)
            state = self.states[event['broker']]
            if state['capture_id'] == event['capture_id']:
                if len(state['previous']) >= 1000:
                    state['previous'].clear()
                state['previous'][event['_previous_key']] = now

    @contextmanager
    def span(self, broker, operation, source=None, request_id=None):
        event = self.begin(broker, operation, source or source_location(2), request_id)
        token = _current.set(event['span_id']) if event else None
        try:
            yield event
        except BaseException:
            self.end(event, 'error')
            raise
        else:
            self.end(event)
        finally:
            if token is not None:
                _current.reset(token)

    def call(self, broker, operation, function, *args, **kwargs):
        with self.span(broker, operation, source_location(2)):
            return function(*args, **kwargs)

    def mark(self, broker, operation, source=None):
        event = self.begin(broker, operation, source or source_location(2))
        self.end(event)

    def report(self, broker):
        if broker not in BROKERS:
            raise ValueError('Unsupported diagnostic broker.')
        with self.lock:
            state = self.states[broker]
            events = [{k: v for k, v in event.items() if not k.startswith('_')} for event in state['events']]
            slow = sorted((e for e in events if e['elapsed_ms'] is not None), key=lambda e: e['elapsed_ms'], reverse=True)[:10]
            measured = [e for e in slow if e['elapsed_ms'] > 1]
            findings = ([{'evidence': 'measured', 'summary': f"Longest observed span: {measured[0]['operation']} ({measured[0]['elapsed_ms']:.2f} ms). This is an observed bottleneck candidate, not proof of the underlying network/provider cause.",
                          'span_id': measured[0]['span_id']}] if measured else
                        [{'evidence': 'insufficient', 'summary': 'No completed span above 1 ms captured yet. Reproduce the delay while capture is enabled.'}])
            return {'broker': broker, 'enabled': self.active(broker), 'capture_id': state['capture_id'],
                    'remaining_seconds': max(0, round(state['enabled_until'] - time.monotonic())),
                    'source_root': str(Path(__file__).resolve().parents[1]),
                    'process': {'pid': __import__('os').getpid(), 'python_executable': __import__('sys').executable,
                                'entry_script': str(Path(__import__('sys').argv[0]).resolve()),
                                'arguments': 'omitted to protect credentials'},
                    'events': events, 'slowest_spans': slow, 'findings': findings,
                    'interpretation': 'Nested durations overlap; do not add parent and child spans. time_from_preceding_step_start_ms follows capture-wide start order; gap_from_preceding_step_ms is from the preceding completion in the same thread and parent/request context. Missing spans were not observed.'}


diagnostics = BrokerDiagnostics()


def broker_for_host(host):
    host = (host or '').lower()
    for suffix, broker in [('fyers.in', 'FYERS'), ('delta.exchange', 'DELTA_INDIA')]:
        if host == suffix or host.endswith('.' + suffix):
            return broker
    return None


def install_http_timing():
    """Wrap existing requests traffic only; never issues an additional broker request."""
    import requests
    original = requests.sessions.Session.send
    if getattr(original, '_broker_timing', False) is True:
        return

    def send(session, request, **kwargs):
        broker = broker_for_host(urlsplit(request.url).hostname)
        if not broker or not diagnostics.active(broker):
            return original(session, request, **kwargs)
        # Host and method only: paths, queries, headers and bodies may contain secrets.
        source = source_location(1)
        callers = []
        frame = inspect.currentframe().f_back
        try:
            while frame:
                path = Path(frame.f_code.co_filename).resolve()
                if path != Path(__file__).resolve() and 'requests' not in path.parts:
                    callers.append({'script_path': str(path), 'line': frame.f_lineno, 'function': frame.f_code.co_name})
                    if len(callers) >= 8:
                        break
                frame = frame.f_back
        finally:
            del frame
        if callers:
            source = {**callers[0], 'caller_chain': callers}
        with diagnostics.span(broker, 'HTTP ' + request.method + ' ' + urlsplit(request.url).hostname, source):
            return original(session, request, **kwargs)
    send._broker_timing = True
    requests.sessions.Session.send = send
