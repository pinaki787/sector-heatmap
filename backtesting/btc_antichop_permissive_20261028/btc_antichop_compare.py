"""Read-only BTCUSD adaptive anti-chop research; never accesses order APIs."""
from pathlib import Path
import json,time,hashlib,sys,importlib.util,csv,math,copy
import numpy as np,pandas as pd,vectorbt as vbt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
ROOT=Path('/home/trading/sector-heatmap');OUT=ROOT/'backtesting/btc_antichop_permissive_20261028';OUT.mkdir(parents=True,exist_ok=True)
ACCOUNT=ROOT/'.private/dashboard-login/accounts/a6ef4c9bcecd21d54c4a07e2b9b137a7/source'
DATA=ACCOUNT/'.private/renko-delta-history/BTCUSD-1m.json'
STATE=ACCOUNT/'.private/renko-delta-instances/0fa0ae88f933ca46cbe8/renko-delta-state.json'
if not (OUT/'candles_snapshot.json').exists():
 raw=DATA.read_bytes();(OUT/'candles_snapshot.json').write_bytes(raw)
 (OUT/'config_snapshot.json').write_text(json.dumps(json.loads(STATE.read_text())['config'],indent=2))
 (OUT/'anti_chop_snapshot.py').write_text((ACCOUNT/'strategies/renko_supertrend/anti_chop.py').read_text())
