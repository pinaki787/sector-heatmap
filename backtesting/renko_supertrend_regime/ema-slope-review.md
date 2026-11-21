# EMA slope and volatility review

Completed historical research on both NIFTY archive years. Six additional EMA/volatility rules were tested using the saved chart engine. No runtime settings were changed.

EMA slopes are measured from completed five-minute host candles and normalized by current ATR5. Direction must agree with Supertrend. The three-bar EMA10 threshold is 0.05 ATR per bar; EMA30 is 0.02 ATR per bar. Six-bar EMA30 uses the same 0.02 threshold. Combined EMA mode requires both three-bar thresholds. The volatility variant additionally requires ATR5 to be 0.80–1.50 times the mean of its previous 20 observations. The efficiency variant requires direction-adjusted 12-bar close progress / total close movement >=0.30.

| Rule | Earlier-year signal PF | Latest-year signal PF | Earlier samples | Latest samples |
|---|---:|---:|---:|---:|
| Baseline | 1.14 | 1.06 | 2009 | 1978 |
| EMA10_3 | 1.11 | 1.04 | 1445 | 1438 |
| EMA30_3 | 1.09 | 1.02 | 1746 | 1741 |
| EMA30_6 | 1.11 | 1.06 | 1623 | 1598 |
| Both_EMAs | 1.11 | 1.04 | 1442 | 1438 |
| Both_ATR_stable | 1.15 | 1.06 | 1047 | 1089 |
| Both_efficiency | 1.07 | 1.04 | 744 | 682 |

**Finding:** simple EMA slopes do not outperform baseline consistently. EMA slope plus a bounded volatility regime is approximately flat against baseline: 1.15 versus 1.14 in the earlier year; both round to 1.06 in the latest year. This small historical difference is not evidence of a useful improvement. Latest-year positive-move frequency falls from 50.96% baseline to 49.49% with that volatility gate.

**Why another slope can be redundant:** existing entries already depend on EMA alignment, widening and RSI slope. Additional slope gates often remove signals without isolating a reliably better subset. This is an explanation consistent with the configuration, not a proven causal attribution.

**Practical conclusion:** do not add another live entry gate on this evidence. First evaluate the complete trade lifecycle and identify whether losses cluster by entry timing, holding/exit behavior, brick calibration, volatility regime or option costs. A 30-minute signal study cannot decide those questions.

**Limits:** hypothetical overlapping 30-minute underlying-index signals at next real bar opens, before actual costs; current 27.71-point manual brick applied retrospectively; historical periods have already been inspected and are exploratory; full runner guards, position lifecycle, max trades, real option premiums, fills, spread and decay are not simulated. Approximate PF ties may conceal small unrounded differences. No improvement in trade profit factor or winning streaks is established.

Seven boundary tests passed for directional symmetry, flat/opposing slopes, volatility limits and warm-up.
