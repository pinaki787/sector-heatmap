# Quick-loss filter assessment — 9 October 2026

This is a fresh review of archived SENSEX research, not a new crude-oil backtest. It cannot establish profitability for the current MCX EMA30 configuration.

Comparison uses completed underlying OHLC, next-open fills, a three-candle quick-loss window, EMA10/reversal exits and a legacy NSE cutoff. Exposure ranges use whole-bar extremes rather than actual post-fill ticks. Costs below are two basis points per side of underlying notional: a sensitivity proxy, not actual option fees or spreads. Historical comparison sessions were already inspected; they are not untouched validation.

| Timeframe | Policy | Comparison trades | Net underlying points | Maximum drawdown points | Development net points |
|---|---|---:|---:|---:|---:|
| one-minute | Filter off | 121 | -1702.26 | 2034.50 | -19932.74 |
| one-minute | Current filter on | 118 | -1724.91 | 2093.19 | -18716.14 |
| one-minute | Experimental directional lock | 33 | -8.37 | 524.92 | -7303.85 |
| five-minute | Filter off | 24 | 187.19 | 611.50 | -4566.85 |
| five-minute | Current filter on | 23 | 225.52 | 573.17 | -4180.41 |
| five-minute | Experimental directional lock | 15 | 174.60 | 685.96 | -2805.92 |

## Conclusion

The current filter reduced trade counts but did not consistently improve net results. One-minute comparison net and drawdown worsened slightly; five-minute comparison improved slightly. All development results remained negative at this modeled cost. This does not support describing the flag as a profitability fix.

The experimental directional lock reduced one-minute churn and drawdown substantially, but comparison net remained negative and five-minute drawdown worsened. It remains a research candidate.

A valid current-MCX assessment requires mapping the historical source to the exact contract, freezing the active strategy settings and session cutoff, using EMA30 exits and actual order limits, and adding executable option bid/ask and fees. Unlabelled chart caches cannot safely be assumed to belong to crude oil. No Live configuration, runner, position or order was changed.
