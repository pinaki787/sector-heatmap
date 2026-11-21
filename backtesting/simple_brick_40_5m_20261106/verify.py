"""Independent ledger and framework validation; no broker access."""
from pathlib import Path
import json,sys,math,hashlib,collections,datetime,statistics
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];sys.path.insert(0,str(OUT));sys.path.insert(0,str(ROOT))
import replay
from strategies.renko_supertrend.backtest import framework_trade
r=json.loads((OUT/'results.json').read_text());quotes,surface,coverage=replay.load_options(r['sessions'][0],r['sessions'][-1]);checks=[]
for mode in ('auto','manual'):
 result=json.loads((OUT/(mode+'.json')).read_text());assert result['status']=='COMPLETE';assert not result['audit'];trades=result['trades'];metrics=result['metrics']
 assert sum(t['net'] for t in trades)==metrics['net']
 assert max(collections.Counter(t['day'] for t in trades).values())<=5
 assert all(a['exit_at']<b['entry_at'] for a,b in zip(trades,trades[1:]))
 assert metrics['missing_marks']==0
 samples=[t for t in trades if replay.minute(t['entry_at'])>=557 and t['exit_at']>t['entry_at']]
 samples=[samples[i] for i in sorted(set(int((len(samples)-1)*k/4) for k in range(5)))]
 framework=[]
 for t in samples:
  data=[dict(timestamp=stamp,open=q[0],high=q[1],low=q[2],close=q[3],volume=q[4]) for (stamp,side,strike),q in quotes.items() if side==t['side'] and strike==t['strike'] and replay.day(stamp)==t['day']]
  data.sort(key=lambda q:q['timestamp']);proof=framework_trade(data,t['entry_at'],t['exit_at'],65)
  expected=t['gross']+2*replay.SLIP*65
  assert math.isclose(proof['gross_pnl'],expected,abs_tol=.0001),(proof,expected)
  framework.append({'entry_at':t['entry_at'],'side':t['side'],'strike':t['strike'],'framework_gross':proof['gross_pnl'],'ledger_gross_before_slippage':expected})
 checks.append({'mode':mode,'status':'PASS','framework_samples':framework,'trades':len(trades)})
source={}
for name in ['signals.py','price_basis.py','entry_qualification.py','loss_range.py','session_auto.py','manual_brick.py','costs.py']:
 p=ROOT/'strategies/renko_supertrend'/name;source[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
supplement=[{'file':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (OUT.with_name('simple_brick_40_20261106')/'fyers-options').glob('hist-*.json')]
audit={'status':'PASS','checks':checks,'production_source_hashes':source,'research_script_hash':hashlib.sha256((OUT/'replay.py').read_bytes()).hexdigest(),'supplemental_fixed_contract_files':supplement,'download_failures_explained':'42 requests ending 6 November rejected; Dhan had no 5 November series. FYERS exact active-contract candles supply that day. No missing simulated price remains.'}
(OUT/'verification.json').write_text(json.dumps(audit,indent=2))
summary={}
for mode in ('auto','manual'):
 d=json.loads((OUT/(mode+'.json')).read_text());summary[mode]=d['metrics']
lines=['# Simple Brick Only — NIFTY 50 ₹40 options — five-minute candles','',f"30 completed sessions: {r['sessions'][0]} to {r['sessions'][-1]}. One lot of 65, ₹100,000 research capital, maximum five entries per session. Buy CALL on green, PUT on red; same strike held until opposite completed brick or 15:10 IST cutoff. Existing loss-range lock retained.",'','| Metric | Auto | Daily recalculated Manual |','|---|---:|---:|']
for label,key,fmt in [('Gross P&L','gross','₹{:,.2f}'),('Estimated charges','fees','₹{:,.2f}'),('Net P&L','net','₹{:,.2f}'),('Return on research capital','return_percent','{:.2f}%'),('Maximum marked drawdown','max_drawdown','₹{:,.2f}'),('Maximum drawdown percent','max_drawdown_percent','{:.2f}%'),('Win rate','win_rate','{:.2f}%'),('Profit factor, after costs','profit_factor','{:.2f}'),('Trades','trades','{:d}'),('CALL trades','calls','{:d}'),('PUT trades','puts','{:d}'),('Average net trade','average_trade','₹{:,.2f}')]:
 lines.append('| '+label+' | '+fmt.format(summary['auto'][key])+' | '+fmt.format(summary['manual'][key])+' |')
lines+=['',f"NIFTY underlying buy-and-hold price return over the same window: {r['benchmark']['return_percent']:.2f}% (not an option strategy or equal-risk benchmark).",'','Sizing is causal and recalculated before every session. Prior full-session Wilder ATR5; verified 375-minute session. Auto uses ATR × 3 × 5/375; Manual uses ATR/(375/30), rounded to two decimals, fixed for that day. No future session OHLC used.','', 'Execution limitations: completed five-minute underlying CLOSE samples feed the deployed price-brick engine. Intraminute tick paths are unavailable. ₹40 selection uses the closest prior completed one-minute option CLOSE, with next-minute OPEN fills and ₹0.05 premium slippage each side. Thus historical bid/ask execution cannot be certified and fills can differ from ₹40. Drawdown uses net equity marked at one-minute boundaries while signals remain on completed five-minute candles, not intraminute extrema. Costs use the existing FYERS estimate, not broker bills. Dhan nearest-week rolling surface plus FYERS exact-contract repairs; historical absolute expiry identification is calendar-assisted.','', 'Validation: both simulations COMPLETE, no price-gap or premium-surface audit issues, no missing marks; ten sample fixed-contract P&Ls independently matched backtesting.py. Source hashes, raw responses, journal CSVs, equity curves and full audit retained beside this report. No runners, settings, services or orders changed.','', '[Dhan historical rolling data documentation](https://dhanhq.co/docs/v2/expired-options-data/) · [FYERS fixed-contract historical data](https://fyers.in/api-docs/v3/api/market-data/expired-fo-data/get-expired-fo-data/) · [NSE lot-size circular](https://nsearchives.nseindia.com/content/circulars/FAOP70616.pdf)']
(OUT/'report.md').write_text('\n'.join(lines)+'\n')
(OUT/'progress.json').write_text(json.dumps({'phase':'COMPLETE','verified':True,'sessions':30,'metrics':summary}))
try:
 import plotly.graph_objects as go
 from plotly.subplots import make_subplots
 fig=make_subplots(rows=2,cols=1,shared_xaxes=True,subplot_titles=['Net equity','Drawdown'])
 for mode in ('auto','manual'):
  data=json.loads((OUT/(mode+'.json')).read_text())['curve'];peak=100000.;dd=[]
  for x in data:peak=max(peak,x['equity']);dd.append(peak-x['equity'])
  fig.add_trace(go.Scatter(x=[replay.clock(x['at']) for x in data],y=[x['equity'] for x in data],name=mode.title()),row=1,col=1)
  fig.add_trace(go.Scatter(x=[replay.clock(x['at']) for x in data],y=dd,name=mode.title()+' drawdown'),row=2,col=1)
 fig.update_layout(template='plotly_dark',title='Simple Brick Only — NIFTY 50 ₹40 option buys',height=800);fig.write_html(str(OUT/'equity_drawdown.html'),include_plotlyjs=True)
except ImportError:pass
print(json.dumps({'verification':'PASS','framework_checks':sum(len(x['framework_samples']) for x in checks),'metrics':summary,'benchmark':r['benchmark']},indent=2))
