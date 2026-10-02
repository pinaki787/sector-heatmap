"""Read-only weighted-average position accounting from broker fill snapshots."""
from decimal import Decimal, InvalidOperation
from datetime import datetime

def number(value):
    try:
        d=Decimal(str(value));return d if d.is_finite() else None
    except (InvalidOperation,ValueError,TypeError):return None

def lifecycles(fills, positions, history_complete):
    rows=[];active={};seen=set()
    def new(f, signed, verified, missing=False):
        row=dict(symbol=f.get('symbol'),product_id=f.get('product_id'),settlement_currency=f.get('settlement_currency'),direction='LONG' if signed>0 else 'SHORT',entry_side='buy' if signed>0 else 'sell',exit_side='sell' if signed>0 else 'buy',entry_time=None,exit_time=None,entry_contracts=Decimal(0),exit_contracts=Decimal(0),remaining_contracts=abs(signed) if missing else Decimal(0),entry_price=None,exit_price=None,entry_value=Decimal(0),exit_value=Decimal(0),fees=Decimal(0),gross_realized_pnl=Decimal(0),broker_position_realized_pnl=None,details=[],matched_contracts=Decimal(0),verified=verified,missing_opening=missing,values_known=True,pnl_known=not missing,fees_known=True,history_complete=history_complete)
        row['_cost']=None if missing else Decimal(0);row['_sign']=1 if signed>0 else -1;row['_exit_cost']=Decimal(0);rows.append(row);return row
    def stamp(f):
        try:return datetime.fromisoformat(str(f.get('created_at')).replace('Z','+00:00')).timestamp()
        except Exception:return float('inf')
    for f in sorted(fills,key=lambda f:(stamp(f),str(f.get('id')))):
        ident=f.get('id')
        if ident is not None and ident in seen:continue
        if ident is not None:seen.add(ident)
        q=number(f.get('size'));price=number(f.get('price'));side=f.get('side');key=(f.get('product_id') or f.get('symbol'),f.get('settlement_currency'))
        if q is None or q<=0 or price is None or side not in ('buy','sell') or stamp(f)==float('inf'):
            row=new(f,Decimal(1),False,True);row['details'].append(dict(f,allocation='Unmatched invalid fill'));row['pnl_known']=False;row['values_known']=False;continue
        delta=q if side=='buy' else -q;after=number(f.get('position_size_after'));before=after-delta if after is not None else None;row=active.get(key)
        held=(row['_sign']*row['remaining_contracts']) if row else Decimal(0)
        if before is not None and before!=held:
            if row:row['verified']=False;row['reconciliation_error']='Broker position discontinuity';active.pop(key,None)
            row=new(f,before,True,True) if before else None
            if row:active[key]=row
        if row is None:
            row=new(f,delta,before==0);active[key]=row
        remaining=q;fee=number(f.get('commission'));unit=number(f.get('linear_contract_value'));value_ok=unit is not None and unit>0
        closing=row['remaining_contracts']>0 and row['_sign']*delta<0
        allocations=[]
        if closing:
            close=min(q,row['remaining_contracts']);allocations.append((row,close,False));remaining-=close
        if remaining:
            if closing and remaining>0:
                row=new(f,delta,after is not None);active[key]=row
            allocations.append((row,remaining,True))
        for r,qty,entry in allocations:
            allocated_fee=fee*qty/q if fee is not None else None
            if allocated_fee is None:r['fees_known']=False
            else:r['fees']+=allocated_fee
            r['values_known'] &= value_ok
            r['details'].append(dict(f,allocated_contracts=str(qty),allocated_commission=str(allocated_fee) if allocated_fee is not None else None,allocation='entry' if entry else 'exit'))
            if entry:
                r['entry_time']=r['entry_time'] or f.get('created_at');old=r['remaining_contracts'];r['remaining_contracts']+=qty;r['entry_contracts']+=qty
                if r['_cost'] is not None:r['_cost']+=qty*price
                r['entry_value']+=qty*price*(unit or 0)
            else:
                avg=r['_cost']/r['remaining_contracts'] if r['_cost'] is not None else None
                r['exit_contracts']+=qty;r['exit_time']=f.get('created_at');r['exit_value']+=qty*price*(unit or 0);r['_exit_cost']+=qty*price
                if avg is not None:
                    r['matched_contracts']+=qty;r['gross_realized_pnl']+=r['_sign']*(price-avg)*qty*(unit or 0);r['_cost']-=avg*qty
                else:r['pnl_known']=False
                r['remaining_contracts']-=qty
                if not value_ok:r['pnl_known']=False
            if f.get('position_realized_pnl') is not None:
                # A reversal snapshot belongs to the resulting position, never both lifecycles.
                if len(allocations)==1 or entry:r['broker_position_realized_pnl']=f['position_realized_pnl']
        if active.get(key) and active[key]['remaining_contracts']==0:active.pop(key,None)
    current={(p.get('product_id') or p.get('product_symbol'),p.get('settlement_currency')):number(p.get('size')) for p in positions}
    for key,r in active.items():
        if current.get(key,Decimal(0))!=r['_sign']*r['remaining_contracts']:r['verified']=False;r['reconciliation_error']='Remaining quantity differs from broker snapshot'
    for key,size in current.items():
        if size is not None and size!=0 and key not in active:
            p=next(p for p in positions if (p.get('product_id') or p.get('product_symbol'),p.get('settlement_currency'))==key)
            r=new(dict(symbol=p.get('product_symbol'),product_id=p.get('product_id'),settlement_currency=p.get('settlement_currency')),size,True,True)
            r['fees_known']=False
    for r in rows:
        entries=[d for d in r['details'] if d.get('allocation')=='entry'];r['entry_price']=sum((number(d['allocated_contracts'])*number(d['price']) for d in entries),Decimal(0))/r['entry_contracts'] if r['entry_contracts'] else None
        r['exit_price']=r['_exit_cost']/r['exit_contracts'] if r['exit_contracts'] else None
        r['status']=('INCOMPLETE · opening fills missing' if r['missing_opening'] else 'UNRECONCILED' if not r['verified'] else 'OPEN' if r['remaining_contracts'] else 'CLOSED')
        if not history_complete:r['status']+=' · history incomplete'
        r['accounting_basis']='Chronological weighted-average · broker signed position snapshots' if r['verified'] else 'Chronological weighted-average · unverified boundary'
        if not r['values_known']:r['entry_value']=r['exit_value']=None
        if r['missing_opening']:r['entry_value']=None
        if not r['pnl_known'] or not r['verified'] or not r['values_known']:r['gross_realized_pnl']=None
        if not r['fees_known']:r['fees']=None
        # Closed lifecycle fees can be deducted; open entry fees are not assigned to closed portions.
        r['net_realized_pnl']=r['gross_realized_pnl']-r['fees'] if r['gross_realized_pnl'] is not None and r['fees'] is not None and not r['remaining_contracts'] else None
        for k in list(r):
            if k.startswith('_') or k in ('verified','values_known','pnl_known','fees_known'):r.pop(k)
            elif isinstance(r[k],Decimal):r[k]=str(r[k])
    return list(reversed(rows))
