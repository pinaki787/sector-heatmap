"""Independent audit of the minute-close Renko approximation, not tick-fidelity certification."""
import json,hashlib,math,os,time,gzip,zipfile,io,argparse
from pathlib import Path
from decimal import Decimal
import pandas as pd,numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
STUDY=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--range-lock',action='store_true');args=parser.parse_args()
P=STUDY/'entry_brick_range_lock' if args.range_lock else STUDY
PROJECT=Path('/home/trading/sector-heatmap');B=STUDY.parent/'nifty_sma30_options_20261110'
r=json.loads((P/'results.json').read_text());t=pd.read_csv(P/'trades.csv');o=pd.read_csv(P/'orders.csv');eq=pd.read_csv(P/'equity.csv');br=pd.read_csv(P/'bricks.csv');obs=pd.read_csv(P/'brick_observations.csv');c=pd.read_csv(P/'candidate_signals.csv');lots=pd.read_csv(P/'dated_lot_evidence.csv');dec=pd.read_csv(P/'decisions.csv')
raw=json.loads((PROJECT/'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/nifty50_1m.json').read_text())['rows']+json.loads((B/'raw/spot_oct24_31.json').read_text())['candles']
s=pd.DataFrame(raw,columns=['epoch','open','high','low','close','volume']);s.index=pd.to_datetime(s.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata');s=s.between_time('09:15','15:29').loc['2026-05-01':'2026-10-31']
holidays={'2026-05-01','2026-05-28','2026-06-26','2026-09-14','2026-10-02','2026-10-20'};expected={str(x.date()) for x in pd.bdate_range('2026-05-01','2026-10-31') if str(x.date()) not in holidays};actual={str(d) for d in s.index.date}
assert actual==expected and len(actual)==125
assert s.groupby(lambda x:x.date()).size().eq(375).all()
# Independent closed-form brick reconstruction (production uses an incremental loop).
expected_events=[];previous_direction=0;serial=0
for day,d in s.groupby(s.index.date):
 level=int(Decimal(str(d.iloc[0].open))*100);previous_direction=0
 for ts,row in d.iterrows():
  price=int(Decimal(str(row.close))*100);n=abs(price-level)//1200
  if n:
   sign=1 if price>level else -1
   for k in range(n):
    serial+=1;opened=level+sign*k*1200;closed=opened+sign*1200
    expected_events.append((serial,str(day),ts,ts+pd.Timedelta(minutes=1),opened/100,closed/100,sign,bool(previous_direction and sign!=previous_direction)))
    previous_direction=sign
   level+=sign*n*1200
  assert abs(price-level)<1200
assert len(expected_events)==len(br)==r['completed_bricks']
for i,x in enumerate(br.to_dict('records')):
 ref=expected_events[i]
 assert int(x['brick_id'])==ref[0] and x['day']==ref[1]
 assert pd.Timestamp(x['source_minute'])==ref[2] and pd.Timestamp(x['known_at'])==ref[3]
 assert x['brick_open']==ref[4] and x['brick_close']==ref[5] and x['direction']==ref[6] and bool(x['reversal'])==ref[7]
assert br.brick_id.is_unique and np.allclose((br.brick_close-br.brick_open).abs(),12)
# Reconstruct every exact daily evidence row from retained official raw bytes.
evidence={};hash_cache={};table_cache={}
for x in lots.to_dict('records'):
 path=PROJECT/x['source_file'];key=str(path)
 if key not in hash_cache:hash_cache[key]=hashlib.sha256(path.read_bytes()).hexdigest()
 assert hash_cache[key]==x['source_sha256'] and x['effective_from']==x['day']==x['effective_to']
 if key not in table_cache:
  if x['provider']=='NSE_DAILY_MII_MASTER':
   cols=['StockNm','FinInstrmNm','TckrSymb','XpryDt','StrkPric','OptnTp','MinLot','NewBrdLotQty']
   df=pd.read_csv(io.BytesIO(gzip.decompress(path.read_bytes())),usecols=cols,dtype=str);df=df[df.TckrSymb.eq('NIFTY')];table_cache[key]=df.set_index('StockNm')
  else:
   with zipfile.ZipFile(path) as z:df=pd.read_csv(z.open(z.namelist()[0]),dtype=str)
   df=df[df.TckrSymb.eq('NIFTY')];table_cache[key]=df.set_index('FinInstrmNm')
 row=table_cache[key].loc[x['symbol'].removeprefix('NSE:')]
 assert int(row.NewBrdLotQty)==x['lot_size'] and Decimal(row.NewBrdLotQty)==x['lot_size']
 if x['provider']=='NSE_UDIFF_DAILY_BHAVCOPY':
  assert row.TradDt==x['day'] and row.XpryDt==x['expiry'] and Decimal(row.StrkPric)==x['strike'] and row.OptnTp==x['side']
 evidence[(x['day'],x['symbol'])]=x
del table_cache
en=pd.to_datetime(t.entry_time);ex=pd.to_datetime(t.exit_time)
assert (en.dt.date==ex.dt.date).all() and en.dt.strftime('%H:%M').le('15:28').all()
assert (en.iloc[1:].reset_index(drop=True)>=ex.iloc[:-1].reset_index(drop=True)).all()
brickdir=br.set_index('brick_id').direction.to_dict();brickknown=br.set_index('brick_id').known_at.to_dict()
for x in t.to_dict('records'):
 key=(pd.Timestamp(x['entry_time']).strftime('%Y-%m-%d'),x['symbol']);e=evidence[key]
 assert x['quantity']==e['lot_size'] and x['lot_source_sha256']==e['source_sha256']
 assert pd.Timestamp(x['signal_known_at'])==pd.Timestamp(x['entry_time'])==pd.Timestamp(x['signal_source_minute'])+pd.Timedelta(minutes=1)
 assert brickdir[x['entry_brick_id']]==x['direction']
 if x['exit_reason']=='opposite_brick':
  assert brickdir[int(x['exit_signal_brick_id'])]!=x['direction']
  assert pd.Timestamp(brickknown[int(x['exit_signal_brick_id'])])==pd.Timestamp(x['exit_signal_known_at'])
  assert pd.Timestamp(x['exit_time'])>=pd.Timestamp(x['exit_signal_known_at'])
 else:assert pd.Timestamp(x['exit_time']).strftime('%H:%M')=='15:29'
lock_audit={}
if args.range_lock:
 locks=pd.read_csv(P/'lock_events.csv');bl=br.set_index('brick_id').to_dict('index')
 byentry={pd.Timestamp(x['entry_time']):x for x in t.to_dict('records')};byexit={pd.Timestamp(x['exit_time']):x for x in t.to_dict('records')}
 batches={pd.Timestamp(k):g.to_dict('records') for k,g in br.groupby('known_at')}
 lock=None;lastday=None;activations=0;breakouts=0;locked_minutes=0
 for erow in eq.to_dict('records'):
  ts=pd.Timestamp(erow['timestamp'])
  if str(ts.date())!=lastday:lock=None;lastday=str(ts.date())
  exited=byexit.get(ts)
  if exited and exited['net_pnl']<0:
   brick=bl[exited['entry_brick_id']]
   lock=dict(low=min(brick['brick_open'],brick['brick_close']),high=max(brick['brick_open'],brick['brick_close']),activated_at=ts,entry_id=exited['entry_id']);activations+=1
  entered=byentry.get(ts)
  if entered:
   batch=batches[ts];chosen=bl[entered['entry_brick_id']]
   if lock:
    assert ts>lock['activated_at']
    valid=[x for x in batch if (x['brick_close']>lock['high'] and x['direction']==1) or (x['brick_close']<lock['low'] and x['direction']==-1)]
    assert valid and valid[0]['brick_id']==entered['entry_brick_id']
    lock=None;breakouts+=1
   else:assert batch[0]['brick_id']==entered['entry_brick_id']
  assert bool(erow['lock_active'])==(lock is not None)
  if lock:locked_minutes+=1
 for x in locks[locks.event=='lock_activated'].to_dict('records'):
  exited=t[t.entry_id==x['losing_entry_id']].iloc[0];brick=bl[exited.entry_brick_id]
  assert exited.net_pnl<0 and pd.Timestamp(exited.exit_time)==pd.Timestamp(x['time'])
  assert x['entry_brick_id']==exited.entry_brick_id and x['low']==min(brick['brick_open'],brick['brick_close']) and x['high']==max(brick['brick_open'],brick['brick_close'])
 assert activations==r['lock_activations'] and breakouts==r['breakout_entries'] and locked_minutes==r['minutes_locked']
 lock_audit=dict(realized_net_loss_only=True,range_from_original_entry_brick=True,strict_breakout_equality_stays_inside=True,fresh_known_brick_after_loss_fill=True,first_matching_color_breakout_brick=True,lock_clears_only_on_valid_entry=True,session_resets=True,activations=activations,breakouts=breakouts,minutes_locked=locked_minutes,filtered_reasons=dec[dec.reason.str.startswith('range_lock_')].reason.value_counts().to_dict())
else:
 for x in t.to_dict('records'):
  group=br[br.known_at==x['entry_time']]
  assert len(group) and group.iloc[0].brick_id==x['entry_brick_id']
sources=json.loads((P/'data_sources.json').read_text());prices={};inputs={}
for sym,path in sources.items():
 raw=json.loads(Path(path).read_text());rows=raw.get('candles',raw.get('data',{}).get('candles',[]));d=pd.DataFrame([x[:6] for x in rows],columns=['epoch','open','high','low','close','volume'])
 d.index=pd.to_datetime(d.epoch,unit='s',utc=True).dt.tz_convert('Asia/Kolkata');assert not d.index.duplicated().any()
 assert ((d.low<=d[['open','close']].min(axis=1))&(d.high>=d[['open','close']].max(axis=1))).all()
 prices[sym]=d;inputs[path]=dict(sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),bars=len(d))
