"""Account-local candle refresh and immutable confirmed-indicator publication.

No order or runner lifecycle methods are available here. Slow history reads run on
one background worker per symbol/timeframe; consumers never wait behind that IO.
"""
from copy import deepcopy
import hashlib
import json
import threading
import time


class CandlePending(RuntimeError):
    pass


class SharedCandleFeed:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.Lock()
        self.entries = {}
        self.observers = {}

    def register(self, key, owner, config):
        import weakref
        with self.lock:
            owners = self.observers.setdefault(key, weakref.WeakKeyDictionary())
            owners[owner] = deepcopy(config)

    def read(self, key, seconds, loader, with_revision=False):
        now = self.clock()
        with self.lock:
            entry = self.entries.setdefault(key, dict(rows=None, busy=False, next_at=0, attempts=0, revision=None))
            if not entry['busy'] and now >= entry['next_at']:
                entry['busy'] = True
                worker = threading.Thread(target=self._refresh, args=(key, seconds, loader), daemon=True, name='renko-confirmed-candles')
                entry['worker'] = worker
                worker.start()
            rows = deepcopy(entry['rows'])
            error = entry.get('error')
            revision = entry.get('revision')
        if rows is None:
            raise CandlePending(error or 'Broker candles warming up in background; live prices remain independent.')
        return (rows,revision) if with_revision else rows

    def _refresh(self, key, seconds, loader):
        try:
            rows = deepcopy(loader())
            if not rows:
                raise ValueError('Broker returned no candles.')
            # Validate completed prices before publishing a new shared revision.
            from .signals import completed
            completed(rows)
            now = self.clock()
            confirmed = [r for r in rows if not r.get('is_forming')]
            latest = confirmed[-1]['timestamp'] if confirmed else None
            target = int(now // seconds) * seconds - seconds
            # No rapid polling across closed/quiet sessions. During an active
            # sequence, retry late publication briefly, then back off.
            late = latest is not None and latest < target and now-latest <= 3*seconds
            with self.lock:
                entry = self.entries[key]
                entry['attempts'] = entry['attempts']+1 if late else 0
                retry = min(30, 2**min(entry['attempts']-1, 5)) if late else None
                revision = hashlib.sha256(json.dumps(confirmed, sort_keys=True).encode()).hexdigest()
                entry.update(rows=rows, revision=revision, refreshed_at=now, latest_completed=latest,
                             error=None, waiting_for_close=late, next_at=now+retry if late else (int(now//seconds)+1)*seconds+1)
                observers = list(self.observers.get(key, {}).items())
            # Publish verified broker openings immediately. A chart does not
            # wait for another recovery timer after history finishes.
            for observer, config in observers:
                try:observer.observe(config, deepcopy(rows))
                except Exception:pass
        except Exception:
            with self.lock:
                entry = self.entries[key]
                entry['attempts'] += 1
                entry.update(error='Broker candle retrieval unavailable; background retry pending.',
                             next_at=self.clock()+min(30, 2**min(entry['attempts']-1, 5)))
        finally:
            with self.lock:
                self.entries[key]['busy'] = False

    def health(self, key):
        with self.lock:
            entry = self.entries.get(key, {})
            return {k:entry.get(k) for k in ('busy','revision','refreshed_at','latest_completed','error','next_at','waiting_for_close')}


_pool_lock = threading.Lock()


def feed_for(loader):
    # The callback is created inside one account's web-server scope. Never key
    # shared caches by a public symbol alone across accounts or credentials.
    with _pool_lock:
        pool = getattr(loader, '_renko_confirmed_feed', None)
        if pool is None:
            pool = SharedCandleFeed()
            loader._renko_confirmed_feed = pool
        return pool


def confirmed_export(state, include_rows=False):
    engine = state.get('renko_engine')
    if not engine or not state.get('run_id'):
        return None
    identity = dict(run_id=state['run_id'], anchor=engine['anchor'],
                    symbol=(state.get('config') or {}).get('underlying'),
                    timeframe=(state.get('config') or {}).get('timeframe'),
                    count=engine['state']['count'], last_at=engine['last']['timestamp'])
    revision = hashlib.sha256(json.dumps([identity,engine.get('price_fingerprints'),engine['last']], sort_keys=True).encode()).hexdigest()
    result = dict(**identity, revision=revision, latest=deepcopy(engine['last']),
                  basis='Runner confirmed broker candles; provisional ticks excluded.')
    if include_rows:
        result['rows'] = deepcopy(engine.get('rows', []))
    return result


def publish_confirmed(runner):
    state = runner.state
    engine = state.get('renko_engine')
    if not engine or not state.get('run_id'):
        return
    key = (state['run_id'], id(engine), json.dumps(state.get('config'),sort_keys=True))
    if key == getattr(runner,'_published_confirmed_key',None):
        return
    exported = confirmed_export(state, include_rows=True)
    exported['_engine'] = deepcopy({k:engine[k] for k in ('state','last','anchor')})
    exported['_config'] = deepcopy(state.get('config') or {})
    # The immutable publication is replaced atomically, never edited by readers.
    # Holding the prior engine reference prevents object-ID reuse in the key.
    runner._published_confirmed_engine = engine
    runner._confirmed_publication = exported
    runner._published_confirmed_key = key


def bind_confirmed(runner, requested_run, symbol, timeframe):
    publication = getattr(runner,'_confirmed_publication',None)
    if publication is not None:
        if runner.state.get('run_id') != requested_run:
            raise ValueError('Runner identity changed; refresh the selected runner chart.')
        if publication['run_id'] != requested_run:
            raise CandlePending('New run confirmed publication warming up; previous chart retained.')
        if publication['symbol'] != symbol or publication['timeframe'] != timeframe:
            raise ValueError('Runner identity changed; refresh the selected runner chart.')
        # This read does not acquire the execution lock or perform broker IO.
        result = deepcopy(publication)
        if runner.state.get('run_id') != requested_run:
            raise ValueError('Runner identity changed; refresh the selected runner chart.')
        return result
    # A short bounded lock protects an atomic read; no broker calls under it.
    if not runner.lock.acquire(timeout=.02):
        raise CandlePending('Confirmed runner update in progress; keep the previous chart.')
    try:
        state = runner.state
        config = state.get('config') or {}
        if state.get('run_id') != requested_run or config.get('underlying') != symbol or config.get('timeframe') != timeframe:
            raise ValueError('Runner identity changed; refresh the selected runner chart.')
        exported = confirmed_export(state, include_rows=True)
        if exported is None:
            raise CandlePending('Confirmed runner candles are not available yet.')
        exported['_engine'] = deepcopy({k:state['renko_engine'][k] for k in ('state','last','anchor')})
        exported['_config'] = deepcopy(config)
        return exported
    finally:
        runner.lock.release()


class SharedQuoteHub:
    """One data transport per account callback; stopping a runner detaches it."""
    def __init__(self, transport):
        import weakref
        self.transport = transport
        self.members = weakref.WeakSet()
        self.lock = threading.RLock()
        self.transport.on_tick = self.publish

    def join(self, owner):
        with self.lock:
            self.members.add(owner)
            self.transport.start()
            owner.socket = self.transport.socket
            owner.connected = self.transport.connected

    def leave(self, owner):
        with self.lock:
            self.members.discard(owner)
            # Account transport stays alive for charts and later consumers.
            # Runner Stop must never tear down another consumer's data feed.

    def publish(self, raw):
        with self.lock:
            members = list(self.members)
        for owner in members:
            with owner.lock:
                if raw.get('symbol') not in owner.symbols:
                    continue
                owner.ticks[raw['symbol']] = (dict(raw), time.time())
                owner.connected = self.transport.connected
                owner.stream_error = None
            if owner.on_tick:
                try:
                    owner.on_tick(dict(raw))
                except Exception:
                    # An individual consumer failure cannot stop other charts
                    # or execution consumers from receiving market data.
                    pass

    def tick(self, owner, symbol):
        with owner.lock:
            owner.symbols.add(symbol)
        try:
            raw = self.transport.tick(symbol)
            # quote() validates that returned data belongs to this owner's cache.
            # Fanout makes independent copies, so returning transport raw breaks
            # that identity check and strips genuine bid freshness metadata.
            with self.transport.lock:
                item = self.transport.ticks.get(symbol)
                received = item[1] if item and item[0] is raw else None
                snapshot = dict(raw)
            with owner.lock:
                owner.ticks[symbol] = (snapshot, received)
            return snapshot
        finally:
            owner.connected = self.transport.connected
            owner.socket = self.transport.socket
            owner.stream_error = self.transport.stream_error


def quote_hub_for(owner):
    with _pool_lock:
        loader = owner.fetch_candles
        hub = getattr(loader, '_renko_quote_hub', None)
        if hub is None:
            from strategies.ema_crossover.broker import FyersBroker
            from sector_heatmap.chart_feed_recovery import ChartFeedRecoveryMixin
            class Transport(ChartFeedRecoveryMixin, FyersBroker):
                pass
            transport = Transport(owner.master_dir, loader, owner.select_atm)
            hub = SharedQuoteHub(transport)
            loader._renko_quote_hub = hub
        return hub
