import csv,json
from pathlib import Path
p=Path(__file__).parent
r=json.loads((p/'primary-results.json').read_text());rob=json.loads((p/'robustness-results.json').read_text())
selection=json.loads((p/'selection.json').read_text());rec=json.loads((p/'recommendation.json').read_text())
uncertainty=json.loads((p/'uncertainty-adx.json').read_text())
names=['Baseline','adx_60','efficiency_36','choppiness_50','ema_slope_86']
lines=['# Two-year Renko sideways calibration','',
'## Recommendation','',
'Freeze **rising ADX plus adequate volatility** as the primary paper-comparison profile. Keep the directional-efficiency winner as a challenger and the existing configuration as baseline. These are offline research profiles; no Live or hosted Paper runner was started or changed.','',
'The primary profile adds an entry-only gate to an otherwise qualifying directional setup:','',
'1. Use completed five-minute host candles and the existing chart engine.',
'2. ADX14 must be at least **15**.',
'3. ADX14 must exceed its value **three completed candles earlier**.',
'4. ATR5 must be at least **80%** of its preceding **60-value upper median** (the 31st sorted observation of 60).',
'5. Require valid warm-up, same-session ADX lookback and contiguous completed bars.',
'6. Keep existing exit management. A failed gate blocks a fresh entry; it is not an instruction to close an existing position.','',
'ADX gauges strength, not bullish/bearish direction; the existing entry setup continues to supply direction. The volatility floor withholds unusually quiet conditions. Rejected conditions are ineligible regimes, not proof that every rejected interval is sideways.','',
'## What was tested','',
'The primary pass compared **166 declared variants**, including baseline and six matched opening-delay controls. Families: directional efficiency, choppiness, ADX level/rising strength, EMA30 slope, Supertrend slope, range breakout, candle overlap, ATR regimes, efficiency/choppiness combinations, prolonged flatness and RSI strength.','',
'It was followed by **37 robustness replays** of the first-year shortlist: neighboring 20/35-point bricks, effectively uncapped entries, quick-loss recovery proxy on/off, plus an audit of the earlier proposed efficiency/volatility reference. This is a broad bounded calibration, not an exhaustive search of every imaginable strategy.','',
'Each trial replays the sequential underlying-price lifecycle from archived FYERS NIFTY OHLC. Decisions use completed information; ordinary modeled entries/exits use subsequent real candle opens. A position closes at the 15:10 session bar open; there is no same-close entry or entry at cutoff. One modeled position is held at a time. The original engine, selected EMA proximity checks, Supertrend/EMA30 exit logic and research re-arming behavior are retained.','',
'## Current-brick results','',
'At brick 27.71, two modeled entries per day, and hypothetical two-point total friction per completed underlying trade:','',
'| Profile | Earlier-year PF | Latest-year PF | Two-year PF | Two-year trades | Two-year realized DD | Longest loss streak |','|---|---:|---:|---:|---:|---:|---:|']
for name in names:
 x=r[name];a=x['splits']['earlier']['2'];b=x['splits']['latest']['2'];s=x['splits']['all']['2']
 label={'Baseline':'Existing baseline','adx_60':'Rising ADX + volatility','efficiency_36':'Efficiency challenger','choppiness_50':'Low choppiness + volatility','ema_slope_86':'EMA30 slope + volatility'}[name]
 lines.append(f"| {label} | {a['profit_factor']:.2f} | {b['profit_factor']:.2f} | {s['profit_factor']:.2f} | {s['trades']} | {s['realized_drawdown_points']:.2f} | {s['max_loss_streak']} |")
base=r['Baseline']['splits']['all']['2'];a=r['adx_60']['splits']['all']['2']
lines += ['',f"The primary paper profile reduces modeled trades from {base['trades']} to {a['trades']}; positive-trade frequency rises from {base['positive_pct']:.2f}% to {a['positive_pct']:.2f}%. Realized drawdown falls from {base['realized_drawdown_points']:.2f} to {a['realized_drawdown_points']:.2f} index points. Losses still occur frequently; a long winning streak is not guaranteed.",'',
'## Why this recommendation differs from the mechanical winner','',
'The saved first-year ranking selected an **18-bar efficiency >=0.15, ATR ratio >=1.00** profile. Ranking required at least 80 first-year trades, eight trades in each quarter, PF >=1.05 and drawdown <=90% of baseline; then prioritized positive quarters, worst-quarter PF, overall PF and lower drawdown, with family diversity. The latest year was not used to order that shortlist.','',
'That efficiency profile passed the declared cross-year/brick/friction checks, but nearby efficiency thresholds damaged the earlier year. The recommended rising-ADX profile was already in the frozen shortlist and has a broader positive neighboring-threshold region. Selecting it as primary paper profile is a disclosed qualitative judgment after calibration, not the outcome of the original mechanical ranking and not an independent statistical confirmation.','',
'Neighboring rising-ADX thresholds, with the same three-bar rise and ATR floor:','',
'| ADX minimum | Earlier PF | Latest PF |','|---|---:|---:|']
for x in sorted((x for x in r.values() if x['rule']['family']=='adx' and x['rule']['rising'] and x['rule']['floor']==.8),key=lambda x:x['rule']['threshold']):
 lines.append(f"| {x['rule']['threshold']} | {x['splits']['earlier']['2']['profit_factor']:.2f} | {x['splits']['latest']['2']['profit_factor']:.2f} |")
