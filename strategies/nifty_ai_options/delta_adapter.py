"""Exact-owner Delta adapter; construction is inert except its isolated cache DB.

No existing Delta runner, position, setting, journal or credential is modified.
Only an explicitly started AI runtime may invoke an order method.
"""
import hashlib,json,os,sqlite3,time
from pathlib import Path
from datetime import datetime,timezone
try:from .run import ROOT
except ImportError:from run import ROOT

def bound_delta(account,directory):
    from sector_heatmap.delta_india import DeltaIndia
    if not isinstance(account,str) or len(account)!=32 or any(c not in '0123456789abcdef' for c in account):raise ValueError('Exact Delta account id required')
    folder=ROOT/'.private/dashboard-login/accounts'/account
    credentials=json.loads((folder/'credentials.json').read_text())
    with sqlite3.connect((ROOT/'.private/dashboard-login/registry.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('select broker,credential_identity from accounts where id=?',(account,)).fetchone()
    key=credentials.get('DELTA_INDIA_API_KEY')
    if not key or not row or row[0]!='DELTA_INDIA' or row[1]!=hashlib.sha256(('DELTA_INDIA|'+key).encode()).hexdigest():raise ValueError('Delta registry credential owner mismatch')
    class BoundDelta(DeltaIndia):
        def _credentials(self):return dict(credentials,DELTA_INDIA_ENABLE_LIVE_ORDERS=os.getenv('DELTA_INDIA_ENABLE_LIVE_ORDERS',credentials.get('DELTA_INDIA_ENABLE_LIVE_ORDERS','1')))
    path=Path(directory);path.mkdir(parents=True,exist_ok=True)
    return BoundDelta(path/'delta-ai-paper-cache.json',credentials=lambda:dict(credentials))

def select_option(delta,underlying,side,target=40,now=None,expiry=None):
    """Nearest valid listed expiry, then nearest premium in selected CE/PE side."""
    import math
    from strategies.renko_supertrend.delta_contracts import option_contract,perpetual_contract
    now=delta.clock() if now is None else now
    parent=delta.product(underlying);perpetual_contract(parent)
    asset=parent.get('underlying');kind='call_options' if side=='CE' else 'put_options' if side=='PE' else None
    if kind is None:raise ValueError('CE/PE required')
    if isinstance(target,bool) or not isinstance(target,(int,float)) or not math.isfinite(target) or target<=0:raise ValueError('Positive premium target required')
    candidates=[]
    for row in delta.catalog()['instruments']:
        if row.get('underlying')!=asset or row.get('contract_type') not in ('call_options','put_options') or row.get('quoting_currency')!=parent.get('quoting_currency') or row.get('state')!='live' or row.get('trading_status')!='operational':continue
        try:listed_expiry=datetime.fromisoformat(str(row['settlement_time']).replace('Z','+00:00')).timestamp()
        except (KeyError,TypeError,ValueError):raise ValueError('Unknown provider option expiry')
        if listed_expiry<=now:continue
        meta=option_contract(row,now)
        candidates.append((meta['expiry_epoch'],row,meta))
    if not candidates:raise ValueError('No listed tradable selected-underlying option expiry')
    listed=sorted(set(r[0] for r in candidates))
    if expiry is not None:
        try:requested=float(expiry)
        except (TypeError,ValueError):raise ValueError('Invalid selected expiry')
        if requested not in listed:raise ValueError('Selected expiry is expired or not listed for this underlying')
        expiry=requested
    else:expiry=listed[0]
    priced=[]
    from sector_heatmap.delta_india import BASE
    params=dict(contract_types=kind,underlying_asset_symbols=asset,expiry_date=datetime.fromtimestamp(expiry,timezone.utc).strftime('%d-%m-%Y'))
    response=delta.requester.get(BASE+'/v2/tickers',params=params,timeout=15,allow_redirects=False)
    response.raise_for_status();reply=response.json()
    if reply.get('success') is not True:raise ValueError('Delta public option chain rejected')
    if not isinstance(reply.get('result'),list):raise ValueError('Delta option ticker chain unavailable')
    tickers={r.get('symbol'):r for r in reply['result']}
    for _,row,meta in (r for r in candidates if r[0]==expiry and r[1]['contract_type']==kind):
        ticker=tickers.get(row['symbol'],{})
        # Mark price is not substituted for a missing traded option premium.
        value=ticker.get('close')
        try:price=float(value);d=float((ticker.get('greeks') or {}).get('delta'))
        except (TypeError,ValueError):continue
        if not math.isfinite(price) or price<=0 or not math.isfinite(d) or not 0<abs(d)<=1 or (d<=0 if side=='CE' else d>=0):continue
        priced.append((abs(price-target),row['symbol'],dict(meta,underlying=underlying,option_type=side,expiry=str(expiry),selection_ltp=price,selection_delta=d,selected_at=now),d))
    if not priced:raise ValueError('Nearest expiry lacks usable traded premiums/provider delta')
    _,_,contract,d=min(priced,key=lambda r:(r[0],r[1]));return contract,d
