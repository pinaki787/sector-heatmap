"""Fresh-flip confirmation by a real completed brick or smaller closed candle body."""
import math

def positive(value,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Positive finite '+name+' required')
    return value

class HybridConfirmation:
    def __init__(self,brick):
        self.brick=positive(brick,'brick size');self.pending=None;self.consumed=set()
    def arm(self,direction,at,identity,*,source_at=None):
        if direction not in ('LONG','SHORT'):raise ValueError('LONG/SHORT signal direction required')
        if isinstance(at,bool) or not isinstance(at,(int,float)) or not math.isfinite(at):raise ValueError('Finite flip availability time required')
        if not isinstance(identity,(str,int,tuple)):raise ValueError('Stable flip identity required')
        if identity in self.consumed:return
        source_at=at if source_at is None else source_at
        if isinstance(source_at,bool) or not isinstance(source_at,(int,float)) or not math.isfinite(source_at) or source_at>at:raise ValueError('Valid flip source close required')
        self.pending=dict(direction=direction,flip_at=at,source_at=source_at,identity=identity)
    def clear(self):self.pending=None
    def confirm(self,unit,direction,supertrend):
        signal=self.pending
        if not signal or signal['direction']!=direction or unit.get('closed') is not True:return None
        at=unit.get('available_at')
        if isinstance(at,bool) or not isinstance(at,(int,float)) or not math.isfinite(at) or at<signal['flip_at']:return None
        closed_at=unit.get('closed_at',at)
        if isinstance(closed_at,bool) or not isinstance(closed_at,(int,float)) or not math.isfinite(closed_at) or closed_at>at:return None
        if closed_at<signal['source_at']:return None
        opening=positive(unit.get('open'),'unit open');closing=positive(unit.get('close'),'unit close')
        if isinstance(supertrend,bool) or not isinstance(supertrend,(int,float)) or not math.isfinite(supertrend):raise ValueError('Finite Supertrend required')
        line=supertrend
        if not (closing>line if direction=='LONG' else closing<line):return None
        body=abs(closing-opening)
        if unit.get('kind')=='brick':
            if not math.isclose(body,self.brick,rel_tol=2e-12,abs_tol=0):return None
            if not (closing>opening if direction=='LONG' else closing<opening):return None
            basis='COMPLETED_RENKO_BRICK'
        elif unit.get('kind')=='host_candle':
            basis='COMPLETED_CHART_CANDLE'
        elif unit.get('kind')=='candle':
            if body>=self.brick:return None
            basis='COMPLETED_SMALL_CANDLE_BODY'
        else:return None
        self.pending=None;self.consumed.add(signal['identity'])
        return dict(direction=direction,flip_at=signal['flip_at'],flip_source_at=signal['source_at'],closed_at=closed_at,available_at=at,flip_identity=signal['identity'],confirmation_basis=basis,body=body,brick=self.brick)

def confirm_exit(unit,position,signal_direction,supertrend,brick,*,premium=False):
    """Owned exits require adverse direction plus a completed confirming unit.
    Manual entry does not waive confirmation or require a second fresh flip.
    """
    if not position:return None
    desired='SHORT' if premium or position.get('side') in ('LONG','CE') else 'LONG'
    if signal_direction!=desired:return None
    entered=position.get('entry_confirmed_at',position.get('entry_timestamp'))
    at=unit.get('available_at')
    if not isinstance(entered,(int,float)) or isinstance(entered,bool) or not isinstance(at,(int,float)) or isinstance(at,bool) or at<=entered:return None
    closed_at=unit.get('closed_at',at)
    if isinstance(closed_at,bool) or not isinstance(closed_at,(int,float)) or not math.isfinite(closed_at) or closed_at<=entered:return None
    gate=HybridConfirmation(brick);gate.arm(desired,entered,('owned-exit',position.get('symbol'),entered))
    return gate.confirm(unit,signal_direction,supertrend)
