import json
from pathlib import Path
p=Path(__file__).parent;r=json.loads((p/'results.json').read_text());rob=json.loads((p/'robustness.json').read_text())
lines=['# Two-year Renko sideways-market research','',
'**Finding:** directional price efficiency plus a minimum-volatility condition is a credible candidate for controlled paper comparison. It is not a proven Live improvement and does not eliminate every sideways market. The earlier slope-only conclusions were based on fixed 30-minute signal outcomes; this follow-up uses sequential entry/exit lifecycle proxies. These metrics are different and must not be compared as if they were the same backtest.','',
'## Candidate rule','',
'Keep the existing directional entry setup. Permit a new entry only when:','',
'1. The latest 12 completed five-minute close changes show directional efficiency of at least 0.25. Efficiency is net movement in the proposed direction divided by the sum of all absolute close changes.',
'2. Completed ATR5 is at least 80% of the median of its preceding 60 values.',
'3. The 12-bar price window is within the same session and enough ATR history exists.','',
'Example: 30 points of progress with 100 points of total back-and-forth movement gives 0.30 and passes. Only 10 points of progress gives 0.10 and fails. The ATR rule withholds unusually quiet periods rather than assuming every rise in volatility means a trend.','',
'## Current-brick comparison','',
'Manual brick 27.71; two entries per day; hypothetical total 2-point friction per completed underlying trade; quick-loss lock off for both rows. All figures are index points, not rupees or option profits.','',
'| Year / rule | Trades | PF | Positive trades | Net points | Realized drawdown points | Longest losing streak |','|---|---:|---:|---:|---:|---:|---:|']
for phase,label in [('earlier','2024-10-25–2025-10-24'),('latest','2025-10-25–2026-10-23')]:
 for rule in ('Baseline','Efficiency_ATR'):
  s=r['results']['27.71_'+rule]['splits'][phase]['2']
  lines.append(f"| {label} / {rule} | {s['trades']} | {s['profit_factor']:.2f} | {s['positive_pct']:.2f}% | {s['net_points']:.2f} | {s['realized_drawdown_points']:.2f} | {s['max_loss_streak']} |")
lines+=['','The candidate gives up some earlier-year total profit while reducing trade count and realized drawdown. The latest year changes from a losing to a positive underlying proxy under this friction assumption. This is a tradeoff, not universal dominance.','',
'## Robustness checks','',
'- 21 broad comparisons: baseline plus six consolidation/efficiency/breakout/overlap rules at brick sizes 20, 27.71 and 35.',
'- 24 additional replay runs: baseline versus candidate, three brick sizes, two-entry cap versus effectively uncapped, and quick-loss recovery proxy off/on. Some runs duplicate broad-scan scenarios as consistency checks.',
'- At the two-entry cap, candidate PF exceeds baseline in both years at all three brick sizes using the 2-point drag. The latest-year candidate PF ranges from 1.02 to 1.12: the advantage is thin at brick 35.',
'- At brick 27.71 and 4-point drag, candidate PF is 1.04 earlier and 1.03 latest. The small remaining margin warns that real trading costs could remove it.',
'- With effectively uncapped entries at brick 27.71, the earlier-year baseline PF is 1.20 versus candidate 1.13; the latest-year baseline is 0.92 versus candidate 1.12. The candidate does not dominate every operating assumption.',
'- Completed-OHLC quick-loss recovery does not materially change the candidate at the current brick. It is not the broker/tick/actual-option-loss recovery implementation.',
'- Cross-timeframe check: all 1,849 distinct selected entry/exit observations were present in the one-minute archive and matched its candle opens exactly. This verifies archive consistency, not executable fills.',
'- Ten focused tests cover next-open entry/exit, gaps, cutoff, caps, costs, warm-up and directional symmetry.','',
'## Method and limits','',
'Data: archived FYERS NIFTY 50 regular weekday five-minute OHLC, 25 October 2024–23 October 2026, with one-minute opens used for consistency checks. Special sessions excluded; full holiday-calendar certification unavailable. No missing prices fabricated.','',
'Each scenario runs the existing sequential Renko/Supertrend engine. Qualified entries use the next contiguous bar open, subject to the existing EMA proximity check and the scenario filter. Selected Supertrend/EMA30 exits use next-bar opens. Positions close at the 15:10 session bar open. One position is held at a time; no entry at the cutoff. Research re-arms the engine after modeled exits.','',
'The two-entry-per-day cap is an explicit research assumption; it is not a claim about saved runtime per-run quotas. Full runner parity is not established. Internal chart projection state remains part of the shared engine. Tick-driven external gates, exact higher-timeframe overlays, actual position ownership/funds/daily-loss controls, true broker fills and option P&L are not simulated. No hard boundaries or trailing exits were added.','',
'Manual bricks are fixed retrospective research parameters, not historically pre-calibrated sizes. Data had already been inspected in earlier studies, so neither year is a fresh untouched holdout. These are exploratory comparisons with multiple tested candidates, not statistical proof.','',
'The friction values 0/2/4 index points per completed trade are sensitivities only. They are not historical brokerage/STT/slippage estimates or option spreads. Realized drawdown is measured on closed trades, not intratrade mark-to-market. Completed-OHLC recovery freezes the modeled exposure range after a quick loss and releases on a later completed close outside that range; actual tick-path and option-net-loss recovery can differ.','',
'**Recommendation:** freeze the efficiency-plus-volatility rule and compare it against unchanged baseline in controlled paper evaluation before any Live decision. Use real option pricing/execution evidence to assess money performance. No Live runner, allocation, broker connection or order was changed by this research.','',
'## Reproduction','',
'Source: review.py, robustness.py and test_review.py. Evidence: specification.json, results.json, robustness.json, open_consistency.json and job.json. Create a CANCEL file in this folder to stop a running replay at its next checkpoint.']
(p/'README.md').write_text('\n'.join(lines)+'\n')
print('Report saved.')
