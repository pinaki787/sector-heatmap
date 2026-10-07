"""Position history from explicit ownership links; never pair by contract adjacency."""
from collections import defaultdict
import math


def position_history(orders):
    groups=defaultdict(list)
    for row in orders:
        # Older ledgers have no ownership key. Retain each as unpaired audit evidence.
        key=(row.get('mode'),row.get('strategy'),row.get('lifecycle_id') or 'unpaired:'+str(row.get('tag') or row.get('order_id') or id(row)))
        groups[key].append(row)
    result=[]
    for (mode,strategy,lifecycle),rows in groups.items():
        entries=[r for r in rows if r.get('is_entry',r.get('side')=='BUY')];exits=[r for r in rows if not r.get('is_entry',r.get('side')=='BUY')]
        entry_side=next((r.get('entry_side',1) for r in entries),1)
        def qty(rs):return sum(r.get('filled',0) or 0 for r in rs)
        def avg(rs):
            n=qty(rs)
            return sum(r['filled']*r['average_price'] for r in rs)/n if n and all(not r.get('filled') or isinstance(r.get('average_price'),(float,int)) and math.isfinite(r['average_price']) for r in rs) else None
        bought,sold=qty(entries),qty(exits);buy,sell=avg(entries),avg(exits)
        linked=not lifecycle.startswith('unpaired:') and bool(entries) and len({r.get('symbol') for r in rows})==1
        matched=sold if linked and 0<=sold<=bought else None
        mults={r.get('quantity_multiplier') for r in rows};mult=next(iter(mults)) if len(mults)==1 else None
        pnl=matched*(sell-buy)*mult*entry_side if matched and buy is not None and sell is not None and isinstance(mult,(int,float)) and mult>0 else None
        lots={r.get('lot_size') for r in rows};lot=next(iter(lots)) if len(lots)==1 else None
        result.append(dict(lifecycle_id=lifecycle,contract=rows[0].get('symbol'),mode=mode,strategy=strategy or 'Unavailable (legacy ledger)',entry_order_ids=[r.get('order_id') or r.get('tag') for r in entries],exit_order_ids=[r.get('order_id') or r.get('tag') for r in exits],entry_price=buy,exit_price=sell,invested_amount=bought*buy*mult if bought and buy is not None and isinstance(mult,(int,float)) and mult>0 else None,realized_pnl=pnl,pnl_percent=100*(sell-buy)*entry_side/buy if matched and buy and sell is not None else None,basis='Before fees; confirmed matched fills only',matched_quantity=matched,remaining_quantity=bought-sold if linked and sold<=bought else None,entry_requested=sum(r.get('requested',0) for r in entries),exit_requested=sum(r.get('requested',0) for r in exits),entry_filled=bought,exit_filled=sold,lots=bought/lot if bought and isinstance(lot,(int,float)) and lot>0 else None,entry_time=min((r.get('filled_at',r.get('updated_at')) for r in entries if r.get('filled')),default=None),exit_time=None if any(r.get('reason')=='EXTERNAL_MANUAL_EXIT_RECONCILIATION' for r in exits) else max((r.get('filled_at',r.get('updated_at')) for r in exits if r.get('filled')),default=None),exit_time_detail='External fill time unavailable' if any(r.get('reason')=='EXTERNAL_MANUAL_EXIT_RECONCILIATION' for r in exits) else None,entry_types=list(dict.fromkeys(r.get('requested_type') for r in entries)),exit_types=list(dict.fromkeys(r.get('requested_type') for r in exits)),products=list(dict.fromkeys(r.get('product') for r in rows)),entry_reasons=list(dict.fromkeys(r.get('reason') for r in entries)),exit_reasons=list(dict.fromkeys(r.get('reason') for r in exits)),status='PAIRING UNAVAILABLE' if not linked else 'UNFILLED' if not bought else 'CLOSED' if sold==bought else 'PARTIAL EXIT' if sold else 'OPEN',orders=rows))
    return list(reversed(result))


def verified_legacy_rows(orders,events,position,config,metadata=None,links=None):
    """Recover only links anchored by retained fill events or audited ownership snapshots."""
    rows=[{**r,**(metadata or {}).get(r.get('symbol'),{})} for r in orders]
    for r in rows:
        if not r.get('strategy'):
            r['strategy']='EMA Cloud (historical)' if r.get('reason')=='EMA_CLOSE_ENTRY' else 'RSI (historical MA unavailable)' if r.get('reason')=='RSI_CLOSE_ENTRY' else 'Unavailable (legacy ledger)'
    for link in links or []:
        entries=[r for r in rows if r.get('order_id')==link['entry_order_id'] and r.get('symbol')==link['symbol'] and r.get('mode')==link['mode'] and r.get('filled')==link['quantity'] and r.get('average_price')==link['entry_price']]
        exits=[r for r in rows if r.get('order_id') in link['exit_order_ids'] and r.get('symbol')==link['symbol'] and r.get('mode')==link['mode'] and r.get('filled')==link['quantity'] and r.get('average_price')==link['exit_price']]
        if len(entries)==1 and len(exits)==len(link['exit_order_ids']):
            for r in entries+exits:r.update(lifecycle_id=entries[0]['tag'],strategy=link['strategy'],linkage_source=link['source'])
    def confirmed(r,status):
        prefix=f"{r['reason']}: confirmed {r['filled']} filled at {r['average_price']};"
        return any(e.get('status')==status and abs(e['at']-r['updated_at'])<.1 and e.get('message','').startswith(prefix) for e in events)
    owner=None;remaining=0
    for r in sorted(rows,key=lambda r:r['submitted_at']):
        if r.get('lifecycle_id'):continue
        if r.get('side')=='BUY':
            if owner:owner=None;continue
            if r.get('filled',0)>0 and confirmed(r,'POSITION_OPEN'):
                r['lifecycle_id']=r['tag'];owner=r;remaining=r['filled']
        elif owner and r.get('filled',0)>0 and r['filled']<=remaining and all(r.get(k)==owner.get(k) for k in ('symbol','mode','product')) and confirmed(r,'FLAT' if r['filled']==remaining else 'POSITION_OPEN'):
            r.update(lifecycle_id=owner['lifecycle_id'],strategy=owner['strategy']);remaining-=r['filled']
            if not remaining:owner=None
        elif r.get('filled'):owner=None
    if position:
        matches=[r for r in rows if r.get('side')=='BUY' and r.get('symbol')==position['symbol'] and r.get('mode')==config.get('mode') and r.get('filled')==position['quantity'] and r.get('average_price')==position['entry_price'] and abs(r['updated_at']-position['opened_at'])<.1 and (not position.get('entry_order_id') or r.get('order_id')==position['entry_order_id'])]
        if len(matches)==1:
            r=matches[0];r.update(lifecycle_id=r.get('lifecycle_id') or r['tag'],lot_size=position.get('lot_size'),quantity_multiplier=position.get('quantity_multiplier'))
            if r['reason']=='RSI_CLOSE_ENTRY':r['strategy']=config.get('label',r['strategy'])
    return rows
