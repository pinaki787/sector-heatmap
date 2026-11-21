"""Calendar-derived expected expiry; not broker-certified historical contract metadata."""
from datetime import date,timedelta
HOLIDAYS={date.fromisoformat(s) for s in ('2026-01-26','2026-03-03','2026-03-26','2026-03-31','2026-04-03','2026-04-14','2026-05-01','2026-05-28','2026-06-26','2026-09-14','2026-10-02','2026-10-20','2026-11-10','2026-11-24','2026-12-25')}
SOURCES=['https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf','https://www.nseindia.com/static/products-services/equity-derivatives-nifty50']
def expected_weekly_expiry(day):
 if day.year!=2026:raise ValueError('Verified calendar covers 2026 only')
 target=day+timedelta(days=(1-day.weekday())%7)
 while True:
  expiry=target
  while expiry.weekday()>=5 or expiry in HOLIDAYS:expiry-=timedelta(days=1)
  if expiry>=day:return expiry.isoformat()
  target+=timedelta(days=7)
  if target.year!=2026:raise ValueError('Next-year expiry calendar is not verified')
