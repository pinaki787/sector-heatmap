"""Opt-in, bounded, credential-free feed timing (FYERS_FEED_TIMING=1)."""
import os
import time
import uuid
from threading import Lock
from .broker_diagnostics import diagnostics, source_location


class FeedTiming:
    def __init__(self):
        self.enabled = os.getenv('FYERS_FEED_TIMING') == '1'
        self.trace_id = uuid.uuid4().hex[:12]
        self.origin = time.perf_counter()
        self.lock = Lock()
        self.events = []
        self.seen = set()

    def mark(self, stage, once=True):
        if diagnostics.active('FYERS'):
            capture = diagnostics.states['FYERS']['capture_id']
            key = (capture, stage)
            with self.lock:
                fresh = key not in self.seen
                if fresh:
                    self.seen = {value for value in self.seen if not isinstance(value, tuple) or value[0] == capture}
                    self.seen.add(key)
            if fresh or not once:
                diagnostics.mark('FYERS', stage, source_location(2))
        if not self.enabled:
            return
        with self.lock:
            if once and stage in self.seen:
                return
            self.seen.add(stage)
            self.events.append({'stage': stage, 'elapsed_ms': round((time.perf_counter() - self.origin) * 1000, 3),
                                'unix_ms': round(time.time() * 1000, 3)})
            self.events = self.events[-100:]

    def snapshot(self):
        with self.lock:
            return {'trace_id': self.trace_id, 'events': [dict(event) for event in self.events]}
