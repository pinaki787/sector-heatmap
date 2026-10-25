"""New stock-option entries are equity-only on near-month expiry and prior day."""
from datetime import date,datetime,timedelta
from .market_calendar import IST
class EquityOnlyExpiry(ValueError):pass
def stock_symbol(symbol):
    s=str(symbol or '').upper()
    return s.startswith(('NSE:','BSE:')) and not s.endswith('-INDEX') and (s.endswith('-EQ') or s.startswith('BSE:'))
def expiry_day(value):
    if isinstance(value,datetime):return value.astimezone(IST).date() if value.tzinfo else value.date()
    if isinstance(value,date):return value
    if isinstance(value,(int,float)) or isinstance(value,str) and value.isdigit():
        return datetime.fromtimestamp(float(value),IST).date()
    for fmt in ('%Y-%m-%d','%d-%m-%Y'):
        try:return datetime.strptime(str(value)[:10],fmt).date()
        except ValueError:pass
    raise ValueError('A valid listed stock-option expiry is required.')
def require_options_allowed(expiries,now=None):
    now=now or datetime.now(IST)
    today=now.astimezone(IST).date() if isinstance(now,datetime) and now.tzinfo else expiry_day(now)
    dates=sorted({expiry_day(v) for v in expiries if v not in (None,'')})
    active=[d for d in dates if d>=today]
    if not active:raise ValueError('No active listed stock-option expiry; no new option entry.')
    nearest=active[0]
    if nearest<=today+timedelta(days=1):
        raise EquityOnlyExpiry('Equity only: nearest stock-option expiry is '+nearest.isoformat()+'. New stock-option entries are blocked on expiry day and the preceding calendar day (IST); use a separately validated cash-equity plan. No next-month substitution.')
    return nearest
def guard_fyers_rows(rows,ticker,now):
    values=[r[8] for r in rows if len(r)>16 and r[13].strip().upper()==str(ticker).upper() and r[16].upper() in ('CE','PE')]
    return require_options_allowed(values,now)

