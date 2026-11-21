from pathlib import Path
import json
p=Path(__file__).parent;r=json.loads((p/'results.json').read_text())
lines=['# Renko Supertrend sideways review','',
'The first one-year review does not support activating a Supertrend-only sideways filter. No candidate passed the declared validation rule. Several filters look better in the final quarter but worse in the preceding validation quarter. Choosing one after seeing the final quarter would overfit.','',
'**Data:** FYERS NIFTY 50 five-minute archive; 25 October 2025–23 October 2026, 245 regular weekday sessions. September 2025 supplies warm-up. Existing raw data preserved.','',
'**Chart configuration:** current saved FYERS NIFTY chart, manual brick 27.71 points, Supertrend ATR 5/factor 3, completed five-minute host candles. Existing engine also adjusts its effective factor by volatility regime. Its synthetic Renko state updates once per host candle; this is not a tick-by-tick brick reconstruction.','',
'**Candidate logic:** classify as trending only if the Supertrend stays in one direction over the preceding 6 or 12 completed host bars, advances at least twice, moves 0.25/0.5/1 brick in that direction, and has been flat for no more than 3 bars. A stricter variant requires 3 advances and at most 2 flat bars. Session-crossing lookbacks are withheld. Otherwise classify as flat/transition/warm-up.','',
'**Method:** review existing engine entry onsets; enter at the next real bar open, measure direction-adjusted underlying movement 30 minutes later. No same-close execution or future data enters the filter. Development ends 24 April; validation runs 25 April–24 July; final holdout runs 25 July–23 October. A candidate must have at least 30 validation samples, improve average movement and reduce subsequent Supertrend flips versus baseline. None passed.','',
'| Filter | Validation signals | Positive moves | Mean points | Holdout signals | Positive moves | Mean points |',
'|---|---:|---:|---:|---:|---:|---:|']
for name,s in r['results'].items():
 a,b=s['validation'],s['holdout']
 lines.append(f"| {name} | {a['samples']} | {a['positive_pct']:.2f}% | {a['mean_points']:.2f} | {b['samples']} | {b['positive_pct']:.2f}% | {b['mean_points']:.2f} |")
lines += ['', '**Interpretation:** a flat trailing line alone is not proof of sideways price. The current large manual brick also produces very few Supertrend flips even without a filter, making flip suppression a weak standalone objective. Late confirmation can discard early trend opportunities.','',
'**Practical next criterion to investigate:** combine Supertrend persistence with a completed-price efficiency measure or range expansion, then require consistent validation across different periods and sensible brick-size sensitivity. Treat current thresholds as research candidates, not live settings. No claim of eliminating every sideways market or increasing winning streaks is supported by this review.','',
'**Limits:** this is index signal quality, not option strategy P&L. Overlapping signals are not independent executed trades. Current manual brick was calibrated recently and applied retrospectively; it was not historically available throughout the year. External runner guards, live lifecycle, trade caps, historical option premiums, broker fills, spreads, premium decay, and exact historical costs are not simulated. The 2-point drag field is a sensitivity illustration only. No return, Sharpe, drawdown, or option profitability is claimed. Full holiday/special-session certification remains unavailable.','',
'Files: review.py (reproducible study), results.json, signal_features.csv. Live runners and trading settings were not changed.']
(p/'README.md').write_text('\n'.join(lines)+'\n')
print('Research report and comparison saved.')
