"""Authorized official TradingView native sizing. Never submits broker orders.

Connection access is scoped to its authorizing application user. References remain
scoped to exact execution account, broker, symbol, parent and regular session.
"""
import hashlib,json,math,re,sqlite3,time,threading,fcntl
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime,timedelta,time as day_time,timezone
from zoneinfo import ZoneInfo
try:
    from .run import ROOT,atomic
    from .sizing_policy import instrument_contract
    from .tradingview_native import NativePineClient
    from .tradingview_oauth import access_token
except ImportError:
    from run import ROOT,atomic
    from sizing_policy import instrument_contract
    from tradingview_native import NativePineClient
    from tradingview_oauth import access_token
DATA=ROOT/'.private/nifty-ai-options'
POLICY=DATA/'tradingview/production-policy.json'
REVISION='official-native-20261124'
IST=ZoneInfo('Asia/Kolkata')
LOCK=threading.RLock()
JOBS={}
INDEX_ALIASES={'NSE:NIFTY50-INDEX':'NSE:NIFTY','NSE:NIFTYBANK-INDEX':'NSE:BANKNIFTY',
 'NSE:FINNIFTY-INDEX':'NSE:CNXFINANCE','NSE:NIFTYMIDCAPSELECT-INDEX':'NSE:NIFTY_MID_SELECT',
 'NSE:MIDCPNIFTY-INDEX':'NSE:NIFTY_MID_SELECT','BSE:SENSEX-INDEX':'BSE:SENSEX','BSE:BANKEX-INDEX':'BSE:BANKEX',
 'NSE:NIFTYNXT50-INDEX':'NSE:NIFTYJR'}
MONTHS={'JAN':'F','FEB':'G','MAR':'H','APR':'J','MAY':'K','JUN':'M','JUL':'N','AUG':'Q','SEP':'U','OCT':'V','NOV':'X','DEC':'Z'}

