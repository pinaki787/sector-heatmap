# NIFTY sideways-entry assessment

Underlying directional research proxy, NOT option execution or option net profitability.

Completed native host candles; own Engine indicator formulas; next contiguous open fills; exits preserved; no intrabar paths; same-bar reentry forbidden. Re-arm after exit mirrors qualified subsequent candle. Final period forces close. Operational max_trades is per runner lifetime and intentionally omitted: continuous signal research, not production lifecycle replay. No option preflight, spread, quote, expiry, funds or fill model.

0,2,5 basis points per side are sensitivity assumptions on underlying, NOT broker option charges.

| Period | Filter | Trades | Gross points | Net at 2bp/side | Max drawdown points | Avoided baseline losses | Missed baseline winners |
|---|---|---:|---:|---:|---:|---:|---:|
| DEVELOPMENT 2026-08-27 to 2026-09-09 | BASELINE | 32 | 102.55 | -203.726 | 366.195 | 0 | 0 |
| DEVELOPMENT 2026-08-27 to 2026-09-09 | CHOP55 | 28 | 102.25 | -165.857 | 340.333 | 5 | 1 |
| DEVELOPMENT 2026-08-27 to 2026-09-09 | CHOP61.8 | 31 | 103.8 | -192.897 | 355.365 | 1 | 1 |
| DEVELOPMENT 2026-08-27 to 2026-09-09 | ADX20 | 25 | 5.15 | -234.014 | 326.595 | 9 | 6 |
| DEVELOPMENT 2026-08-27 to 2026-09-09 | ADX25 | 21 | -131.4 | -332.266 | 383.048 | 15 | 9 |
| DEVELOPMENT 2026-08-27 to 2026-09-09 | REVERSALS_LOW_PROGRESS | 32 | 102.55 | -203.726 | 366.195 | 0 | 0 |
| VALIDATION 2026-09-10 to 2026-09-24 | BASELINE | 34 | -55.5 | -372.931 | 558.949 | 0 | 0 |
| VALIDATION 2026-09-10 to 2026-09-24 | CHOP55 | 31 | -87.7 | -377.236 | 563.253 | 6 | 2 |
| VALIDATION 2026-09-10 to 2026-09-24 | CHOP61.8 | 32 | -35.05 | -333.868 | 519.885 | 2 | 0 |
| VALIDATION 2026-09-10 to 2026-09-24 | ADX20 | 21 | -128.95 | -325.175 | 511.193 | 14 | 6 |
| VALIDATION 2026-09-10 to 2026-09-24 | ADX25 | 16 | -178.9 | -328.444 | 493.507 | 21 | 8 |
| VALIDATION 2026-09-10 to 2026-09-24 | REVERSALS_LOW_PROGRESS | 34 | -55.5 | -372.931 | 558.949 | 0 | 0 |
| HOLDOUT 2026-09-25 to 2026-10-09 | BASELINE | 25 | 666.25 | 438.958 | 243.093 | 0 | 0 |
| HOLDOUT 2026-09-25 to 2026-10-09 | CHOP55 | 25 | 550.35 | 323.073 | 287.865 | 2 | 3 |
| HOLDOUT 2026-09-25 to 2026-10-09 | CHOP61.8 | 25 | 624.6 | 397.316 | 243.093 | 0 | 2 |
| HOLDOUT 2026-09-25 to 2026-10-09 | ADX20 | 22 | 371.6 | 171.858 | 341.451 | 5 | 5 |
| HOLDOUT 2026-09-25 to 2026-10-09 | ADX25 | 18 | 331.05 | 167.556 | 310.282 | 8 | 8 |
| HOLDOUT 2026-09-25 to 2026-10-09 | REVERSALS_LOW_PROGRESS | 24 | 686.85 | 468.794 | 243.093 | 1 | 0 |

The final third is chronological holdout. Thresholds were fixed before running; no search or threshold selection used. Earlier user research has seen some of these dates: this is a withheld split for this experiment, not globally unseen market data. No executable historical option quotes were available. Omitted baseline trades include changed-path effects, not guaranteed saved money. Auto brick sizing uses each historical host ATR causally. No production files, settings or services changed.

Recommendation: do not add any tested filter to production on this evidence. CHOP55 worsens holdout net from438.96 to323.07 proxy points at2bp/side, and drawdown243.09 to287.87. CHOP61.8 also worsens holdout net to397.32. ADX20/25 worsen it to171.86/167.56. Reversal/low-progress improves to468.79 by omitting one losing baseline entry, but leaves development and validation unchanged: insufficient events for a reliable conclusion. At5bp/side, holdout baseline98.02 versus CHOP55−17.84, CHOP61.8 56.39, ADX20−127.75, ADX25−77.69, reversal141.71. No tested variant produces positive net across all three periods.

Holdout matched same-direction delayed entries: CHOP55 five, mean17min; CHOP61.8 two, mean5min; ADX20 seven, mean32.86min; ADX25 nine, mean36.11min. These describe later entries before the original baseline exit, not guaranteed equivalent trades.

Validation: three independent prefix checks confirm future bars do not change historical features; six boundary/missing-value checks passed. Source Engine hash matches selected FYERS worker source. No missing next-open executions were encountered. Ordinary time candles feed CHOP/ADX/efficiency; synthetic Renko directions feed reversal count. Warmup3sessions; chronological10/10/10session splits. Only NIFTY available in this selected account cache; cross-instrument stability remains untested. Require new unseen sessions and executable option bid/ask histories before claiming option cost savings.
