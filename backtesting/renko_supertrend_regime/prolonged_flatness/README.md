# Prolonged Supertrend flatness test

Six research variants were tested: block a Supertrend line flat for 3, 6, 9 or 12 completed five-minute bars; and permit a direction-matching completed-close range breakout to override the 6- or 12-bar flatness block. Flat means the same Supertrend band stayed within half a 0.05-point tick across the entire window. No ATR/RSI/ADX regime gate was added.

| Rule | Full-year signal PF | Middle quarter PF | Latest quarter PF | Matched-window baseline PF | Signals retained |
|---|---:|---:|---:|---:|---:|
| Baseline | 1.06 | 0.99 | 0.90 | 1.06 | 1978 |
| Flat3 | 1.00 | 0.86 | 1.24 | 1.05 | 795 |
| Flat6 | 1.01 | 0.77 | 1.14 | 1.05 | 945 |
| Flat9 | 1.02 | 0.83 | 1.08 | 1.06 | 1017 |
| Flat12 | 1.00 | 0.79 | 1.08 | 1.05 | 1065 |
| Flat6_breakout | 1.05 | 0.85 | 1.09 | 1.05 | 1141 |
| Flat12_breakout | 1.00 | 0.76 | 1.07 | 1.05 | 1134 |

Matched-window control removes warm-up and session-crossing signals from the baseline comparison for each rule. Baseline is otherwise the same saved engine entry population.

Conclusion: no candidate improves full-year PF over the unfiltered 1.06 baseline. This does not establish that flatness blocks improve complete strategy performance or winning streaks.

Limits: same retrospectively applied current brick; overlapping next-open 30-minute NIFTY index movements before trading costs; historical periods already inspected; no complete runner lifecycle, actual options, costs or fill simulation. No Live changes were made.
