"""Local exchange calendar gates: no broker work outside the applicable session."""
from datetime import datetime,timedelta
from .market_calendar import IST,market_session,is_trading_day,NSE_SPECIAL_SESSIONS,REGULAR_OPEN,REGULAR_CLOSE

def window(segment,now,commodity_group=None):
    if segment=='DELTA_24X7':return dict(open=True,next_open=now,close=now+86400,label='Delta India · 24 hours, 7 days',reason='Continuous crypto session',segment=segment)
    local=datetime.fromtimestamp(now,IST)
    if local.year!=2026:raise ValueError('Exchange holiday calendar requires review before monitoring in '+str(local.year)+'.')
    if segment in ('NSE_EQ','BSE_EQ'):
        session=market_session(local)
        opening,closing=NSE_SPECIAL_SESSIONS.get(local.date(),(REGULAR_OPEN,REGULAR_CLOSE))[:2]
        close=datetime.combine(local.date(),closing,IST).timestamp()
        return dict(open=session['status']=='OPEN',next_open=datetime.fromisoformat(session['next_open']).timestamp(),
                    close=close,label='09:15–15:30 IST · exchange trading days',reason=session['reason'],segment=segment)
    if segment!='MCX_COMM':raise ValueError('No verified monitoring session exists for this segment.')
    # MCX protection/valuation adapters must explicitly supply the contract's group.
    # Do not treat all commodities as energy contracts.
    if commodity_group not in ('NON_AGRI','AGRI','INTERNATIONAL_AGRI'):
        raise ValueError('Verified commodity session group is required before monitoring.')
    from .dhan_mcx import trading_bounds
    def bounds(day):
        if day.year!=2026:raise ValueError('MCX holiday calendar requires review before '+str(day.year)+'.')
        opening,closing=trading_bounds(day.timestamp())
        if commodity_group=='AGRI':closing=min(closing,17*60)
        elif commodity_group=='INTERNATIONAL_AGRI':closing=min(closing,21*60)
        return opening,closing
    opening,closing=bounds(local)
    minutes=local.hour*60+local.minute+local.second/60
    opened=opening<closing and opening<=minutes<closing
    close=local.replace(hour=closing//60,minute=closing%60,second=0,microsecond=0).timestamp() if closing else None
    candidate=local
    for _ in range(15):
        start,end=bounds(candidate)
        stamp=candidate.replace(hour=start//60,minute=start%60,second=0,microsecond=0)
        if start<end and (opened or stamp.timestamp()>now):
            return dict(open=opened,next_open=stamp.timestamp(),close=close,
                        label='MCX '+commodity_group.replace('_',' ').lower()+' · full applicable morning/evening session',
                        reason='Commodity session open' if opened else 'Commodity exchange closed',segment=segment)
        candidate=(candidate+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
    raise ValueError('Next commodity session is unavailable; calendar review required.')
