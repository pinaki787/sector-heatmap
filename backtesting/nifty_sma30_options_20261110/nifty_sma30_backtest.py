"""Read-only FYERS baseline. Run from project root; no runner or order APIs."""
import os,json,csv,time,re,hashlib,math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import requests,numpy as np,pandas as pd
from dotenv import load_dotenv,find_dotenv
from openalgo import ta
import vectorbt as vbt
import plotly.graph_objects as go
ROOT=Path(__file__).resolve().parent
RAW=ROOT/'raw';RAW.mkdir(exist_ok=True)
load_dotenv(find_dotenv(),override=False)
IST=ZoneInfo('Asia/Kolkata')
token=json.loads(Path(os.environ['FYERS_RESEARCH_TOKEN_FILE']).read_text())
app=token.get('app_id') or token.get('client_id')
value=(token.get('access_token') or token.get('token')).split(':',1)[-1]
headers={'Authorization':app+':'+value}
base='https://api-t1.fyers.in/data/'
def get(name,path,params):
 p=RAW/(name+'.json')
 if p.exists():return json.loads(p.read_text())
 r=requests.get(base+path,headers=headers,params=params,timeout=(4,25));r.raise_for_status()
 d=r.json();p.write_text(json.dumps(d));time.sleep(.36)
 if d.get('s') not in ('ok','no_data',None):raise RuntimeError(str(d))
 return d
def frame(rows):
 d=pd.DataFrame(rows,columns=['epoch','open','high','low','close','volume'])
 d.index=pd.to_datetime(d.epoch,unit='s',utc=True).dt.tz_convert(IST)
 assert not d.index.duplicated().any()
 assert ((d.low<=d[['open','close']].min(axis=1)) & (d.high>=d[['open','close']].max(axis=1))).all()
 return d.sort_index()
archive=Path('data/backtesting/nifty50-fyers-2024-10-25_2026-10-24')
r=json.loads((archive/'nifty50_1m.json').read_text())['rows']
fresh=get('spot_oct24_31','history',dict(symbol='NSE:NIFTY50-INDEX',resolution='1',date_format='1',range_from='2026-10-24',range_to='2026-10-31',cont_flag='1'))
spot=frame(r+fresh['candles'])
spot=spot.between_time('09:15','15:29')
# Warm SMA across regular-session bars; never reset at midnight.
spot['sma30']=ta.sma(spot.close,30)
above=(spot.close>spot.sma30)&(spot.close.shift(1)<=spot.sma30.shift(1))
below=(spot.close<spot.sma30)&(spot.close.shift(1)>=spot.sma30.shift(1))
above=pd.Series(ta.exrem(above.fillna(False),below.fillna(False)),index=spot.index)
below=pd.Series(ta.exrem(below.fillna(False),above.fillna(False)),index=spot.index)
spot['signal']=np.where(above,1,np.where(below,-1,0))
month=spot.loc['2026-10-01':'2026-10-31'].copy()
counts=month.groupby(month.index.date).size()
assert (counts==375).all(),counts.to_dict()
exp=get('expiries','history/fno/expired/expiry-dates',dict(symbol='NSE:NIFTY50-INDEX',date_format='1',range_from='2026-10-01',range_to='2026-11-06'))['data']['expiry_dates']['options']
contracts={}
for e in exp:
 if e<'2026-10-01':continue
 contracts[e]=get('contracts_'+e,'history/fno/expired/underlying-symbols',dict(symbol='NSE:NIFTY50-INDEX',expiry_date=e))['data']['contracts']['options']
 if e>str(month.index[-1].date()):break
def symbol(day,strike,side):
 e=min(x for x in contracts if x>=day)
 # Match exact strike suffix and provider-returned symbol only.
 matches=[s for s in contracts[e] if re.search(r'(?<![0-9])'+str(strike)+side+'$',s)]
 # Prefix ends in numeric expiry day: obtain strike by known expiry-specific symbol suffix length.
 if not matches:matches=[s for s in contracts[e] if s.endswith(str(strike)+side)]
 assert len(matches)==1,(day,strike,side,matches)
 return matches[0],e
pending=[];signals=[]
for day,d in month.groupby(month.index.date):
 active=None
 for i,(ts,row) in enumerate(d.iterrows()):
  if row.signal and i<len(d)-1:
   execute=ts+pd.Timedelta(minutes=1)
   if active:
    active['exit_time']=execute;active['exit_reason']='opposite_cross';pending.append(active);active=None
   if execute.strftime('%H:%M')<'15:29':
    strike=int(math.floor(row.close/50+.5)*50);side='CE' if row.signal==1 else 'PE'
    s,e=symbol(str(day),strike,side)
    active=dict(signal_time=ts,entry_time=execute,symbol=s,expiry=e,strike=strike,side=side,spot_signal_close=row.close)
  # At each session boundary no position is carried.
 if active:
  active['exit_time']=d.index[-1];active['exit_reason']='scheduled_15:29';pending.append(active)
 symbols=sorted({x['symbol'] for x in pending})
print('planned trades',len(pending),'contracts',len(symbols),flush=True)
price={}
for n,s in enumerate(symbols):
 data=get('option_'+s.replace(':','_'),'history/fno/expired/historical-data',dict(symbol=s,resolution='1',date_format='1',range_from='2026-10-01',range_to='2026-10-31'))
 rows=data.get('candles',data.get('data',{}).get('candles',[]))
 price[s]=frame([x[:6] for x in rows])
 print('contract',n+1,len(symbols),s,len(rows),flush=True)
