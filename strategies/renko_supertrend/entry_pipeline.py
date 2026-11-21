"""Bounded read-only execution checks; never submits, retries or relaxes entry age."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import math
import threading
import time

_POOL = ThreadPoolExecutor(max_workers=8,thread_name_prefix='entry-read')
_SLOTS = threading.BoundedSemaphore(8)

def _schedule(fn):
    if not _SLOTS.acquire(blocking=False):
        raise ValueError('Entry read capacity busy; waiting for a new fresh event.')
    try:
        future=_POOL.submit(fn)
    except BaseException:
        _SLOTS.release()
        raise
    future.add_done_callback(lambda done:_SLOTS.release())
    return future

def bounded_read(fn, deadline):
    remaining=deadline-time.time()
    if remaining<=0:
        raise ValueError('Confirmed price entry expired before ownership preflight.')
    future=_schedule(fn)
    try:return future.result(timeout=min(10,remaining))
    except TimeoutError:
        future.cancel()
        raise ValueError('Ownership preflight exceeded fresh-entry deadline; no order sent.') from None

def broker_preflight(adapter,order,config):
    from strategies.ema_crossover import broker as source
    from strategies.ema_crossover.spread_policy import enabled as spread_filter_enabled
    from strategies.ema_crossover.valuation import amount
    deadline=config['_entry_deadline']
    stages={key:None for key in ('metadata','positions','orders','funds','margin')}
    started=time.time()
    def timed(name,fn):
        begin=time.monotonic()
        try:return fn()
        finally:stages[name]=round(time.monotonic()-begin,6)
    futures=[]
    try:
        if deadline-time.time()<=0:
            raise ValueError('Confirmed price entry expired before broker preflight.')
        def metadata():
            adapter.validate_order(order)
            return adapter.contract(order['symbol'])
        contract=timed('metadata',metadata)
        quote=adapter.quote(order['symbol'])
        if spread_filter_enabled(config) and (quote['ask']-quote['bid'])/quote['ask']>0.03:
            raise ValueError('Entry spread exceeds 3%.')
        client=source._current_client()
        def margin():
            response=source.requests.post(
                'https://api-t1.fyers.in/api/v3/multiorder/margin',
                headers={'Authorization':source.load_config().get('FYERS_ACCESS_TOKEN','')},
                json={'data':[order]},timeout=min(10,max(.01,deadline-time.time())))
            response.raise_for_status()
            return response.json()
        checks={
            'positions':adapter.positions,
            'orders':adapter.orders,
            'funds':lambda:source.account_read(client,'funds'),
            'margin':margin}
        remaining=deadline-time.time()
        if remaining<=0:
            raise ValueError('Confirmed price entry expired during metadata preflight.')
        for name,fn in checks.items():
            futures.append((name,_schedule(lambda name=name,fn=fn:timed(name,fn))))
        values={}
        for name,future in futures:
            remaining=min(10,deadline-time.time())
            if remaining<=0:
                raise ValueError('Confirmed price entry expired during broker preflight; no historical replay.')
            try:values[name]=future.result(timeout=remaining)
            except TimeoutError:
                raise ValueError('Broker preflight exceeded fresh-entry deadline; no order sent.') from None
        if any(r.get('symbol')==order['symbol'] and float(r.get('netQty',0))!=0 for r in values['positions']):
            raise ValueError('Existing position in the same option contract blocks entry; external positions are never adopted.')
        if any(r.get('symbol')==order['symbol'] and int(r.get('status',0)) not in {1,2,5,7} for r in values['orders']):
            raise ValueError('Outstanding order in the same option contract blocks entry.')
        balance=source.available_funds(values['funds'])
        premium=amount(contract,order['qty'],quote['ask'])
        if not math.isfinite(balance) or balance<premium*1.01:
            raise ValueError('Insufficient available funds for option premium plus 1% reserve.')
        margin=values['margin'];data=margin.get('data',margin)
        if margin.get('s')!='ok':
            raise ValueError('FYERS margin validation failed.')
        required=float(data.get('margin_total',data.get('margin_new_order',float('nan'))))
        if not math.isfinite(required) or required<0 or required>balance:
            raise ValueError('FYERS margin unavailable or exceeds available funds.')
        # The socket quote and original event age are checked again at submission.
        if time.time()>deadline:
            raise ValueError('Confirmed price entry expired during broker preflight; no historical replay.')
    finally:
        for _,future in futures:future.cancel()
        adapter.last_entry_preflight={
            'started_at':started,'finished_at':time.time(),
            'elapsed_seconds':time.time()-started,'stages':stages.copy()}
