"""Cached first-valid ATR bootstrap observed in the public chart-library client.
Research only: source history/context parity with the native reference feed is
not established. This module is deliberately not a strategy reference provider.
"""
from dataclasses import dataclass
import hashlib,json,math
from indicator import RMA,Traditional

@dataclass(frozen=True)
class BootstrapContext:
    owner:str
    broker:str
    symbol:str
    parent_minutes:int
    atr_length:int
    session:str
    min_tick:float
    source_start:int

    def __post_init__(self):
        if not all(isinstance(x,str) and x for x in (self.owner,self.broker,self.symbol,self.session)):
            raise ValueError('Explicit isolated bootstrap identity required')
        if type(self.parent_minutes) is not int or self.parent_minutes<=0 or type(self.atr_length) is not int or self.atr_length<=0:
            raise ValueError('Positive parent/ATR length required')
        if isinstance(self.min_tick,bool) or not isinstance(self.min_tick,(int,float)) or not math.isfinite(self.min_tick) or self.min_tick<=0:
            raise ValueError('Positive native tick required')

class CachedATRBootstrap:
    def __init__(self,context):
        self.context=context
        self.rma=RMA(context.atr_length)
        self.previous_close=None;self.last_bar=None
        self.box=None;self.seed_atr=None;self.initialized_at=None;self.engine=None
        self.bars=0

    def update(self,bar,*,closed):
        if not closed:return []
        row={k:bar[k] for k in ('time','open','high','low','close')}
        if not all(not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v) for v in row.values()):
            raise ValueError('Finite completed source OHLC required')
        if not row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']:
            raise ValueError('Invalid source OHLC')
        if self.last_bar:
            if row['time']==self.last_bar['time']:
                if row!=self.last_bar:raise ValueError('Completed bootstrap source revised')
                return []
            if row['time']<self.last_bar['time']:raise ValueError('Out-of-order bootstrap source')
        elif row['time']!=self.context.source_start:
            raise ValueError('Canonical source start differs')
        previous=self.previous_close
        self.previous_close=row['close'];self.last_bar=row;self.bars+=1
        # The observed client ATR uses undefined TR for the first source bar.
        value=None if previous is None else self.rma.update(max(row['high']-row['low'],abs(row['high']-previous),abs(row['low']-previous)))
        if self.box is None:
            if value is None:return []
            self.seed_atr=value
            self.box=max(self.context.min_tick,math.floor(value/self.context.min_tick+.5)*self.context.min_tick)
            self.initialized_at=row['time'];self.engine=Traditional(self.box)
            self.engine.update(row['close'])
            return []
        return [dict(brick,source_time=row['time']) for brick in self.engine.update(row['close'])]

    def snapshot(self):
        key=hashlib.sha256(json.dumps(self.context.__dict__,sort_keys=True).encode()).hexdigest()
        return dict(status='RESEARCH_ONLY_SOURCE_CONTEXT_PARITY_UNPROVEN',context=self.context.__dict__,
            context_sha256=key,source_bars=self.bars,seed_atr=self.seed_atr,box=self.box,
            initialized_at=self.initialized_at,eligible_for_strategy=False)
