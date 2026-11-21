"""Produce retained research report and trade journals, never deploy settings."""
import json,pathlib,csv,html,statistics,hashlib
P=pathlib.Path(__file__).resolve().parent
d=json.loads((P/'results.json').read_text());plan=d['plan'];results=d['results'];days=plan['data']['days'];mid=days[10];audit=d['option_audit']
def metric(r,scenario,period):return r['scenarios'][scenario][period]['metrics']
def valid(r):return all(v['valid'] for s in r['scenarios'].values() for v in s.values())
def score(r):m=metric(r,'stress','development');return m['net']-.5*m['max_drawdown']
def eligible(r):
 m=metric(r,'stress','development');tr=r['scenarios']['stress']['development']['trades']
 return valid(r) and m['trades']>=8 and m['net']>0 and m['calls']>0 and m['puts']>0 and all(sum(t['net'] for t in tr if (t['day']<mid)==half)>0 for half in [True,False])
valids=[r for r in results if valid(r)];ranked=sorted(valids,key=score,reverse=True);eligible_rows=sorted([r for r in valids if eligible(r)],key=score,reverse=True);selected=eligible_rows[0] if eligible_rows else None
passed=False
if selected:
 v=metric(selected,'stress','validation');passed=v['trades']>=5 and v['net']>0 and v['calls']>0 and v['puts']>0
decision={'status':'Paper Trade Recommended' if passed else 'Needs Improvement','live_ready':False,'selected_using_development':selected['name'] if selected else None,'validation_passed':passed,'reason':'Small sample and previously examined validation dates; never an ideal/proven live setting.','source_drift':[]}
for file,expected in plan['source_hashes'].items():
 f=P.parents[1]/file
 if hashlib.sha256(f.read_bytes()).hexdigest()!=expected:decision['source_drift'].append(file)
if decision['source_drift']:decision.update(status='Needs Improvement',validation_passed=False,reason='Source changed during replay; reproduction requires frozen-source review.')
(P/'decision.json').write_text(json.dumps(decision,indent=2))
rows=[]
for r in results:
 for scenario,periods in r['scenarios'].items():
  for period,x in periods.items():
   rows.append(dict(name=r['name'],scenario=scenario,period=period,valid=x['valid'],**x['metrics']))