o.time=pd.to_datetime(o.time);bytime={k:v for k,v in o.groupby('time')};cash=0.;inventory={};maxerr=0.
for x in eq.to_dict('records'):
 ts=pd.Timestamp(x['timestamp'])
 if ts in bytime:
  for order in bytime[ts].to_dict('records'):
   sym=order['symbol'];qty=order['quantity'] if order['side']=='BUY' else -order['quantity']
   assert prices[sym].loc[ts,'volume']>0 and abs(prices[sym].loc[ts,'open']-order['premium'])<1e-7
   cash-=qty*order['premium']+order['costs'];inventory[sym]=inventory.get(sym,0)+qty;assert inventory[sym]>=0
 assert sum(qty>0 for qty in inventory.values())<=1
 mark=sum(qty*prices[sym].loc[ts,'close'] for sym,qty in inventory.items() if qty)
 err=abs(cash+mark-x['net_pnl']);maxerr=max(maxerr,err);assert err<1e-6
assert all(qty==0 for qty in inventory.values())
assert abs(cash-r['net_pnl'])<1e-6 and abs(t.net_pnl.sum()-cash)<1e-6 and abs(o.costs.sum()-r['costs'])<1e-6
t['month']=en.dt.strftime('%Y-%m');t['holding_minutes']=(ex-en).dt.total_seconds()/60
eq.timestamp=pd.to_datetime(eq.timestamp);eq['month']=eq.timestamp.dt.strftime('%Y-%m')
def metrics(d):
 losses=-d.net_pnl[d.net_pnl<0].sum();return dict(trades=len(d),wins=int(d.net_pnl.gt(0).sum()),win_rate_pct=d.net_pnl.gt(0).mean()*100,profit_factor=d.net_pnl[d.net_pnl>0].sum()/losses if losses else None,gross_pnl=d.gross_pnl.sum(),costs=d.costs.sum(),net_pnl=d.net_pnl.sum(),opposite_brick_exits=int(d.exit_reason.eq('opposite_brick').sum()),EOD_exits=int(d.exit_reason.eq('scheduled_15:29').sum()),median_holding_minutes=d.holding_minutes.median())