def authorize(owner,broker):
    if not isinstance(owner,str) or not re.fullmatch(r'[a-f0-9]{32}',owner):raise ValueError('Exact registered account required')
    try:policy=json.loads(POLICY.read_text())
    except (OSError,ValueError):raise ValueError('Authorized TradingView sizing connection unavailable') from None
    with sqlite3.connect((ROOT/'.private/dashboard-login/registry.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('select user_id,broker from accounts where id=?',(owner,)).fetchone()
    if not row or row[1]!=broker:raise ValueError('Sizing broker/account registration mismatch')
    if policy.get('enabled') is not True or policy.get('authorized_user_id')!=row[0]:
        raise ValueError('This application user has not authorized a TradingView sizing connection')
    return row[0]

def map_symbol(symbol,broker):
    if not isinstance(symbol,str) or not symbol or len(symbol)>100:raise ValueError('Exact selected broker symbol required')
    if broker=='DELTA_INDIA':
        if not re.fullmatch(r'[A-Z0-9]+USD',symbol):raise ValueError('No exact Delta perpetual reference mapping for selected symbol')
        return 'DELTAIN:'+symbol+'.P'
    if broker!='FYERS':raise ValueError('Selected broker sizing adapter is unavailable')
    if symbol in INDEX_ALIASES:return INDEX_ALIASES[symbol]
    match=re.fullmatch(r'(NSE|BSE):([A-Z0-9_&.-]+)-EQ',symbol)
    if match:return match[1]+':'+match[2]
    match=re.fullmatch(r'(NSE|BSE|MCX):([A-Z0-9_&.-]+?)([0-9]{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)FUT',symbol)
    if match:return match[1]+':'+match[2]+MONTHS[match[4]]+'20'+match[3]
    if re.fullmatch(r'(NSE|BSE):[A-Z0-9_&.-]+-INDEX',symbol):return symbol[:-6]
    if re.fullmatch(r'(NSE|BSE|MCX):[A-Z0-9_&.-]+',symbol):return symbol
    raise ValueError('No exact TradingView mapping for '+symbol+'; no alternate instrument used')

def context(config):
    expected=instrument_contract(config['market'],config.get('asset'),is_option=config.get('execution_route')=='OPTIONS',explicit_category=config.get('sizing_category'),option_moneyness=config.get('option_moneyness','OTM'))
    return dict(expected,tv_symbol=config.get('_resolved_tv_symbol') or ('NATIVE_PENDING:'+config['underlying'] if config['broker'] in ('DHAN','MOTILAL_OSWAL') else map_symbol(config['underlying'],config['broker'])),broker_symbol=config['underlying'],broker=config['broker'],account=config['account'])

def key(config):
    scope=context(config);scope.pop('tv_symbol',None)
    return hashlib.sha256(json.dumps(scope,sort_keys=True).encode()).hexdigest()

def parent_key(config):
    scope=context(config);scope.pop('tv_symbol',None)
    for field in ('option_divisor','option_multiplier','option_moneyness'):scope.pop(field,None)
    return hashlib.sha256(json.dumps(scope,sort_keys=True).encode()).hexdigest()

def legacy_variants(config):
    result={}
    for route,classification in (('DIRECT','OTM'),('OPTIONS','OTM'),('OPTIONS','ATM')):
        variant=dict(config,execution_route=route,option_moneyness=classification)
        result[key(variant)]=variant
    result[key(config)]=config
    return result

def import_session_state(config,lease,now,path):
    candidates=[]
    for ident in legacy_variants(config):
        legacy=DATA/'native-session-cache'/config['account']/(ident+'.json')
        if legacy==path:continue
        with disk_lock(legacy.with_suffix('.lock')):value=read_state(legacy)
        if isinstance(value,dict) and value.get('session')==lease['id'] and value.get('symbol',config['underlying'])==config['underlying'] and value.get('state') in ('READY','RUNNING','FAILED'):
            candidates.append((ident,value))
    if not candidates:return {}
    base=dict(session=lease['id'],symbol=config['underlying'],updated_at=now,migrated_scope_keys=[ident for ident,_ in candidates])
    if any(value['state']=='RUNNING' for _,value in candidates):
        saved=dict(base,state='FAILED',error='Previous native sizing attempt is unresolved; automatic fetching paused for this session',retry_after=lease['valid_until'])
    else:
        refs=[value.get('reference') for _,value in candidates if value['state']=='READY']
        ctx=context(config)
        valid=[ref for ref in refs if isinstance(ref,dict) and ref.get('account')==config['account'] and ref.get('broker')==config['broker'] and (ref.get('broker_symbol') or ref.get('symbol'))==config['underlying'] and ref.get('parent_hours')==ctx['parent_hours'] and ref.get('atr_length')==ctx['atr_length'] and ref.get('verified_native_size') is True and ref.get('status')=='VERIFIED_OFFICIAL_NATIVE' and ref.get('chart_session')=='Regular trading hours' and ref.get('reference_measure')=='NATIVE_RENKO_ATR_BOX' and ref.get('valid_until',0)>now and isinstance(ref.get('native_box'),(int,float)) and not isinstance(ref.get('native_box'),bool) and math.isfinite(ref['native_box']) and ref['native_box']>0]
        if refs and len(valid)==len(refs) and len({ref['native_box'] for ref in valid})==1:
            saved=dict(base,state='READY',reference=valid[0])
        elif refs:
            saved=dict(base,state='FAILED',error='Saved parent sizing values require reconciliation; no automatic fetch was repeated',retry_after=lease['valid_until'])
        else:
            failures=[value for _,value in candidates if value['state']=='FAILED']
            previous=max(failures,key=lambda value:value.get('updated_at',0))
            saved=dict(base,state='FAILED',error=previous.get('error') or 'Native sizing failed; automatic fetching paused for this session',retry_after=previous.get('retry_after',lease['valid_until']))
    atomic(path,saved)
    return saved

def resolve_symbol(config,client):
    symbol=config['underlying']
    if config['broker'] in ('DHAN','MOTILAL_OSWAL'):
        try:from .native_indian import bound_native,map_native_host
        except ImportError:from native_indian import bound_native,map_native_host
        adapter=bound_native(config)
        return map_native_host(config,adapter.native.underlying(symbol))
    candidate=map_symbol(symbol,config['broker'])
    if config['broker']!='FYERS' or not symbol.endswith('-INDEX') or symbol in INDEX_ALIASES:return candidate
    try:from .instrument_search import master_rows
    except ImportError:from instrument_search import master_rows
    exchange=symbol.split(':')[0]
    rows=[r for r in master_rows(DATA/'instrument-master'/config['account'],exchange+'_CM') if r[9]==symbol]
    if len(rows)!=1:raise ValueError('Selected index not found uniquely in current broker master')
    description=rows[0][1]
    result=client.search_symbols(description.removesuffix('-INDEX'),type_filter='index')
    data=result.get('structuredContent') or {}
    if result.get('isError') or data.get('success') is not True:raise ValueError('Native index symbol lookup unavailable')
    def normalized(value):return re.sub(r'[^A-Z0-9]','',value.upper().replace('S&P','').replace('INDEX',''))
    wanted=normalized(description)
    matches=[r['symbol'] for r in data.get('data',{}).get('symbols',[]) if r.get('exchange')==exchange and r.get('type')=='index' and normalized(r.get('description',''))==wanted]
    if len(set(matches))!=1:raise ValueError('No unique same-exchange native index matches the selected broker master')
    return matches[0]

def parse_result(reply,config,*,now=None):
    now=time.time() if now is None else now;ctx=context(config)
    if ctx['tv_symbol'].startswith('NATIVE_PENDING:'):raise ValueError('Native sizing host metadata has not been verified')
    data=reply.get('structuredContent') or {}
    if reply.get('isError') or data.get('success') is not True:
        raw=json.dumps(reply)
        if 'TOOL_QUOTA_EXCEEDED' in raw:
            raise ValueError('TradingView native sizing quota exceeded; automatic fetching paused for this session')
        raise ValueError('TradingView native sizing calculation failed; automatic fetching paused for this session')
    if data.get('symbol')!=ctx['tv_symbol'] or data.get('timeframe')!='30m':raise ValueError('TradingView sizing symbol/timeframe mismatch')
    names={p['title']:p['id'] for p in data.get('metainfo',{}).get('plots',[])}
    values=(data.get('last_values') or {}).get('plots',{})
    def number(name):
        v=values.get(names.get(name))
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('Native sizing result lacks '+name)
        return v
    box=number('Completed native box');start=number('Completed parent start')/1000;end=number('Completed parent end')/1000
    native=number('Completed native time')/1000;calculated=number('Calculated at')/1000;host_end=number('Host end')/1000
    current_start=number('Current parent start')/1000;current_end=number('Current parent end')/1000
    if box<=0 or not 0<start<end<=now or end-start>ctx['parent_minutes']*60+1:raise ValueError('Native sizing has no valid completed parent window')
    if not 0<=now-calculated<=120:raise ValueError('Native sizing calculation timestamp is stale or in the future')
    if native>end or native<=0:raise ValueError('Native sizing uses a future or invalid Renko source observation')
    session=datetime.fromtimestamp(end,IST).date().isoformat()
    if config['market'] in ('NSE','BSE'):
        from sector_heatmap.market_calendar import market_session
        calendar=market_session(datetime.fromtimestamp(now,IST))
        expected=calendar['last_completed_session']
        if session!=expected:raise ValueError('Native sizing is not from the expected completed regular session')
        # A previous-session reference does not require current-session quotes.
        # Validate host coverage against the requested completed window, not now.
        # Native Renko time may identify a carried brick and is a separate clock.
        if host_end<end or host_end>now+1800:
            raise ValueError('TradingView host data does not cover the completed reference window')
        if calendar.get('last_completed_session_close'):
            close=datetime.fromisoformat(calendar['last_completed_session_close']).timestamp()
            if end<close-1800 or end>close:
                raise ValueError('Native reference does not cover the completed regular-session close')
    elif config['market']=='MCX':
        # Overnight/holiday gaps are not trading time. A shortened regular
        # session may still have an open parent while yesterday's is authoritative.
        if now-end>7*86400:raise ValueError('Completed MCX native parent reference is stale')
        if current_end>now and (end>current_start or not -1800<=now-host_end<=3600):
            raise ValueError('MCX current regular-session source is stale or inconsistent')
    elif now-end>ctx['parent_hours']*3600+1800:
        raise ValueError('Completed native parent reference is stale')
    if config['broker']=='DELTA_INDIA' and not -1800<=now-host_end<=3600:raise ValueError('TradingView crypto source is stale')
    lease=session_scope(config,now=now)
    valid_until=lease['valid_until']
    return dict(ctx,reference_measure='NATIVE_RENKO_ATR_BOX',renko_method='ATR',source_price='Close',wicks=False,
        symbol=config['underlying'],native_box=box,chart_session='Regular trading hours',chart_type='Renko',
        reference_session=session,completed_parent_at=end,completed_parent_start=start,completed_parent=True,
        verified_native_size=True,status='VERIFIED_OFFICIAL_NATIVE',native_provider='TRADINGVIEW',
        source='TradingView official native calculation',url='https://www.tradingview.com/',
        observed_at=datetime.fromtimestamp(now,IST).isoformat(),calculated_at=calculated,host_end=host_end,
        native_observation_at=native,native_observation_role='LAST_NATIVE_BRICK_TIME',
        native_observation_carried=native<start,host_data_checked_at=now,
        current_parent_start=current_start,current_parent_end=current_end,
        valid_until=valid_until,sizing_session=lease['id'],session_cache_revision='session-frozen-v1',provider_revision=REVISION,execution_data_source='SELECTED_BROKER',
        whole_session=config['market'] in ('NSE','BSE'))

def _acquire(config,*,client_factory=None,now=None):
    authorize(config['account'],config['broker'])
    client=(client_factory or (lambda:NativePineClient(access_token)))()
    try:
        config=dict(config,_resolved_tv_symbol=resolve_symbol(config,client));ctx=context(config)
        reply=client.run_sizing(ctx['tv_symbol'],parent_minutes=ctx['parent_minutes'],atr_length=ctx['atr_length'],whole_session=config['market'] in ('NSE','BSE'))
        ref=parse_result(reply,config,now=now)
    finally:client.close()
    path=DATA/'references'/config['account']/(key(config)+'.json')
    # Completed-window identity includes the calculation method and exact account context.
    # Retain prior observations for auditing instead of overwriting their source evidence.
    archive=DATA/'reference-observations'/config['account']/(key(config)+'-'+str(int(ref['calculated_at']*1000))+'.json')
    if path.exists():
        previous=json.loads(path.read_text())
        if previous.get('completed_parent_at')==ref['completed_parent_at'] and previous.get('native_box')!=ref['native_box']:
            atomic(archive,dict(ref,status='REJECTED_SAME_WINDOW_REVISION',verified_native_size=False))
            raise ValueError('Native sizing revised the same completed window; new entries require a reconciled reference')
    atomic(archive,ref);atomic(path,ref)
    return ref


def session_scope(config,*,now=None):
    """Acquisition lease, separate from the native parent/window anchor.
    Indian pre-open belongs to the upcoming session. MCX daily leases roll at
    09:00 IST (not its seasonally variable close); broker gates still govern
    actual holidays/shortened trading. Continuous products use UTC calendar days.
    """
    now=time.time() if now is None else now
    local=datetime.fromtimestamp(now,IST)
    if config['market'] in ('NSE','BSE'):
        from sector_heatmap.market_calendar import market_session,next_trading_day,NSE_SPECIAL_SESSIONS,REGULAR_OPEN
        calendar=market_session(local)
        opening=datetime.fromisoformat(calendar['next_open'])
        day=opening.date()
        following=next_trading_day(day+timedelta(days=1))
        boundary=datetime.combine(following,NSE_SPECIAL_SESSIONS.get(following,(REGULAR_OPEN,))[0],IST)
    elif config['market']=='MCX':
        day=local.date()
        while day.weekday()>4:day+=timedelta(days=1)
        following=day+timedelta(days=1)
        while following.weekday()>4:following+=timedelta(days=1)
        boundary=datetime.combine(following,day_time(9),IST)
    else:
        utc=datetime.fromtimestamp(now,timezone.utc)
        day=utc.date()
        boundary=datetime.combine(day+timedelta(days=1),day_time(),timezone.utc)
    return dict(id=config['market']+':'+day.isoformat(),valid_until=boundary.timestamp())

@contextmanager
def disk_lock(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)

def read_state(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return {}

def session_path(config):
    return DATA/'native-session-cache'/config['account']/(parent_key(config)+'.json')

def acquire(config,*,client_factory=None,now=None):
    user=authorize(config['account'],config['broker'])
    supplied_now=now
    now=time.time() if now is None else now
    lease=session_scope(config,now=now);path=session_path(config)
    with disk_lock(path.with_suffix('.lock')):
        saved=read_state(path)
        if saved.get('session')!=lease['id']:saved=import_session_state(config,lease,now,path) or saved
        if saved.get('session')==lease['id']:
            if saved.get('state')=='READY':return saved['reference']
            if saved.get('state')=='FAILED':raise ValueError(saved['error'])
            if saved.get('state')=='RUNNING':
                # A previous process may have died after sending the request.
                # Never duplicate an uncertain provider attempt in this session.
                raise ValueError('Native sizing attempt interrupted; automatic fetching paused for this session')
        # Import only a still-valid, identity-bound existing reference. Do not
        # extend expired legacy leases or bless stale references.
        existing=read_state(DATA/'references'/config['account']/(key(config)+'.json'))
        if (existing.get('verified_native_size') is True and existing.get('status')=='VERIFIED_OFFICIAL_NATIVE'
            and existing.get('account')==config['account'] and existing.get('broker')==config['broker']
            and existing.get('valid_until',0)>now
            and (existing.get('sizing_session')==lease['id'] or
                 existing.get('observed_at') and session_scope(config,now=datetime.fromisoformat(existing['observed_at']).timestamp())['id']==lease['id'])):
            ref=dict(existing,valid_until=lease['valid_until'],sizing_session=lease['id'],session_cache_revision='session-frozen-v1')
            atomic(path,dict(session=lease['id'],symbol=config['underlying'],state='READY',reference=ref,updated_at=now))
            atomic(DATA/'references'/config['account']/(key(config)+'.json'),ref)
            return ref
        gate=DATA/'native-session-cache'/('connection-'+str(user)+'.json')
        with disk_lock(gate.with_suffix('.lock')):
            cooldown=read_state(gate)
            if cooldown.get('retry_after',0)>now:
                error='TradingView native sizing quota cooldown active; automatic fetching paused for this session'
                atomic(path,dict(session=lease['id'],symbol=config['underlying'],state='FAILED',error=error,updated_at=now,retry_after=lease['valid_until']))
                raise ValueError(error)
            atomic(path,dict(session=lease['id'],symbol=config['underlying'],state='RUNNING',updated_at=now))
            try:
                ref=_acquire(config,client_factory=client_factory,now=supplied_now)
                atomic(path,dict(session=lease['id'],symbol=config['underlying'],state='READY',reference=ref,updated_at=now))
                return ref
            except Exception as exc:
                error=str(exc) if isinstance(exc,ValueError) else 'TradingView sizing connection unavailable; automatic fetching paused for this session'
                atomic(path,dict(session=lease['id'],symbol=config['underlying'],state='FAILED',error=error,updated_at=now,retry_after=lease['valid_until']))
                if 'quota' in error.lower():
                    # Daily quota can outlast a short MCP cooldown. Never retry
                    # this connection automatically sooner than next UTC day.
                    utc=datetime.fromtimestamp(now,timezone.utc)
                    retry=datetime.combine(utc.date()+timedelta(days=1),day_time(),timezone.utc).timestamp()
                    atomic(gate,dict(retry_after=max(now+600,retry),error_code='TOOL_QUOTA_EXCEEDED'))
                raise ValueError(error) from None

def apply_reference(config,ref):
    projection={field:context(config)[field] for field in ('option_divisor','option_multiplier','option_moneyness')}
    reference_context=dict(ref,**projection,projection_context='CURRENT_CONFIGURATION')
    return dict(config,reference_source='verified_native_cache',reference_value=ref['native_box'],reference_symbol=config['underlying'],
        reference_session=ref['reference_session'],reference_evidence=ref['source']+' · '+ref['tv_symbol'],reference_state='VERIFIED',
        reference_valid_until=ref['valid_until'],reference_completed_parent_at=ref['completed_parent_at'],reference_native_provider='TRADINGVIEW',
        native_provider_revision=REVISION,reference_context=reference_context)

def manual_parent_reference(config,*,now=None):
    """Explicit user-supplied parent value; never a verified provider result."""
    now=time.time() if now is None else now
    value=config.get('manual_parent_value')
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
        raise ValueError('Enter a positive finite manual parent brick size')
    scope={k:config.get(k) for k in ('account','broker','underlying','market','asset')}
    if config.get('manual_parent_scope')!=scope:
        raise ValueError('Manual parent size belongs to another account or instrument; enter a value for this selection')
    expiry=config.get('manual_parent_valid_until')
    if not isinstance(expiry,(int,float)) or expiry<=now:
        raise ValueError('Manual parent size has expired; review and re-enter it for this session')
    ctx=context(config)
    ref=dict(ctx,native_box=value,symbol=config['underlying'],broker_symbol=config['underlying'],
        source='User-entered parent brick override',native_provider='USER',
        verified_native_size=False,completed_parent=False,status='MANUAL_USER_OVERRIDE',
        chart_session='Regular trading hours',chart_type='Renko',
        valid_until=expiry,observed_at=config.get('manual_parent_entered_at'),
        reference_session=config.get('manual_parent_session'),completed_parent_at=None)
    return dict(config,reference_source='manual_parent_override',reference_value=value,
        reference_symbol=config['underlying'],reference_session=config.get('manual_parent_session'),
        reference_evidence='Explicit user-entered parent brick size; not independently verified',
        reference_state='MANUAL',reference_native_provider='USER',reference_context=ref,
        reference_valid_until=expiry,reference_completed_parent_at=None)

def remember_manual(config):
    result=manual_parent_reference(config)
    if re.fullmatch(r'[a-f0-9]{32}',str(config.get('account',''))):
        fields={k:v for k,v in config.items() if k.startswith('manual_parent_')}
        fields['manual_parent_identity']={k:config.get(k) for k in ('account','broker','underlying','market','asset','execution_route','option_moneyness','sizing_category')}
        atomic(DATA/'manual-session-fallback'/config['account']/(parent_key(config)+'.json'),fields)
    return result

def manual_fallback(config,reason=None):
    parent_path=DATA/'manual-session-fallback'/config['account']/(parent_key(config)+'.json')
    paths=[parent_path] if parent_path.exists() else [DATA/'manual-session-fallback'/config['account']/(ident+'.json') for ident in legacy_variants(config)]
    candidates=[]
    for path in paths:
        saved=read_state(path)
        if not isinstance(saved,dict) or not saved:continue
        try:result=manual_parent_reference(dict(config,**saved,sizing_mode='MANUAL_PARENT'))
        except ValueError:continue
        if result.get('manual_parent_session')==session_scope(config)['id']:candidates.append(result)
    if not candidates:return None
    result=max(candidates,key=lambda row:row.get('manual_parent_entered_at') or 0)
    return dict(result,requested_sizing_mode='AUTO',sizing_fallback=True,
        sizing_fallback_reason=reason or 'Automatic native sizing unavailable')

def failed_session_fallback(config):
    saved=read_state(session_path(config))
    if saved.get('session')==session_scope(config)['id'] and saved.get('state')=='FAILED':
        return manual_fallback(config,saved.get('error'))
    return None

def ensure(config):
    if config.get('sizing_mode')=='MANUAL_PARENT':
        try:return remember_manual(config)
        except ValueError:
            if config.get('requested_sizing_mode')!='AUTO':raise
            config=dict(config,sizing_mode='AUTO')
    try:return apply_reference(config,acquire(config))
    except ValueError as error:
        fallback=manual_fallback(config,str(error))
        if fallback:return fallback
        raise

def request(config):
    authorize(config['account'],config['broker']);ident=parent_key(config)
    saved=read_state(session_path(config))
    if saved.get('session')==session_scope(config)['id'] and saved.get('state') in ('READY','FAILED'):
        ref=saved.get('reference') or {}
        return dict(state=saved['state'],symbol=config['underlying'],updated_at=saved['updated_at'],
                    native_box=ref.get('native_box'),completed_parent_at=ref.get('completed_parent_at'),error=saved.get('error'),retry_after=saved.get('retry_after'))
    with LOCK:
        current=JOBS.get((config['account'],ident))
        if current and (current['state']=='RUNNING' or current.get('session')==session_scope(config)['id'] and time.time()-current['updated_at']<30):return dict(current)
        state=dict(state='RUNNING',session=session_scope(config)['id'],symbol=config['underlying'],started_at=time.time(),updated_at=time.time(),error=None)
        JOBS[(config['account'],ident)]=state
        def run():
            try:
                ref=acquire(config);result=dict(state='READY',symbol=config['underlying'],updated_at=time.time(),native_box=ref['native_box'],completed_parent_at=ref['completed_parent_at'],error=None)
            except Exception as error:result=dict(state='FAILED',symbol=config['underlying'],updated_at=time.time(),error=str(error) if isinstance(error,ValueError) else 'TradingView sizing connection unavailable')
            with LOCK:JOBS[(config['account'],ident)].update(result)
        threading.Thread(target=run,daemon=True,name='native-sizing').start()
        return dict(state)

def jobs(owner):
    with LOCK:result={ident:dict(v,state='STALLED' if v['state']=='RUNNING' and time.time()-v['updated_at']>120 else v['state']) for (account,ident),v in JOBS.items() if account==owner}
    if isinstance(owner,str) and re.fullmatch(r'[a-f0-9]{32}',owner):
        for path in (DATA/'native-session-cache'/owner).glob('*.json'):
            saved=read_state(path)
            if saved.get('state') not in ('READY','FAILED','RUNNING'):continue
            ref=saved.get('reference') or {}
            result[path.stem]=dict(state=saved['state'],symbol=saved.get('symbol'),updated_at=saved.get('updated_at'),
                error=saved.get('error'),retry_after=saved.get('retry_after'),native_box=ref.get('native_box'),sizing_session=saved.get('session'))
    return list(result.values())
