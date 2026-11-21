"""Telegram market updates require an open, identified exchange session."""
import time
from .holdings_sessions import window

MARKET_KINDS={'SECTOR_CARD','COMBINED_CARD','HANDOFF_CARD','POSITION_SUMMARY'}

def segments(event):
    kind=event.get('kind')
    if kind in {'SECTOR_CARD','COMBINED_CARD'}:
        return [('NSE_EQ',None)]
    snapshot=event.get('snapshot') or {}
    rows=event.get('positions') or snapshot.get('rows') or [event]
    broker=str(event.get('broker') or snapshot.get('broker') or '').upper()
    result=[]
    for row in rows:
        symbol=str(row.get('symbol') or row.get('tradingsymbol') or '').upper()
        exchange=str(row.get('exchange') or row.get('segment') or '').upper()
        venue=symbol.split(':',1)[0] if ':' in symbol else exchange
        if venue.startswith('NSE'):segment,group='NSE_EQ',None
        elif venue.startswith('BSE'):segment,group='BSE_EQ',None
        elif venue.startswith('MCX'):
            segment='MCX_COMM'
            group=row.get('commodity_group') or event.get('commodity_group')
            # Native contract families whose session is non-agricultural.
            native=symbol.split(':')[-1]
            if not group and native.startswith(('NATURALGAS','CRUDEOIL','GOLD','SILVER','COPPER','ZINC','ALUMINIUM','LEAD','NICKEL')):
                group='NON_AGRI'
        elif 'DELTA' in broker or venue in {'DELTA','CRYPTO'}:
            segment,group='DELTA_24X7',None
        elif kind=='HANDOFF_CARD' and broker in {'FYERS','DHAN','MOTILAL'}:
            segment,group='NSE_EQ',None
        else:
            raise ValueError('Exchange session cannot be identified')
        result.append((segment,group))
    return result

def gate(event,created,now=None):
    if event.get("kind")=="COMBINED_CARD" and event.get("completed_run") is True:
        return None,None  # Authorized reporting runs finish even after their start session.
    now=time.time() if now is None else now
    # This module is only called for Telegram market/trade events.
    try:
        venues=segments(event)
        occurred=event.get('time',created)
        occurred=occurred if isinstance(occurred,(int,float)) else created
        for segment,group in venues:
            current=window(segment,now,group)
            original=window(segment,occurred,group)
            if not current['open'] or not original['open']:
                return 'SKIPPED','Exchange closed; market update suppressed without replay'
            if segment!='DELTA_24X7' and occurred < current['close']-86400:
                return 'SKIPPED','Previous-session market update suppressed'
        return None,None
    except (ValueError,TypeError,KeyError,OverflowError):
        return 'SKIPPED','Verified exchange session unavailable; market update suppressed'
