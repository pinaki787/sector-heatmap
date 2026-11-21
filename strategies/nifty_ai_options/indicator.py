"""Direct sequential recurrence of ai-renko-supertrend.pine (ADX disabled)."""
import math

class RMA:
    def __init__(self, length):
        self.length, self.seed, self.value = length, [], None
    def update(self, value):
        if self.value is None:
            self.seed.append(value)
            if len(self.seed) == self.length:
                self.value = sum(self.seed) / self.length
        else:
            self.value += (value - self.value) / self.length
        return self.value

class AIRenko:
    """Host bars update smoothing even when no synthetic brick is crossed."""
    def __init__(self, length=5, factor=3.0, manual_brick=None, tick=.05, pine_series_precision=False):
        self.length, self.factor, self.manual_brick, self.tick = length, factor, manual_brick, tick
        self.pine_series_precision=pine_series_precision
        self.atrs = [RMA(n) for n in (length,15,9)]
        self.previous_close = self.rc = self.ro = self.atr = None
        self.upper = self.lower = self.st = None
        self.direction = 1
    def q(self,value):
        if not self.pine_series_precision or abs(value)*1e10>=2**53:return value
        return math.floor(value*1e10+.5)/1e10
    def update(self, bar):
        h,l,c = (float(bar[k]) for k in ('high','low','close'))
        if not all(math.isfinite(x) and x>=0 for x in (h,l,c)) or not l<=c<=h:
            raise ValueError('Invalid OHLC')
        tr = h-l if self.previous_close is None else max(h-l,abs(h-self.previous_close),abs(l-self.previous_close))
        host, regime, low = [a.update(tr) for a in self.atrs]
        self.previous_close = c
        ratio = host/regime if regime is not None and regime>0 and host is not None else 1.
        effective = self.factor + (1 if ratio>1.2 else -.5 if ratio<.8 else 0)
        auto = None if host is None else max(self.tick,host*1.5 if ratio>1.2 else low*.7 if ratio<.8 else host)
        box = self.manual_brick if self.manual_brick is not None else auto
        if self.rc is None: self.rc = self.ro = self.q(c)
        previous_rc = self.rc
        delta = c-self.rc
        steps = math.floor(abs(delta)/box) if box is not None and box>0 else 0
        if steps>=1:
            self.ro = self.q(self.rc)
            self.rc = self.q(self.rc+math.copysign(steps*box,delta))
        rh,rl = max(self.ro,self.rc),min(self.ro,self.rc)
        synthetic_tr = max(rh-rl,abs(rh-previous_rc),abs(rl-previous_rc))
        self.atr = self.q(synthetic_tr if self.atr is None else self.atr+(synthetic_tr-self.atr)/self.length)
        midpoint=(rh+rl)/2
        bu,bl=midpoint+effective*self.atr,midpoint-effective*self.atr
        pu,pl,ps,pd=self.upper,self.lower,self.st,self.direction
        self.upper=self.q(bu if pu is None or bu<pu or previous_rc>pu else pu)
        self.lower=self.q(bl if pl is None or bl>pl or previous_rc<pl else pl)
        self.direction=1 if ps is None else (-1 if self.rc>self.upper else 1) if ps==pu else (1 if self.rc<self.lower else -1)
        self.st=self.lower if self.direction<0 else self.upper
        return dict(direction=self.direction,flip=self.direction!=pd,box=box,
                    synthetic_open=self.ro,synthetic_close=self.rc,synthetic_atr=self.atr,
                    st=self.st,effective_factor=effective,host_atr=host,steps=steps)

class Traditional:
    """Exact close-source, no-wick chart-workspace-studies.js grid recurrence."""
    def __init__(self,size):
        if not math.isfinite(size) or size<=0:raise ValueError('Positive brick required')
        self.size,self.level,self.direction=size,None,0
    def grid(self,price):
        ratio=price/self.size
        nearest=math.floor(ratio+.5)
        tolerance=abs(ratio)*2.220446049250313e-16*2
        return nearest if abs(ratio-nearest)<=tolerance else ratio
    def update(self,price):
        position=self.grid(price)
        if self.level is None:self.level=math.floor(position)
        delta=position-self.level
        step=1 if delta>0 else -1 if delta<0 else 0
        count=math.floor(abs(delta))
        reversal=self.direction!=0 and step!=self.direction
        if count<(2 if reversal else 1):return []
        if count>1000:raise ValueError('Increase brick size: more than 1000 crossed bricks')
        if reversal:self.level+=step
        out=[]
        for _ in range(1 if reversal else 0,count):
            op=self.level*self.size;self.level+=step;cl=self.level*self.size
            out.append(dict(open=op,high=max(op,cl),low=min(op,cl),close=cl))
        self.direction=step
        return out
