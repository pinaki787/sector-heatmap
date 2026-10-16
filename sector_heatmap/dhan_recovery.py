"""Read-only evidence for a fully closed, externally managed Dhan position."""
from datetime import datetime
from pathlib import Path
import hashlib
from .dhan_execution import IST

def external_close_evidence(broker, position, pending, history):
    """Fail closed unless exact entry and subsequent full exit are broker-proven."""
    symbol=position['symbol'];qty=int(position['quantity'])
    entry_id=str(position.get('entry_order_id') or '')
    if not entry_id or qty<=0 or position.get('entry_side',1)!=1:
        raise ValueError('Exact bought-option entry order and quantity required.')
    entries=[r for r in history if str(r.get('order_id'))==entry_id and r.get('mode')=='LIVE'
             and r.get('side')=='BUY' and r.get('symbol')==symbol and r.get('filled')==qty]
    if len(entries)!=1:raise ValueError('Entry ownership or remaining quantity is ambiguous.')
    if pending:
        if pending.get('id') or pending.get('order',{}).get('side')!= -1 or pending['order'].get('symbol')!=symbol:
            raise ValueError('Unresolved submitted order requires normal reconciliation.')
        tag=pending.get('tag')
        if not tag:raise ValueError('Pending correlation ID missing.')
        intent=Path(broker.service.folder)/'dhan-strategy-intents'/(hashlib.sha256(tag.encode()).hexdigest()+'.json')
        if intent.exists():raise ValueError('Durable submission intent exists; outcome remains uncertain.')
    positions=broker._account_rows('/positions')
    orders=broker._account_rows('/orders')
    trades=broker._account_rows('/trades')
    segment,security=symbol.split(':',1)
    def same(r):
        return r.get('exchangeSegment')==segment and str(r.get('securityId'))==security and r.get('productType')=='MARGIN'
    if any(same(r) and float(r.get('netQty',0))!=0 for r in positions):
        raise ValueError('Broker still has exposure.')
    if any(same(r) and r.get('orderStatus') in ('TRANSIT','PENDING','PART_TRADED') for r in orders):
        raise ValueError('Broker has an outstanding order.')
    if pending and any(r.get('correlationId')==pending['tag'] for r in orders):
        raise ValueError('Pending correlation is present at broker; normal reconciliation required.')
    def stamp(r):
        return datetime.strptime(r['exchangeTime'],'%Y-%m-%d %H:%M:%S').replace(tzinfo=IST).timestamp()
    own=[r for r in trades if same(r) and str(r.get('orderId'))==entry_id and r.get('transactionType')=='BUY']
    if not own or sum(int(r['tradedQuantity']) for r in own)!=qty:
        raise ValueError('Exact entry fills unavailable.')
    if abs(sum(int(r['tradedQuantity'])*float(r['tradedPrice']) for r in own)/qty-float(position['entry_price']))>0.000001:
        raise ValueError('Broker entry price differs from saved position.')
    start=min(stamp(r) for r in own)
    later=[r for r in trades if same(r) and stamp(r)>=start and str(r.get('orderId'))!=entry_id]
    if not later or any(r.get('transactionType')!='SELL' for r in later):
        raise ValueError('Intervening entries make external-close attribution ambiguous.')
    if sum(int(r['tradedQuantity']) for r in later)!=qty:
        raise ValueError('External close does not exactly match retained quantity.')
    ids={str(r['orderId']) for r in later}
    if len(ids)!=1:raise ValueError('Multiple external exit orders require manual attribution.')
    if len({str(r['exchangeTradeId']) for r in own+later})!=len(own+later):
        raise ValueError('Duplicate broker trade evidence.')
    exit_id=next(iter(ids))
    matched=[r for r in orders if str(r.get('orderId'))==exit_id and same(r) and r.get('transactionType')=='SELL' and r.get('orderStatus')=='TRADED']
    if len(matched)!=1:raise ValueError('Terminal external exit order unavailable.')
    return dict(entry_order_id=entry_id,exit_order_id=exit_id,quantity=qty,
                price=sum(int(r['tradedQuantity'])*float(r['tradedPrice']) for r in later)/qty,
                exchange_at=max(stamp(r) for r in later),source='Dhan owned trade book and terminal order; broker position flat')

