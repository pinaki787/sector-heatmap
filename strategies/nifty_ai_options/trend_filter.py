"""Incremental V1 Gaussian Midline and automatic-entry trend qualification.
Only entry admission uses this module. Owned-position exits are never gated.
"""
import math

class GaussianMidline:
    def __init__(self,period=123):
        if isinstance(period,bool) or not isinstance(period,int) or not 5<=period<=500:
            raise ValueError('Midline period must be a whole number from 5 to 500')
        self.period=period
        beta=(1-math.cos(2*math.pi/period))/(math.pow(2,1/3)-1)
        self.alpha=-beta+math.sqrt(beta*beta+2*beta)
        self.g1=self.g2=self.g3=None
    def update(self,close):
        if isinstance(close,bool) or not isinstance(close,(int,float)) or not math.isfinite(close):
            raise ValueError('Finite Midline close required')
        a=self.alpha;d=1-a
        self.g1=close if self.g1 is None else a*close+d*self.g1
        self.g2=self.g1 if self.g2 is None else a*self.g1+d*self.g2
        self.g3=self.g2 if self.g3 is None else a*self.g2+d*self.g3
        return self.g3

def entry_allowed(engine,side,result=None):
    result=engine.under_result if result is None else result
    from strategies.nifty_ai_options.swing_targets import admission
    from strategies.nifty_ai_options.zone_targets import admission as zone_admission
    direction='LONG' if side in ('LONG','CE') else 'SHORT'
    if not zone_admission(engine,direction,result) or not admission(engine,side,result):return False
    key='bull_entry_level' if side in ('LONG','CE') else 'bear_entry_level'
    level=engine.config.get(key)
    if level is not None:
        close=(result or {}).get('bar_close')
        finite=lambda v:not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v)
        allowed=finite(level) and level>0 and finite(close) and (close>level if key=='bull_entry_level' else close<level)
        engine.entry_level_status=dict(enabled=True,allowed=bool(allowed),level=level,close=close,side=side)
        if not allowed:return False
    if not engine.config.get('midline_filter_enabled',False):return True
    result=engine.under_result if result is None else result
    direction='LONG' if side in ('LONG','CE') else 'SHORT' if side in ('SHORT','PE') else None
    period=engine.config.get('midline_period',123)
    close=(result or {}).get('bar_close');line=(result or {}).get('midline')
    finite=lambda value:not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)
    ready=direction is not None and finite(close) and finite(line) and (result or {}).get('midline_period')==period
    allowed=ready and (close>line if direction=='LONG' else close<line)
    engine.midline_filter_status=dict(enabled=True,ready=ready,allowed=bool(allowed),direction=direction,
        period=period,close=close,midline=line,symbol=engine.config.get('underlying'),
        reason='CONFIRMED_CLOSE_ABOVE_MIDLINE' if allowed and direction=='LONG' else
               'CONFIRMED_CLOSE_BELOW_MIDLINE' if allowed else
               'MIDLINE_UNAVAILABLE' if not ready else 'CLOSE_NOT_ON_REQUIRED_SIDE')
    return bool(allowed)

def entry_proof(engine):
    return dict(getattr(engine,'midline_filter_status',{})) if engine.config.get('midline_filter_enabled',False) else None

def current_trend_confirmation(engine,unit,result):
    """A newly completed brick may qualify under the latest trend without a flip."""
    level_key='bull_entry_level' if (result or {}).get('direction')==-1 else 'bear_entry_level'
    from strategies.nifty_ai_options.zone_targets import continuation
    from strategies.nifty_ai_options.support_retest import get
    retest=get(engine)
    from strategies.nifty_ai_options.zone_targets import record_exit_unit
    record_exit_unit(engine,unit,result)
    if retest:retest.observe_unit(engine,unit,result)
    if not (continuation(engine) or retest and retest.wait and retest.wait.get('direction')==('LONG' if (result or {}).get('direction')==-1 else 'SHORT') or engine.config.get('midline_filter_enabled',False) or engine.config.get(level_key) is not None or engine.config.get('swing_targets_enabled') and engine.config.get('display_mode','RENKO')=='RENKO' and ((retest.wait if retest else getattr(engine,'swing_wait',None)) or {}).get('direction')==('LONG' if (result or {}).get('direction')==-1 else 'SHORT')) or engine.position is not None or getattr(engine,'entry_paused',False):return None
    if unit.get('kind')!='brick' or unit.get('closed') is not True or unit.get('provisional') or unit.get('historyOnly'):return None
    at=unit.get('available_at');closed=unit.get('closed_at')
    finite=lambda value:not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)
    if not finite(at) or not finite(closed) or closed>at or at<=getattr(engine,'entry_reset_at',0):return None
    if not result or result.get('direction') not in (-1,1) or not finite(result.get('st')):return None
    if not all(finite(unit.get(k)) for k in ('open','close')) or result.get('bar_close')!=unit['close']:return None
    if not math.isclose(abs(unit['close']-unit['open']),engine.spot_size,rel_tol=2e-12,abs_tol=0):return None
    direction='LONG' if result['direction']<0 else 'SHORT'
    if continuation(engine):
        if unit['close']<=unit['open'] if direction=='LONG' else unit['close']>=unit['open']:return None
        wait=engine.zone_policy.wait
        if at<=wait['exit_requested_at']:return None
        engine.zone_break_proof=dict(zone_id=wait['id'],close=unit['close'],available_at=at,closed_at=closed)
    if retest and retest.wait and not retest.confirmation(engine,unit,result):return None
    if not entry_allowed(engine,direction,result):return None
    return dict(direction=direction,closed_at=closed,available_at=at,
                confirmation_basis='COMPLETED_RENKO_CURRENT_TREND_MIDLINE' if engine.config.get('midline_filter_enabled') else 'COMPLETED_RENKO_CURRENT_TREND_PRICE_LEVEL',
                body=abs(unit['close']-unit['open']),brick=engine.spot_size,
                midline_confirmation=entry_proof(engine),entry_level_confirmation=getattr(engine,'entry_level_status',None))