with (P/'comparison.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
trades=[]
for r in results:
 for scenario,periods in r['scenarios'].items():
  for period,x in periods.items():
   for t in x['trades']:trades.append(dict(variant=r['name'],scenario=scenario,period=period,**{k:v for k,v in t.items() if k!='entry_indicators'},entry_indicators=json.dumps(t['entry_indicators'])))
if trades:
 with (P/'trade-journal.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(trades[0]));w.writeheader();w.writerows(trades)
lines=['# Nifty Renko Supertrend — thirty-session review','',f"**Decision: {decision['status']}. No live parameter change is justified by this study.**",'',f"Period: {days[0]} through {days[-1]}, 30 complete trading sessions. Development: first 20; chronological validation: final 10. All 39 variants were declared before option replay. This validation overlaps earlier research and is not pristine unseen evidence.",'', '## Configuration and execution','', 'FYERS Nifty one-minute spot candles supply signals; Dhan expired-option candles supply premium history. These are simulated FYERS trades, not historical FYERS fills. One lot of 65, starting capital INR100,000; nearest weekly ATM call on bullish entry or put on bearish entry, strike frozen until exit. Expiry dates are calendar inferred, not broker-certified. No manual overrides.', '', 'Daily arming at 09:15 IST; indicators retain preceding-session warmup. Evaluate only completed candles; execute at the next contiguous one-minute open. First completed-host evaluation: 5-minute 09:20, 1-minute 09:16. Fresh higher-timeframe confirmation delays possible entry: saved 5m/15m setup no earlier than 09:30; prior 1m/5m setup no earlier than 09:20. Mandatory square-off 15:10, no overnight positions. No automatic job/schedule or runner start was created.', '', 'Costs use the [FYERS published tariff](https://fyers.in/charges-list): INR20 per executed option order plus STT, exchange, clearing, SEBI, IPFT, stamp and GST. Base adverse slippage: 0.05% per side; stress: 0.20% per side, with full path reruns. Historical bid/ask spreads and tick execution are unavailable; actual fees and fills may differ.', '', '## Data quality','',f"Underlying: {plan['data']['duplicates']} duplicate, {plan['data']['invalid']} invalid, {plan['data']['offsession']} off-session rows excluded. Every scored spot session has 375 contiguous one-minute candles. Option history: {audit['quotes']:,} unique valid strike/time observations; {audit['conflicts']} conflicting observations removed; {audit['invalid']} invalid observations and {audit['offsession']} off-session observations excluded.",'', f"Complete scenario coverage: {len(valids)} / {len(results)} variants. A missing required contract invalidates a replay; it is never filled with a different strike or a zero-profit trade.",'', '## Development-ranked comparison','', 'Ranking uses development stress net minus half sampled drawdown. Validation is displayed only after the candidate is selected; it does not select a replacement.', '', '| Variant | Dev trades | Dev net, base INR | Dev net, stress INR | Validation trades | Validation net, base INR | Validation net, stress INR | Validation drawdown, base INR |','|---|---:|---:|---:|---:|---:|---:|---:|']
show=[]
for name in ['saved_5m_15m','prior_1m_5m','RSI_slope_only','ema_proximity_distance_0.75']:
 show.extend(r for r in results if r['name']==name and valid(r))
show += [r for r in ranked[:8] if r not in show]
for r in show:
 a=metric(r,'base','development');b=metric(r,'base','validation');s=metric(r,'stress','development');v=metric(r,'stress','validation')
 lines.append(f"| {r['name']} | {a['trades']} | {a['net']:,.2f} | {s['net']:,.2f} | {b['trades']} | {b['net']:,.2f} | {v['net']:,.2f} | {b['max_drawdown']:,.2f} |")
lines+=['',f"Development-eligible candidates: {len(eligible_rows)}. Selected: {selected['name'] if selected else 'none'}. Validation gate passed: {passed}. The gate requires at least eight development trades, positive call and put stress net, and positive stress net in both development halves; validation requires at least five trades and positive call and put stress net.",'', '## Call/put and risk detail','']
for r in show[:3]:
 lines+=['### '+r['name'],'']
 for period in ['development','validation']:
  x=metric(r,'base',period)
  lines.append(f"- {period}: calls {x['call_trades']} trades / INR{x['calls']:,.2f}; puts {x['put_trades']} trades / INR{x['puts']:,.2f}; win rate {100*x['win_rate']:.1f}%, profit factor {x['profit_factor']}, expectancy INR{x['expectancy']:,.2f}, largest win INR{x['largest_win']:,.2f}, largest loss INR{x['largest_loss']:,.2f}, worst loss streak {x['max_consecutive_losses']}, fees INR{x['fees']:,.2f}." if x['trades'] else f"- {period}: no trades; profitability cannot be assessed.")
lines+=['','## What to do before the next live run','','Do not pick the largest historical winner. If no candidate passes, retain the baseline only as a research reference and do not label any replacement ideal. Manual overrides must be assessed separately; today they bypassed the very filters being optimized. The existing sideways control is a quick-loss range lock, not a predictive entry classifier. ADX and widening/proximity changes are tests of selectivity, not guarantees against ranges. Broker quantity reconciliation is an independent operational concern.','','Thirty sessions and a maximum two trades/day cannot establish robust live profitability across regimes. These tests do not exhaust all combinations. A promising candidate requires paper forward testing and additional genuinely unseen sessions, including higher slippage and expiry-day checks.','','## Reproduction and artifacts','','Run research.py prepare, research.py run, then report.py in this folder. Retained plan.json includes all configured settings, tested changes, data audit and source hashes. comparison.csv includes all scenarios; trade-journal.csv includes fixed strikes, entry/exit times, reasons, costs and entry indicators. A no-trade cash benchmark earns INR0; the original and saved runner settings are the actionable strategy benchmarks.','','No live settings, credentials, runner activation, orders, or service state were changed.']
lines += ['', '## Full thirty-session outcomes — descriptive, not selection evidence', '', '| Configuration | Trades | Net INR | Win rate | Max sampled drawdown INR | Call net INR | Put net INR |', '|---|---:|---:|---:|---:|---:|---:|']
for r in show[:4]:
 x=r['full_period']['base']
 lines.append(f"| {r['name']} | {x['trades']} | {x['net']:,.2f} | {100*x['win_rate']:.1f}% | {x['max_drawdown']:,.2f} | {x['calls']:,.2f} | {x['puts']:,.2f} |")
lead=next(r for r in results if r['name']=='RSI_slope_only');tr=lead['scenarios']['base']['development']['trades']+lead['scenarios']['base']['validation']['trades'];values=sorted([t['net'] for t in tr],reverse=True)
lines += ['', f"Exploratory RSI-slope-only variant: remove the host RSI level band, retain RSI14 slope and every other saved baseline setting. Removing its three largest winners changes full-period net to INR{sum(values[3:]):,.2f}. Its call side is negative across the full sample. This is not sufficient evidence for a combined call/put live setting.", '', 'The ADX20/25 variants and quick-loss-window changes did not improve the baseline trade path in this sample. More enabled filters do not automatically remove range losses.', '', '## Saved baseline settings', '', '| Setting | Value |', '|---|---|']
base=json.loads((P/'saved-config.json').read_text())
for key in ['timeframe','supertrend_timeframe','brick_mode','manual_brick','atr_length','factor','ema_fast_length','ema_slow_length','widening_window','ema_proximity_mode','ema_proximity_distance','rsi_slope_length','rsi_bullish_min','rsi_bullish_max','rsi_bearish_min','rsi_bearish_max','retest_enabled','use_adx','adx_threshold','ema_exit_length','sideways_enabled','sideways_max_candles','trailing_enabled','max_trades','lots','rsi_htf_1_enabled','rsi_htf_2_enabled','rsi_htf_3_enabled']:
 lines.append(f"| {key} | {base.get(key)} |")
lines += ['', '## Next trading session', '', 'Tuesday 20 October is an NSE F&O trading holiday for Dussehra. The next normal session is Wednesday 21 October. Source: [NSE 2026 F&O holiday circular](https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf). No schedule has been created.', '', 'A saved-config.json snapshot preserves every configured field. An isolated plotting environment is used only for this research. QuantStats is unavailable; annualized performance ratios and risk-of-ruin forecasts are omitted because this short option sample would not establish them.']

(P/'report.md').write_text('\n'.join(lines))
(P/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Nifty thirty-session review</title><style>body{font:15px system-ui;max-width:1150px;margin:32px auto;background:#f8fafc;color:#172536}pre{white-space:pre-wrap;line-height:1.6}</style><pre>'+html.escape('\n'.join(lines))+'</pre>')
print(json.dumps({'decision':decision,'valid_variants':len(valids),'top':[{k:r[k] for k in ['name','changes']}|{'dev':metric(r,'base','development'),'validation':metric(r,'base','validation'),'stress_validation':metric(r,'stress','validation')} for r in show[:3]]},indent=2))

