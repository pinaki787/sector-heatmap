"""MCX non-agricultural session calendar, independent of any data broker.

Source: MCX published 2026 trading holidays and non-agricultural contract sessions.
Unknown calendar years fail closed; special Muhurat hours are not inferred.
"""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
IST=ZoneInfo('Asia/Kolkata')
FULL_CLOSED={'2026-01-26','2026-04-03','2026-10-02','2026-12-25'}
EVENING_ONLY={'2026-03-03','2026-03-26','2026-03-31','2026-04-14','2026-05-01','2026-05-28','2026-06-26','2026-09-14','2026-10-20','2026-11-10','2026-11-24'}
MORNING_ONLY={'2026-01-01'}

def trading_bounds(now):
    day=datetime.fromtimestamp(now,IST)
    if day.year!=2026:raise ValueError('MCX holiday calendar requires an update for '+str(day.year)+'.')
    key=day.date().isoformat()
    if day.weekday()>4 or key in FULL_CLOSED:return 0,0
    ny=day.replace(hour=12,minute=0,second=0,microsecond=0).astimezone(ZoneInfo('America/New_York'))
    ending=23*60+30 if ny.dst()!=timedelta(0) else 23*60+55
    return (17*60 if key in EVENING_ONLY else 9*60,17*60 if key in MORNING_ONLY else ending)
