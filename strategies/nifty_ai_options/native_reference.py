"""Identity-bound verified native reference lookup. Never substitutes raw OHLC ATR."""
import json,math,time
from pathlib import Path
try:from .sizing_policy import parent_hours
except ImportError:from sizing_policy import parent_hours
BASE=Path('/home/trading/sector-heatmap/strategies/nifty_ai_options/evidence')
DATA=Path('/home/trading/sector-heatmap/.private/nifty-ai-options/references')

def choose_reference(references,symbol,market,asset=None,*,expected_session=None,now=None):
    market=str(market).upper()
    hours=parent_hours(market,asset);now=time.time() if now is None else now;matches=[]
    for ref in references:
        if not isinstance(ref,dict):continue
        if ref.get('reference_measure')!='NATIVE_RENKO_ATR_BOX':continue
        if ref.get('renko_method')!='ATR' or ref.get('source_price')!='Close' or ref.get('wicks') is not False:continue
        value=ref.get('native_box');broker_symbol=ref.get('broker_symbol') or ref.get('symbol')
        if broker_symbol!=symbol or not str(ref.get('status','')).startswith('VERIFIED_'):continue
        if ref.get('parent_hours')!=hours or ref.get('atr_length')!=5:continue
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:continue
        if market in ('NSE','BSE'):
            if ref.get('chart_session')!='Regular trading hours' or not expected_session or ref.get('reference_session')!=expected_session:continue
        else:
            completed=ref.get('completed_parent_at')
            if isinstance(completed,bool) or not isinstance(completed,(int,float)) or not 0<=now-completed<=hours*3600:continue
        matches.append(ref)
    if not matches:return None
    if market not in ('NSE','BSE'):
        latest=max(r['completed_parent_at'] for r in matches)
        matches=[r for r in matches if r['completed_parent_at']==latest]
    # A completed reference window is immutable. Observation timestamps cannot
    # resolve a conflicting native value; require reconciliation instead.
    if len({r['native_box'] for r in matches})!=1:return None
    return max(matches,key=lambda r:str(r.get('observed_at','')))

def resolve_reference(owner,symbol,market,asset=None):
    market=str(market).upper()
    paths=list(BASE.glob('native-reference-*.json'))
    if isinstance(owner,str) and len(owner)==32 and all(c in '0123456789abcdef' for c in owner):paths+=list((DATA/owner).glob('*.json'))
    refs=[]
    for path in paths:
        try:
            value=json.loads(path.read_text())
            if isinstance(value,dict):refs.append(value)
        except (OSError,ValueError):continue
    expected=None
    if market in ('NSE','BSE'):
        from sector_heatmap.market_calendar import market_session
        expected=market_session()['last_completed_session']
    return choose_reference(refs,symbol,market,asset,expected_session=expected)
