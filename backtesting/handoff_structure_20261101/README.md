# Confirmed swing structure and Handoff conviction: research, 1 November 2026

Decision: display-only evidence is reasonable to investigate; this test does not justify a ranking bonus or hard filter. No production changes made.

## Fixed design

Public Yahoo daily OHLCV, 12 named current large-cap stocks spanning financials, technology, consumer, industrials, auto, pharma, energy and metals: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, ITC, HINDUNILVR, LT, MARUTI, SUNPHARMA, TATASTEEL. Each has 2,472 observations from 2016-11-01 through 2026-10-30. Raw responses retained with SHA256 manifest. No broker credentials used.

Corporate-action adjusted OHLC: multiply each raw OHLC by adjclose/close. Adjusted price outcomes are total-return-like, not executable fills. Vendor history is not exchange-calendar or corporate-action certified. Present-day stock choice entails survivorship/selection bias.

Baseline calls the actual sector_heatmap.analysis.calculate_timeframe_state on history available through the observation, with its existing EMA/slope/RSI/ADX/DMI calculations and 210-candle minimum. Require daily and completed weekly state both >=1 or both <=-1. This is a TWO-timeframe proxy, not actual four-timeframe Handoff. Weekly bars become available at Friday session close; partial current weeks are excluded. Relative strength does not affect the trend state; benchmark input is empty. No reconstructed Chartink membership, sector candidate selection, liquidity gates, Handoff evidence_conviction score, 15m or 1h gates.

Swing definition fixed before the run: a strict high/low pivot exceeds/is below both two preceding and two following daily bars. Confirm only after the two following bars have closed. Bullish requires last two confirmed highs rising AND last two confirmed lows rising, latest confirmed low never subsequently breached by any observed low. Bearish is the inverse with latest confirmed high unbroken. Insufficient pivots is separately unconfirmed; mixed/broken structure fails the flag. Latest pivots are not forced to alternate. This tests daily structure only.

Observe every fifth trading bar on a fixed schedule from January 2021, independent of signals; baseline same-direction samples only. Entry proxy next session adjusted open, exit fifth subsequent session adjusted close. Structure changes selection only, never entry/exit prices or holding time. Five-session windows do not overlap within each stock; cross-stock observations remain correlated. End-date samples without all five future bars are excluded. Outcomes are signed directional forward returns, NOT an executable portfolio simulation. Bearish five-day stock short outcomes are diagnostic only; no borrow, overnight short availability, futures basis, fees or slippage model. No CAGR, equity drawdown or Sharpe claimed. MAE is worst signed intrawindow low/high relative to entry, capped at zero, not portfolio drawdown.

Development 2021-2023; held-out 2024-01-05 through 2026-10-23. One pivot setting and one horizon, no optimization. Holdout inspected once after design frozen. Reproducibility uses cached raw JSON to avoid rolling 10-year download drift.

## Main comparable results (percent)

| Period/group | N | Retained | Mean gross return | Hit rate | Mean MAE |
|---|---:|---:|---:|---:|---:|
| Development baseline |999|100.00|0.18|53.05|-2.41|
| Development confirmed |465|46.55|-0.00|52.26|-2.40|
| Held-out baseline |899|100.00|-0.07|50.72|-2.42|
| Held-out confirmed |395|43.94|0.01|54.43|-2.41|
| Held-out other structure |504|56.06|-0.12|47.82|-2.44|
| Held-out bullish baseline |645|100.00|0.03|52.56|-2.26|
| Held-out bullish confirmed |286|44.34|0.11|55.94|-2.18|
| Held-out bearish baseline |254|100.00|-0.32|46.06|-2.84|
| Held-out bearish confirmed |109|42.91|-0.26|50.46|-3.02|

Held-out mean-return improvement +0.07 percentage points; 95% calendar-month block bootstrap interval [-0.08,+0.22] pp, includes zero. Hit-rate improvement +3.71 pp, interval [+0.48,+6.48] pp. Bootstrap resamples whole calendar months jointly across stocks, 2,000 draws, seed 20261101; conditional on this universe/history and not proof of future significance. Development mean improvement was -0.18 pp; interval [-0.42,+0.04] pp. Confirmed beats other-structure average return in 6/12 held-out stocks and 3/12 development stocks. Cross-regime and cross-stock consistency is weak. Held-out worst MAE stays -18.11% in both baseline and confirmed; bearish mean MAE worsens. Improved hit rate is not equivalent to useful expectancy.

No cost-adjusted edge established: held-out confirmed average gross return is effectively flat overall, and bullish mean is only 0.11% before costs. No parameter fishing, alternative horizons or additional variants were used.

## Reproduce on authoritative remote Ubuntu

From /home/trading/sector-heatmap:
PYTHONPATH=. .venv/bin/python backtesting/handoff_structure_20261101/research.py
.venv/bin/python backtesting/handoff_structure_20261101/robustness.py

Files: research.py, robustness.py, raw per-symbol JSON, manifest.json, observations.csv (1,898 samples), summary.csv, per_stock.csv, uncertainty.json, run.log, robustness.log. Five future-perturbation checks verify structure flags before a cutoff are unchanged by altered future highs/lows. Existing production analysis/config/indicator source hashes retained in source_sha256.txt.

Next useful validation would prospectively log actual account-scoped Handoff candidates and completed four-timeframe evidence with structure flags, then evaluate unchanged entries/exits and realistic costs. This is a research suggestion, not an enabled logging job or deployment.
