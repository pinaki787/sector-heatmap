"""Conditional volatility-based investment plans; no order authority."""
from decimal import Decimal,ROUND_FLOOR
from .investment import number
def plan(row,tick,now):
    unavailable=dict(status='UNAVAILABLE',entry=None,stoploss=None,target=None,reward_risk=None,reason='Valid current-session price, ATR14, reported ATH and displayable exchange tick are required.')
    m=row.get('metrics',{});price=number(row.get('price'));ath=number(row.get('reported_ath'));atr=number(m.get('ATR'));stamp=number(m.get('time'));tick=number(tick)
    if any(v is None or v<=0 for v in (price,ath,atr,tick)) or stamp is None or not -86400<=now-stamp<=5*86400 or tick<.01:return unavailable
    step=Decimal(str(tick))
    def floor(v):return (Decimal(str(v))/step).to_integral_value(rounding=ROUND_FLOOR)*step
    entry=floor(max(price,ath))+step
    stop=floor(float(entry)-2*atr)
    if stop<=0 or stop>=entry:return unavailable
    risk=entry-stop
    target=entry+2*risk
    return dict(status='CONDITIONAL' if row.get('eligible') else 'OUTSIDE_SCREEN_RULES',entry=float(entry),stoploss=float(stop),target=float(target),reward_risk=2.,risk_per_share=float(risk),tick_size=tick,atr14=atr,reference_price=price,reference_bar_at=row.get('market_bar_at'),method='Reported-ATH breakout; 2 × ATR14 volatility stop; target at 2R',trigger='Daily close above the verified ATH, followed by a fresh quote and volume/liquidity review. Entry is an indicative breakout reference, not a filled price.',invalidation='Cancel if the reported ATH or corporate-action adjustment is incorrect, the breakout fails, the price gaps beyond the planned entry, or fresh data changes the plan.',limitations=['Planning only; ATH history is unverified.','Stop is volatility-based, not a verified chart-structure stop.','Target is a 2R scenario, not a price forecast.','Gaps, slippage and costs can make the realised loss exceed planned risk.'],order_authority='NONE')

