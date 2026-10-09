"""One watchdog per active Renko runner. A living worker is never duplicated."""
import faulthandler
import os
import threading
import time


class Recovery:
    stale_seconds = 45
    retry_seconds = 30

    def __init__(self, runner, monotonic=time.monotonic):
        self.runner = runner
        self.clock = monotonic
        self.heartbeat = self.clock()
        self.next_attempt = 0
        self.attempts = 0
        self.status = 'HEALTHY'
        self.error = None
        self.worker = None
        self.guard = threading.Lock()
        self.next_diagnostic = 0

    def beat(self):
        self.heartbeat = self.clock()
        self.status = 'HEALTHY'
        self.error = None

    def snapshot(self):
        return dict(status=self.status, heartbeat_age_seconds=round(max(0, self.clock()-self.heartbeat), 1),
                    attempts=self.attempts, error=self.error)

    def check(self):
        r = self.runner
        if not r.state.get('running'):
            self.status = 'STOPPED'
            return
        worker = r.thread
        if worker and worker.is_alive():
            if self.clock()-self.heartbeat > self.stale_seconds:
                self.status = 'WAITING_FOR_INFLIGHT_WORK'
                if self.clock() >= self.next_diagnostic:
                    self.next_diagnostic = self.clock()+120
                    try:
                        path = r.path.with_name('stale-worker-stacks.txt')
                        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                        with os.fdopen(fd, 'w') as output:
                            faulthandler.dump_traceback(file=output, all_threads=True)
                    except (AttributeError, OSError, RuntimeError):
                        pass
                self.error = 'Worker is still alive; duplicate execution is prohibited.'
                r.wake.set()
            return
        if self.clock() < self.next_attempt or not self.guard.acquire(blocking=False):
            return
        try:
            if not r.lock.acquire(blocking=False):
                self.status = 'WAITING_FOR_INFLIGHT_WORK'
                return
            try:
                if not r.state.get('running') or (r.thread and r.thread.is_alive()):
                    return
                self.next_attempt = self.clock()+self.retry_seconds
                if not r.file_lock:
                    raise ValueError('Runner process ownership is unavailable; manual recovery required.')
                config = r.state['config']
                if config.get('mode') == 'LIVE' and not r.adapter.live_enabled():
                    raise ValueError('Live runtime gate is disabled.')
                context = r.adapter.validate_config(config)
                if context.get('account_identity') != r.state.get('account_identity'):
                    raise ValueError('Broker account changed; manual recovery required.')
                # Keep owned exposure, pending intents, seen signals and entry permissions.
                # The normal step reconciles pending orders before considering any entry.
                r.state['eligible_since'] = r.clock()
                r.event('RECOVERING', 'Failed worker recovered; historical entry signals remain excluded.')
                self.attempts += 1
                self.beat()
                r.thread = threading.Thread(target=r.loop, name='renko-recovered-worker', daemon=True)
                r.thread.start()
            except Exception as error:
                self.status = 'RECOVERY_BLOCKED'
                self.error = str(error)
            finally:
                r.lock.release()
        finally:
            self.guard.release()

    def start(self):
        with self.guard:
            if self.worker and self.worker.is_alive():
                return
            def watch():
                while self.runner.state.get('running'):
                    time.sleep(5)
                    self.check()
                self.status = 'STOPPED'
            self.worker = threading.Thread(target=watch, name='renko-recovery-watchdog', daemon=True)
            self.worker.start()