spec=importlib.util.spec_from_file_location('frozen_anti_chop',OUT/'anti_chop_snapshot.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
raw=(OUT/'candles_snapshot.json').read_bytes();data=json.loads(raw);now=time.time();rows=[r for r in data['rows'] if r['timestamp']+60<=now]
rows.sort(key=lambda r:r['timestamp']);assert len({r['timestamp'] for r in rows})==len(rows)
assert all(b['timestamp']-x['timestamp']==60 for x,b in zip(rows,rows[1:]))
assert all(0<r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high'] and all(math.isfinite(r[k]) for k in ['timestamp','open','high','low','close']) for r in rows)
index=pd.to_datetime([r['timestamp'] for r in rows],unit='s',utc=True);close=pd.Series([r['close'] for r in rows],index=index);opens=np.array([r['open'] for r in rows]);N=len(rows)
base=json.loads((OUT/'config_snapshot.json').read_text());ema=np.empty(N)
for i,r in enumerate(rows):ema[i]=r['close'] if i==0 else ema[i-1]+2/11*(r['close']-ema[i-1])
variants=[('Current 20/50',{},'all'),('Structure 2 only',{'anti_chop_structure_bars':2},'all'),('Softer 20/50',{'anti_chop_structure_bars':2,'anti_chop_cross_bars':3,'anti_chop_slope_percentile':40.,'anti_chop_gap_percentile':40.,'anti_chop_overlap_percentile':60.},'all'),('Softer 10/30',{'anti_chop_structure_bars':2,'anti_chop_cross_bars':3,'anti_chop_slope_percentile':40.,'anti_chop_gap_percentile':40.,'anti_chop_overlap_percentile':60.,'anti_chop_ema_fast_length':10,'anti_chop_ema_slow_length':30},'all'),('Trend-aware 10/30',{'anti_chop_structure_bars':2,'anti_chop_cross_bars':3,'anti_chop_slope_percentile':40.,'anti_chop_gap_percentile':40.,'anti_chop_overlap_percentile':60.,'anti_chop_ema_fast_length':10,'anti_chop_ema_slow_length':30},'either')]
# Fix calendar split before measuring results. Earliest 70% development, final 30% holdout;
# all variants retain rolling past-only calibration, including during the holdout.
split=int(N*.7);valid_start=1000
manifest={'symbol':'BTCUSD','source':'Delta India durable traded-price perpetual candle archive','product_id':data['product_id'],'sha256':hashlib.sha256(raw).hexdigest(),'bars':N,'first':str(index[0]),'last':str(index[-1]),'missing_minutes':0,'duplicates':0,'split':str(index[split]),'warmup_bars':valid_start,'variants':[{'name':n,'changes':c,'rule':'all four' if rule=='all' else 'slope AND separation AND (ATR OR structure)'} for n,c,rule in variants],'costs_roundtrip_bps':[0,5,10],'capital_usd':1000000,'size_btc':1,'execution':'Completed-close signal; next-minute-open fill. EMA10 adverse completed close exits at next open. At least one later completed candle before re-entry. Forced flat at sample boundaries; no cross-split trades. No option price, spread, funding, margin or broker-fill simulation. No tuning on holdout results.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'phase':'audit','bars':N,'first':str(index[0]),'last':str(index[-1]),'split':str(index[split])}),flush=True)
summaries=[];alltrades=[];curves={};gate_audits=[]
def simulate(name,qualified,directions,begin,end,cost):
 pending=None;held=None;orders=np.zeros(N);prices=opens.copy();trades=[];last_exit=-1
 for i in range(begin,end):
  if pending:
   action,sgn=pending;pending=None
   if action=='exit':
    gross=held['sign']*(opens[i]-held['price']);fees=(held['price']+opens[i])*cost/20000
    trades.append(dict(variant=name,entry_time=str(index[held['i']]),exit_time=str(index[i]),entry_price=held['price'],exit_price=float(opens[i]),direction='Long' if held['sign']==1 else 'Short',gross_points=gross,cost_points=fees,net_points=gross-fees,exit_reason='EMA10'))
    orders[i]=-held['sign'];held=None;last_exit=i
   else:
    orders[i]=sgn;held={'sign':sgn,'price':float(opens[i]),'i':i}
  if i==end-1:
   if held:
    price=rows[i]['close'];orders[i]-=held['sign'];prices[i]=price
    gross=held['sign']*(price-held['price']);fees=(held['price']+price)*cost/20000
    trades.append(dict(variant=name,entry_time=str(index[held['i']]),exit_time=str(index[i]+pd.Timedelta(seconds=60)),entry_price=held['price'],exit_price=price,direction='Long' if held['sign']==1 else 'Short',gross_points=gross,cost_points=fees,net_points=gross-fees,exit_reason='SAMPLE_END'))
    held=None
   break
  if held:
   if rows[i]['close']<ema[i] if held['sign']==1 else rows[i]['close']>ema[i]:pending=('exit',held['sign'])
  elif qualified[i] and i>last_exit:pending=('entry',directions[i])
 # No same-open netting. A final forced exit coincident with an entry fill would
 # need two orders/prices; don't allow entries on the final bar.
 pf=vbt.Portfolio.from_orders(close.iloc[begin:end],size=orders[begin:end],price=prices[begin:end],fees=cost/20000,init_cash=1_000_000,min_size=1,size_granularity=1,allow_partial=False,freq='1min')
 vals=pf.value();net=sum(t['net_points'] for t in trades)
 if abs(float(vals.iloc[-1])-1_000_000-net)>1e-6:raise AssertionError((name,cost,float(vals.iloc[-1])-1_000_000,net))
 wins=sum(t['net_points']>0 for t in trades);pos=sum(max(0,t['net_points']) for t in trades);neg=-sum(min(0,t['net_points']) for t in trades)
 summary=dict(variant=name,window='Development' if begin==valid_start else 'Holdout',cost_bps=cost,bars=end-begin,pass_pct=100*float(qualified[begin:end].mean()),trades=len(trades),gross_points=sum(t['gross_points'] for t in trades),net_points=net,profit_factor=pos/neg if neg else None,win_pct=100*wins/len(trades) if trades else 0,max_drawdown_points=float((vals.cummax()-vals).max()),return_pct=100*net/1_000_000)
 if cost==5:curves[(name,summary['window'])]=vals-1_000_000;alltrades.extend([{**t,'window':summary['window'],'cost_bps':cost} for t in trades])
 return summary
for name,changes,rule in variants:
 cfg={**base,**changes};state={};qual=np.zeros(N,dtype=bool);directions=np.zeros(N,dtype=int);fail={k:0 for k in ['atr','slope','separation','structure']}
 for i,row in enumerate(rows):
  gate=a.observe(state,row,cfg,'NEUTRAL',60);checks={x['key']:x['passed'] for x in gate['checks']}
  qual[i]=gate['allowed'] if rule=='all' else gate['ready'] and checks['slope'] and checks['separation'] and (checks['atr'] or checks['structure'])
  directions[i]=1 if gate['direction']=='BULLISH' else -1
  if i>=valid_start:
   for k,v in checks.items():fail[k]+=not v
  if i>=N-120:gate_audits.append({'variant':name,'time':str(index[i]),'close':row['close'],'direction':gate['direction'],'qualified':bool(qual[i]),'failures':','.join(k for k,v in checks.items() if not v),'thresholds':gate['thresholds']})
 # Never schedule a fresh entry onto the last bar, which is reserved for boundary liquidation.
 for end in [split,N]:qual[end-2]=False
 for begin,end in [(valid_start,split),(split,N)]:
  for cost in [0,5,10]:summaries.append(simulate(name,qual,directions,begin,end,cost))
 print(json.dumps({'phase':'variant_done','name':name,'failures':fail,'holdout':[x for x in summaries if x['variant']==name and x['window']=='Holdout']}),flush=True)
 pd.DataFrame(summaries).to_csv(OUT/'comparison.csv',index=False)
 pd.DataFrame(alltrades).to_csv(OUT/'trades_5bps.csv',index=False)
(OUT/'results.json').write_text(json.dumps(summaries,indent=2,allow_nan=False))
(OUT/'recent_gate_audit.json').write_text(json.dumps(gate_audits,indent=2))
# A directly comparable one-BTC buy-and-hold benchmark at next-open start.
bench=[]
for label,begin,end in [('Development',valid_start,split),('Holdout',split,N)]:
 entry=opens[begin];exit=rows[end-1]['close'];net=exit-entry-(entry+exit)*5/20000
 bench.append(dict(window=label,variant='Buy & hold BTC',net_points=net,trades=1,cost_bps=5,max_drawdown_points=float((close.iloc[begin:end].cummax()-close.iloc[begin:end]).max())))
(OUT/'benchmark.json').write_text(json.dumps(bench,indent=2))
fig=make_subplots(rows=2,cols=1,subplot_titles=['Holdout: cumulative net USD points per 1 BTC, 5 bps round trip','Development: cumulative net USD points per 1 BTC, 5 bps round trip'])
for (name,window),curve in curves.items():
 thin=curve.iloc[::15];fig.add_trace(go.Scatter(x=thin.index,y=thin,name=name,legendgroup=name,showlegend=window=='Holdout'),row=1 if window=='Holdout' else 2,col=1)
fig.update_layout(template='plotly_dark',height=850,title='BTCUSD anti-chop comparison · research only',hovermode='x unified');fig.write_html(OUT/'equity.html',include_plotlyjs=True)
# Tearsheet for the predeclared faster variant; daily sampling avoids misleading
# annualized minute-frequency statistics on a short sample.
try:
 import openstatz as ostz
 curve=curves[('Softer 10/30','Holdout')]+1_000_000
 daily=curve.resample('1D').last().pct_change().dropna();daily.name='Softer 10/30 · holdout proxy'
 benchmark=close.reindex(curve.index).resample('1D').last().pct_change().dropna();benchmark.name='BTCUSD buy and hold'
 daily.index=daily.index.tz_localize(None);benchmark.index=benchmark.index.tz_localize(None)
 ostz.dashboard(daily,benchmark=benchmark,output=str(OUT/'tearsheet.html'),periods_per_year=365,rolling_window=5,open_browser=False)
except Exception as e:(OUT/'tearsheet_note.txt').write_text(str(e))
df=pd.DataFrame(summaries);table=df[(df.window=='Holdout')&(df.cost_bps==5)].copy();table=table[['variant','pass_pct','trades','gross_points','net_points','profit_factor','win_pct','max_drawdown_points']]
html='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>BTCUSD anti-chop comparison</title><style>body{background:#0d1421;color:#e5edf8;font:16px system-ui;max-width:1180px;margin:40px auto;padding:0 24px;line-height:1.6}h1{font-size:30px}h2{font-size:21px;color:#b9d3ef}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:right;padding:12px;border-bottom:1px solid #29364b}td:first-child,th:first-child{text-align:left}th{color:#9fbbd8}.scroll{overflow:auto}a{color:#83c8ff}.note{background:#162235;padding:20px;border-radius:12px}iframe{width:100%;height:900px;border:0}</style></head><body><h1>BTCUSD: is Adaptive anti-chop too restrictive?</h1>'''
html+=f'<p>Delta India perpetual traded-price candles · {N:,} consecutive one-minute candles · {index[0]} through {index[-1]} UTC.</p>'
html+='<div class="note">Research only. Production runner and settings were left unchanged. These are linear underlying-price simulations with EMA10 exits, not the currently traded ATM options. Hypothetical costs are 0, 5 and 10 basis points round trip; actual option fees, spread, Greeks, expiry and fills are not modeled.</div>'
html+=f'<h2>Chronological holdout</h2><p>Final 30% starts {index[split]} UTC. Parameters and variants were fixed before this run; rolling thresholds use prior completed observations only. Earlier 70% is shown separately. No claim of out-of-sample profitability from strategy selection.</p><div class="scroll">'+table.to_html(index=False,float_format=lambda x:f'{x:,.2f}',border=0)+'</div>'
html+='<h2>What changes</h2><ul>'+''.join('<li><b>'+n+'</b>: '+('existing settings' if not c else ', '.join(k.replace('anti_chop_','')+'='+str(v) for k,v in c.items()))+('; slope and separation mandatory, with ATR or structure sufficient' if rule=='either' else '; all four checks required')+'</li>' for n,c,rule in variants)+'</ul>'
html+='<h2>Cost sensitivity</h2><div class="scroll">'+df[df.window=='Holdout'][['variant','cost_bps','net_points','trades','profit_factor']].to_html(index=False,float_format=lambda x:f'{x:,.2f}',border=0)+'</div>'
html+='<h2>BTC benchmark, 5 bps round trip</h2><div class="scroll">'+pd.DataFrame(bench).to_html(index=False,float_format=lambda x:f'{x:,.2f}',border=0)+'</div>'
html+='<h2>Execution and limitations</h2><p>One BTC fixed size and one million USD virtual accounting capital. Entries and EMA10 exits fill at the next minute open; no same-candle execution. No trade crosses the development/holdout boundary; last candle forces liquidation. One later completed candle is required after an exit before re-entry. No daily trade cap in research (the active Paper runner has a five-entry run limit). No funding, executable spread, margin or option history. This study cannot estimate the running options strategy P&amp;L.</p><iframe src="equity.html" title="Equity curves"></iframe><p><a href="comparison.csv">All results CSV</a> · <a href="trades_5bps.csv">Trade ledger</a> · <a href="manifest.json">Data audit and rules</a> · <a href="btc_antichop_compare.py">Reproducible script</a></p></body></html>'
(OUT/'report.html').write_text(html)
print(json.dumps({'phase':'complete','report':str(OUT/'report.html'),'benchmark':bench}),flush=True)
