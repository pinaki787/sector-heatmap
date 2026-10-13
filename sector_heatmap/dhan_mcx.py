"""Dhan-native MCX contract discovery.

Symbols identify an exact futures host; never roll a running strategy implicitly.
Execution metadata (valuation/session) must be verified separately.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
from .dhan_execution import IST

def current(row, now):
    try:
        expiry=datetime.strptime(row['SEM_EXPIRY_DATE'],'%Y-%m-%d %H:%M:%S').replace(tzinfo=IST)
    except (KeyError,TypeError,ValueError):
        return False
    return expiry.timestamp()>now

def commodity(row):
    # Dhan supplies this explicitly; avoid splitting names or guessing expiries.
    value=str(row.get('SM_SYMBOL_NAME') or '').strip()
    if not value:raise ValueError('Dhan MCX underlying name is missing.')
    return value

def futures(rows, now, text=''):
    query=''.join(text.upper().removeprefix('MCX:').split())
    result=[r for r in rows if r.get('SEM_EXM_EXCH_ID')=='MCX'
            and r.get('SEM_SEGMENT')=='M' and r.get('SEM_INSTRUMENT_NAME') in ('FUTCOM','FUTIDX')
            and r.get('SEM_OPTION_TYPE')=='XX' and current(r,now)
            and query in ''.join(r.get('SEM_TRADING_SYMBOL','').upper().split())]
    return sorted(result,key=lambda r:(commodity(r),r['SEM_EXPIRY_DATE'],r['SEM_SMST_SECURITY_ID']))

def host(rows,symbol,now):
    matches=[r for r in futures(rows,now) if ('MCX:'+r['SEM_TRADING_SYMBOL']).upper()==symbol.upper()]
    if len(matches)!=1:raise ValueError('Exact unexpired Dhan MCX futures host is missing or ambiguous.')
    return matches[0]

def option_series(rows,future,now):
    # Options on futures expire before their delivery future. Associate each
    # series with its first subsequent same-commodity future, not today's front.
    family=commodity(future)
    hosts=[r for r in futures(rows,now) if commodity(r)==family]
    result=[]
    for row in rows:
        if row.get('SEM_EXM_EXCH_ID')!='MCX' or row.get('SEM_SEGMENT')!='M' or row.get('SEM_OPTION_TYPE') not in ('CE','PE') or not current(row,now):continue
        if commodity(row)!=family:continue
        if family=='MCXBULLDEX' and row['SEM_EXPIRY_DATE'][:10]!=future['SEM_EXPIRY_DATE'][:10]:continue
        following=[r for r in hosts if r['SEM_EXPIRY_DATE']>=row['SEM_EXPIRY_DATE']]
        if following and following[0]['SEM_SMST_SECURITY_ID']==future['SEM_SMST_SECURITY_ID']:
            result.append(row)
    return result

def paired_options(options):
    """Require both sides at the same expiry and strike, not just any CE/PE."""
    pairs={}
    for row in options:
        try:
            strike=Decimal(str(row.get('SEM_STRIKE_PRICE')))
            if not strike.is_finite() or strike<=0:continue
        except InvalidOperation:
            continue
        pairs.setdefault((row['SEM_EXPIRY_DATE'],strike),set()).add(row['SEM_OPTION_TYPE'])
    return {key for key,kinds in pairs.items() if kinds=={'CE','PE'}}

def search(rows,now,text=''):
    # Index option series once. Re-scanning the full security master for every
    # future stalls concurrent searches and status requests on an empty query.
    hosts=futures(rows,now)
    families={}
    for future in hosts:
        families.setdefault(commodity(future),[]).append(future)
    options_by_host={}
    for row in rows:
        if row.get('SEM_EXM_EXCH_ID')!='MCX' or row.get('SEM_SEGMENT')!='M' or row.get('SEM_OPTION_TYPE') not in ('CE','PE') or not current(row,now):
            continue
        family=commodity(row)
        following=[future for future in families.get(family,[])
                   if future['SEM_EXPIRY_DATE']>=row['SEM_EXPIRY_DATE']
                   and (family!='MCXBULLDEX' or future['SEM_EXPIRY_DATE'][:10]==row['SEM_EXPIRY_DATE'][:10])]
        if following:
            options_by_host.setdefault(following[0]['SEM_SMST_SECURITY_ID'],[]).append(row)
    result=[]
    for row in futures(rows,now,text):
        if paired_options(options_by_host.get(row['SEM_SMST_SECURITY_ID'],[])):
            result.append(dict(symbol=('MCX:'+row['SEM_TRADING_SYMBOL']).upper(),
                underlying=row['SEM_CUSTOM_SYMBOL'],description=row['SEM_CUSTOM_SYMBOL'],
                security_id=row['SEM_SMST_SECURITY_ID'],exchange_segment='MCX_COMM'))
    return result[:50]

# Quote-point value per Dhan API contract, not API order quantity.
# Exchange specifications and effective dates are recorded in docs/dhan-mcx-specifications.md.
POINT_VALUES = {
    'CRUDEOIL':100, 'CRUDEOILM':10, 'NATURALGAS':1250, 'NATGASMINI':250,
    'GOLD':100, 'GOLDM':10, 'SILVER':30, 'SILVERM':5, 'COPPER':2500, 'ZINC':5000,
}

def valuation(row):
    family=commodity(row)
    if row.get('SEM_EXM_EXCH_ID')!='MCX' or row.get('SEM_SEGMENT')!='M':
        raise ValueError('MCX valuation requires the native MCX master row.')
    lot=Decimal(str(row.get('SEM_LOT_UNITS')))
    if lot!=1:
        raise ValueError('Dhan MCX API lot convention changed; contract valuation requires review.')
    if family=='MCXBULLDEX':
        # MCX revised November 2026 and later contracts from 30 to 15 index units.
        multiplier=15 if row['SEM_EXPIRY_DATE'][:7]>='2026-11' else 30
    else:
        multiplier=POINT_VALUES.get(family)
    if multiplier is None:raise ValueError('MCX contract valuation is not verified for '+family+'.')
    return dict(quantity_multiplier=multiplier,valuation_source='MCX contract specification / Dhan contract quantity',
                valuation_revision='DHAN_MCX_2026_10',commodity=family,
                expiry_epoch=expiry_at(row))

def session(now):
    local=datetime.fromtimestamp(now,IST)
    # MCX non-agricultural regular session follows US daylight saving.
    ny=local.replace(hour=12,minute=0,second=0,microsecond=0).astimezone(ZoneInfo('America/New_York'))
    ending='2330' if ny.dst()!=timedelta(0) else '2355'
    return dict(session_open='09:00',session_deadline=ending[:2]+':'+ending[2:],
                session_segment='MCX_COMM',session_exchange='MCX',
                session_source='MCX non-agricultural contract regular session',
                master_regular_session='0900-'+ending,seven_day_session=False)

def expiry_at(row):
    expiry=datetime.strptime(row['SEM_EXPIRY_DATE'][:10],'%Y-%m-%d').replace(tzinfo=IST)
    ending='1700' if commodity(row)=='MCXBULLDEX' else session(expiry.timestamp())['master_regular_session'][-4:]
    return expiry.replace(hour=int(ending[:2]),minute=int(ending[2:])).timestamp()

def entry_cutoff(row):
    # Exit before the previous regular session closes; no expiry-day entries or
    # option devolvement. Matching existing commodity carry protection.
    previous=datetime.fromtimestamp(expiry_at(row),IST)-timedelta(days=1)
    while True:
        opening,closing=trading_bounds(previous.timestamp())
        if closing>opening:break
        previous-=timedelta(days=1)
    return (previous.replace(hour=closing//60,minute=closing%60)-timedelta(minutes=30)).timestamp()

# MCX published 2026 holiday sessions. Special Muhurat hours are not assumed.
FULL_CLOSED={'2026-01-26','2026-04-03','2026-10-02','2026-12-25'}
EVENING_ONLY={'2026-03-03','2026-03-26','2026-03-31','2026-04-14','2026-05-01',
              '2026-05-28','2026-06-26','2026-09-14','2026-10-20','2026-11-10','2026-11-24'}
MORNING_ONLY={'2026-01-01'}

def trading_bounds(now):
    day=datetime.fromtimestamp(now,IST)
    if day.year!=2026:raise ValueError('MCX holiday calendar requires an update for '+str(day.year)+'.')
    key=day.date().isoformat()
    if day.weekday()>4 or key in FULL_CLOSED:return 0,0
    end=session(now)['master_regular_session'][-4:]
    return (17*60 if key in EVENING_ONLY else 9*60,
            17*60 if key in MORNING_ONLY else int(end[:2])*60+int(end[2:]))

def session_open(now):
    day=datetime.fromtimestamp(now,IST);opening,closing=trading_bounds(now)
    return opening<=day.hour*60+day.minute<closing