monthly=[]
for month,d in t.groupby('month'):
 e=eq[eq.month==month];net=e.net_pnl-e.net_pnl.iloc[0];dd=net-net.cummax().clip(lower=0)
 monthly.append(dict(month=month,sessions=len({x.date() for x in e.timestamp}),**metrics(d),max_drawdown_rupees=float(-dd.min())))
monthly=pd.DataFrame(monthly);monthly.to_csv(P/'monthly_results.csv',index=False)
reason=t.groupby('exit_reason').agg(trades=('entry_id','size'),gross_pnl=('gross_pnl','sum'),costs=('costs','sum'),net_pnl=('net_pnl','sum')).reset_index();reason.to_csv(P/'exit_attribution.csv',index=False)
exclusions=dec[dec.reason.isin(['missing_entry_candle','zero_volume_entry_candle'])].copy();exclusions.to_csv(P/'execution_exclusions.csv',index=False)
# Actual option-data availability lag only. Unknown intra-minute brick timing is not estimated.
delays=t[t.get('exit_extra_delay_minutes',pd.Series(0,index=t.index)).fillna(0)>0].copy();delays.to_csv(P/'delayed_exits.csv',index=False)
def fee(p,q,buy):
 v=p*q;return (20+v*(.000355299+.00009+.000001+.000000001))*1.18+v*(.00003 if buy else .0015)
