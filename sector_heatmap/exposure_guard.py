"""Selected-broker symbol/underlying exposure; never combines broker accounts."""
import math
import re

ALIASES={'NIFTY50':'NIFTY','NIFTYBANK':'BANKNIFTY','NIFTYFIN':'FINNIFTY','NIFTYMIDSELECT':'MIDCPNIFTY'}
PENDING={'3','4','6','PENDING','OPEN','TRANSIT','PART_TRADED','PARTIALLY_FILLED','TRIGGER_PENDING','VALIDATION_PENDING'}
TERMINAL_ORDERS={'1','2','5','7','CANCEL','CANCELLED','CANCELED','TRADED','FILLED','CLOSED','COMPLETE','COMPLETED','REJECTED','ERROR','EXPIRED'}


def symbol_key(symbol):
    text=str(symbol or '').strip().upper()
    if not text:return None
    exchange,sep,name=text.partition(':')
    if not sep:exchange='';name=text
    name=re.sub(r'-(EQ|BE|BZ|INDEX|A|B)$','',name)
    derivative=re.fullmatch(r'([A-Z][A-Z0-9&_\-]*?)(?:\d{2}[A-Z]{1,3}\d{0,2}|\d{6})\d*(?:CE|PE|FUT)',name)
    if derivative:name=derivative.group(1)
    return (exchange,ALIASES.get(name,name))


def same_underlying(first,second):
    a,b=symbol_key(first),symbol_key(second)
    return bool(a and b and a[1]==b[1] and (not a[0] or not b[0] or a[0]==b[0]))


def open_exposures(positions,orders=()):
    result=[]
    for row in positions:
        raw=next((row[k] for k in ('netQty','net_qty','netQuantity','quantity','qty') if row.get(k) is not None),None)
        try:quantity=float(raw)
        except (TypeError,ValueError):raise ValueError('Broker position quantity unavailable; duplicate exposure cannot be ruled out.') from None
        if not math.isfinite(quantity):raise ValueError('Broker position quantity invalid.')
        if quantity:result.append(row)
    for row in orders:
        status=str(row.get('status',row.get('orderStatus',''))).upper()
        if status in PENDING:result.append(row)
        elif status not in TERMINAL_ORDERS:raise ValueError('Broker order status unavailable or unknown; duplicate exposure cannot be ruled out.')
    return result


def matches_exposure(symbol,rows,contract_symbols=()):
    requested=[symbol,*contract_symbols]
    for row in rows:
        symbols=[row.get(k) for k in ('symbol','tradingSymbol','trading_symbol','underlying','underlyingSymbol','underlying_symbol','customSymbol') if row.get(k)]
        if not symbols:raise ValueError('Broker exposure symbol unavailable; no new entry is eligible.')
        if any(same_underlying(a,b) for a in requested for b in symbols):return True
    return False


def exclude_exposure(candidates,positions,orders=()):
    rows=open_exposures(positions,orders);eligible=[];excluded=[]
    for candidate in candidates:
        (excluded if matches_exposure(candidate.get('symbol'),rows) else eligible).append(candidate)
    return eligible,excluded


def exclude_handoff_cards(candidates,cards,positions,orders=()):
    eligible,excluded=exclude_exposure(candidates,positions,orders)
    keys={candidate['key'] for candidate in eligible}
    return eligible,[card for card in cards if card.get('candidate_key') in keys],excluded


def broker_exposures(broker):
    """Resolve opaque native contract IDs with this account's own master."""
    positions=broker.positions()
    if hasattr(broker,'service') and getattr(broker,'account_identity',None) and any(c.__module__.endswith('motilal_strategy_broker') for c in type(broker).__mro__):
        from .motilal_strategy_broker import STATES
        orders=[]
        for row in broker.service.book('orders')['data']:
            state=STATES.get(str(row.get('orderstatus') or '').strip().upper())
            if state is None:raise ValueError('Native order status unknown; duplicate exposure cannot be excluded.')
            if state in (3,4,6):orders.append(dict(symbol='MO:'+str(row['exchange'])+':'+str(row['symboltoken']),status=state))
    else:orders=broker.orders()
    rows=open_exposures(positions,orders)
    result=[]
    for row in rows:
        symbol=row.get('symbol','')
        if any(c.__module__.endswith('dhan_strategy_broker') for c in type(broker).__mro__):
            from .dhan_handoff import contract_underlying
            segment,security=symbol.split(':',1)
            matches=[r for r in broker._rows() if str(r['SEM_SMST_SECURITY_ID'])==security and broker._segment(r)==segment]
            if len(matches)!=1:raise ValueError('Dhan exposure has no unique native master mapping.')
            row={**row,'underlying':matches[0]['SEM_EXM_EXCH_ID']+':'+contract_underlying(matches[0])}
        if symbol.startswith(('MO:','DHAN:')):
            meta=broker.contract(symbol)
            exchange=str(meta.get('exchange') or meta.get('exchange_segment') or '').removesuffix('FO')
            underlying=meta.get('underlying') or meta.get('underlying_symbol')
            if not exchange or not underlying:raise ValueError('Native exposure underlying mapping unavailable.')
            row={**row,'underlying':exchange+':'+str(underlying)}
        result.append(row)
    return result