# Estimated October FYERS cost schedule. Each entry/exit one executed order.
LOT=65
def costs(p,buy):
 turnover=p*LOT
 brokerage=20.;exchange=turnover*.000355299;sebi=turnover*.000001
 ipft=turnover*.000000001;clearing=turnover*.00009
 gst=.18*(brokerage+exchange+sebi+ipft+clearing)
 return dict(brokerage=brokerage,exchange=exchange,sebi=sebi,ipft=ipft,clearing=clearing,gst=gst,stamp=turnover*.00003 if buy else 0.,stt=0. if buy else turnover*.0015)
errors=[];trades=[]
for x in pending:
 q=price[x['symbol']]
 try:
  en=q.loc[x['entry_time']];ex=q.loc[x['exit_time']]
  if en.volume<=0 or ex.volume<=0:raise ValueError('zero-volume execution candle')
  assert en.open>0 and ex.open>0
  a=costs(en.open,True);b=costs(ex.open,False)
  trade={**x,'quantity':LOT,'entry_premium':float(en.open),'exit_premium':float(ex.open),'entry_volume':float(en.volume),'exit_volume':float(ex.volume),'entry_cost':sum(a.values()),'exit_cost':sum(b.values())}
  trade.update({k:a[k]+b[k] for k in a})
  trade['gross_pnl']=(ex.open-en.open)*LOT;trade['costs']=trade['entry_cost']+trade['exit_cost'];trade['net_pnl']=trade['gross_pnl']-trade['costs'];trades.append(trade)
 except (KeyError,ValueError,AssertionError) as e:errors.append({**x,'error':str(e)})
def serial(x):
 if isinstance(x,(pd.Timestamp,datetime)):return x.isoformat()
 if isinstance(x,np.generic):return x.item()
 return str(x)
(ROOT/'missing_executions.json').write_text(json.dumps(errors,default=serial,indent=2))
if errors:
 (ROOT/'status.json').write_text(json.dumps(dict(status='BLOCKED_INCOMPLETE_EXECUTIONS',planned=len(pending),available=len(trades),missing=len(errors)),indent=2))
 raise RuntimeError(f'{len(errors)} missing executions; refusing partial performance metrics')
t=pd.DataFrame(trades);t.to_csv(ROOT/'trades.csv',index=False)
# Mark held option each completed minute, with next-open executions and actual fixed contract.
equity=[];realized=0.;active=None
byentry={x['entry_time']:x for x in trades};byexit={x['exit_time']:x for x in trades}
for ts,row in month.iterrows():
 if ts in byexit:
  x=byexit[ts];realized+=(x['exit_premium']-x['entry_premium'])*LOT-x['exit_cost'];active=None
 if ts in byentry:
  active=byentry[ts];realized-=active['entry_cost']
 mark=0.
 if active:
  q=price[active['symbol']]
  if ts not in q.index:raise RuntimeError('Missing held contract mark '+str(ts))
  mark=(q.loc[ts,'close']-active['entry_premium'])*LOT
 equity.append((ts,realized+mark))
eq=pd.DataFrame(equity,columns=['timestamp','net_pnl']).set_index('timestamp')
eq['drawdown_rupees']=eq.net_pnl-eq.net_pnl.cummax().clip(lower=0)
eq.to_csv(ROOT/'equity.csv')
assert abs(eq.net_pnl.iloc[-1]-t.net_pnl.sum())<1e-6
# Independent vectorbt order replay per immutable trade, including each side's full costs.
n=len(t);sizes=np.array([np.full(n,LOT),np.full(n,-LOT)])
prices=np.array([t.entry_premium.values,t.exit_premium.values])
fees=np.array([t.costs.values,np.zeros(n)])
# VectorBT rejects an exit when its fee exceeds sale proceeds, even with ample cash.
# Move total round-trip fees to entry only in this terminal-P&L cross-check.
# The authoritative minute equity above preserves actual fee timing.
pf=vbt.Portfolio.from_orders(prices,size=sizes,price=prices,fees=0.,fixed_fees=fees,init_cash=100000,min_size=LOT,size_granularity=LOT,raise_reject=True)
print('RECON',pf.total_profit().sum(),t.net_pnl.sum(),pf.orders.count().sum(),len(t)*2,flush=True); assert abs(pf.total_profit().sum()-t.net_pnl.sum())<1e-6
wins=t.net_pnl[t.net_pnl>0];loss=t.net_pnl[t.net_pnl<0]
summary=dict(status='COMPLETE',start=str(month.index[0]),end=str(month.index[-1]),sessions=len(counts),spot_bars=len(month),trades=n,contracts=len(symbols),quantity=LOT,gross_pnl=t.gross_pnl.sum(),costs=t.costs.sum(),net_pnl=t.net_pnl.sum(),win_rate_pct=(t.net_pnl>0).mean()*100,profit_factor=wins.sum()/-loss.sum(),max_drawdown_rupees=-eq.drawdown_rupees.min(),cost_breakdown={k:t[k].sum() for k in costs(100,True)},vectorbt_pnl_verified=True,signal_sma='30 completed regular-session minute bars, continuous across days',execution='next minute bar open following signal close, exact timestamp required; fixed contract; EOD 15:29 open',atm='nearest 50 points at signal close; halfway rounds up',slippage='zero baseline; market bar opens are not guaranteed fills',benchmark_nifty_spot_return_pct=(month.close.iloc[-1]/month.open.iloc[0]-1)*100)
(ROOT/'results.json').write_text(json.dumps(summary,default=serial,indent=2))
(ROOT/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.glob('*.json')},indent=2))
fig=go.Figure(go.Scatter(x=eq.index,y=eq.net_pnl,name='Net option P&L'));fig.update_layout(template='plotly_dark',title='NIFTY SMA30 options — October 2026',yaxis_title='Rupees');fig.write_html(ROOT/'equity.html',include_plotlyjs=True)
print(json.dumps(summary,default=serial,indent=2))