def scenario(delta):
 altered=o.copy();altered['price']=np.where(altered.side=='BUY',altered.premium+delta,np.maximum(0,altered.premium-delta))
 altered['fee']=[fee(p,q,side=='BUY') for p,q,side in zip(altered.price,altered.quantity,altered.side)]
 altered['flow']=np.where(altered.side=='BUY',-1,1)*altered.quantity*altered.price
 per=altered.groupby('entry_id').agg(gross=('flow','sum'),fees=('fee','sum'));per['net_pnl']=per.gross-per.fees
 changes=altered.flow-altered.fee-(np.where(altered.side=='BUY',-1,1)*altered.quantity*altered.premium-altered.costs)
 changes=pd.DataFrame({'time':altered.time,'change':changes}).groupby('time').change.sum();curve=eq.net_pnl.to_numpy()+changes.reindex(pd.DatetimeIndex(eq.timestamp),fill_value=0).cumsum().to_numpy();peak=np.maximum.accumulate(np.maximum(curve,0));dd=(peak-curve).max()
 loss=-per.net_pnl[per.net_pnl<0].sum()
 return dict(adverse_premium_points_per_unit_each_fill=delta,gross_pnl=per.gross.sum(),costs=per.fees.sum(),net_pnl=per.net_pnl.sum(),win_rate_pct=per.net_pnl.gt(0).mean()*100,profit_factor=per.net_pnl[per.net_pnl>0].sum()/loss,max_drawdown_rupees=dd)
