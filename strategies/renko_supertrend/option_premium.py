"""Optional FYERS index-option premium selection using fresh executable asks."""
import math
import time

REVISION='index-target-premium-v1'
MAX_CANDIDATES=61

def index_option(config):
    symbol=str(config.get('underlying',config.get('symbol','')))
    return (symbol.startswith(('NSE:','BSE:')) and symbol.endswith('-INDEX')
            and config.get('execution_route','OPTIONS')=='OPTIONS'
            and config.get('broker','FYERS')=='FYERS')

def native_option(config):
    return (config.get('broker') in ('DHAN','MOTILAL_OSWAL')
            and str(config.get('underlying',config.get('symbol',''))).startswith(('NSE:','BSE:','MCX:'))
            and config.get('execution_route','OPTIONS')=='OPTIONS')

def native_option(config):
    return (config.get('broker') in ('DHAN','MOTILAL_OSWAL')
            and str(config.get('underlying',config.get('symbol',''))).startswith(('NSE:','BSE:','MCX:'))
            and config.get('execution_route','OPTIONS')=='OPTIONS')

def settings(payload):
    value=payload.get('target_option_premium')
    if value in (None,''):
        return {'target_option_premium':None}
    try:target=float(value)
    except (TypeError,ValueError,OverflowError):
        raise ValueError('Target option premium must be a positive amount or blank.') from None
    if isinstance(value,bool) or not math.isfinite(target) or target<=0:
        raise ValueError('Target option premium must be a positive amount or blank.')
    if not (index_option(payload) or native_option(payload)):
        raise ValueError('Target option premium requires supported Indian options; cash and futures routes cannot use it.')
    return {'target_option_premium':target}

def candidates(adapter,config,atm):
    host=adapter.underlying(config['underlying'])
    segment=config['underlying'].split(':')[0]+'_FO'
    rows=[]
    for row in adapter.rows(segment):
        if len(row)<17 or row[13]!=host[13] or row[16]!=atm['option_type']:
            continue
        try:
            expiry=int(float(row[8]));strike=float(row[15])
            if expiry!=atm['expiry_epoch'] or expiry<=time.time() or strike<=0 or not math.isfinite(strike):
                continue
            if float(row[3])<=0 or float(row[4])<=0 or not row[9]:continue
        except (TypeError,ValueError,OverflowError):continue
        rows.append({'symbol':row[9],'strike':strike,'expiry_epoch':expiry,'option_type':row[16]})
    # Bound websocket interests and per-event work. No REST quote polling.
    return sorted(rows,key=lambda row:(abs(row['strike']-atm['strike']),row['strike'],row['symbol']))[:MAX_CANDIDATES]

def choose(adapter,config,atm):
    target=settings(config)['target_option_premium']
    if target is None:return atm
    started=time.perf_counter()
    rows=candidates(adapter,config,atm);available=[]
    candidates_done=time.perf_counter()
    if hasattr(adapter,'symbols') and hasattr(adapter,'lock') and hasattr(adapter,'subscribe_all'):
        with adapter.lock:adapter.symbols.update(row['symbol'] for row in rows)
        adapter.subscribe_all()

    for row in rows:
        try:
            quote=adapter.quote(row['symbol'])
            bid,ask=float(quote['bid']),float(quote['ask']);now=time.time()
            if not all(math.isfinite(v) for v in (bid,ask)) or not 0<bid<=ask:continue
            if any(not isinstance(quote.get(k),(int,float)) or not 0<=now-quote[k]<=15 for k in ('received_at','exchange_at')):continue
            available.append((row,quote))
        except (ValueError,RuntimeError,KeyError,TypeError):
            continue # quote() requests missing socket interests; no invented prices.
    scan_done=time.perf_counter()
    now=time.time()
    # Quotes can change while the bounded scan runs. Compare all candidates
    # at selection time; never keep a quote that aged out during the scan.
    available=[item for item in available if all(
        isinstance(item[1].get(k),(int,float)) and 0<=now-item[1][k]<=15
        for k in ('received_at','exchange_at'))]
    if not available:
        raise ValueError('Index option premiums are warming: waiting for fresh two-sided quotes near ATM; no entry sent.')
    row,quote=min(available,key=lambda item:(abs(item[1]['ask']-target),abs(item[0]['strike']-atm['strike']),item[0]['strike'],item[0]['symbol']))
    metadata_started=time.perf_counter()
    selected={**atm,**row,**adapter.contract(row['symbol'])}
    finished=time.perf_counter()
    selected['premium_selection']={
        'revision':REVISION,'target_premium':target,'selected_ask':quote['ask'],
        'selected_bid':quote['bid'],'difference':abs(quote['ask']-target),
        'observed_at':now,'exchange_at':quote['exchange_at'],
        'quoted_candidates':len(available),'candidate_count':len(rows),
        'basis':'Closest fresh executable ask across nearby strikes in the nearest expiry',
        'selection_timing_seconds':{
            'candidate_scan':candidates_done-started,
            'quote_scan':scan_done-candidates_done,
            'selected_metadata':finished-metadata_started,
            'total':finished-started}}
    return selected


def choose_native(adapter,config,contracts,spot):
    """Every entry resolves anew; callers enforce underlying, side and expiry."""
    target=settings(config)['target_option_premium']
    if target is None:raise ValueError('Native premium selection requires an explicit target.')
    rows=sorted(contracts,key=lambda r:(abs(float(r['strike'])-spot),float(r['strike']),r['symbol']))[:MAX_CANDIDATES]
    if not rows:raise ValueError('No eligible option contracts for target premium selection.')
    quotes=adapter.premium_quotes(rows) if hasattr(adapter,'premium_quotes') else {}
    available=[]
    for row in rows:
        try:
            quote=quotes.get(row['symbol']) if hasattr(adapter,'premium_quotes') else adapter.quote(row['symbol'])
            bid,ask=float(quote['bid']),float(quote['ask']);now=adapter.clock()
            if not all(math.isfinite(v) for v in (bid,ask)) or not 0<bid<=ask:continue
            if any(not isinstance(quote.get(k),(int,float)) or not 0<=now-quote[k]<=15 for k in ('received_at','exchange_at')):continue
            available.append((row,quote))
        except (ValueError,RuntimeError,KeyError,TypeError):continue
    if not available:raise ValueError('Target option premium is waiting for fresh two-sided quotes; no ATM fallback or entry sent.')
    row,quote=min(available,key=lambda item:(abs(item[1]['ask']-target),abs(float(item[0]['strike'])-spot),float(item[0]['strike']),item[0]['symbol']))
    selected={**row,'premium_selection':dict(revision=REVISION,target_premium=target,selected_ask=quote['ask'],selected_bid=quote['bid'],difference=abs(quote['ask']-target),observed_at=adapter.clock(),exchange_at=quote['exchange_at'],quoted_candidates=len(available),candidate_count=len(rows),basis='Closest fresh executable ask across nearby strikes in the nearest expiry')}

    adapter.resolved_contracts=getattr(adapter,'resolved_contracts',{})
    adapter.resolved_contracts[selected['symbol']]=dict(selected)
    return selected
