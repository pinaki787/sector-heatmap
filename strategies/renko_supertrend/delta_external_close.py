"""Conservative attribution of an existing Delta external close; never submits."""
from datetime import datetime
from decimal import Decimal

def confirmed_close(position, fills, active_orders, broker_size):
    product=position['product_id']
    if broker_size != 0:
        raise ValueError('External close requires a verified flat Delta contract.')
    if any(int(r.get('product_id',-1))==product for r in active_orders):
        raise ValueError('Active Delta contract order blocks external-close reconciliation.')
    rows=[r for r in fills if int(r.get('product_id',-1))==product]
    def stamp(r): return datetime.fromisoformat(r['created_at'].replace('Z','+00:00')).timestamp()
    rows.sort(key=stamp)
    ids=[r['id'] for r in rows]
    if len(set(ids))!=len(ids): raise ValueError('Duplicate Delta fill evidence.')
    entries=[r for r in rows if str(r.get('order_id'))==str(position.get('entry_order_id'))]
    quantity=Decimal(str(position['quantity']));side=position.get('entry_side',1)
    entry_side='buy' if side==1 else 'sell'
    if not entries or any(r['side']!=entry_side for r in entries) or sum(Decimal(str(r['size'])) for r in entries)!=quantity:
        raise ValueError('Original Delta entry fills do not match owned exposure.')
    opened=max(stamp(r) for r in entries)
    after=[r for r in rows if stamp(r)>=min(stamp(e) for e in entries) and r not in entries]
    if not after or any(stamp(r)<=opened or r['side']==entry_side for r in after):
        raise ValueError('Intervening or missing Delta exit fill evidence.')
    if len({str(r['order_id']) for r in after})!=1 or sum(Decimal(str(r['size'])) for r in after)!=quantity:
        raise ValueError('Delta external exit is partial or ambiguous.')
    for r in entries+after:
        size=Decimal(str(r['size']));price=Decimal(str(r['price']))
        if not size.is_finite() or size<=0 or not price.is_finite() or price<=0:
            raise ValueError('Invalid Delta fill price or quantity.')
    price=sum(Decimal(str(r['size']))*Decimal(str(r['price'])) for r in after)/quantity
    commission=sum(Decimal(str(r['commission'])) for r in after)
    if not commission.is_finite() or commission<0:raise ValueError('Invalid Delta fill commission.')
    return dict(order_id=str(after[0]['order_id']),symbol=position['symbol'],quantity=int(quantity),
                side=-side,product=position['product'],price=float(price),filled_at=max(stamp(r) for r in after),
                entry_order_id=str(position['entry_order_id']),commission=float(commission),fills=after)

def read_evidence(delta,execution,position,account_identity,clock):
    if execution.authenticate()!=account_identity:
        raise ValueError('Delta account differs from owned exposure.')
    fills=[];cursor=None;seen=set()
    for _ in range(100):
        params=dict(product_ids=str(position['product_id']),page_size=100,
                    start_time=int((position['opened_at']-120)*1e6),end_time=int(clock()*1e6))
        if cursor:params['after']=cursor
        data=delta._private('GET','/v2/fills',params=params)
        if not isinstance(data.get('result'),list):raise ValueError('Delta fills unavailable.')
        fills.extend(data['result'])
        cursor=(data.get('meta') or {}).get('after')
        if not cursor:break
        if cursor in seen:raise ValueError('Delta fill pagination did not advance.')
        seen.add(cursor)
    else:raise ValueError('Delta fill history incomplete.')
    return confirmed_close(position,fills,execution.active_orders(),delta._position(position['product_id']))

def stopped_external_identity(source,state):
    """Reload exception for an already-requested Stop with proven external fills."""
    from copy import deepcopy
    from pathlib import Path
    from sector_heatmap.delta_india import DeltaIndia
    from .delta_execution import Execution
    c=state.get('config') or {};p=state.get('position') or {};pending=state.get('pending') or {}
    if (state.get('schema')!=1 or c.get('mode')!='LIVE' or c.get('broker')!='DELTA_INDIA'
            or state.get('squareoff_requested') is not True or state.get('accepting_entries') is not False
            or not state.get('run_id') or not state.get('account_identity') or not p
            or p.get('run_id')!=state['run_id'] or p.get('underlying_symbol')!=c.get('underlying')
            or p.get('exit_requested') is not True or p.get('exit_reason')!='MANUAL_SQUARE_OFF'
            or state.get('positions') or (pending and not pending.get('reconciliation_only'))):
        raise ValueError('Only an identified, already-requested Delta external-close Stop can hand off.')
    delta=DeltaIndia(Path(source)/'.private'/'delta-india-paper.json')
    execution=Execution(delta)
    first=read_evidence(delta,execution,p,state['account_identity'],delta.clock)
    if first!=read_evidence(delta,execution,p,state['account_identity'],delta.clock):
        raise ValueError('Delta external-close evidence changed during reload guard.')
    return dict(kind='DELTA_EXTERNAL_CLOSE_STOP',run_id=state['run_id'],account_identity=state['account_identity'],
                config=deepcopy(c),position={k:p.get(k) for k in ('symbol','product_id','quantity','entry_order_id','opened_at','run_id','lifecycle_id')},
                external_close=first,stop_requested=True)