slippage=pd.DataFrame([scenario(x) for x in [0,.05,.1,.25,.5,1.]])
assert abs(slippage.iloc[0].net_pnl-r['net_pnl'])<1e-6
slippage.to_csv(P/'slippage_sensitivity.csv',index=False)
daily=t.groupby(en.dt.strftime('%Y-%m-%d')).net_pnl.sum();daily.to_csv(P/'daily_results.csv')
audit=dict(status='VERIFIED_CLOSE_PATH_APPROXIMATION',tick_fidelity_verified=False,input_granularity='Spot1mOHLC,signals ONLY sequential1mcloses; option1mOHLC for next-open pricing',no_complete_six_month_tick_archive_found=True,production_builder_has_2brick_reversal_but_this_study_explicitly_1=True,one_brick_reversal_and_full12point_thresholds_verified=True,independent_closed_form_all_bricks_match=True,locked_prefix_depends_only_on_prices_seen=True,dated_exact_contract_lot_rows_verified=len(lots),lot_sizes=sorted(t.quantity.unique().tolist()),dated_lot_providers=lots.provider.value_counts().to_dict(),exact_daily_exchange_source_checksums_verified=True,calendar_expected_sessions=125,observed_sessions=125,missing_sessions=[],independent_every_minute_cash_inventory_error=maxerr,all_executed_option_opens_match_real_positive_volume_bars=True,no_pyramiding_or_overnight_inventory=True,trade_and_order_costs_reconcile=True,vectorbt_terminal_check=r['vectorbt_terminal_verified'],completed_bricks=len(br),completed_trade_count=len(t),range_lock_audit=lock_audit,entry_exclusions=len(exclusions),exit_lag_events=len(delays),maximum_extra_option_exit_delay_minutes=float(delays.exit_extra_delay_minutes.max()) if len(delays) else 0,unknown_intraminute_brick_events_not_reconstructed=True)
(P/'verification.json').write_text(json.dumps(audit,indent=2))
analysis=dict(overall=metrics(t),monthly=monthly.to_dict('records'),exit_attribution=reason.to_dict('records'),profitable_months=int(monthly.net_pnl.gt(0).sum()),losing_months=int(monthly.net_pnl.lt(0).sum()),profitable_days=int(daily.gt(0).sum()),losing_days=int(daily.lt(0).sum()),best5days_net=daily.nlargest(5).sum(),other_days_net=r['net_pnl']-daily.nlargest(5).sum(),slippage=slippage.to_dict('records'),entry_exclusion_reasons=exclusions.reason.value_counts().to_dict())
(P/'analysis.json').write_text(json.dumps(analysis,indent=2,default=lambda x:x.item() if isinstance(x,np.generic) else str(x)))
(P/'input_manifest.json').write_text(json.dumps(inputs,indent=2))
provenance=[STUDY/'backtest.py',STUDY/'verify.py',P/'dated_lot_evidence.csv',PROJECT/'strategies/renko_supertrend/price_basis.py',PROJECT/'strategies/renko_supertrend/brick_basis.py',B/'raw/spot_oct24_31.json',PROJECT/'data/backtesting/nifty50-fyers-2024-10-25_2026-10-24/manifest.json']
(P/'provenance.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in provenance},indent=2))
fig=make_subplots(rows=2,cols=1,subplot_titles=['Net option marked P&L — CLOSE-PATH APPROXIMATION','Monthly net P&L'])
fig.add_trace(go.Scatter(x=eq.timestamp,y=eq.net_pnl,name='Net rupees'),row=1,col=1);fig.add_trace(go.Bar(x=monthly.month,y=monthly.net_pnl,name='Monthly net'),row=2,col=1)
fig.update_layout(template='plotly_dark',title='Renko12,one-brick reversals,one lot — May–October2026 minute-close approximation',height=800);fig.write_html(P/'equity.html',include_plotlyjs=True)
r['status']='VERIFIED_CLOSE_PATH_APPROXIMATION';(P/'results.json').write_text(json.dumps(r,indent=2))
verification_status=dict(status='VERIFIED_COMPLETE_APPROXIMATION',variant='entry_brick_range_lock' if args.range_lock else 'plain',verified_epoch=time.time());(P/'verification_status.json').write_text(json.dumps(verification_status,indent=2))
status=json.loads((STUDY/'job_status.json').read_text())
if status.get('status')!='RUNNING' and status.get('variant')==verification_status['variant']:
 status.update(verification_status,stage='verified');(STUDY/'job_status.json').write_text(json.dumps(status,indent=2))
print(json.dumps(dict(verification=audit,analysis=analysis),indent=2,default=str))

