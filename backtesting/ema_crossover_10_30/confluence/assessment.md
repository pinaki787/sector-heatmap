# EMA 10/30 confluence research

Period: 29 September 2025–28 September 2026, 245 complete weekday sessions.
Source: the same cached FYERS Nifty 50 spot-index candles as the baseline.
Eighteen predefined variants tested: RSI 50/50, 55/45, 60/40; ADX 18,
22, 25; EMA 100/200 alignment; RSI+ADX; EMA+RSI; EMA+ADX; ADX rising.
Both long and short directions retained. No changes to EMA lengths or exits.

## Selected filter

At the completed crossover candle, ADX(14) must be at least 18 and greater
than its value on the preceding candle. Enter at the next 5-minute open.
An invalid crossover is skipped, not entered later. Any opposite EMA crossover
still exits the position even if the new direction fails the ADX filter.
All positions close at 15:20. No stop-loss, target, or overnight exposure.

## Results at 5 points of assumed all-in roundtrip friction

| Metric | Baseline | ADX >=18 and rising |
|---|---:|---:|
| Trades | 532 | 164 |
| Win rate | 37.78% | 45.12% |
| Net index points | 346.00 | 105.10 |
| Profit factor | 1.026 | 1.024 |
| Maximum bar-close drawdown, points | 1076.05 | 729.30 |
| Average net points per trade | 0.65 | 0.64 |

Win rate improves 7.34 percentage points and absolute drawdown falls 32.22%,
but trade count falls 69.17% and net profit falls 69.62%. Much of the lower
drawdown therefore accompanies less market exposure rather than better expectancy.
Profit factor is almost unchanged. At 10 points of friction, the filtered
full-period result is -714.90 points.

## Chronological checks

Selection used only the first 60% and next 20% of sessions. The final 20%
was held out from filter selection; its unfiltered baseline results were
already known from the preceding study, so it is not pristine unseen data.

| Slice | Dates | Filtered trades | Filtered net points | Filtered PF |
|---|---|---:|---:|---:|
| Train | 29 Sep 2025–8 May 2026 | 96 | 199.25 | 1.07 |
| Validation | 11 May–20 Jul 2026 | 35 | -265.15 | 0.75 |
| Holdout | 21 Jul–28 Sep 2026 | 33 | 171.00 | 1.32 |

Holdout baseline: 114 trades, 30.70% wins, -503.20 points, 890.55-point
drawdown. Filtered: 33 trades, 42.42% wins, +171.00 points, 256.10-point
drawdown. At 10-point friction, filtered holdout profit is only +6 points.

No candidate passed the predefined development gates: at least 60 train and
20 validation trades, higher win rate and lower drawdown in both periods,
positive P&L and profit factor >=1.2 in both periods. The selected candidate
was the exploratory fallback ranked for the user's win-rate/drawdown goal.
It was frozen before its holdout result was evaluated; no second selection
was made using holdout performance.

## Verdict and limitations

Research only. ADX offers fewer trades and a smoother historical path, but
does not establish a stronger profitable edge. Losing validation, thin net
expectancy and sensitivity to friction rule out claiming a validated upgrade.
The recent 33-trade result is too small to establish reliability.
Fresh forward testing and contract-level data are required for further validation.

Index points are not actual futures/options P&L. Friction is a sensitivity
assumption, not a broker fee quote. Drawdowns are marked at candle closes,
so adverse movement within a candle can be greater. EMA/ADX carry across
sessions; incomplete/special sessions are excluded from trading. The baseline
matches the previous 532-trade ledger exactly. Every selected entry, exit,
next-open price and per-trade friction was reconciled; ADX prefix invariance
was checked to guard against future-data leakage.

Outputs: comparison.csv, development.csv, selection.csv, frozen_selection.json,
selected_full_trades.csv, selected_test_trades.csv, report.html, comparison.png.
