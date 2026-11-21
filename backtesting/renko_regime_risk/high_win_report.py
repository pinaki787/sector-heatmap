import json,csv
from pathlib import Path
p=Path(__file__).parent;r=json.loads((p/'high-win-results.json').read_text());selection=json.loads((p/'high-win-selection.json').read_text())
names=['adx_60_HighWin_stop3.0_target0.25','overlap_130_HighWin_stop3.0_target0.75']
lines=['# Joint high-win-rate calibration: requested outcome not achieved','',
'**Conclusion: no tested strategy met the joint acceptance targets. No candidate from this research is approved as a solution to the requested high win rate, negligible losing streaks, good profit factor and low drawdown.**','',
'The earlier 36%-win-rate risk candidate did not meet that objective. Calling its drawdown improvement a completed solution would be wrong.','',
'## The additional test','',
'80 combinations crossed four entry profiles with 20 fixed ATR stop/target pairs: stops of 1/1.5/2/3 ATR and targets of 0.25/0.50/0.75/1/1.5 ATR. Existing selected exits remain active. All entries use already completed information. Stops and profit levels are tick-aligned; if both touch inside one minute, the replay uses the adverse stop-first order.','',
'Working acceptance targets, chosen for this calibration rather than supplied as exact numbers by the user:','',
'- At least 65% positive trades in each year.',
'- Profit factor at least 1.30 in each year under two-point friction.',
'- At most three consecutive losses or non-positive trades across the complete record.',
'- At least 50% lower realized and minute-close drawdown in each year.',
'- At least 60 completed trades in each year, and positive net result under four-point friction.','',
f'**Passing combinations: {len(selection["eligible"])} of {len(r)}.**','',
'## What the high win rates concealed','',
'| Example | Earlier win rate | Latest win rate | Earlier PF, 2-point drag | Latest PF, 2-point drag | Earlier PF, 4-point drag | Latest PF, 4-point drag | Longest loss streak |',
'|---|---:|---:|---:|---:|---:|---:|---:|']
for name in names:
 x=r[name];a=x['splits']['earlier'];b=x['splits']['latest'];s=x['splits']['all']['2']
 label='Very small target / wide stop' if name==names[0] else 'Best worst-year PF among >=65% wins'
 lines.append(f"| {label} | {a['2']['positive_pct']:.2f}% | {b['2']['positive_pct']:.2f}% | {a['2']['profit_factor']:.2f} | {b['2']['profit_factor']:.2f} | {a['4']['profit_factor']:.2f} | {b['4']['profit_factor']:.2f} | {s['max_loss_streak']} |")
lines+=['','A high hit rate can be created by taking small profits while allowing larger losses. It does not establish a profitable strategy. The approximately 72%-win case produced two-year PF 1.14 at two-point friction, but 0.94 at four-point friction; it also had a five-loss streak. The higher-hit-rate example had PF below one even at the lower friction.','',
'## What is established','',
'The research found improvements to particular objectives, such as drawdown reduction or historical hit rate. It did not establish a parameter set that reliably achieves all requested objectives together. I do not recommend activating these changes in Live or presenting a selected historical peak as a robust strategy.','',
'The saved risk-first recommendation remains an experimental tradeoff, not a qualifying high-win strategy. The complete leaderboards and rejected cases are retained so the result is reviewable. Further tuning on the same already-inspected data cannot by itself provide independent evidence that a new peak generalizes.','',
'## Limits','',
'All figures are underlying NIFTY price-model results, not actual option trades, rupee returns or verified fills. Friction values are sensitivities, not measured broker/option costs. Stop touches assume execution without liquidity/latency evidence. Both archive years were already explored; no fresh untouched holdout remains. Complete aligned sessions were used, with short/special observations excluded and the first five sessions reserved for initialization.','',
'Raw evidence: high-win-specification.json, high-win-results.json, high-win-selection.json and per-trial records. Source: high_win.py and model.py. Four additional target/ordering tests passed, bringing the focused research test total to 57. No live parameters, runners or orders were changed.']
(p/'HIGH_WIN_RESULT.md').write_text('\n'.join(lines)+'\n')
with (p/'high-win-leaderboard.csv').open('w') as f:
 cols=['scenario','earlier_win_pct','latest_win_pct','earlier_pf','latest_pf','all_pf','max_loss_streak','max_nonpositive_streak','earlier_pf_4pt','latest_pf_4pt']
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
 for name,x in r.items():
  a=x['splits']['earlier'];b=x['splits']['latest'];s=x['splits']['all']['2']
  w.writerow(dict(scenario=name,earlier_win_pct=a['2']['positive_pct'],latest_win_pct=b['2']['positive_pct'],earlier_pf=a['2']['profit_factor'],latest_pf=b['2']['profit_factor'],
   all_pf=s['profit_factor'],max_loss_streak=s['max_loss_streak'],max_nonpositive_streak=s['max_nonpositive_streak'],earlier_pf_4pt=a['4']['profit_factor'],latest_pf_4pt=b['4']['profit_factor']))
# Make the current limitation prominent in the older risk-first report.
old=p/'README.md';text=old.read_text()
notice='> Subsequent high-win-rate testing did not meet the full joint objective. The risk-first profile below is an experimental tradeoff, not a completed solution. See HIGH_WIN_RESULT.md.\n\n'
if notice not in text:old.write_text(notice+text)
print('Joint-goal failure report and all 80 cases saved.')