lines+=['','The three-bar opening-delay control alone gives PF 1.04/1.06, versus the ADX profile 1.21/1.26. This suggests its improvement is not explained entirely by withholding the first few candles.','',
'## Robustness and costs','',
'| ADX profile / brick | Earlier PF, 2-point drag | Latest PF, 2-point drag | Earlier PF, 4-point drag | Latest PF, 4-point drag |','|---|---:|---:|---:|---:|']
for brick in (20.,27.71,35.):
 x=r['adx_60'] if brick==27.71 else rob[f'adx_60_brick{brick}_cap2_lockFalse']
 lines.append(f"| {brick:.2f} | {x['splits']['earlier']['2']['profit_factor']:.2f} | {x['splits']['latest']['2']['profit_factor']:.2f} | {x['splits']['earlier']['4']['profit_factor']:.2f} | {x['splits']['latest']['4']['profit_factor']:.2f} |")
lines += ['','Effectively uncapped entries at brick 27.71 give primary-profile PF 1.28/1.27. The completed-OHLC quick-loss recovery proxy produces approximately 1.21/1.26. Neither test proves parity with actual option net-loss recovery, runtime quotas or tick exposure ranges.','',
'## Uncertainty','',
'Paired five-observed-session block resampling, 3,000 replications, gives the following descriptive interval for candidate-minus-baseline profit factor:','',
'| Period | 95% interval |','|---|---:|']
for phase,label in [('earlier','Earlier year'),('latest','Latest year'),('all','Combined')]:
 lo,hi=uncertainty['results'][phase]['candidate_minus_baseline_pf_interval95']
 lines.append(f"| {label} | {lo:.2f} to {hi:.2f} |")
lines+=['','The earlier-year interval includes no improvement. The combined/latest intervals are positive in this resampling exercise, but adaptive exploration, multiple comparisons and previously inspected data are not corrected. These are not confidence guarantees about future option returns.','',
'## Data and practical limits','',
'Archive window: 25 October 2024–23 October 2026. Regular weekday observations only; special sessions excluded and full holiday certification unavailable. The first five observed sessions are excluded from scoring for initialization; scoring begins **4 November 2024**. That explains the small change in earlier-year baseline versus earlier reports that included those sessions.','',
'Results are **underlying-index lifecycle proxies**, not rupee P&L, actual NIFTY cash trades, option profits or broker fills. Real historical option premiums, IV/decay, spreads, contract costs, money sizing, funds and exact account risk controls are not available in this replay. The 0/2/4-point friction assumptions are stress cases, not historical fee estimates.','',
'The two-entry limit is per observed trading day for this research; actual runtime per-run quota semantics are not established. Warm-up, re-arming and external tick/higher-timeframe gates mean full runner/chart/execution parity is not claimed. Realized drawdown uses closed-trade marks, not maximum intratrade drawdown.','',
'Fixed current/neighboring manual bricks are retrospective research parameters. Both years had already been inspected during prior studies, so no fresh untouched holdout remains. No calibration can guarantee removing every sideways market.','',
'## Suggested next step','',
'Keep the primary profile and challenger **frozen** for a controlled comparison on new paper observations, with real option quotes and simulated execution costs recorded. Log every allowed/blocked entry, rejection reason, entry/exit contract, spread, costs, P&L and exposure. Review after a predeclared evaluation window such as 50 completed paper trades; that is an evaluation checkpoint, not automatic permission to go Live. Do not keep adjusting thresholds after each small sample.','',
'The isolated assessment modules are prepared and tested. They are not integrated into the hosted runner or chart. A hosted implementation should expose an optional entry gate and clear reasons, preserve existing saved choices, and default to off until explicitly activated.','',
'## Reproduction and evidence','',
'Source: grid.py, run.py, robustness.py, select.py, uncertainty.py, candidate.py, adx_candidate.py and tests. Persistent evidence: specification.json, primary-results.json, trials/, training-shortlist.json, selection.json, recommendation.json, robustness-results.json, uncertainty-adx.json and audit.json. Job status/heartbeat: job.json. A CANCEL file stops active replays at their next checkpoint.','',
'All research ran on the authoritative Ubuntu checkout. No production service restart, broker rebind, runner start or order submission was performed for this calibration.']
(p/'README.md').write_text('\n'.join(lines)+'\n')
with (p/'leaderboard.csv').open('w') as f:
 cols=['name','family','parameters','earlier_pf','latest_pf','all_pf','trades','realized_drawdown','net_points']
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
 for name,x in r.items():
  s=x['splits']['all']['2']
  w.writerow(dict(name=name,family=x['rule']['family'],parameters=json.dumps(x['rule']),earlier_pf=x['splits']['earlier']['2']['profit_factor'],
   latest_pf=x['splits']['latest']['2']['profit_factor'],all_pf=s['profit_factor'],trades=s['trades'],realized_drawdown=s['realized_drawdown_points'],net_points=s['net_points']))
print('Calibration report and full leaderboard saved.')
