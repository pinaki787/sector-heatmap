"""Explicit body-based patterns for completed host-candle retests.

Star variants omit a mandatory inter-candle gap for intraday markets. These
geometric labels do not establish profitability or statistical signal strength.
"""
def matches(rows,bullish,config):
    if not rows:return []
    def body(c):return abs(c['close']-c['open'])
    def lo(c):return min(c['open'],c['close'])
    def hi(c):return max(c['open'],c['close'])
    def up(c):return c['close']>c['open']
    def down(c):return c['close']<c['open']
    c=rows[-1];aligned=up if bullish else down;opposite=down if bullish else up
    if not aligned(c):return []
    found=[]
    if len(rows)>=2:
        p=rows[-2]
        if opposite(p) and body(p)>0:
            if config.get('retest_engulfing',True) and lo(c)<=lo(p) and hi(c)>=hi(p) and body(c)>body(p):
                found.append('BULLISH_ENGULFING' if bullish else 'BEARISH_ENGULFING')
            if config.get('retest_harami',True) and lo(c)>lo(p) and hi(c)<hi(p) and 0<body(c)<body(p):
                found.append('BULLISH_HARAMI' if bullish else 'BEARISH_HARAMI')
    if len(rows)>=3 and config.get('retest_star',True):
        p,m=rows[-3:-1];mid=(p['open']+p['close'])/2
        middle_on_retest_side=hi(m)<mid if bullish else lo(m)>mid
        crossed=c['close']>mid if bullish else c['close']<mid
        if opposite(p) and body(p)>0 and body(m)<=.3*body(p) and body(c)>=.5*body(p) and middle_on_retest_side and crossed:
            found.append('MORNING_STAR_INTRADAY' if bullish else 'EVENING_STAR_INTRADAY')
    return found
