# Renko Supertrend line slope only

This study isolates the plotted Supertrend line slope. ATR expansion, ADX and RSI are not added as regime gates. Existing strategy signals remain the baseline population.

Normalized slope = (current Supertrend - Supertrend N completed host bars ago) / (N × current brick size). Positive slope supports bullish direction; negative supports bearish direction. Flat or weak slope withholds a fresh entry. A band-direction change within the lookback is withheld: its line jump is not counted as a trend slope. All lookback bars must be from the same session.

The study tests 6 and 12 completed five-minute host bars, with directional thresholds of 0.02, 0.05 or 0.10 brick per bar. This is host-time slope on the actual chart engine, not a per-brick or screen-angle measure.

| Filter | Full-year signal PF | Middle quarter PF | Latest quarter PF | Full-year signals |
|---|---:|---:|---:|---:|
| Baseline | 1.06 | 0.99 | 0.90 | 1978 |
| Slope6_0.02 | 1.01 | 0.70 | 1.15 | 722 |
| Slope6_0.05 | 1.00 | 0.72 | 1.17 | 676 |
| Slope6_0.1 | 1.17 | 0.77 | 1.50 | 510 |
| Slope12_0.02 | 1.01 | 0.65 | 1.22 | 799 |
| Slope12_0.05 | 1.01 | 0.61 | 1.35 | 609 |
| Slope12_0.1 | 1.08 | 0.65 | 1.38 | 375 |

The six-bar 0.10 rule raises the full-year index signal PF from 1.06 to 1.17 and latest-quarter PF from 0.90 to 1.50, but lowers the middle-quarter PF from 0.99 to 0.77. At a 27.71-point brick, that threshold corresponds to 16.63 points of Supertrend advance across six completed five-minute bars. It is a tested candidate, not a recommended live threshold.

Limits: retrospective current manual brick, overlapping next-open 30-minute underlying signals before actual costs, already-inspected historical periods, no complete runner lifecycle or option P&L. This is not evidence of improved trade profit factor or winning streaks. No new Live gate or chart label was activated.
