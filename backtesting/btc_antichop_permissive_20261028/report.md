# BTCUSD adaptive anti-chop comparison

96,659 consecutive completed one-minute Delta India perpetual candles, 22 August–28 October 2026 IST. Final 28,998 candles (about 20 days) used as a chronological validation segment. Parameters were fixed before the run. Prior-only rolling calibration; EMA10 adverse-close exits; next-open fills.

| variant           |   pass_pct |   trades |   gross_points |   net_points |   profit_factor |
|:------------------|-----------:|---------:|---------------:|-------------:|----------------:|
| Current 20/50     |       1.57 |      235 |        -1161.5 |     -10797.1 |            0.39 |
| Structure 2 only  |       2.43 |      306 |        -1647   |     -14196.4 |            0.37 |
| Softer 20/50      |       6.3  |      641 |        -5167   |     -31440   |            0.29 |
| Softer 10/30      |       7.11 |      724 |        -5031.5 |     -34704.8 |            0.32 |
| Trend-aware 10/30 |      24.69 |     1318 |        -5454   |     -59495.8 |            0.3  |

Points are USD price points per one BTC. Net assumes a hypothetical five-basis-point round-trip cost, applied to entry and exit turnover. This is not actual Delta options P&L, fees or fill evidence. Zero- and ten-basis-point scenarios are in comparison.csv. All variants lost even before costs in validation. No funding, spread, margin, Greeks or expiry model; no production five-entry cap in research.

The trend-aware version qualified in the recent bearish move, but its higher trading activity worsened aggregate results. Baseline replay matched 120 recorded runtime candles with no direction, threshold or qualification mismatches. Production Paper configuration was left unchanged and running.

Files: report.html (self-contained), summary.png, equity.html, comparison.csv, trades_5bps.csv, manifest.json, runtime_parity.json, recent_gate_audit.json, frozen source/config/data and reproducible script. Adaptive lookbacks remain fixed parameters; only thresholds roll. Five candidates on one market/timeframe and a short validation window cannot establish general robustness.