def _reconcile_external_close(runner, payload):
    """Archive a proven external close without submitting or rearming anything."""
    from copy import deepcopy
    with runner.lock:
        state=runner.state
        if state.get('running') or (runner.thread and runner.thread.is_alive()):
            raise ValueError('Stop monitoring before reconciling an external close.')
        if (state.get('config') or {}).get('mode')!='LIVE' or not state.get('position'):
            raise ValueError('A retained Live position is required.')
        if not state.get('run_id') or payload.get('run_id')!=state['run_id']:
            raise ValueError('Recovery context changed; refresh the runner.')
        evidence=external_close_evidence(runner.adapter,state['position'],state.get('pending'),state.get('order_history',[]))
        prior=deepcopy(state['position']);pending=deepcopy(state.get('pending'))
        entry=next(r for r in state['order_history'] if str(r.get('order_id'))==evidence['entry_order_id'] and r.get('mode')=='LIVE')
        audit=dict(at=runner.clock(),evidence=evidence,position=prior,pending=pending,run_id=state['run_id'])
        state.setdefault('external_reconciliations',[]).append(audit)
        if pending:
            row=next((r for r in state['order_history'] if r.get('tag')==pending['tag']),None)
            if row:row.update(status='NOT_SUBMITTED',filled=0,remaining=row.get('requested'),reason='No durable Dhan submission intent or broker correlation; archived during external-close reconciliation')
        exit_row={**deepcopy(entry), 'tag':'DHAN-EXTERNAL-'+evidence['exit_order_id'],
                  'order_id':evidence['exit_order_id'],'side':'SELL','is_entry':False,
                  'requested':evidence['quantity'],'filled':evidence['quantity'],'remaining':0,
                  'average_price':evidence['price'],'status':'FILLED','reason':'EXTERNAL_BROKER_CLOSE',
                  'submitted_at':evidence['exchange_at'],'filled_at':evidence['exchange_at'],
                  'updated_at':runner.clock(),'first_fill_confirmed_at':runner.clock(),
                  'spot_fill_observations':[],'option_quote_observation':None,'indicator_snapshot':None,
                  'reconciliation_events':[evidence], 'external_close_evidence':evidence}
        state['order_history'].append(exit_row)
        realized=(evidence['price']-prior['entry_price'])*evidence['quantity']*float(prior.get('quantity_multiplier',1))
        state['realized_pnl']=state.get('realized_pnl',0)+realized
        day=datetime.fromtimestamp(evidence['exchange_at'],IST).date().isoformat()
        state.setdefault('losses',{})[day]=state.get('losses',{}).get(day,0)+max(0,-realized)
        state.update(position=None,pending=None,running=False,accepting_entries=False,
                     rearm_after_exit=False,squareoff_requested=False,management_only=False)
        runner.event('STOPPED','External close verified from Dhan trade book. Broker is flat; runner remains stopped.')
        return runner.snapshot()


def reconcile_external_close(runner, payload):
    import fcntl,json
    with runner.lock:
        handle=None
        try:
            if getattr(runner,'path',None) is not None and runner.file_lock is None:
                handle=open(runner.path.with_suffix('.lock'),'a')
                try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except OSError:raise ValueError('Another process owns the runner; recovery refused.')
                if runner.path.exists():
                    saved=json.loads(runner.path.read_text())
                    if any(saved.get(k)!=runner.state.get(k) for k in ('run_id','position','pending')):
                        raise ValueError('Saved recovery evidence changed; reload before reconciliation.')
            return _reconcile_external_close(runner,payload)
        finally:
            if handle:
                fcntl.flock(handle,fcntl.LOCK_UN);handle.close()
