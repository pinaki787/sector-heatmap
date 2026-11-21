"""Audit causal V1 grid availability; no invented target/stop trading results."""
import json,hashlib
from pathlib import Path
import pandas as pd
p=Path(__file__).resolve().parent
baseline=p.parent/'nifty_sma30_options_20261110'
source=Path('sector-pulse-v1.pine')
rows=json.loads(Path('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json').read_text())['rows']
rows+=json.loads((baseline/'raw/spot_oct24_31.json').read_text())['candles']
d=pd.DataFrame(rows,columns=['epoch','open','high','low','close','volume'])
d.index=pd.to_datetime(d.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata')
d=d.between_time('09:15','15:29').loc['2026-10-01':'2026-10-31']
refs=[]
for day,x in d.groupby(d.index.date):
 f=x.resample('5min',origin='start_day',offset='9h15min').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
 f=f.iloc[1:]
 red=f[f.close<f.open]
 if len(red):
  t=red.index[0];r=red.iloc[0];h=r.high;l=r.low;s=h-l
  refs.append(dict(day=str(day),reference_start=t,available_at=t+pd.Timedelta(minutes=5),high=h,low=l,span=s,p44=l+.44*s,p50=l+.50*s,p56=l+.56*s,up1=h+s,up2=h+2*s,down1=l-s,down2=l-2*s))
r=pd.DataFrame(refs);r.to_csv(p/'causal_daily_grid.csv',index=False)
t=pd.read_csv(baseline/'trades.csv');t['day']=t.entry_time.str[:10];a=t.merge(r,on='day',how='left')
a['available_at']=pd.to_datetime(a.available_at);a['signal_confirmed_at']=pd.to_datetime(a.signal_time)+pd.Timedelta(minutes=1)
a['fresh_grid_available']=a.available_at.le(a.signal_confirmed_at)
a.to_csv(p/'baseline_entry_grid_availability.csv',index=False)
summary=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),baseline_trades=len(t),fresh_grid_available_at_signal=int(a.fresh_grid_available.sum()),fresh_grid_unavailable_at_signal=int((~a.fresh_grid_available).sum()),daily_grids=len(r),source_has_explicit_trading_stop=False,status='AWAITING_EXIT_RULE',notes=['Grid uses completed reference candle only. No retrospective session-start placement is tradable before reference close.','Earlier-session or historical grids are distinct candidates; fresh daily grid audit does not assume those can be substituted.','No target/stop options performance is calculated until exit policy is specified.'])
(p/'grid_audit.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

